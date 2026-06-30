#!/usr/bin/env python3
"""Compress logo and Pan Svitik mascots for fast LCP (WebP + smaller PNG)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "static" / "images"
DIMS_PATH = ROOT / "static" / "images" / "svitik-dims.json"

LOGO_WIDTHS = {"": 200, "@2x": 400}
SVITIK_MAX_WIDTH = 368
SVITIK_SM_WIDTH = 184
WEBP_QUALITY = 82


def _save_webp_and_png(img: Image.Image, base: Path) -> None:
    rgb = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    rgb.save(base.with_suffix(".webp"), "WEBP", quality=WEBP_QUALITY, method=6)
    if rgb.mode == "RGBA":
        rgb.save(base, optimize=True)
    else:
        rgb.convert("RGB").save(base, optimize=True)


def _resize_width(img: Image.Image, max_width: int) -> Image.Image:
    if img.width <= max_width:
        return img
    ratio = max_width / img.width
    return img.resize((max_width, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)


def optimize_logos() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for suffix, max_w in LOGO_WIDTHS.items():
        png = IMAGES / f"logo-header{suffix}.png"
        if not png.is_file():
            continue
        img = Image.open(png)
        img = _resize_width(img, max_w)
        _save_webp_and_png(img, png)
        out[suffix or "1x"] = {"width": img.width, "height": img.height}
        print(f"logo-header{suffix}: {img.width}x{img.height}")
    return out


def optimize_svitik_mascots() -> dict[str, list[int]]:
    dims: dict[str, list[int]] = {}
    for png in sorted(IMAGES.glob("pan-svitik-*.png")):
        if png.name == "pan-svitik.png" or "-sm.png" in png.name:
            continue
        img = Image.open(png)
        img = _resize_width(img, SVITIK_MAX_WIDTH)
        _save_webp_and_png(img, png)
        webp_name = png.name.replace(".png", ".webp")
        dims[png.name] = [img.width, img.height]
        dims[webp_name] = [img.width, img.height]
        print(f"{png.name} -> {img.width}x{img.height}")

        sm = _resize_width(img, SVITIK_SM_WIDTH)
        sm_base = png.with_name(png.name.replace(".png", "-sm.png"))
        _save_webp_and_png(sm, sm_base)
        sm_webp = sm_base.name.replace(".png", ".webp")
        dims[sm_base.name] = [sm.width, sm.height]
        dims[sm_webp] = [sm.width, sm.height]
        print(f"{sm_base.name} -> {sm.width}x{sm.height}")
    return dims


def main() -> int:
    logos = optimize_logos()
    svitik = optimize_svitik_mascots()
    DIMS_PATH.write_text(
        json.dumps({"logos": logos, "svitik": svitik}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {DIMS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
