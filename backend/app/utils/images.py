from __future__ import annotations
from typing import Tuple, Optional
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import hashlib

# Allow-list of MIME types you want to accept from uploads
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def read_bytes_limit(data: bytes, max_bytes: int = 5 * 1024 * 1024) -> bytes:
    """
    Ensure payload is within a sane limit to avoid memory abuse.
    """
    if len(data) > max_bytes:
        raise ValueError(f"Image exceeds {max_bytes // (1024 * 1024)} MB limit.")
    return data


def sniff_mime_and_size(data: bytes) -> Tuple[str, Tuple[int, int]]:
    """
    Use Pillow to validate image and return a normalized MIME type and (width, height).
    Raises ValueError if not a valid/allowed image.
    """
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except UnidentifiedImageError as e:
        raise ValueError(f"Unsupported or corrupted image: {e}") from e

    mime = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }.get(fmt, "")

    if not mime or mime not in ALLOWED_MIME:
        raise ValueError(f"Unsupported image format: {fmt or 'UNKNOWN'}")

    return mime, (width, height)


def ensure_allowed_mime(mime: str) -> None:
    if mime not in ALLOWED_MIME:
        raise ValueError(f"MIME not allowed: {mime}")


def compute_sha256(data: bytes) -> str:
    """
    Stable content hash for deduplication/cache keys.
    """
    return hashlib.sha256(data).hexdigest()


def load_image_rgb(data: bytes) -> Image.Image:
    """
    Return a Pillow Image in RGB mode (helpful for models expecting RGB).
    """
    with Image.open(BytesIO(data)) as img:
        return img.convert("RGB")
