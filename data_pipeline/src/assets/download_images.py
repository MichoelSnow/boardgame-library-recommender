import pandas as pd
import os
from pathlib import Path
from urllib.parse import urlparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse
import time
from typing import Optional

try:
    from ..common.logging_utils import build_log_handlers
    from .r2_sync import R2ImageSyncer, build_r2_image_key, download_image_content
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers
    from data_pipeline.src.assets.r2_sync import (
        R2ImageSyncer,
        build_r2_image_key,
        download_image_content,
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("image_downloader.log"),
)
logger = logging.getLogger(__name__)

# Resolve project root from `data_pipeline/src/assets`.
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMAGES_DIR = PROJECT_ROOT / "backend" / "database" / "images"


def ensure_images_dir():
    """Create the images directory if it doesn't exist."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_image_filename(url):
    """Extract filename from URL or generate one if needed."""
    if not url:
        return None

    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)

    # If no filename in URL, generate one from the path
    if not filename or "." not in filename:
        filename = f"game_{hash(url)}.jpg"

    return filename


def download_image(
    url,
    filename,
    *,
    game_id: Optional[int] = None,
    overwrite=False,
    syncer: Optional[R2ImageSyncer] = None,
    r2_overwrite_existing: bool = False,
):
    """Download a single image."""
    if not url:
        return False

    filepath = IMAGES_DIR / filename

    # Skip if file exists and overwrite is False
    if filepath.exists() and not overwrite:
        logger.debug(f"Skipping existing image: {filename}")
        return True

    try:
        image_bytes, content_type = download_image_content(url, timeout_seconds=20)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        if syncer is not None and game_id:
            key = build_r2_image_key(game_id, image_url=url, content_type=content_type)
            if not r2_overwrite_existing and syncer.object_exists(key):
                logger.debug(
                    "R2 object already exists for game_id=%s key=%s", game_id, key
                )
            else:
                syncer.upload_bytes(
                    key=key, content=image_bytes, content_type=content_type
                )
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False


def process_games_data(
    overwrite=False,
    exclude_expansions=False,
    max_rank=5000,
    sync_r2=False,
    r2_overwrite_existing=False,
):
    """Process the most recent games data file and download images."""
    # Find the most recent processed games file
    data_dir = PROJECT_ROOT / "data" / "transform" / "processed"
    processed_files = list(data_dir.glob("*/processed_games_data_*.csv"))
    if not processed_files:
        raise FileNotFoundError(f"No processed games files found in {data_dir}")

    latest_file = max(processed_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Using most recent processed games file: {latest_file}")

    # Read the CSV file
    df = pd.read_csv(latest_file, sep="|", escapechar="\\")

    # Filter out rows without images
    df = df[df["image"].notna()]

    if exclude_expansions:
        df = df[df["is_expansion"] == 0]

    df = df[df["rank"] <= max_rank]

    # Create a list of (url, filename) tuples
    download_tasks = []
    skipped_count = 0
    for _, row in df.iterrows():
        filename = get_image_filename(row["image"])
        if filename:
            filepath = IMAGES_DIR / filename
            if filepath.exists() and not overwrite:
                skipped_count += 1
                continue
            game_id = None
            try:
                game_id = int(row["id"])
            except Exception:
                game_id = None
            download_tasks.append((row["image"], filename, game_id))

    if skipped_count > 0:
        logger.info(f"Skipping {skipped_count} existing images")

    if not download_tasks:
        logger.info("No new images to download")
        return

    # Download images in parallel with batches
    BATCH_SIZE = 10
    successful_downloads = 0

    syncer = R2ImageSyncer.from_env() if sync_r2 else None

    for i in range(0, len(download_tasks), BATCH_SIZE):
        batch = download_tasks[i : i + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    download_image,
                    url,
                    filename,
                    game_id=game_id,
                    overwrite=overwrite,
                    syncer=syncer,
                    r2_overwrite_existing=r2_overwrite_existing,
                )
                for url, filename, game_id in batch
            ]

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Downloading batch {i // BATCH_SIZE + 1}/{(len(download_tasks) + BATCH_SIZE - 1) // BATCH_SIZE}",
            ):
                if future.result():
                    successful_downloads += 1

        # Wait 1 second between batches if there are more batches to come
        if i + BATCH_SIZE < len(download_tasks):
            time.sleep(2)

    logger.info(
        f"Successfully downloaded {successful_downloads} out of {len(download_tasks)} images"
    )


def main():
    """Main function to download images."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Download board game images.")
    parser.add_argument(
        "--overwrite-existing", action="store_true", help="Overwrite existing images"
    )
    parser.add_argument(
        "--exclude-expansions",
        action="store_true",
        help="Exclude board game expansions from the output",
    )
    parser.add_argument(
        "--max-rank",
        type=int,
        default=5000,
        help="Maximum rank to download images for (default: 5000)",
    )
    parser.add_argument(
        "--sync-r2",
        action="store_true",
        help="Upload downloaded images to Cloudflare R2 using canonical games/<bgg_id>.<ext> keys.",
    )
    parser.add_argument(
        "--r2-overwrite-existing",
        action="store_true",
        help="Overwrite existing R2 objects when --sync-r2 is enabled.",
    )
    args = parser.parse_args()

    try:
        ensure_images_dir()
        process_games_data(
            overwrite=args.overwrite_existing,
            exclude_expansions=args.exclude_expansions,
            max_rank=args.max_rank,
            sync_r2=args.sync_r2,
            r2_overwrite_existing=args.r2_overwrite_existing,
        )
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise


if __name__ == "__main__":
    main()
