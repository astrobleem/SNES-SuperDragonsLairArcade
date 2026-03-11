#!/usr/bin/env python3
"""
benchmark_converters.py - Compare gracon.py vs superfamiconv + reduce_tiles

Measures wall time, tile count, PSNR, and output sizes for both converters
on the same test images. Uses background PNGs (always on disk) and optionally
samples video frames from data/chapters/ if they exist.

Usage:
  python3 tools/benchmark_converters.py [--verbose] [--frames N]
"""

import os
import sys

# CRITICAL: Set BLAS to single-threaded BEFORE importing numpy (matches production)
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

import time
import glob
import argparse
import struct
import tempfile
import shutil
import numpy as np
from PIL import Image

# Add tools/ to path for imports
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import gracon
import userOptions
from paths import PROJECT_ROOT

PROJECT_DIR = str(PROJECT_ROOT)
BACKGROUNDS_DIR = os.path.join(PROJECT_DIR, 'data', 'backgrounds')
CHAPTERS_DIR = os.path.join(PROJECT_DIR, 'data', 'chapters')

# Pipeline constants (must match generate_msu_data.py)
BPP = 4
PALETTES = 1
MAX_TILES = 512
MAX_COLORS = PALETTES * (2 ** BPP)
FRAME_WIDTH = 256
FRAME_HEIGHT = 160
TILEMAP_TARGET_SIZE = 1280  # 32x20 tiles * 2 bytes

# Import superfamiconv converter + reduce_tiles from generate_msu_data
from generate_msu_data import (
    convert_frame_superfamiconv, reduce_tiles, pad_tilemap,
    read_snes_palette, decode_tiles_4bpp_rgb, SUPERFAMICONV,
)


def make_gracon_options(maxtiles=MAX_TILES):
    """Create gracon options matching the video pipeline settings."""
    options = userOptions.Options([], {
        'bpp': {'value': BPP, 'type': 'int', 'max': 8, 'min': 1},
        'palettes': {'value': PALETTES, 'type': 'int', 'max': 8, 'min': 1},
        'mode': {'value': 'bg', 'type': 'str'},
        'optimize': {'value': True, 'type': 'bool'},
        'directcolor': {'value': False, 'type': 'bool'},
        'transcol': {'value': 0x7c1f, 'type': 'hex', 'max': 0x7fff, 'min': 0x0},
        'tilethreshold': {'value': 1, 'type': 'int', 'max': 0xffff, 'min': 0},
        'verify': {'value': False, 'type': 'bool'},
        'tilesizex': {'value': 8, 'type': 'int', 'max': 16, 'min': 8},
        'tilesizey': {'value': 8, 'type': 'int', 'max': 16, 'min': 8},
        'maxtiles': {'value': maxtiles, 'type': 'int', 'max': 0x3ff, 'min': 0},
        'refpalette': {'value': '', 'type': 'str'},
        'infile': {'value': '', 'type': 'str'},
        'outfilebase': {'value': '', 'type': 'str'},
        'resolutionx': {'value': 256, 'type': 'int', 'max': 0xffff, 'min': 1},
        'resolutiony': {'value': 224, 'type': 'int', 'max': 0xffff, 'min': 1},
    })
    return options


def convert_frame_gracon_bench(png_path, tmp_dir, options):
    """Convert one PNG using gracon, write output files to tmp_dir.

    Returns (tile_bytes, map_bytes, pal_bytes) or raises on failure.
    """
    image = gracon.getInputImage(options, png_path)
    tiles = gracon.parseTiles(image, options)
    palettes = gracon.parseGlobalPalettes(tiles, options)
    palettized = gracon.palettizeTiles(tiles, palettes)

    # Optimize with maxtiles loop (same as gracon main())
    options.set('tilethreshold', 1)  # reset for each image
    optimized = gracon.optimizeTiles(palettized, options)
    while len([t for t in optimized if t['refId'] is None]) > options.get('maxtiles'):
        options.set('tilethreshold', options.get('tilethreshold') + 3)
        optimized = gracon.optimizeTiles(palettized, options)

    out_tiles = gracon.augmentOutIds(optimized)
    out_palettes = gracon.augmentOutIds(palettes)

    tile_bytes = gracon.getTileWriteStream(out_tiles, options)
    map_bytes = gracon.getBgTileMapStream(optimized, palettes, options)
    pal_bytes = gracon.getPaletteWriteStream(out_palettes, options)

    # Write files
    base = os.path.join(tmp_dir, os.path.basename(png_path)[:-4])
    with open(base + '.tiles', 'wb') as f:
        f.write(tile_bytes)
    with open(base + '.tilemap', 'wb') as f:
        # Truncate to TILEMAP_TARGET_SIZE (gracon outputs 2048 for 32x32)
        f.write(map_bytes[:TILEMAP_TARGET_SIZE])
    with open(base + '.palette', 'wb') as f:
        f.write(pal_bytes)

    return tile_bytes, map_bytes[:TILEMAP_TARGET_SIZE], pal_bytes


def convert_frame_sfc_bench(png_path, tmp_dir):
    """Convert one PNG using superfamiconv + reduce_tiles.

    Copies png into the project tree (tmp subdir of data/) so superfamiconv's
    relative-path requirement is satisfied. Cleans up after.
    Returns (tile_bytes, map_bytes, pal_bytes) or raises on failure.
    """
    # superfamiconv needs paths relative to PROJECT_DIR, so work inside the project
    work_dir = os.path.join(PROJECT_DIR, 'data', '_bench_tmp')
    os.makedirs(work_dir, exist_ok=True)
    tmp_png = os.path.join(work_dir, os.path.basename(png_path))
    shutil.copy2(png_path, tmp_png)

    try:
        ok, err = convert_frame_superfamiconv(tmp_png)
        if not ok:
            raise RuntimeError(f"superfamiconv failed: {err}")

        base = tmp_png[:-4]
        with open(base + '.tiles', 'rb') as f:
            tile_bytes = f.read()
        with open(base + '.tilemap', 'rb') as f:
            map_bytes = f.read()
        with open(base + '.palette', 'rb') as f:
            pal_bytes = f.read()

        return tile_bytes, map_bytes, pal_bytes
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def reconstruct_image(tile_bytes, map_bytes, pal_bytes, width=256, height=160):
    """Reconstruct RGB image from SNES tile/tilemap/palette data.

    Returns (height, width, 3) float32 array.
    """
    bytes_per_tile = 8 * BPP  # 32
    num_tiles = len(tile_bytes) // bytes_per_tile
    tiles_w = width // 8
    tiles_h = height // 8

    # Parse palette
    pal_rgb = np.zeros((16, 3), dtype=np.float32)
    num_colors = min(16, len(pal_bytes) // 2)
    for i in range(num_colors):
        bgr555 = struct.unpack_from('<H', pal_bytes, i * 2)[0]
        pal_rgb[i, 0] = (bgr555 & 0x1F) * (255.0 / 31.0)
        pal_rgb[i, 1] = ((bgr555 >> 5) & 0x1F) * (255.0 / 31.0)
        pal_rgb[i, 2] = ((bgr555 >> 10) & 0x1F) * (255.0 / 31.0)

    # Decode tiles to RGB
    tiles_raw = np.frombuffer(tile_bytes, dtype=np.uint8).reshape(num_tiles, bytes_per_tile)
    tiles_rgb = decode_tiles_4bpp_rgb(tiles_raw, pal_rgb)  # (N, 192)

    # Parse tilemap
    tilemap = np.frombuffer(map_bytes[:tiles_w * tiles_h * 2], dtype=np.uint16)
    tile_indices = tilemap & 0x3FF
    h_flip = (tilemap >> 14) & 1
    v_flip = (tilemap >> 15) & 1

    # Reconstruct
    img = np.zeros((height, width, 3), dtype=np.float32)
    for ty in range(tiles_h):
        for tx in range(tiles_w):
            map_idx = ty * tiles_w + tx
            if map_idx >= len(tilemap):
                continue
            tidx = int(tile_indices[map_idx])
            if tidx >= num_tiles:
                continue

            tile_rgb = tiles_rgb[tidx].reshape(8, 8, 3)

            if h_flip[map_idx]:
                tile_rgb = tile_rgb[:, ::-1, :]
            if v_flip[map_idx]:
                tile_rgb = tile_rgb[::-1, :, :]

            y0, x0 = ty * 8, tx * 8
            img[y0:y0+8, x0:x0+8, :] = tile_rgb

    return img


def compute_psnr(original_path, reconstructed, width=256, height=160):
    """Compute PSNR between original PNG and reconstructed image."""
    orig = Image.open(original_path).convert('RGB')
    # Crop/resize to match target dimensions
    if orig.size != (width, height):
        orig = orig.resize((width, height), Image.LANCZOS)
    orig_arr = np.array(orig, dtype=np.float32)

    mse = np.mean((orig_arr - reconstructed[:height, :width, :]) ** 2)
    if mse == 0:
        return float('inf')
    return 10 * np.log10(255.0 ** 2 / mse)


def find_test_images(max_video_frames=50):
    """Find background PNGs and optionally sample video frames."""
    images = []

    # Background PNGs (always on disk)
    bg_pngs = glob.glob(os.path.join(BACKGROUNDS_DIR, '*', '*.png'))
    for p in sorted(bg_pngs):
        images.append(('bg', p))

    # Sample video frames if available
    if os.path.isdir(CHAPTERS_DIR):
        video_pngs = []
        for chapter_dir in sorted(os.listdir(CHAPTERS_DIR)):
            cdir = os.path.join(CHAPTERS_DIR, chapter_dir)
            if not os.path.isdir(cdir):
                continue
            frames = sorted(glob.glob(os.path.join(cdir, '*.gfx_video.png')))
            if frames:
                # Take 1 frame from each chapter that has frames
                video_pngs.append(frames[len(frames) // 2])
            if len(video_pngs) >= max_video_frames:
                break
        for p in video_pngs:
            images.append(('video', p))

    return images


def run_benchmark(images, warmup=2, verbose=False):
    """Run benchmark on all images, return results list."""
    options = make_gracon_options()
    results = []

    for idx, (img_type, png_path) in enumerate(images):
        name = os.path.basename(png_path)
        is_warmup = idx < warmup

        if verbose or not is_warmup:
            tag = " [warmup]" if is_warmup else ""
            print(f"  [{idx+1}/{len(images)}] {name} ({img_type}){tag}")

        # Detect image dimensions
        with Image.open(png_path) as img:
            w, h = img.size

        # --- gracon ---
        tmp_gracon = tempfile.mkdtemp(prefix='bench_gracon_')
        try:
            t0 = time.perf_counter()
            gc_tiles, gc_map, gc_pal = convert_frame_gracon_bench(png_path, tmp_gracon, options)
            gc_time = time.perf_counter() - t0
            gc_tile_count = len(gc_tiles) // 32
            gc_recon = reconstruct_image(gc_tiles, gc_map, gc_pal, w, h)
            gc_psnr = compute_psnr(png_path, gc_recon, w, h)
            gc_total_size = len(gc_tiles) + len(gc_map) + len(gc_pal)
        except Exception as e:
            if verbose:
                print(f"    gracon ERROR: {e}")
            gc_time = gc_tile_count = gc_psnr = gc_total_size = None
        finally:
            shutil.rmtree(tmp_gracon, ignore_errors=True)

        # --- superfamiconv + reduce_tiles ---
        tmp_sfc = tempfile.mkdtemp(prefix='bench_sfc_')
        try:
            t0 = time.perf_counter()
            sfc_tiles, sfc_map, sfc_pal = convert_frame_sfc_bench(png_path, tmp_sfc)
            sfc_time = time.perf_counter() - t0
            sfc_tile_count = len(sfc_tiles) // 32
            sfc_recon = reconstruct_image(sfc_tiles, sfc_map, sfc_pal, w, h)
            sfc_psnr = compute_psnr(png_path, sfc_recon, w, h)
            sfc_total_size = len(sfc_tiles) + len(sfc_map) + len(sfc_pal)
        except Exception as e:
            if verbose:
                print(f"    superfamiconv ERROR: {e}")
            sfc_time = sfc_tile_count = sfc_psnr = sfc_total_size = None
        finally:
            shutil.rmtree(tmp_sfc, ignore_errors=True)

        if verbose and gc_time is not None and sfc_time is not None:
            speedup = sfc_time / gc_time if gc_time > 0 else float('inf')
            print(f"    gracon:       {gc_time*1000:7.1f}ms  tiles={gc_tile_count:3d}  "
                  f"PSNR={gc_psnr:5.1f}dB  size={gc_total_size}")
            print(f"    superfamiconv:{sfc_time*1000:7.1f}ms  tiles={sfc_tile_count:3d}  "
                  f"PSNR={sfc_psnr:5.1f}dB  size={sfc_total_size}")
            print(f"    speedup: {speedup:.1f}x")

        if not is_warmup:
            results.append({
                'name': name,
                'type': img_type,
                'width': w,
                'height': h,
                'gracon_time': gc_time,
                'gracon_tiles': gc_tile_count,
                'gracon_psnr': gc_psnr,
                'gracon_size': gc_total_size,
                'sfc_time': sfc_time,
                'sfc_tiles': sfc_tile_count,
                'sfc_psnr': sfc_psnr,
                'sfc_size': sfc_total_size,
            })

    return results


def print_summary(results):
    """Print formatted summary table."""
    if not results:
        print("No results to summarize.")
        return

    gc_times = [r['gracon_time'] for r in results if r['gracon_time'] is not None]
    sfc_times = [r['sfc_time'] for r in results if r['sfc_time'] is not None]
    gc_psnrs = [r['gracon_psnr'] for r in results if r['gracon_psnr'] is not None]
    sfc_psnrs = [r['sfc_psnr'] for r in results if r['sfc_psnr'] is not None]
    gc_tiles_list = [r['gracon_tiles'] for r in results if r['gracon_tiles'] is not None]
    sfc_tiles_list = [r['sfc_tiles'] for r in results if r['sfc_tiles'] is not None]

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    # Per-image table
    hdr = f"{'Image':<40} {'gracon ms':>9} {'sfc ms':>9} {'Speedup':>8} {'gc PSNR':>8} {'sfc PSNR':>9}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        gc_t = f"{r['gracon_time']*1000:.1f}" if r['gracon_time'] is not None else "ERR"
        sfc_t = f"{r['sfc_time']*1000:.1f}" if r['sfc_time'] is not None else "ERR"
        if r['gracon_time'] and r['sfc_time'] and r['gracon_time'] > 0:
            spd = f"{r['sfc_time']/r['gracon_time']:.1f}x"
        else:
            spd = "N/A"
        gc_p = f"{r['gracon_psnr']:.1f}" if r['gracon_psnr'] is not None else "ERR"
        sfc_p = f"{r['sfc_psnr']:.1f}" if r['sfc_psnr'] is not None else "ERR"
        print(f"{r['name']:<40} {gc_t:>9} {sfc_t:>9} {spd:>8} {gc_p:>8} {sfc_p:>9}")

    print()

    def stats(arr):
        if not arr:
            return "N/A"
        return f"mean={np.mean(arr):.1f}  med={np.median(arr):.1f}  min={np.min(arr):.1f}  max={np.max(arr):.1f}"

    print("--- Timing (ms) ---")
    print(f"  gracon:       {stats([t*1000 for t in gc_times])}")
    print(f"  superfamiconv:{stats([t*1000 for t in sfc_times])}")
    if gc_times and sfc_times:
        mean_speedup = np.mean(sfc_times) / np.mean(gc_times)
        med_speedup = np.median(sfc_times) / np.median(gc_times)
        print(f"  Mean speedup: {mean_speedup:.1f}x  Median speedup: {med_speedup:.1f}x")

    print(f"\n--- PSNR (dB) ---")
    print(f"  gracon:       {stats(gc_psnrs)}")
    print(f"  superfamiconv:{stats(sfc_psnrs)}")

    print(f"\n--- Tile count ---")
    print(f"  gracon:       {stats([float(t) for t in gc_tiles_list])}")
    print(f"  superfamiconv:{stats([float(t) for t in sfc_tiles_list])}")

    # Throughput estimate for full pipeline (~35K frames)
    if gc_times:
        gc_fps = 1.0 / np.mean(gc_times)
        print(f"\n--- Estimated throughput (35K frames) ---")
        print(f"  gracon:        {gc_fps:.0f} frames/sec  → {35000/gc_fps/60:.1f} min total")
    if sfc_times:
        sfc_fps = 1.0 / np.mean(sfc_times)
        print(f"  superfamiconv: {sfc_fps:.0f} frames/sec  → {35000/sfc_fps/60:.1f} min total")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Benchmark gracon vs superfamiconv')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print per-image details')
    parser.add_argument('--frames', type=int, default=50,
                        help='Max video frames to sample (default: 50)')
    parser.add_argument('--warmup', type=int, default=2,
                        help='Warmup iterations to exclude (default: 2)')
    args = parser.parse_args()

    print("Benchmark: gracon.py vs superfamiconv + reduce_tiles")
    print(f"  superfamiconv: {SUPERFAMICONV}")
    print(f"  gracon:        {os.path.join(TOOLS_DIR, 'gracon.py')}")
    print()

    # Check superfamiconv exists
    if not os.path.exists(SUPERFAMICONV):
        print(f"WARNING: superfamiconv not found at {SUPERFAMICONV}")
        print("  superfamiconv results will show as ERR")

    images = find_test_images(max_video_frames=args.frames)
    if not images:
        print("ERROR: No test images found")
        sys.exit(1)

    bg_count = sum(1 for t, _ in images if t == 'bg')
    vid_count = sum(1 for t, _ in images if t == 'video')
    print(f"Found {len(images)} test images ({bg_count} backgrounds, {vid_count} video frames)")
    print(f"Warmup: {args.warmup} images (excluded from stats)\n")

    results = run_benchmark(images, warmup=args.warmup, verbose=args.verbose)
    print_summary(results)


if __name__ == '__main__':
    main()
