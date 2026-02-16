#!/usr/bin/env python3
"""Generate blank/placeholder frames for chapters that have no video frames.

Scans data/chapters/ for directories missing *.gfx_video.tiles files and generates
a single black 256x192 PNG, then converts it via superfamiconv to .tiles/.tilemap/.palette.

Special cases:
  - atmd_insert_coins: "INSERT COIN" text on black background
  - atmd_start_dead:   "GAME OVER" text on black background

All other empty chapters get a plain black frame (routing nodes that transition instantly).

Usage:
    python3 tools/generate_blank_frames.py [--dry-run]
"""

import glob
import os
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAPTERS_DIR = os.path.join(PROJECT_DIR, 'data', 'chapters')
SUPERFAMICONV = os.path.join(PROJECT_DIR, 'tools', 'superfamiconv', 'superfamiconv.exe')

WIDTH, HEIGHT = 256, 192
BPP = 4
MAX_COLORS = 16
TILEMAP_TARGET_SIZE = 2048

# Chapters that get placeholder text instead of plain black
PLACEHOLDER_TEXT = {
    'atmd_insert_coins': 'INSERT COIN',
    'atmd_start_dead':   'GAME OVER',
}


def make_black_frame(path):
    """Create a 256x192 black PNG."""
    img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
    img.save(path)


def make_text_frame(path, text):
    """Create a 256x192 black PNG with centered white text."""
    img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try to get a TrueType font; fall back to default bitmap font
    font = None
    for size in [24, 20, 16]:
        try:
            font = ImageFont.truetype("arial.ttf", size)
            break
        except (IOError, OSError):
            continue

    if font is not None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    else:
        font = ImageFont.load_default()
        # Default bitmap font: use textsize-compatible measurement
        tw = len(text) * 6  # ~6px per char for default font
        th = 10

    x = (WIDTH - tw) // 2
    y = (HEIGHT - th) // 2
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    img.save(path)


def pad_tilemap(tilemap_file):
    """Pad tilemap to 32x32 (2048 bytes) for SNES compatibility."""
    with open(tilemap_file, 'rb') as f:
        data = f.read()
    if len(data) < TILEMAP_TARGET_SIZE:
        with open(tilemap_file, 'wb') as f:
            f.write(data)
            f.write(b'\x00' * (TILEMAP_TARGET_SIZE - len(data)))


def convert_superfamiconv(png_path):
    """Convert a PNG to SNES tiles/tilemap/palette via superfamiconv."""
    base = png_path[:-4]  # strip .png
    pal_file = base + '.palette'
    tile_file = base + '.tiles'
    map_file = base + '.tilemap'

    sfc = os.path.relpath(SUPERFAMICONV, PROJECT_DIR)
    rel_png = os.path.relpath(png_path, PROJECT_DIR)
    rel_pal = os.path.relpath(pal_file, PROJECT_DIR)
    rel_tile = os.path.relpath(tile_file, PROJECT_DIR)
    rel_map = os.path.relpath(map_file, PROJECT_DIR)

    run_kw = dict(capture_output=True, text=True, timeout=30, cwd=PROJECT_DIR)

    # 1. Palette
    r = subprocess.run([sfc, 'palette', '-i', rel_png, '-d', rel_pal, '-C', str(MAX_COLORS)], **run_kw)
    if r.returncode != 0:
        return False, f"palette: {r.stderr.strip()}"

    # 2. Tiles
    r = subprocess.run([sfc, 'tiles', '-i', rel_png, '-p', rel_pal, '-d', rel_tile, '-B', str(BPP)], **run_kw)
    if r.returncode != 0:
        return False, f"tiles: {r.stderr.strip()}"

    # 3. Tilemap
    r = subprocess.run([sfc, 'map', '-i', rel_png, '-p', rel_pal, '-t', rel_tile, '-d', rel_map, '-B', str(BPP)], **run_kw)
    if r.returncode != 0:
        return False, f"map: {r.stderr.strip()}"

    # 4. Pad tilemap to 32x32
    pad_tilemap(map_file)

    return True, ""


def find_empty_chapters():
    """Find chapter directories with no *.gfx_video.tiles files."""
    empty = []
    if not os.path.isdir(CHAPTERS_DIR):
        print(f"ERROR: chapters directory not found: {CHAPTERS_DIR}")
        sys.exit(1)

    for name in sorted(os.listdir(CHAPTERS_DIR)):
        cdir = os.path.join(CHAPTERS_DIR, name)
        if not os.path.isdir(cdir):
            continue
        tiles = glob.glob(os.path.join(cdir, '*.gfx_video.tiles'))
        if not tiles:
            empty.append((name, cdir))
    return empty


def main():
    dry_run = '--dry-run' in sys.argv

    empty = find_empty_chapters()
    if not empty:
        print("All chapters already have video frames. Nothing to do.")
        return

    print(f"Found {len(empty)} chapters with no video frames.")
    if dry_run:
        for name, _ in empty:
            tag = f" [{PLACEHOLDER_TEXT[name]}]" if name in PLACEHOLDER_TEXT else ""
            print(f"  {name}{tag}")
        print("(dry run, no files written)")
        return

    generated = 0
    failed = 0
    for name, cdir in empty:
        png_path = os.path.join(cdir, 'video_000001.gfx_video.png')

        # Generate PNG
        if name in PLACEHOLDER_TEXT:
            make_text_frame(png_path, PLACEHOLDER_TEXT[name])
            print(f"  {name}: placeholder \"{PLACEHOLDER_TEXT[name]}\"")
        else:
            make_black_frame(png_path)
            print(f"  {name}: black frame")

        # Convert to SNES tiles
        ok, err = convert_superfamiconv(png_path)
        if ok:
            generated += 1
        else:
            print(f"    ERROR converting {name}: {err}")
            failed += 1

    print(f"\nDone: {generated} generated, {failed} failed, {len(empty)} total empty chapters.")


if __name__ == '__main__':
    main()
