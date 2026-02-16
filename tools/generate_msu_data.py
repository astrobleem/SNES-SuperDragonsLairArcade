#!/usr/bin/env python3
"""
generate_msu_data.py - Generate MSU-1 .msu video data file from dl_arcade.mp4

Pipeline:
1. Parse chapter XMLs for timing info
2. Extract video frames from MP4 per chapter (ffmpeg with CUDA GPU accel)
3. Convert frames to SNES tiles/tilemap/palette (superfamiconv)
   - Each 256x192 frame produces up to 768 unique 8x8 tiles, but SNES VRAM
     only holds 512 at 4BPP. reduce_tiles() merges the 256 most visually
     similar pairs using RGB-space L2 distance with a global greedy algorithm.
4. Package into .msu file (msu1blockwriter.py)

Usage (from project root, in WSL or Windows):
  python3 tools/generate_msu_data.py [--workers N] [--chapter NAME] [--skip-extract] [--skip-convert] [--skip-package]
"""

import os
import sys

# CRITICAL: Set BLAS to single-threaded BEFORE importing numpy.
# reduce_tiles() uses numpy matrix multiplication (pixels @ pixels.T) which calls
# multi-threaded BLAS internally. When multiple Python threads in ThreadPoolExecutor
# call BLAS concurrently, the shared BLAS thread pool corrupts results. This caused
# 63% of video frames to have scrambled tilemaps.
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

import xml.dom.minidom
import subprocess
import concurrent.futures
import time
import glob
import argparse
import shutil
import struct
import numpy as np

# ---------- Configuration ----------
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_DIR = os.path.join(PROJECT_DIR, 'data', 'events')
CHAPTERS_DIR = os.path.join(PROJECT_DIR, 'data', 'chapters')
TOOLS_DIR = os.path.join(PROJECT_DIR, 'tools')
SUPERFAMICONV = os.path.join(TOOLS_DIR, 'superfamiconv', 'superfamiconv.exe')
MSU_WRITER = os.path.join(TOOLS_DIR, 'msu1blockwriter.py')
DRAGON_ROAR_PCM = os.path.join(PROJECT_DIR, 'data', 'sounds', 'SuperDragonsLairArcade-900.pcm')
BLANK_FRAMES_SCRIPT = os.path.join(TOOLS_DIR, 'generate_blank_frames.py')

# Windows ffmpeg with CUDA support (WSL-mounted path for subprocess, Windows path for display)
WIN_FFMPEG_WSL = "/mnt/c/Users/chad/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-6.0-full_build/bin/ffmpeg.exe"
WIN_FFMPEG_WIN = r"C:\Users\chad\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-6.0-full_build\bin\ffmpeg.exe"
# Fallback to system ffmpeg
SYSTEM_FFMPEG = "ffmpeg"

FPS = 24  # MSU-1 playback fps (msu1blockwriter uses integer)
SOURCE_FPS = 23.9777  # Source video fps for frame number calculation
BPP = 4
PALETTES = 1
MAX_COLORS = PALETTES * (2 ** BPP)  # 1 * 16 = 16 (one sub-palette per frame for reliable conversion)
MAX_TILES = 512  # VRAM tile buffer is $4000 bytes = 512 tiles at 4BPP (32 bytes/tile)
FRAME_WIDTH = 256
FRAME_HEIGHT = 192
TILEMAP_TARGET_SIZE = 2048  # 32x32 tiles * 2 bytes per entry
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
MSU1_AUDIO_HEADER = b"MSU1" + struct.pack('<I', 0)  # "MSU1" + loop point (0 = no loop)

OUTPUT_MSU = os.path.join(PROJECT_DIR, 'build', 'SuperDragonsLairArcade.msu')
FINAL_MSU_PATH = os.path.join(PROJECT_DIR, '..', 'SuperDragonsLairArcade.sfc', 'SuperDragonsLairArcade.msu')

# Daphne source paths (computed relative to project parent directory)
DEFAULT_FRAMEFILE = os.path.join(os.path.dirname(PROJECT_DIR), 'DaphneCDROM', 'framefile', 'dlcdrom.TXT')
DEFAULT_CONTENT_ROOT = os.path.join(os.path.dirname(PROJECT_DIR), 'DaphneCDROM', 'DLCDROM')

# ---------- Path conversion ----------
_is_wsl = None
def is_wsl():
    global _is_wsl
    if _is_wsl is None:
        try:
            with open('/proc/version', 'r') as f:
                _is_wsl = 'microsoft' in f.read().lower()
        except FileNotFoundError:
            _is_wsl = False
    return _is_wsl

def to_win_path(path):
    """Convert WSL path to Windows path for Windows executables."""
    if not is_wsl():
        return path
    path = os.path.abspath(path)
    if path.startswith('/mnt/'):
        parts = path[5:]
        drive = parts[0].upper()
        rest = parts[1:]
        return drive + ':' + rest.replace('/', '\\')
    return path

# ---------- Daphne Framefile ----------
def parse_framefile(framefile_path, content_root=None):
    """Parse Daphne framefile into sorted list of segment entries.

    Each entry: {frame, m2v_path, ogg_path, filename}
    The framefile format is: first line = relative content dir, then frame<tab>filename per line.
    """
    segments = []
    with open(framefile_path) as f:
        lines = f.readlines()

    if not content_root:
        # First line is relative path to content directory (may use backslashes)
        framefile_dir = os.path.dirname(os.path.abspath(framefile_path))
        relative_dir = lines[0].strip().replace('\\', '/')
        content_root = os.path.normpath(os.path.join(framefile_dir, relative_dir))

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        frame = int(parts[0])
        filename = parts[1].strip()

        m2v_path = os.path.join(content_root, filename)
        ogg_path = m2v_path.replace('.m2v', '.ogg')

        segments.append({
            'frame': frame,
            'm2v_path': m2v_path,
            'ogg_path': ogg_path,
            'filename': filename,
        })

    return sorted(segments, key=lambda s: s['frame'])


def find_segment(segments, target_frame):
    """Find the segment containing target_frame via binary search.

    Returns (segment_dict, offset_seconds) or (None, 0).
    offset_seconds is the time offset from the segment's start frame.
    """
    lo, hi = 0, len(segments) - 1
    result = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if segments[mid]['frame'] <= target_frame:
            result = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if result is not None:
        seg = segments[result]
        offset_seconds = (target_frame - seg['frame']) / 23.976
        return seg, offset_seconds
    return None, 0


# ---------- XML Parsing ----------
def parse_time(element):
    return (int(element.getAttribute('min')) * 60 * 1000 +
            int(element.getAttribute('second')) * 1000 +
            int(element.getAttribute('ms')))

def parse_chapter_xml(xml_path):
    with open(xml_path, 'rb') as f:
        dom = xml.dom.minidom.parseString(f.read())
    chapter = dom.getElementsByTagName('chapter')[0]
    # Get the chapter's own timeline (not nested event timelines)
    timeline = [t for t in chapter.getElementsByTagName('timeline')
                if t.parentNode == chapter][0]
    timestart_el = timeline.getElementsByTagName('timestart')[0]
    timestart = parse_time(timestart_el)
    timeend = parse_time(timeline.getElementsByTagName('timeend')[0])

    # Read optional laserdisc frame attribute
    start_frame = None
    if timestart_el.hasAttribute('frame'):
        start_frame = int(timestart_el.getAttribute('frame'))

    return {
        'name': chapter.getAttribute('name'),
        'timestart_ms': timestart,
        'timeend_ms': timeend,
        'duration_ms': max(0, timeend - timestart),
        'start_frame': start_frame,
    }

# ---------- Frame Extraction ----------
def format_time(ms):
    return "%02d:%02d:%02d.%03d" % (0, ms // 60000, (ms % 60000) // 1000, ms % 1000)

def get_ffmpeg():
    """Return (exe_path, needs_win_paths, has_cuda)."""
    if is_wsl() and os.path.exists(WIN_FFMPEG_WSL):
        # Use Windows ffmpeg via WSL interop (has CUDA), but it needs Windows paths for -i and -f image2
        return WIN_FFMPEG_WSL, True, True
    if not is_wsl() and os.path.exists(WIN_FFMPEG_WIN):
        return WIN_FFMPEG_WIN, False, True
    # Fallback: system ffmpeg (no CUDA in WSL typically)
    return SYSTEM_FFMPEG, False, False

def extract_chapter_frames_from_segment(chapter_info, chapter_dir, segments):
    """Extract video frames directly from a Daphne .m2v segment.

    Uses CPU-only decode with yadif deinterlace, fps conversion via filter,
    and trim filter for frame-accurate extraction (no -ss seeking).

    Returns frame count on success, 0 if skipped, or -1 on error.
    """
    if chapter_info['duration_ms'] <= 0:
        return 0

    start_frame = chapter_info.get('start_frame')
    if start_frame is None:
        return 0  # No frame info, skip

    seg, offset_seconds = find_segment(segments, start_frame)
    if seg is None:
        return 0

    m2v_path = seg['m2v_path']
    if not os.path.exists(m2v_path):
        return 0

    duration_s = chapter_info['duration_ms'] / 1000.0

    ffmpeg_path, needs_win_paths, _ = get_ffmpeg()

    if needs_win_paths:
        out_pattern = to_win_path(os.path.join(chapter_dir, "video_%06d.gfx_video.png"))
        video_path = to_win_path(m2v_path)
    else:
        out_pattern = os.path.join(chapter_dir, "video_%06d.gfx_video.png")
        video_path = m2v_path

    # Filter chain: yadif deinterlace (29.97i -> progressive) -> fps conversion
    # to 23.976 -> trim to target range -> reset PTS -> scale -> palette
    # No CUDA, no -ss seeking — CPU decode from start, trim handles offset
    filter_str = (
        f'yadif,fps=24000/1001,'
        f'trim=start={offset_seconds:.6f}:duration={duration_s:.6f},'
        f'setpts=PTS-STARTPTS,'
        f'scale={FRAME_WIDTH}:{FRAME_HEIGHT}[s];'
        f'[s]split[s1][s2];'
        f'[s1]palettegen=max_colors={MAX_COLORS}:stats_mode=single[p];'
        f'[s2][p]paletteuse=new=1:dither=bayer'
    )

    cmd = [
        ffmpeg_path, '-y',
        '-i', video_path,
        '-filter_complex', filter_str,
        '-f', 'image2',
        out_pattern
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"    ffmpeg error: {result.stderr[-200:] if result.stderr else 'unknown'}")
            return -1
    except subprocess.TimeoutExpired:
        return -1

    return len(glob.glob(os.path.join(chapter_dir, "video_*.gfx_video.png")))


# ---------- Audio Extraction ----------
def extract_chapter_audio_from_segment(chapter_info, chapter_dir, segments):
    """Extract audio from a Daphne .ogg segment.

    Returns True on success, or False on error/skip.
    """
    if chapter_info['duration_ms'] <= 0:
        return False

    start_frame = chapter_info.get('start_frame')
    if start_frame is None:
        return False

    seg, offset_seconds = find_segment(segments, start_frame)
    if seg is None:
        return False

    ogg_path = seg['ogg_path']
    if not os.path.exists(ogg_path):
        return False

    dur = format_time(chapter_info['duration_ms'])

    ffmpeg_path, needs_win_paths, _ = get_ffmpeg()

    if needs_win_paths:
        audio_path = to_win_path(ogg_path)
    else:
        audio_path = ogg_path

    raw_audio_path = os.path.join(chapter_dir, "sfx_video.raw")
    pcm_output_path = os.path.join(chapter_dir, "sfx_video.pcm")

    if needs_win_paths:
        raw_out = to_win_path(raw_audio_path)
    else:
        raw_out = raw_audio_path

    # Double-seeking for .ogg
    pre_seek_s = max(0, offset_seconds - 5)
    precise_offset_s = offset_seconds - pre_seek_s

    cmd = [
        ffmpeg_path, '-y',
        '-ss', f'{pre_seek_s:.3f}',
        '-i', audio_path,
        '-ss', f'{precise_offset_s:.3f}',
        '-t', dur,
        '-vn',
        '-ar', str(AUDIO_SAMPLE_RATE),
        '-ac', str(AUDIO_CHANNELS),
        '-f', 's16le',
        '-acodec', 'pcm_s16le',
        raw_out
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False
    except subprocess.TimeoutExpired:
        return False

    try:
        with open(raw_audio_path, 'rb') as f:
            raw_pcm = f.read()
        with open(pcm_output_path, 'wb') as f:
            f.write(MSU1_AUDIO_HEADER)
            f.write(raw_pcm)
        os.remove(raw_audio_path)
        return True
    except IOError:
        return False


# ---------- Tile Conversion ----------
def pad_tilemap(tilemap_file):
    """Pad tilemap to 32x32 (2048 bytes) for SNES compatibility."""
    with open(tilemap_file, 'rb') as f:
        data = f.read()
    if len(data) < TILEMAP_TARGET_SIZE:
        with open(tilemap_file, 'wb') as f:
            f.write(data)
            f.write(b'\x00' * (TILEMAP_TARGET_SIZE - len(data)))

def read_snes_palette(palette_file):
    """Read SNES BGR555 palette file and return (16, 3) float32 RGB array.

    SNES color format: 0BBBBBGG GGGRRRRR (little-endian 16-bit)
    Returns RGB values scaled to 0.0-255.0 for distance computation.
    """
    with open(palette_file, 'rb') as f:
        data = f.read()
    num_colors = len(data) // 2
    palette = np.zeros((max(16, num_colors), 3), dtype=np.float32)
    for i in range(num_colors):
        bgr555 = struct.unpack_from('<H', data, i * 2)[0]
        palette[i, 0] = (bgr555 & 0x1F) * (255.0 / 31.0)         # R
        palette[i, 1] = ((bgr555 >> 5) & 0x1F) * (255.0 / 31.0)  # G
        palette[i, 2] = ((bgr555 >> 10) & 0x1F) * (255.0 / 31.0) # B
    return palette


def decode_tiles_4bpp_rgb(tiles_raw, palette_rgb):
    """Decode SNES 4BPP tiles to RGB values using the frame's actual palette.

    tiles_raw: (N, 32) uint8 array of raw SNES 4BPP tile data
    palette_rgb: (16, 3) float32 array of RGB values for the palette
    Returns: (N, 192) float32 array (64 pixels x 3 RGB channels)

    Comparing tiles in RGB color space (rather than palette index space) is
    critical because palette indices have no inherent ordering — index 3 and
    14 might be nearly identical colors while 0 and 1 are completely different.

    SNES 4BPP tile format (32 bytes per 8x8 tile):
      Bytes  0-15: bitplanes 0,1 interleaved by row (2 bytes/row x 8 rows)
      Bytes 16-31: bitplanes 2,3 interleaved by row (2 bytes/row x 8 rows)
    Each pixel's 4-bit color index = bp0 | (bp1<<1) | (bp2<<2) | (bp3<<3)
    """
    N = tiles_raw.shape[0]
    pixel_indices = np.zeros((N, 8, 8), dtype=np.uint8)
    for row in range(8):
        # Bitplanes 0,1 are in bytes 0-15 (interleaved per row)
        bp0 = tiles_raw[:, 2 * row].astype(np.uint16)
        bp1 = tiles_raw[:, 2 * row + 1].astype(np.uint16)
        # Bitplanes 2,3 are in bytes 16-31 (interleaved per row)
        bp2 = tiles_raw[:, 16 + 2 * row].astype(np.uint16)
        bp3 = tiles_raw[:, 16 + 2 * row + 1].astype(np.uint16)
        for px in range(8):
            bit = 7 - px  # MSB = leftmost pixel
            pixel_indices[:, row, px] = (
                ((bp0 >> bit) & 1) |
                (((bp1 >> bit) & 1) << 1) |
                (((bp2 >> bit) & 1) << 2) |
                (((bp3 >> bit) & 1) << 3)
            ).astype(np.uint8)
    # Map palette indices to RGB colors: (N, 64) indices -> (N, 64, 3) RGB
    flat_indices = pixel_indices.reshape(N, 64)
    rgb = palette_rgb[flat_indices]  # numpy fancy indexing: (N, 64, 3)
    return rgb.reshape(N, 192)


def reduce_tiles(tile_file, tilemap_file, palette_file, max_tiles=MAX_TILES):
    """Reduce tile count to max_tiles using global greedy merge in RGB color space.

    SNES VRAM buffer is $4000 bytes = 512 tiles at 4BPP. Video frames at
    256x192 can have up to 768 unique tiles. This function finds the most
    similar tile pairs across the ENTIRE image and merges them, distributing
    quality loss evenly rather than concentrating it in the bottom rows.

    Uses L2 distance on actual RGB color values (decoded through the frame's
    palette) for accurate visual similarity matching. This is critical because
    palette indices have no inherent ordering — two indices that are numerically
    far apart may map to nearly identical colors.
    """
    bytes_per_tile = 8 * BPP  # 32 for 4BPP

    with open(tile_file, 'rb') as f:
        tile_data = f.read()
    num_tiles = len(tile_data) // bytes_per_tile
    if num_tiles <= max_tiles:
        return  # nothing to do

    tiles = np.frombuffer(tile_data, dtype=np.uint8).reshape(num_tiles, bytes_per_tile)

    # Decode tiles to RGB color space using the frame's actual palette
    palette_rgb = read_snes_palette(palette_file)
    pixels = decode_tiles_4bpp_rgb(tiles, palette_rgb)  # (N, 192) float32

    # Compute pairwise L2 squared distance matrix using dot product trick:
    # ||A-B||^2 = ||A||^2 + ||B||^2 - 2*A·B
    sq_norms = np.sum(pixels * pixels, axis=1)  # (N,)
    dot_products = pixels @ pixels.T             # (N, N) via BLAS
    dist = sq_norms[:, None] + sq_norms[None, :] - 2 * dot_products

    # Get all unique pairs (i < j) sorted by distance
    rows_idx, cols_idx = np.triu_indices(num_tiles, k=1)
    pair_dists = dist[rows_idx, cols_idx]
    sort_order = np.argsort(pair_dists)

    # Greedy merge: iterate through closest pairs, merge when both alive
    to_remove = num_tiles - max_tiles
    alive = set(range(num_tiles))
    merge_target = list(range(num_tiles))  # merge_target[i] = tile that i maps to
    removed = 0

    for idx in sort_order:
        if removed >= to_remove:
            break
        i = int(rows_idx[idx])
        j = int(cols_idx[idx])
        if i not in alive or j not in alive:
            continue
        # Remove the higher-indexed tile, keep the lower
        alive.discard(j)
        merge_target[j] = i
        removed += 1

    # Resolve transitive merges (j→i, but i may also have been merged later)
    for idx in range(num_tiles):
        target = merge_target[idx]
        while merge_target[target] != target:
            target = merge_target[target]
        merge_target[idx] = target

    # Re-index surviving tiles to contiguous 0..(max_tiles-1)
    alive_sorted = sorted(alive)
    reindex = {}
    for new_i, old_i in enumerate(alive_sorted):
        reindex[old_i] = new_i

    # Build final remap: old tile index → new contiguous index
    final_remap = np.array([reindex[merge_target[i]] for i in range(num_tiles)],
                           dtype=np.uint16)

    # Update tilemap
    with open(tilemap_file, 'rb') as f:
        tilemap_raw = f.read()
    tilemap = np.frombuffer(tilemap_raw, dtype=np.uint16).copy()
    tile_indices = tilemap & 0x3ff
    flags = tilemap & 0xfc00

    # Vectorized remap of all tilemap indices
    new_indices = final_remap[tile_indices]
    tilemap = flags | new_indices

    # Write reduced tiles (only surviving tiles, in original order)
    new_tile_data = tiles[alive_sorted].tobytes()
    with open(tile_file, 'wb') as f:
        f.write(new_tile_data)

    # Write updated tilemap
    with open(tilemap_file, 'wb') as f:
        f.write(tilemap.tobytes())

def convert_frame_superfamiconv(png_path):
    """Convert one PNG frame to SNES tiles/tilemap/palette using superfamiconv."""
    base = png_path[:-4]  # Remove .png
    pal_file = base + '.palette'
    tile_file = base + '.tiles'
    map_file = base + '.tilemap'

    # superfamiconv.exe (Windows binary) only works with relative paths in WSL.
    # Use cwd=PROJECT_DIR and make all paths relative.
    sfc = os.path.relpath(SUPERFAMICONV, PROJECT_DIR)
    rel_png = os.path.relpath(png_path, PROJECT_DIR)
    rel_pal = os.path.relpath(pal_file, PROJECT_DIR)
    rel_tile = os.path.relpath(tile_file, PROJECT_DIR)
    rel_map = os.path.relpath(map_file, PROJECT_DIR)

    run_kw = dict(capture_output=True, text=True, timeout=30, cwd=PROJECT_DIR)

    # 1. Palette extraction
    r = subprocess.run([sfc, 'palette', '-i', rel_png, '-d', rel_pal, '-C', str(MAX_COLORS)], **run_kw)
    if r.returncode != 0:
        return False, f"palette: {r.stderr.strip()}"

    # 2. Tile conversion (no tile limit — post-process to reduce)
    r = subprocess.run([sfc, 'tiles', '-i', rel_png, '-p', rel_pal, '-d', rel_tile, '-B', str(BPP)], **run_kw)
    if r.returncode != 0:
        return False, f"tiles: {r.stderr.strip()}"

    # 3. Tilemap generation
    r = subprocess.run([sfc, 'map', '-i', rel_png, '-p', rel_pal, '-t', rel_tile, '-d', rel_map, '-B', str(BPP)], **run_kw)
    if r.returncode != 0:
        return False, f"map: {r.stderr.strip()}"

    # 4. Reduce tiles to fit in VRAM buffer (512 max at 4BPP)
    reduce_tiles(tile_file, map_file, pal_file)

    # 5. Pad tilemap to 32x32
    pad_tilemap(map_file)

    return True, ""

def convert_chapter_frames(chapter_dir, max_workers=4):
    """Convert all PNG frames in a chapter directory to SNES tiles."""
    pngs = sorted(glob.glob(os.path.join(chapter_dir, "*.gfx_video.png")))
    if not pngs:
        return 0

    converted = 0
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(convert_frame_superfamiconv, p): p for p in pngs}
        for future in concurrent.futures.as_completed(futures):
            success, err = future.result()
            if success:
                converted += 1
            else:
                failed += 1
                if failed <= 3:  # Only print first few errors
                    print(f"    WARN: Failed {os.path.basename(futures[future])}: {err}")

    return converted

# ---------- Main Pipeline ----------
def main():
    parser = argparse.ArgumentParser(description='Generate MSU-1 .msu video data')
    parser.add_argument('--workers', type=int, default=8,
                        help='Parallel workers for tile conversion (default: 8)')
    parser.add_argument('--chapter', type=str,
                        help='Process a single chapter by name')
    parser.add_argument('--skip-extract', action='store_true',
                        help='Skip frame extraction (use existing PNGs)')
    parser.add_argument('--skip-convert', action='store_true',
                        help='Skip tile conversion (use existing tiles)')
    parser.add_argument('--skip-package', action='store_true',
                        help='Skip .msu packaging step')
    parser.add_argument('--skip-audio', action='store_true',
                        help='Skip audio extraction')
    parser.add_argument('--clean', action='store_true',
                        help='Remove existing video frames before extraction')
    parser.add_argument('--framefile', type=str, default=DEFAULT_FRAMEFILE,
                        help='Path to Daphne framefile (default: %(default)s)')
    parser.add_argument('--content-root', type=str, default=None,
                        help='Path to Daphne content directory (default: from framefile)')
    args = parser.parse_args()

    print("=" * 60)
    print("MSU-1 Video Data Generator")
    print("=" * 60)
    print(f"Chapters dir: {CHAPTERS_DIR}")
    print(f"Output MSU:   {OUTPUT_MSU}")
    print(f"Workers:      {args.workers}")

    ffmpeg_path, needs_win_paths, has_cuda = get_ffmpeg()
    print(f"ffmpeg:       {ffmpeg_path}")
    print(f"CUDA GPU:     {'Yes' if has_cuda else 'No (CPU fallback)'}")
    print(f"superfamiconv: {SUPERFAMICONV}")

    # Load Daphne framefile for direct .m2v/.ogg extraction (mandatory)
    if not os.path.exists(args.framefile):
        print(f"\nERROR: Daphne framefile not found: {args.framefile}")
        sys.exit(1)

    daphne_segments = parse_framefile(args.framefile, args.content_root)
    print(f"Framefile:    {args.framefile} ({len(daphne_segments)} segments)")

    if daphne_segments:
        sample_m2v = daphne_segments[0]['m2v_path']
        content_dir = os.path.dirname(sample_m2v)
        if os.path.isdir(content_dir):
            print(f"Content root: {content_dir}")
        else:
            print(f"\nERROR: Content root not found: {content_dir}")
            sys.exit(1)
    else:
        print(f"\nERROR: Framefile parsed 0 segments")
        sys.exit(1)

    print(f"\nUsing direct .m2v/.ogg extraction from Daphne segments")
    print()

    # Build chapter list
    chapters = []
    for chapter_name in sorted(os.listdir(CHAPTERS_DIR)):
        chapter_dir = os.path.join(CHAPTERS_DIR, chapter_name)
        if not os.path.isdir(chapter_dir):
            continue
        xml_path = os.path.join(EVENTS_DIR, chapter_name + '.xml')
        if not os.path.exists(xml_path):
            print(f"WARN: No XML for chapter {chapter_name}, skipping")
            continue
        if args.chapter and chapter_name != args.chapter:
            continue
        chapters.append((chapter_name, chapter_dir, xml_path))

    print(f"Found {len(chapters)} chapters to process\n")

    # Phase 1: Extract video frames from .m2v segments
    total_frames = 0
    extract_errors = 0
    skipped_no_frame = 0
    if not args.skip_extract:
        print("--- Phase 1: Extracting video frames (ffmpeg from .m2v) ---")
        extract_start = time.time()

        for i, (name, cdir, xml) in enumerate(chapters):
            info = parse_chapter_xml(xml)
            if info['duration_ms'] <= 0:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: skip (0 duration)")
                continue

            if args.clean:
                for f in glob.glob(os.path.join(cdir, "*.gfx_video.png")):
                    os.remove(f)

            existing = glob.glob(os.path.join(cdir, "*.gfx_video.png"))
            if existing and not args.clean:
                n = len(existing)
                print(f"[{i+1:3d}/{len(chapters)}] {name}: {n} frames (cached)")
                total_frames += n
                continue

            if info.get('start_frame') is None:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: SKIP (no start_frame)")
                skipped_no_frame += 1
                continue

            n = extract_chapter_frames_from_segment(info, cdir, daphne_segments)
            if n > 0:
                total_frames += n
                print(f"[{i+1:3d}/{len(chapters)}] {name}: {n} frames (from .m2v)")
            elif n == 0:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: 0 frames (no segment)")
            else:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: EXTRACTION ERROR")
                extract_errors += 1

        extract_elapsed = time.time() - extract_start
        print(f"\nExtraction done: {total_frames} frames in {extract_elapsed:.1f}s "
              f"({extract_errors} errors, {skipped_no_frame} skipped no start_frame)\n")
    else:
        for name, cdir, xml in chapters:
            total_frames += len(glob.glob(os.path.join(cdir, "*.gfx_video.png")))
        print(f"Skipping extraction. {total_frames} existing PNG frames found.\n")

    # Phase 1b: Extract audio per chapter from .ogg segments
    total_audio = 0
    audio_errors = 0
    if not args.skip_audio:
        print("--- Phase 1b: Extracting audio per chapter (ffmpeg from .ogg) ---")
        audio_start = time.time()

        for i, (name, cdir, xml) in enumerate(chapters):
            info = parse_chapter_xml(xml)
            if info['duration_ms'] <= 0:
                continue

            pcm_path = os.path.join(cdir, "sfx_video.pcm")
            if os.path.exists(pcm_path) and not args.clean:
                total_audio += 1
                if (i + 1) % 50 == 0 or i == len(chapters) - 1:
                    print(f"[{i+1:3d}/{len(chapters)}] {name}: audio (cached)")
                continue

            if extract_chapter_audio_from_segment(info, cdir, daphne_segments):
                total_audio += 1
                if (i + 1) % 50 == 0 or i == len(chapters) - 1:
                    print(f"[{i+1:3d}/{len(chapters)}] {name}: audio (from .ogg)")
            else:
                audio_errors += 1
                if audio_errors <= 5:
                    print(f"[{i+1:3d}/{len(chapters)}] {name}: AUDIO ERROR")

        audio_elapsed = time.time() - audio_start
        print(f"\nAudio extraction done: {total_audio} chapters in {audio_elapsed:.1f}s "
              f"({audio_errors} errors)\n")
    else:
        for name, cdir, xml in chapters:
            if os.path.exists(os.path.join(cdir, "sfx_video.pcm")):
                total_audio += 1
        print(f"Skipping audio extraction. {total_audio} existing PCM files found.\n")

    # Phase 1c: Copy PCM files to numbered output files (SuperDragonsLairArcade-{chapterID}.pcm)
    pcm_copied = 0
    if total_audio > 0:
        print("--- Phase 1c: Copying PCM files to numbered output ---")
        build_dir = os.path.dirname(OUTPUT_MSU)
        os.makedirs(build_dir, exist_ok=True)
        final_dir = os.path.normpath(os.path.join(PROJECT_DIR, '..', 'SuperDragonsLairArcade.sfc'))
        base_name = os.path.splitext(os.path.basename(OUTPUT_MSU))[0]

        for name, cdir, xml in chapters:
            pcm_path = os.path.join(cdir, "sfx_video.pcm")
            if not os.path.exists(pcm_path):
                continue

            # Read chapter ID from chapter.id.NNN file
            id_files = [f for f in os.listdir(cdir) if f.startswith('chapter.id')]
            if not id_files:
                continue
            try:
                chapter_id = int(id_files[0].split('chapter.id')[-1].lstrip('.'))
            except ValueError:
                continue

            out_name = f"{base_name}-{chapter_id}.pcm"
            build_pcm = os.path.join(build_dir, out_name)
            shutil.copy2(pcm_path, build_pcm)
            pcm_copied += 1

            if os.path.isdir(final_dir):
                shutil.copy2(pcm_path, os.path.join(final_dir, out_name))

        print(f"Copied {pcm_copied} PCM files to {build_dir}")
        if os.path.isdir(final_dir):
            print(f"Also copied to {final_dir}")
        print()

    # Phase 1d: Copy dragon roar PCM (track 900) to build and sfc directories
    if os.path.exists(DRAGON_ROAR_PCM):
        build_dir = os.path.dirname(OUTPUT_MSU)
        final_dir = os.path.normpath(os.path.join(PROJECT_DIR, '..', 'SuperDragonsLairArcade.sfc'))
        roar_name = os.path.basename(DRAGON_ROAR_PCM)
        shutil.copy2(DRAGON_ROAR_PCM, os.path.join(build_dir, roar_name))
        if os.path.isdir(final_dir):
            shutil.copy2(DRAGON_ROAR_PCM, os.path.join(final_dir, roar_name))
        print(f"Copied dragon roar PCM (track 900) to build + sfc directories\n")
    else:
        print(f"WARNING: Dragon roar PCM not found at {DRAGON_ROAR_PCM}\n"
              f"  Run: python3 tools/convert_roar_pcm.py\n")

    # Phase 1e: Generate blank frames for chapters with no video
    if not args.skip_extract:
        print("--- Phase 1e: Generating blank frames for empty chapters ---")
        result = subprocess.run(
            [sys.executable, BLANK_FRAMES_SCRIPT],
            capture_output=True, text=True, timeout=600, cwd=PROJECT_DIR)
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"WARNING: blank frame generation failed: {result.stderr.strip()}")
        print()

    # Phase 2: Convert frames to SNES tiles
    total_converted = 0
    if not args.skip_convert:
        print(f"--- Phase 2: Converting frames to SNES tiles (superfamiconv, {args.workers} workers) ---")
        convert_start = time.time()

        for i, (name, cdir, xml) in enumerate(chapters):
            pngs = glob.glob(os.path.join(cdir, "*.gfx_video.png"))
            existing_tiles = glob.glob(os.path.join(cdir, "*.gfx_video.tiles"))

            if not pngs:
                continue

            if len(existing_tiles) == len(pngs) and not args.clean:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: {len(existing_tiles)} tiles (cached)")
                total_converted += len(existing_tiles)
                continue

            n = convert_chapter_frames(cdir, max_workers=args.workers)
            total_converted += n
            print(f"[{i+1:3d}/{len(chapters)}] {name}: {n}/{len(pngs)} converted")

        convert_elapsed = time.time() - convert_start
        print(f"\nConversion done: {total_converted} tiles in {convert_elapsed:.1f}s\n")
    else:
        for name, cdir, xml in chapters:
            total_converted += len(glob.glob(os.path.join(cdir, "*.gfx_video.tiles")))
        print(f"Skipping conversion. {total_converted} existing tile files found.\n")

    # Phase 3: Package .msu file
    if not args.skip_package:
        print("--- Phase 3: Packaging .msu file ---")

        # Ensure build directory exists
        os.makedirs(os.path.dirname(OUTPUT_MSU), exist_ok=True)

        cmd = [
            sys.executable, MSU_WRITER,
            '-title', "SUPER DRAGON'S LAIR",
            '-infilebase', CHAPTERS_DIR,
            '-outfile', OUTPUT_MSU,
            '-bpp', str(BPP),
            '-fps', str(FPS),
        ]
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            msu_size = os.path.getsize(OUTPUT_MSU) if os.path.exists(OUTPUT_MSU) else 0
            print(f"Success! MSU file: {OUTPUT_MSU} ({msu_size / 1024 / 1024:.1f} MB)")
            if result.stdout.strip():
                print(result.stdout.strip())

            # Copy to sfc folder
            final_path = os.path.normpath(FINAL_MSU_PATH)
            if os.path.isdir(os.path.dirname(final_path)):
                shutil.copy2(OUTPUT_MSU, final_path)
                print(f"Copied to: {final_path}")
            else:
                print(f"NOTE: Target folder doesn't exist, skipping copy to {final_path}")
        else:
            print(f"ERROR packaging .msu:")
            print(result.stderr)
            sys.exit(1)
    else:
        print("Skipping .msu packaging.\n")

    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Frames extracted: {total_frames}")
    print(f"  Audio extracted:  {total_audio}")
    print(f"  Tiles converted:  {total_converted}")
    if os.path.exists(OUTPUT_MSU):
        print(f"  MSU file size:    {os.path.getsize(OUTPUT_MSU) / 1024 / 1024:.1f} MB")
    print("=" * 60)


if __name__ == '__main__':
    main()
