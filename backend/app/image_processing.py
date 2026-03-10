from __future__ import annotations

from io import BytesIO
from pathlib import Path


def build_thumbnail_relative_path(game_id: int) -> str:
    return f"thumbnails/{game_id}.webp"


def create_webp_thumbnail(
    image_bytes: bytes,
    *,
    max_height: int = 240,
    quality: int = 80,
) -> bytes:
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        image.thumbnail((image.width, max_height), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=quality, method=6)
        return output.getvalue()


def write_webp_thumbnail(
    image_bytes: bytes,
    destination: Path,
    *,
    max_height: int = 240,
    quality: int = 80,
) -> bool:
    try:
        thumb_bytes = create_webp_thumbnail(
            image_bytes,
            max_height=max_height,
            quality=quality,
        )
    except (ImportError, OSError, ValueError):
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_bytes(thumb_bytes)
    tmp_path.replace(destination)
    return True
