from __future__ import annotations

from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency path
    Image = None


def build_thumbnail_relative_path(game_id: int) -> str:
    return f"thumbnails/{game_id}.webp"


def is_probably_supported_image(image_bytes: bytes) -> bool:
    if not image_bytes:
        return False
    if image_bytes.startswith(b"\xff\xd8\xff"):  # JPEG
        return True
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):  # PNG
        return True
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):  # GIF
        return True
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":  # WEBP
        return True
    if len(image_bytes) >= 12 and image_bytes[4:12] == b"ftypavif":  # AVIF
        return True
    return False


def create_webp_thumbnail(
    image_bytes: bytes,
    *,
    max_height: int = 240,
    quality: int = 80,
) -> bytes:
    if Image is None:
        raise ImportError("Pillow is not installed")

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
    if not is_probably_supported_image(image_bytes):
        return False

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
