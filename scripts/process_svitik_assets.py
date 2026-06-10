#!/usr/bin/env python3
"""Prepare Pan Svitik PNGs: optional caption crop, remove background, trim."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(
    "/Users/olegbonislavskyi/.cursor/projects/Users-olegbonislavskyi-Sites-SvitPC/assets"
)
OUT = ROOT / "static" / "images"

# Brand-kit poses (full-body, no bottom caption). Filename prefix is enough for resolve_source().
SOURCES: dict[str, str] = {
    "pan-svitik-tech.png": "hf_20260604_110846_3eb5965d-1f30-43be-bc3c-44d2975f48e6",
    "pan-svitik-choice.png": "hf_20260604_110535_3c5ccdf7-e721-4f95-9614-b2c619b7f167",
    "pan-svitik-search.png": "hf_20260604_110721_bf19155e-6eea-4add-bbeb-4bf3a73e7078",
    "pan-svitik-coins.png": "hf_20260604_110958_98a7e123-0e01-4cc5-b9b4-99e6aef26a89",
    "pan-svitik-celebrate.png": "hf_20260604_111352_2b473a62-3cb9-412c-a259-7befbfcfaa8c",
}


def _is_white(r: int, g: int, b: int) -> bool:
    return r > 245 and g > 245 and b > 245


def _row_content(px, w: int, y: int) -> int:
    return sum(1 for x in range(w) if not _is_white(*px[x, y]))


def detect_crop_y(img: Image.Image, *, pad: int = 16) -> int:
    """Crop above a bottom caption band while keeping shoes/feet (legacy sources)."""
    img_rgb = img.convert("RGB")
    w, h = img_rgb.size
    px = img_rgb.load()
    contents = [_row_content(px, w, y) for y in range(h)]
    start = int(h * 0.945)

    for y in range(start, h - 3):
        if contents[y] >= 120:
            continue
        above = max(contents[max(int(h * 0.90), y - 40) : y], default=0)
        if above >= 200:
            return min(h, y + pad)

    for y in range(h - 3, start, -1):
        if contents[y] - contents[y - 5] > 30 and contents[y] > 850:
            return min(h, y - 3 + pad)

    return h


def trim_caption(img: Image.Image, crop_y: int) -> Image.Image:
    w, h = img.size
    crop_y = max(1, min(h, crop_y))
    return img.crop((0, 0, w, crop_y))


def is_bg_pixel(r: int, g: int, b: int, *, mode: str, tol: int) -> bool:
    if mode == "black":
        return r <= tol and g <= tol and b <= tol
    return r >= 255 - tol and g >= 255 - tol and b >= 255 - tol


def flood_transparent(img: Image.Image, *, mode: str = "white", tol: int = 34) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    q: deque[tuple[int, int]] = deque()

    for x in range(w):
        q.extend([(x, 0), (x, h - 1)])
    for y in range(h):
        q.extend([(0, y), (w - 1, y)])

    while q:
        x, y = q.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        k = y * w + x
        if seen[k]:
            continue
        r, g, b, _a = px[x, y]
        if not is_bg_pixel(r, g, b, mode=mode, tol=tol):
            continue
        seen[k] = 1
        px[x, y] = (r, g, b, 0)
        q.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    return img


def white_matte(img: Image.Image) -> Image.Image:
    """Un-premultiply white matte on edge pixels."""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0 or a == 255:
                continue
            af = a / 255.0
            nr = int((r - (1.0 - af) * 255) / af)
            ng = int((g - (1.0 - af) * 255) / af)
            nb = int((b - (1.0 - af) * 255) / af)
            nr = max(0, min(255, nr))
            ng = max(0, min(255, ng))
            nb = max(0, min(255, nb))
            px[x, y] = (nr, ng, nb, a)
    return img


def cleanup_fringe(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    for _pass in range(2):
        copy = img.copy()
        cpx = copy.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                neighbors_transparent = False
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and cpx[nx, ny][3] == 0:
                        neighbors_transparent = True
                        break
                if not neighbors_transparent:
                    continue
                if max(r, g, b) < 95 and a < 220:
                    px[x, y] = (r, g, b, 0)
                elif max(r, g, b) - min(r, g, b) < 15 and max(r, g, b) < 210:
                    px[x, y] = (r, g, b, 0)
    return img


def autotrim(img: Image.Image, pad: int = 12) -> Image.Image:
    bbox = img.split()[-1].getbbox()
    if not bbox:
        return img
    return img.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad),
            min(img.height, bbox[3] + pad),
        )
    )


def resolve_source(assets: Path, src_prefix: str) -> Path:
    matches = sorted(assets.glob(f"{src_prefix}*.png"), key=lambda p: p.stat().st_mtime)
    if matches:
        return matches[-1]
    raise FileNotFoundError(f"Source not found for prefix: {src_prefix}")


def process(
    src: Path,
    dst: Path,
    *,
    mode: str = "white",
    crop_caption: bool = False,
) -> tuple[int, int]:
    img = Image.open(src)
    src_h = img.height
    crop_y = detect_crop_y(img) if crop_caption else src_h
    img = trim_caption(img, crop_y)
    img = flood_transparent(img, mode=mode)
    if mode == "white":
        img = white_matte(img)
    img = cleanup_fringe(img)
    img = autotrim(img)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, optimize=True)
    print(f"{dst.name}: crop_y={crop_y}/{src_h} -> {img.size}")
    return img.size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, default=ASSETS)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    dims: dict[str, tuple[int, int]] = {}
    for dst_name, src_prefix in SOURCES.items():
        src = resolve_source(args.assets, src_prefix)
        size = process(src, args.out / dst_name, crop_caption=False)
        dims[dst_name] = size

    print("\n# Paste into apps/core/svitik.py SVITIK_MASCOT_DIMS:")
    for name, (w, h) in dims.items():
        print(f'    "{name}": ({w}, {h}),')


if __name__ == "__main__":
    main()
