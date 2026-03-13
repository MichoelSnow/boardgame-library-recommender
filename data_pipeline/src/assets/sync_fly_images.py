"""
Seed and refresh Fly-local image storage from BoardGameGeek origin URLs.

Intended runtime:
- Fly app machine (dev/prod), where IMAGE_STORAGE_DIR points to /data/images.
- Can also run locally for local image cache workflows.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.app import models
from backend.app.database import SessionLocal
from backend.app.image_processing import (
    build_thumbnail_relative_path,
    write_webp_thumbnail,
)
from backend.app.logging_utils import build_log_handlers


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}

IMAGE_STORAGE_DIR = Path(os.getenv("IMAGE_STORAGE_DIR", "/data/images")).resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("sync_fly_images.log"),
)
logger = logging.getLogger(__name__)


def infer_extension_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    media_type = content_type.split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_TO_EXTENSION.get(media_type)


def infer_extension_from_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    guessed_type, _ = mimetypes.guess_type(image_url)
    if guessed_type:
        extension = infer_extension_from_content_type(guessed_type)
        if extension:
            return extension
    filename = image_url.split("?", 1)[0].split("#", 1)[0].rsplit("/", 1)[-1]
    if "." not in filename:
        return None
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return "jpg" if extension == "jpeg" else extension
    return None


def build_relative_image_path(
    game_id: int,
    *,
    image_url: str | None = None,
    content_type: str | None = None,
) -> Path:
    extension = (
        infer_extension_from_content_type(content_type)
        or infer_extension_from_url(image_url)
        or "jpg"
    )
    return Path("games") / f"{game_id}.{extension}"


def find_existing_image_path(game_id: int, image_root: Path) -> Path | None:
    games_dir = image_root / "games"
    for extension in sorted(ALLOWED_IMAGE_EXTENSIONS):
        candidate = games_dir / f"{game_id}.{extension}"
        if candidate.exists():
            return candidate
    return None


def thumbnail_path_for_game(game_id: int, image_root: Path) -> Path:
    return image_root / build_thumbnail_relative_path(game_id)


def parse_bool_scope(scope: str) -> tuple[bool, bool]:
    normalized = scope.strip().lower()
    if normalized == "all-qualified":
        return True, True
    if normalized == "library-only":
        return True, False
    if normalized == "top-rank-only":
        return False, True
    raise ValueError(f"Unsupported scope: {scope}")


def qualifies_for_seed(
    *,
    game_id: int,
    rank: Optional[int],
    library_ids: set[int],
    max_rank: int,
    include_library: bool,
    include_top_rank: bool,
) -> bool:
    is_library = game_id in library_ids
    is_top_ranked = rank is not None and rank <= max_rank
    return (include_library and is_library) or (include_top_rank and is_top_ranked)


def collect_candidates(
    db: Session,
    *,
    max_rank: int,
    scope: str,
    include_expansions: bool,
) -> list[tuple[int, str]]:
    include_library, include_top_rank = parse_bool_scope(scope)
    library_ids = {
        row[0]
        for row in db.execute(
            select(models.LibraryGame.bgg_id).where(models.LibraryGame.bgg_id.isnot(None))
        ).all()
        if row[0] is not None
    }

    query = select(
        models.BoardGame.id,
        models.BoardGame.image,
        models.BoardGame.rank,
        models.BoardGame.is_expansion,
    ).where(models.BoardGame.image.isnot(None))
    rows = db.execute(query).all()

    candidates: list[tuple[int, str]] = []
    for game_id, image_url, rank, is_expansion in rows:
        if game_id is None or not image_url:
            continue
        if (not include_expansions) and bool(is_expansion):
            continue
        if not qualifies_for_seed(
            game_id=int(game_id),
            rank=int(rank) if rank is not None else None,
            library_ids=library_ids,
            max_rank=max_rank,
            include_library=include_library,
            include_top_rank=include_top_rank,
        ):
            continue
        image_url_str = str(image_url).strip()
        if not image_url_str:
            continue
        candidates.append((int(game_id), image_url_str))
    return candidates


@retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def download_image_content(
    client: httpx.AsyncClient,
    image_url: str,
    *,
    timeout_seconds: int,
) -> tuple[bytes, str | None]:
    response = await client.get(image_url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content, response.headers.get("Content-Type")


async def seed_images(
    *,
    candidates: list[tuple[int, str]],
    image_root: Path,
    overwrite_existing: bool,
    concurrency: int,
    timeout_seconds: int,
    dry_run: bool,
) -> tuple[int, int, int]:
    image_root.mkdir(parents=True, exist_ok=True)
    (image_root / "games").mkdir(parents=True, exist_ok=True)
    worker_count = max(1, concurrency)

    downloaded = 0
    skipped = 0
    failed = 0

    async with httpx.AsyncClient() as client:

        async def process_one(game_id: int, image_url: str) -> None:
            nonlocal downloaded, skipped, failed
            existing_path = find_existing_image_path(game_id, image_root)
            if existing_path is not None and not overwrite_existing:
                skipped += 1
                return

            if dry_run:
                downloaded += 1
                return

            try:
                content, content_type = await download_image_content(
                    client,
                    image_url,
                    timeout_seconds=timeout_seconds,
                )
                relative_path = build_relative_image_path(
                    game_id,
                    image_url=image_url,
                    content_type=content_type,
                )
                target_path = image_root / relative_path
                # Re-check after download to avoid race overwrite when another process seeded first.
                if target_path.exists() and not overwrite_existing:
                    skipped += 1
                    return
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=str(target_path.parent),
                    prefix=f"{target_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as tmp_file:
                    tmp_file.write(content)
                    tmp_name = tmp_file.name
                Path(tmp_name).replace(target_path)
                write_webp_thumbnail(
                    content,
                    thumbnail_path_for_game(game_id, image_root),
                )
                downloaded += 1
            except Exception as exc:  # pragma: no cover - safety net
                failed += 1
                logger.warning(
                    "Failed image seed for game_id=%s (%s): %s", game_id, image_url, exc
                )

        queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue()
        for candidate in candidates:
            queue.put_nowait(candidate)
        for _ in range(worker_count):
            queue.put_nowait(None)

        async def worker() -> None:
            while True:
                item = await queue.get()
                try:
                    if item is None:
                        return
                    game_id, image_url = item
                    await process_one(game_id, image_url)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await queue.join()
        await asyncio.gather(*workers)

    return downloaded, skipped, failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync images from BGG URLs directly into Fly/local image storage.",
    )
    parser.add_argument(
        "--scope",
        choices=["all-qualified", "library-only", "top-rank-only"],
        default="all-qualified",
        help="Candidate scope (default: all-qualified).",
    )
    parser.add_argument(
        "--max-rank",
        type=int,
        default=10000,
        help="Top-rank threshold used by qualifying scopes (default: 10000).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional candidate cap (0 means no cap).",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Overwrite existing local image files if present.",
    )
    parser.add_argument(
        "--include-expansions",
        action="store_true",
        help="Include expansion rows in seed candidates.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Parallel download workers (default: 8).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Per-request timeout in seconds (default: 20).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List scope summary without writing any files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    db = SessionLocal()
    try:
        candidates = collect_candidates(
            db,
            max_rank=args.max_rank,
            scope=args.scope,
            include_expansions=args.include_expansions,
        )
    finally:
        db.close()

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]

    logger.info(
        "Fly image seed scope=%s max_rank=%s candidates=%s dry_run=%s root=%s",
        args.scope,
        args.max_rank,
        len(candidates),
        args.dry_run,
        IMAGE_STORAGE_DIR,
    )

    downloaded, skipped, failed = asyncio.run(
        seed_images(
            candidates=candidates,
            image_root=IMAGE_STORAGE_DIR,
            overwrite_existing=args.overwrite_existing,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
    )
    logger.info(
        "Fly image seed complete downloaded=%s skipped=%s failed=%s dry_run=%s",
        downloaded,
        skipped,
        failed,
        args.dry_run,
    )
    return 1 if failed > 0 and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
