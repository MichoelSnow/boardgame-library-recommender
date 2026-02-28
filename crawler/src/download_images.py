import pandas as pd
import requests
import os
from pathlib import Path
from urllib.parse import urlparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse
import time

try:
    from .logging_utils import build_log_handlers
except ImportError:
    from logging_utils import build_log_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("image_downloader.log"),
)
logger = logging.getLogger(__name__)

# Get the project root directory (two levels up from this script)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
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
    if not filename or '.' not in filename:
        filename = f"game_{hash(url)}.jpg"
    
    return filename

def download_image(url, filename, overwrite=False):
    """Download a single image."""
    if not url:
        return False
    
    filepath = IMAGES_DIR / filename
    
    # Skip if file exists and overwrite is False
    if filepath.exists() and not overwrite:
        logger.debug(f"Skipping existing image: {filename}")
        return True
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def process_games_data(overwrite=False, exclude_expansions=False, max_rank=5000):
    """Process the most recent games data file and download images."""
    # Find the most recent processed games file
    data_dir = PROJECT_ROOT / "data" / "processed"
    processed_files = list(data_dir.glob("processed_games_data_*.csv"))
    if not processed_files:
        raise FileNotFoundError(f"No processed games files found in {data_dir}")
    
    latest_file = max(processed_files, key=lambda x: int(x.stem.split('_')[-1]))
    logger.info(f"Using most recent processed games file: {latest_file}")
    
    # Read the CSV file
    df = pd.read_csv(latest_file, sep="|", escapechar="\\")
    
    # Filter out rows without images
    df = df[df['image'].notna()]

    if exclude_expansions:
        df = df[df['is_expansion'] == 0]

    df = df[df['rank'] <= max_rank]
    
    # Create a list of (url, filename) tuples
    download_tasks = []
    skipped_count = 0
    for _, row in df.iterrows():
        filename = get_image_filename(row['image'])
        if filename:
            filepath = IMAGES_DIR / filename
            if filepath.exists() and not overwrite:
                skipped_count += 1
                continue
            download_tasks.append((row['image'], filename))
    
    if skipped_count > 0:
        logger.info(f"Skipping {skipped_count} existing images")
    
    if not download_tasks:
        logger.info("No new images to download")
        return
    
    # Download images in parallel with batches
    BATCH_SIZE = 10
    successful_downloads = 0
    
    for i in range(0, len(download_tasks), BATCH_SIZE):
        batch = download_tasks[i:i + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(download_image, url, filename, overwrite) 
                      for url, filename in batch]
            
            for future in tqdm(as_completed(futures), total=len(futures), 
                             desc=f"Downloading batch {i//BATCH_SIZE + 1}/{(len(download_tasks) + BATCH_SIZE - 1)//BATCH_SIZE}"):
                if future.result():
                    successful_downloads += 1
        
        # Wait 1 second between batches if there are more batches to come
        if i + BATCH_SIZE < len(download_tasks):
            time.sleep(2)
    
    logger.info(f"Successfully downloaded {successful_downloads} out of {len(download_tasks)} images")


def main():
    """Main function to download images."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download board game images.')
    parser.add_argument('--overwrite-existing', action='store_true',
                      help='Overwrite existing images')
    parser.add_argument('--exclude-expansions', action='store_true',
                      help='Exclude board game expansions from the output')
    parser.add_argument(
            "--max-rank",
            type=int,
            default=5000,
            help="Maximum rank to download images for (default: 5000)",
        )
    args = parser.parse_args()
    
    try:
        ensure_images_dir()
        process_games_data(overwrite=args.overwrite_existing, exclude_expansions=args.exclude_expansions, max_rank=args.max_rank)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
