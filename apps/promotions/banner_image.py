"""Resize and compress uploaded banner images for faster LCP."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PIL import Image

from apps.promotions.home_ads import CONTENT_MAX_WIDTH

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile

DESKTOP_MAX_WIDTH = CONTENT_MAX_WIDTH
MOBILE_MAX_WIDTH = 640
JPEG_QUALITY = 85


def _resize_width(img: Image.Image, max_width: int) -> Image.Image:
    if img.width <= max_width:
        return img
    ratio = max_width / img.width
    return img.resize((max_width, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)


def _encode_image(img: Image.Image, original_name: str) -> tuple[bytes, str]:
    lower = original_name.lower()
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha or lower.endswith(".png"):
        out = io.BytesIO()
        rgba = img.convert("RGBA") if img.mode != "RGBA" else img
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue(), ".png"
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), ".jpg"


def optimize_field_file(field: FieldFile, *, max_width: int) -> bool:
    """Compress in place when the file is oversized. Returns True if rewritten."""
    if not field or not field.name:
        return False

    from django.core.files.base import ContentFile

    try:
        # Не закривати файл (без with): для ще не збереженого upload це той самий
        # об'єкт, який Django Storage читатиме далі — закриття ламає save().
        handle = field.open("rb")
        original = handle.read()
        try:
            handle.seek(0)
        except (OSError, ValueError):
            pass
        img = Image.open(io.BytesIO(original))
        img.load()
    except (OSError, Image.UnidentifiedImageError):
        return False

    resized = _resize_width(img, max_width)
    encoded, ext = _encode_image(resized, field.name)
    if len(encoded) >= len(original) and resized.width >= img.width:
        return False

    stem = field.name.rsplit(".", 1)[0]
    new_name = f"{stem}{ext}" if not field.name.lower().endswith(ext) else field.name
    field.save(new_name, ContentFile(encoded), save=False)
    return True
