#!/usr/bin/env python3
"""
generate_msu_data.py - Generate MSU-1 .msu video data file from dl_arcade.mp4

Pipeline:
1. Parse chapter XMLs for timing info
2. Extract video frames from MP4 per chapter (ffmpeg with CUDA GPU accel)
3. Convert frames to SNES tiles/tilemap/palette (superfamiconv)
   - Each 256x160 frame produces up to 640 unique 8x8 tiles, but SNES VRAM
     budget is 512 at 4BPP. reduce_tiles() merges the most visually
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
import math
import numpy as np
from PIL import Image

# ---------- Configuration ----------
from paths import PROJECT_ROOT, BUILD_DIR, TOOLS_DIR, DISTRIBUTION, DAPHNE_FRAMEFILE, DAPHNE_CONTENT, FFMPEG

PROJECT_DIR = str(PROJECT_ROOT)
EVENTS_DIR = os.path.join(PROJECT_DIR, 'data', 'events')
CHAPTERS_DIR = os.path.join(PROJECT_DIR, 'data', 'chapters')
SUPERFAMICONV = os.path.join(str(TOOLS_DIR), 'superfamiconv', 'superfamiconv.exe')
MSU_WRITER = os.path.join(str(TOOLS_DIR), 'msu1blockwriter.py')
DRAGON_ROAR_PCM = os.path.join(PROJECT_DIR, 'data', 'sounds', 'SuperDragonsLairArcade-900.pcm')

FPS = 24  # MSU-1 playback fps (msu1blockwriter uses integer)
SOURCE_FPS = 23.9777  # Source video fps for frame number calculation
BPP = 4
PALETTES = 8
MAX_COLORS = PALETTES * (2 ** BPP)  # 8 * 16 = 128 (8 sub-palettes for color fidelity)
MAX_TILES = 512  # VRAM tile buffer: 512 tiles at 4BPP (32 bytes/tile) = $4000 bytes
FRAME_WIDTH = 256
FRAME_HEIGHT = 160
TILEMAP_TARGET_SIZE = 1280  # 32x20 tiles * 2 bytes per entry

# Dithering method constants
DITHER_NONE = 'none'
DITHER_FLOYD_STEINBERG = 'floyd-steinberg'
DITHER_ORDERED = 'ordered'
DEFAULT_DITHER = DITHER_FLOYD_STEINBERG

# 4x4 Bayer threshold matrix normalized to BGR555 quantization step (~+-4.1 in RGB-255 space)
_BAYER_4x4 = np.array([
    [ 0,  8,  2, 10],
    [12,  4, 14,  6],
    [ 3, 11,  1,  9],
    [15,  7, 13,  5],
], dtype=np.float32)
_BAYER_4x4_SCALED = (_BAYER_4x4 / 16.0 - 0.5) * (255.0 / 31.0)

# Scale mode constants for frame extraction
SCALE_STRETCH = 'stretch'
SCALE_FIT = 'fit'
SCALE_CROP = 'crop'

# Scene name -> chapter prefix mapping (29 scenes)
SCENE_PREFIXES = {
    'introduction': 'intr_',
    'vestibule': 'vest_',
    'snake_room': 'snkr_',
    'bower': 'bowr_',
    'fire_room': 'firm_',
    'throne_room': 'thrn_',
    'tilting_room': 'tltr_',
    'tentacle_room': 'tntr_',
    'wind_room': 'wndr_',
    'giddy_goons': 'gg_',
    'catwalk_bats': 'cwbt_',
    'mudmen': 'mudm_',
    'rolling_balls': 'rbal_',
    'underground_river': 'ugr_',
    'flaming_ropes': 'flrp_',
    'flying_horse': 'fh_',
    'bubbling_cauldron': 'bcld_',
    'giant_bat': 'gbat_',
    'crypt_creeps': 'cc_',
    'alice_room': 'alrm_',
    'robot_knight': 'rk_',
    'smithee': 'sm_',
    'smithee_reversed': 'smr_',
    'grim_reaper': 'gr_',
    'yellow_brick_road': 'ybr_',
    'black_knight': 'bknt_',
    'lizard_king': 'lzkg_',
    'the_dragons_lair': 'tdl_',
    'attract_mode': 'atmd_',
}
AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
MSU1_AUDIO_HEADER = b"MSU1" + struct.pack('<I', 0)  # "MSU1" + loop point (0 = no loop)

OUTPUT_MSU = os.path.join(str(BUILD_DIR), 'SuperDragonsLairArcade.msu')
FINAL_MSU_PATH = os.path.join(str(DISTRIBUTION), 'SuperDragonsLairArcade.msu')

DEFAULT_FRAMEFILE = str(DAPHNE_FRAMEFILE)
DEFAULT_CONTENT_ROOT = str(DAPHNE_CONTENT)

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
    """Return (exe_path, needs_win_paths, has_cuda).

    Uses the FFMPEG path from paths.py (configurable via project.conf or
    FFMPEG env var). If the resolved path is a Windows executable accessed
    from WSL, needs_win_paths is True.
    """
    ffmpeg_path = FFMPEG
    needs_win = is_wsl() and (ffmpeg_path.endswith('.exe') or '\\' in ffmpeg_path)
    has_cuda = ffmpeg_path != "ffmpeg" and os.path.exists(ffmpeg_path)
    return ffmpeg_path, needs_win, has_cuda

def _build_scale_filter(width, height, scale_mode, aspect_ratio=None):
    """Build ffmpeg video filter chain for scaling to the target resolution.

    Returns a list of ffmpeg filter strings (to be comma-joined into a -vf chain).

    Scale modes:
      stretch: scale=W:H (forces exact dimensions, may distort)
      fit:     scale to fit inside WxH, pad with black bars
      crop:    scale to cover WxH, center-crop overflow
    """
    filters = []

    # Aspect ratio override (pre-scale) — only meaningful for fit/crop
    if aspect_ratio and scale_mode != SCALE_STRETCH:
        ar = aspect_ratio.replace('/', ':')
        ar_w, ar_h = ar.split(':')
        filters.append(f'scale=trunc(ih*{ar_w}/{ar_h}/2)*2:ih')
        filters.append('setsar=1')

    if scale_mode == SCALE_FIT:
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=decrease')
        filters.append(f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black')
    elif scale_mode == SCALE_CROP:
        filters.append(f'scale={width}:{height}:force_original_aspect_ratio=increase')
        filters.append(f'crop={width}:{height}')
    else:
        # stretch (default)
        filters.append(f'scale={width}:{height}')

    return filters


def extract_chapter_frames_from_segment(chapter_info, chapter_dir, segments,
                                        scale_mode=SCALE_STRETCH,
                                        aspect_ratio=None):
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
    # to 23.976 -> trim to target range -> reset PTS -> scale
    # Output full-color 24-bit RGB PNGs (palette optimization done in Python)
    # No CUDA, no -ss seeking — CPU decode from start, trim handles offset
    scale_filters = _build_scale_filter(FRAME_WIDTH, FRAME_HEIGHT,
                                        scale_mode, aspect_ratio)
    filter_str = (
        f'yadif,fps=24000/1001,'
        f'trim=start={offset_seconds:.6f}:duration={duration_s:.6f},'
        f'setpts=PTS-STARTPTS,'
        + ','.join(scale_filters)
    )

    cmd = [
        ffmpeg_path, '-y',
        '-i', video_path,
        '-vf', filter_str,
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


def rgb_to_bgr555(r, g, b):
    """Convert 8-bit RGB to SNES BGR555 (16-bit value)."""
    r5 = int(round(r * 31.0 / 255.0)) & 0x1F
    g5 = int(round(g * 31.0 / 255.0)) & 0x1F
    b5 = int(round(b * 31.0 / 255.0)) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


def bgr555_to_rgb_float(bgr555):
    """Convert BGR555 to (R, G, B) as floats in 0-255 range."""
    r = (bgr555 & 0x1F) * (255.0 / 31.0)
    g = ((bgr555 >> 5) & 0x1F) * (255.0 / 31.0)
    b = ((bgr555 >> 10) & 0x1F) * (255.0 / 31.0)
    return (r, g, b)


def simple_kmeans(data, k, max_iter=20):
    """K-means++ clustering on (N, D) float32 array. Returns (labels, centers)."""
    N = data.shape[0]
    if N <= k:
        labels = np.arange(N, dtype=np.int32)
        centers = data.copy()
        # Pad with duplicates if fewer points than clusters
        if N < k:
            centers = np.vstack([centers, np.tile(centers[0], (k - N, 1))])
            labels = np.arange(N, dtype=np.int32)
        return labels, centers

    rng = np.random.RandomState(42)

    # K-means++ initialization
    centers = np.empty((k, data.shape[1]), dtype=data.dtype)
    idx = rng.randint(N)
    centers[0] = data[idx]

    for c in range(1, k):
        dists = np.min(np.sum((data[:, None, :] - centers[None, :c, :]) ** 2, axis=2), axis=1)
        total = dists.sum()
        if total == 0:
            # All points identical — pick random
            idx = rng.randint(N)
        else:
            probs = dists / total
            probs /= probs.sum()  # renormalize for float rounding
            idx = rng.choice(N, p=probs)
        centers[c] = data[idx]

    for _ in range(max_iter):
        dists = np.sum((data[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1).astype(np.int32)

        new_centers = np.empty_like(centers)
        for c in range(k):
            mask = labels == c
            if mask.any():
                new_centers[c] = data[mask].mean(axis=0)
            else:
                new_centers[c] = centers[c]

        if np.allclose(new_centers, centers):
            break
        centers = new_centers

    return labels, centers


def compute_shared_palette(png_paths, num_palettes=PALETTES, grayscale=False):
    """Compute a shared palette from multiple frames for temporal stability.

    Samples colors and tile means from all provided frames, then builds
    sub-palettes that work well across all of them. This prevents palette
    shifts between frames, reducing dither "swimming".

    Args:
        png_paths: List of PNG file paths to sample from
        num_palettes: Number of sub-palettes
        grayscale: If True, convert frames to grayscale before sampling

    Returns:
        List of sub-palettes, each a list of 16 BGR555 values (color 0 = 0x0000)
    """
    all_tile_means = []
    all_tile_bgr555 = []

    for path in png_paths:
        img = Image.open(path).convert('RGB')
        if grayscale:
            img = img.convert('L').convert('RGB')
        rgb = np.array(img, dtype=np.float32)
        H, W = rgb.shape[:2]
        tiles_h, tiles_w = H // 8, W // 8

        rgb5 = np.round(rgb * 31.0 / 255.0).clip(0, 31).astype(np.uint8)
        rgb_q = rgb5.astype(np.float32) * (255.0 / 31.0)

        tile_blocks = rgb_q.reshape(tiles_h, 8, tiles_w, 8, 3).transpose(0, 2, 1, 3, 4)
        tile_means = tile_blocks.mean(axis=(2, 3))

        for tr in range(tiles_h):
            for tc in range(tiles_w):
                all_tile_means.append(tile_means[tr, tc])
                block = rgb5[tr * 8:(tr + 1) * 8, tc * 8:(tc + 1) * 8]
                bgr_set = set()
                for y in range(8):
                    for x in range(8):
                        r5, g5, b5 = int(block[y, x, 0]), int(block[y, x, 1]), int(block[y, x, 2])
                        bgr = r5 | (g5 << 5) | (b5 << 10)
                        bgr_set.add(bgr)
                all_tile_bgr555.append(bgr_set)

    all_tile_means = np.array(all_tile_means, dtype=np.float32)

    labels, _centers = simple_kmeans(all_tile_means, num_palettes)

    sub_palettes = []
    for p in range(num_palettes):
        mask = labels == p
        tile_indices = np.where(mask)[0]

        bgr555_set = set()
        for ti in tile_indices:
            bgr555_set.update(all_tile_bgr555[ti])
        bgr555_set.discard(0)

        if len(bgr555_set) <= 15:
            colors = sorted(bgr555_set)
        else:
            unique_list = sorted(bgr555_set)
            unique_rgb = np.array([bgr555_to_rgb_float(c) for c in unique_list], dtype=np.float32)
            clabels, ccenters = simple_kmeans(unique_rgb, 15)
            colors = []
            for c in ccenters:
                colors.append(rgb_to_bgr555(int(round(c[0])), int(round(c[1])), int(round(c[2]))))
            colors = sorted(set(colors))
            if 0 in colors:
                colors.remove(0)
            colors = colors[:15]

        full_palette = [0] + colors
        while len(full_palette) < 16:
            full_palette.append(0)
        sub_palettes.append(full_palette)

    return sub_palettes


def _smooth_tile_assignments(tile_labels, palettes, snes_tiles,
                             tiles_h, tiles_w,
                             max_error_ratio=math.e, max_iterations=3):
    """Spatially smooth tile-to-palette assignments to reduce boundary artifacts.

    For each tile, if a majority of its 4-connected neighbors use a different
    palette and switching has acceptable quantization error cost, reassign it.
    This eliminates visible 8x8 block artifacts in smooth gradient regions
    where adjacent tiles land on different sub-palettes.

    Args:
        tile_labels: (tiles_h, tiles_w) int, current palette assignments
        palettes: list of num_palettes lists of 16 BGR555 values (index 0 = transparent)
        snes_tiles: (n_tiles, 8, 8) uint16 BGR555 pixel data
        tiles_h, tiles_w: grid dimensions
        max_error_ratio: maximum allowed error increase per tile (1.15 = 15%)
        max_iterations: maximum smoothing iterations

    Returns:
        (tiles_h, tiles_w) int array of smoothed palette assignments
    """
    n_tiles = tiles_h * tiles_w
    num_palettes = len(palettes)

    # Precompute full (n_tiles, num_palettes) error matrix — fully vectorized.
    # For each palette, compute weighted quantization error for ALL tiles at once.
    # Pixel data: (n_tiles, 64) uint16 BGR555 values
    pixels = snes_tiles.reshape(n_tiles, 64).astype(np.int32)
    px_r = (pixels & 0x1F).astype(np.float64)           # (n_tiles, 64)
    px_g = ((pixels >> 5) & 0x1F).astype(np.float64)
    px_b = ((pixels >> 10) & 0x1F).astype(np.float64)

    error_matrix = np.zeros((n_tiles, num_palettes), dtype=np.float64)
    for p in range(num_palettes):
        bgr = np.array(palettes[p][1:], dtype=np.int32)  # skip transparent
        pr = (bgr & 0x1F).astype(np.float64)             # (15,)
        pg = ((bgr >> 5) & 0x1F).astype(np.float64)
        pb = ((bgr >> 10) & 0x1F).astype(np.float64)
        # Distance from each pixel to each palette color: (n_tiles, 64, 15)
        dr = px_r[:, :, None] - pr[None, None, :]
        dg = px_g[:, :, None] - pg[None, None, :]
        db = px_b[:, :, None] - pb[None, None, :]
        dist = 2.0 * dr * dr + 4.0 * dg * dg + db * db
        # Min distance per pixel, then mean across tile (equal weight per pixel)
        error_matrix[:, p] = dist.min(axis=2).mean(axis=1)

    labels = tile_labels.copy()

    for iteration in range(max_iterations):
        changed = 0
        for r in range(tiles_h):
            for c in range(tiles_w):
                current_pal = labels[r, c]
                idx = r * tiles_w + c

                # Collect 4-connected neighbor palettes
                neighbor_pals = []
                if r > 0:           neighbor_pals.append(labels[r - 1, c])
                if r < tiles_h - 1: neighbor_pals.append(labels[r + 1, c])
                if c > 0:           neighbor_pals.append(labels[r, c - 1])
                if c < tiles_w - 1: neighbor_pals.append(labels[r, c + 1])

                if not neighbor_pals:
                    continue

                # Find majority neighbor palette
                counts = {}
                for p in neighbor_pals:
                    counts[p] = counts.get(p, 0) + 1
                majority_pal = max(counts, key=counts.get)
                majority_count = counts[majority_pal]

                if majority_pal == current_pal or majority_count < 2:
                    continue

                # Check error ratio from precomputed matrix
                current_error = error_matrix[idx, current_pal]
                alt_error = error_matrix[idx, majority_pal]

                if current_error > 0 and alt_error / current_error <= max_error_ratio:
                    labels[r, c] = majority_pal
                    changed += 1

        if changed == 0:
            break

    return labels


def tileaware_palette_generate(rgb5, tiles_h, tiles_w, num_palettes):
    """Generate sub-palettes using tile-aware iterative optimization.

    Converts the BGR555-quantized image into tiles and calls
    tiledpalettequant's build_palettes_tileaware() for joint tile-palette
    assignment and palette color optimization.

    Args:
        rgb5: (H, W, 3) uint8 array of 5-bit RGB components
        tiles_h, tiles_w: tile grid dimensions
        num_palettes: number of sub-palettes

    Returns:
        (sub_palettes, tile_labels):
            sub_palettes: list of num_palettes lists of 16 BGR555 values
            tile_labels: (tiles_h, tiles_w) int array of palette assignments
    """
    from tiledpalettequant import build_palettes_tileaware

    # Build BGR555 uint16 pixel grid
    bgr_pixels = (rgb5[:, :, 0].astype(np.uint16) |
                  (rgb5[:, :, 1].astype(np.uint16) << 5) |
                  (rgb5[:, :, 2].astype(np.uint16) << 10))

    # Reshape into (n_tiles, 8, 8) tiles
    snes_tiles = bgr_pixels.reshape(tiles_h, 8, tiles_w, 8).transpose(0, 2, 1, 3)
    snes_tiles = snes_tiles.reshape(-1, 8, 8)

    palettes, _indexed_tiles, tile_pal_ids = build_palettes_tileaware(
        snes_tiles,
        num_palettes=num_palettes,
        colors_per_palette=16,
        trans_color=0x0000,
    )

    tile_labels = tile_pal_ids.reshape(tiles_h, tiles_w).astype(int)

    # Spatial smoothing: reduce palette boundary artifacts in gradient regions
    tile_labels = _smooth_tile_assignments(
        tile_labels, palettes, snes_tiles, tiles_h, tiles_w)

    return palettes, tile_labels


def compute_shared_palette_tileaware(png_paths, num_palettes=PALETTES, grayscale=False):
    """Compute a shared palette using tile-aware optimization across multiple frames.

    Loads sampled frames, converts to BGR555 tiles, concatenates all tiles,
    and runs tiledpalettequant's joint optimization on the combined set.

    Args:
        png_paths: List of PNG file paths to sample from
        num_palettes: Number of sub-palettes
        grayscale: If True, convert frames to grayscale

    Returns:
        List of sub-palettes, each a list of 16 BGR555 values (color 0 = 0x0000)
    """
    from tiledpalettequant import build_palettes_tileaware

    all_tiles = []
    for path in png_paths:
        img = Image.open(path).convert('RGB')
        if grayscale:
            img = img.convert('L').convert('RGB')
        rgb = np.array(img, dtype=np.float32)
        H, W = rgb.shape[:2]
        tiles_h, tiles_w = H // 8, W // 8

        rgb5 = np.round(rgb * 31.0 / 255.0).clip(0, 31).astype(np.uint8)
        bgr_pixels = (rgb5[:, :, 0].astype(np.uint16) |
                      (rgb5[:, :, 1].astype(np.uint16) << 5) |
                      (rgb5[:, :, 2].astype(np.uint16) << 10))
        tiles = bgr_pixels.reshape(tiles_h, 8, tiles_w, 8).transpose(0, 2, 1, 3)
        tiles = tiles.reshape(-1, 8, 8)
        all_tiles.append(tiles)

    combined = np.concatenate(all_tiles, axis=0)

    palettes, _indexed_tiles, _tile_pal_ids = build_palettes_tileaware(
        combined,
        num_palettes=num_palettes,
        colors_per_palette=16,
        trans_color=0x0000,
    )

    return palettes


def encode_tiles_4bpp(pixel_indices, tile_palettes, width, height):
    """Encode pixel index grid to SNES 4BPP tile data + tilemap.

    pixel_indices: (H, W) uint8, values 0-15 (local to each tile's sub-palette)
    tile_palettes: (tiles_h, tiles_w) uint8, sub-palette number per tile
    Returns: (tile_data_bytes, tilemap_bytes)
    """
    tiles_h = height // 8
    tiles_w = width // 8

    # Reshape into tiles: (tiles_h, tiles_w, 8, 8)
    tiles = pixel_indices.reshape(tiles_h, 8, tiles_w, 8)
    tiles = tiles.transpose(0, 2, 1, 3)

    tile_dict = {}
    tile_data_list = []
    tilemap = np.zeros(tiles_h * tiles_w, dtype=np.uint16)

    for tr in range(tiles_h):
        for tc in range(tiles_w):
            tile = tiles[tr, tc]  # (8, 8) uint8

            # Encode SNES 4BPP bitplane format
            encoded = bytearray(32)
            for row in range(8):
                bp0 = bp1 = bp2 = bp3 = 0
                for px in range(8):
                    idx = int(tile[row, px])
                    bit = 7 - px
                    bp0 |= ((idx >> 0) & 1) << bit
                    bp1 |= ((idx >> 1) & 1) << bit
                    bp2 |= ((idx >> 2) & 1) << bit
                    bp3 |= ((idx >> 3) & 1) << bit
                encoded[2 * row] = bp0
                encoded[2 * row + 1] = bp1
                encoded[16 + 2 * row] = bp2
                encoded[16 + 2 * row + 1] = bp3

            encoded_bytes = bytes(encoded)
            if encoded_bytes not in tile_dict:
                tile_dict[encoded_bytes] = len(tile_data_list)
                tile_data_list.append(encoded_bytes)

            tile_idx = tile_dict[encoded_bytes]
            pal_num = int(tile_palettes[tr, tc])
            tilemap[tr * tiles_w + tc] = tile_idx | (pal_num << 10)

    tile_data = b''.join(tile_data_list)
    tilemap_bytes = tilemap.astype('<u2').tobytes()
    return tile_data, tilemap_bytes


def per_tile_palette_optimize(png_path, pal_file, tile_file, map_file,
                              num_palettes=PALETTES,
                              dither_method=DEFAULT_DITHER,
                              grayscale=False, shared_palette=None,
                              palette_method='kmeans'):
    """Convert full-color PNG to SNES tiles with sub-palettes + dithering.

    Algorithm:
    1. Load PNG, quantize pixels to BGR555 color space
    2. Cluster 8x8 tiles into groups by mean color (K-means)
    3. Build 15-color sub-palettes per cluster (color 0 reserved = $0000)
    4. Build BGR555 lookup tables for O(1) nearest-color per sub-palette
    5. Dithering across entire image (none, ordered, or Floyd-Steinberg)
    6. Encode to SNES 4BPP tiles + tilemap + palette

    Args:
        num_palettes: Number of sub-palettes (default: 8)
        dither_method: DITHER_NONE, DITHER_ORDERED, or DITHER_FLOYD_STEINBERG
        grayscale: If True, convert image to grayscale before processing
        shared_palette: Pre-computed sub-palettes (list of lists of BGR555 values).
            If provided, skip per-frame palette building and use these instead.
    """
    img = Image.open(png_path).convert('RGB')
    if grayscale:
        img = img.convert('L').convert('RGB')
    rgb = np.array(img, dtype=np.float32)  # (H, W, 3)
    H, W = rgb.shape[:2]
    tiles_h, tiles_w = H // 8, W // 8

    # Quantize to BGR555 (what SNES can actually display)
    rgb5 = np.round(rgb * 31.0 / 255.0).clip(0, 31).astype(np.uint8)  # (H, W, 3) 5-bit
    rgb_q = rgb5.astype(np.float32) * (255.0 / 31.0)  # back to float for processing

    # Build sub-palettes and tile-to-palette assignments
    sub_palettes = []
    sub_palette_rgb = np.zeros((num_palettes, 16, 3), dtype=np.float32)

    if shared_palette is not None:
        # Shared palette takes priority over palette_method — assignment only
        # Per-tile mean colors for clustering (tile assignment)
        tile_blocks = rgb_q.reshape(tiles_h, 8, tiles_w, 8, 3).transpose(0, 2, 1, 3, 4)
        tile_means = tile_blocks.mean(axis=(2, 3))
        flat_means = tile_means.reshape(-1, 3)
        labels, _centers = simple_kmeans(flat_means, num_palettes)
        tile_labels = labels.reshape(tiles_h, tiles_w)

        for p in range(num_palettes):
            if p < len(shared_palette):
                sub_palettes.append(list(shared_palette[p]))
            else:
                sub_palettes.append([0] * 16)
            for ci, bgr in enumerate(sub_palettes[p]):
                sub_palette_rgb[p, ci] = bgr555_to_rgb_float(bgr)

    elif palette_method == 'tileaware':
        # Tile-aware joint optimization of palette colors + tile assignment
        sub_palettes, tile_labels = tileaware_palette_generate(
            rgb5, tiles_h, tiles_w, num_palettes)
        for p in range(num_palettes):
            for ci, bgr in enumerate(sub_palettes[p]):
                sub_palette_rgb[p, ci] = bgr555_to_rgb_float(bgr)

    else:
        # K-means: cluster tiles by mean color, then reduce colors per cluster
        tile_blocks = rgb_q.reshape(tiles_h, 8, tiles_w, 8, 3).transpose(0, 2, 1, 3, 4)
        tile_means = tile_blocks.mean(axis=(2, 3))
        flat_means = tile_means.reshape(-1, 3)
        labels, _centers = simple_kmeans(flat_means, num_palettes)
        tile_labels = labels.reshape(tiles_h, tiles_w)

        for p in range(num_palettes):
            mask = tile_labels == p
            positions = np.argwhere(mask)

            bgr555_set = set()
            for tr, tc in positions:
                block = rgb5[tr * 8:(tr + 1) * 8, tc * 8:(tc + 1) * 8]  # (8,8,3) uint8
                for y in range(8):
                    for x in range(8):
                        r5, g5, b5 = int(block[y, x, 0]), int(block[y, x, 1]), int(block[y, x, 2])
                        bgr = r5 | (g5 << 5) | (b5 << 10)
                        bgr555_set.add(bgr)

            bgr555_set.discard(0)  # color 0 is reserved (transparent/black)

            if len(bgr555_set) <= 15:
                colors = sorted(bgr555_set)
            else:
                # K-means reduction to 15 representative colors
                unique_list = sorted(bgr555_set)
                unique_rgb = np.array([bgr555_to_rgb_float(c) for c in unique_list], dtype=np.float32)
                clabels, ccenters = simple_kmeans(unique_rgb, 15)
                colors = []
                for c in ccenters:
                    colors.append(rgb_to_bgr555(int(round(c[0])), int(round(c[1])), int(round(c[2]))))
                # Deduplicate (rounding might produce duplicates)
                colors = sorted(set(colors))
                if 0 in colors:
                    colors.remove(0)
                colors = colors[:15]

            full_palette = [0] + colors
            while len(full_palette) < 16:
                full_palette.append(0)
            sub_palettes.append(full_palette)

            for ci, bgr in enumerate(full_palette):
                sub_palette_rgb[p, ci] = bgr555_to_rgb_float(bgr)

    # Build BGR555 LUTs for O(1) nearest-color lookup per sub-palette
    all_bgr = np.arange(32768, dtype=np.uint16)
    all_r = (all_bgr & 0x1F).astype(np.float32) * (255.0 / 31.0)
    all_g = ((all_bgr >> 5) & 0x1F).astype(np.float32) * (255.0 / 31.0)
    all_b = ((all_bgr >> 10) & 0x1F).astype(np.float32) * (255.0 / 31.0)
    all_rgb_lut = np.stack([all_r, all_g, all_b], axis=1)  # (32768, 3)

    lut_index = np.zeros((num_palettes, 32768), dtype=np.uint8)
    lut_rgb = np.zeros((num_palettes, 32768, 3), dtype=np.float32)

    for p in range(num_palettes):
        pal_rgb = sub_palette_rgb[p]  # (16, 3)
        diffs = all_rgb_lut[:, None, :] - pal_rgb[None, :, :]  # (32768, 16, 3)
        dists = np.sum(diffs * diffs, axis=2)  # (32768, 16)
        nearest = np.argmin(dists, axis=1)
        lut_index[p] = nearest.astype(np.uint8)
        lut_rgb[p] = pal_rgb[nearest]

    # Dithering dispatch
    output = np.zeros((H, W), dtype=np.uint8)

    if dither_method == DITHER_NONE:
        # Vectorized nearest-color lookup, no error diffusion
        bgr_grid = (rgb5[:, :, 0].astype(np.uint16) |
                    (rgb5[:, :, 1].astype(np.uint16) << 5) |
                    (rgb5[:, :, 2].astype(np.uint16) << 10))
        tile_pal_map = np.repeat(np.repeat(tile_labels, 8, axis=0), 8, axis=1)
        for p in range(num_palettes):
            mask = tile_pal_map == p
            output[mask] = lut_index[p][bgr_grid[mask]]

    elif dither_method == DITHER_ORDERED:
        # Ordered (Bayer) dithering: add threshold matrix, clamp, quantize
        bayer_tiled = np.tile(_BAYER_4x4_SCALED,
                              ((H + 3) // 4, (W + 3) // 4))[:H, :W]
        rgb_dithered = rgb_q.copy()
        for c in range(3):
            rgb_dithered[:, :, c] = np.clip(rgb_dithered[:, :, c] + bayer_tiled,
                                            0, 255)
        rgb5_d = np.round(rgb_dithered * 31.0 / 255.0).clip(0, 31).astype(np.uint8)
        bgr_grid = (rgb5_d[:, :, 0].astype(np.uint16) |
                    (rgb5_d[:, :, 1].astype(np.uint16) << 5) |
                    (rgb5_d[:, :, 2].astype(np.uint16) << 10))
        tile_pal_map = np.repeat(np.repeat(tile_labels, 8, axis=0), 8, axis=1)
        for p in range(num_palettes):
            mask = tile_pal_map == p
            output[mask] = lut_index[p][bgr_grid[mask]]

    else:
        # Floyd-Steinberg error diffusion (default)
        # Convert numpy arrays to Python lists for fast element access in the tight loop
        lut_idx_lists = [lut_index[p].tolist() for p in range(num_palettes)]
        lut_r_lists = [lut_rgb[p, :, 0].tolist() for p in range(num_palettes)]
        lut_g_lists = [lut_rgb[p, :, 1].tolist() for p in range(num_palettes)]
        lut_b_lists = [lut_rgb[p, :, 2].tolist() for p in range(num_palettes)]
        tile_labels_list = tile_labels.tolist()

        # Error buffer: padded +1 col on each side, +1 row on bottom
        err_r = [[0.0] * (W + 2) for _ in range(H + 1)]
        err_g = [[0.0] * (W + 2) for _ in range(H + 1)]
        err_b = [[0.0] * (W + 2) for _ in range(H + 1)]

        # Pre-extract source image channels as Python lists
        src_r = rgb_q[:, :, 0].tolist()
        src_g = rgb_q[:, :, 1].tolist()
        src_b = rgb_q[:, :, 2].tolist()

        for y in range(H):
            xp1 = 1  # error buffer x offset (pixel x=0 maps to err index 1)
            tr = y >> 3  # y // 8
            er_row = err_r[y]
            eg_row = err_g[y]
            eb_row = err_b[y]
            er_next = err_r[y + 1]
            eg_next = err_g[y + 1]
            eb_next = err_b[y + 1]
            sr_row = src_r[y]
            sg_row = src_g[y]
            sb_row = src_b[y]

            for x in range(W):
                ex = x + xp1  # error buffer index for this pixel

                # Accumulated color = original + diffused error
                ar = sr_row[x] + er_row[ex]
                ag = sg_row[x] + eg_row[ex]
                ab = sb_row[x] + eb_row[ex]

                # Clamp to [0, 255]
                if ar < 0.0: ar = 0.0
                elif ar > 255.0: ar = 255.0
                if ag < 0.0: ag = 0.0
                elif ag > 255.0: ag = 255.0
                if ab < 0.0: ab = 0.0
                elif ab > 255.0: ab = 255.0

                # Quantize accumulated color to BGR555 for LUT lookup
                r5 = int(ar * 31.0 / 255.0 + 0.5)
                g5 = int(ag * 31.0 / 255.0 + 0.5)
                b5 = int(ab * 31.0 / 255.0 + 0.5)
                if r5 > 31: r5 = 31
                if g5 > 31: g5 = 31
                if b5 > 31: b5 = 31
                bgr = r5 | (g5 << 5) | (b5 << 10)

                # Look up tile's sub-palette
                p = tile_labels_list[tr][x >> 3]

                # Nearest color via LUT
                idx = lut_idx_lists[p][bgr]
                nr = lut_r_lists[p][bgr]
                ng = lut_g_lists[p][bgr]
                nb = lut_b_lists[p][bgr]

                output[y, x] = idx

                # Quantization error
                qr = ar - nr
                qg = ag - ng
                qb = ab - nb

                # Distribute error (Floyd-Steinberg: 7/16, 3/16, 5/16, 1/16)
                # Right (x+1)
                er_row[ex + 1] += qr * 0.4375
                eg_row[ex + 1] += qg * 0.4375
                eb_row[ex + 1] += qb * 0.4375
                # Bottom-left (x-1, y+1)
                er_next[ex - 1] += qr * 0.1875
                eg_next[ex - 1] += qg * 0.1875
                eb_next[ex - 1] += qb * 0.1875
                # Bottom (x, y+1)
                er_next[ex] += qr * 0.3125
                eg_next[ex] += qg * 0.3125
                eb_next[ex] += qb * 0.3125
                # Bottom-right (x+1, y+1)
                er_next[ex + 1] += qr * 0.0625
                eg_next[ex + 1] += qg * 0.0625
                eb_next[ex + 1] += qb * 0.0625

    # Encode to SNES format
    tile_data, tilemap_data = encode_tiles_4bpp(output, tile_labels.astype(np.uint8), W, H)

    # Write palette: num_palettes sub-palettes × 16 colors × 2 bytes
    pal_bytes = bytearray(num_palettes * 16 * 2)
    for p in range(num_palettes):
        for ci in range(16):
            bgr = sub_palettes[p][ci]
            offset = (p * 16 + ci) * 2
            pal_bytes[offset] = bgr & 0xFF
            pal_bytes[offset + 1] = (bgr >> 8) & 0xFF

    with open(pal_file, 'wb') as f:
        f.write(pal_bytes)
    with open(tile_file, 'wb') as f:
        f.write(tile_data)
    with open(map_file, 'wb') as f:
        f.write(tilemap_data)


def decode_tiles_4bpp_rgb(tiles_raw, palette_rgb, tile_pal_offsets=None):
    """Decode SNES 4BPP tiles to RGB values using the frame's actual palette.

    tiles_raw: (N, 32) uint8 array of raw SNES 4BPP tile data
    palette_rgb: (C, 3) float32 array of RGB values (C=16 single, C=128 multi)
    tile_pal_offsets: optional (N,) uint16, per-tile palette base offset
                      (palette_num * 16). If None, all tiles use palette 0.
    Returns: (N, 192) float32 array (64 pixels x 3 RGB channels)

    SNES 4BPP tile format (32 bytes per 8x8 tile):
      Bytes  0-15: bitplanes 0,1 interleaved by row (2 bytes/row x 8 rows)
      Bytes 16-31: bitplanes 2,3 interleaved by row (2 bytes/row x 8 rows)
    Each pixel's 4-bit color index = bp0 | (bp1<<1) | (bp2<<2) | (bp3<<3)
    """
    N = tiles_raw.shape[0]
    pixel_indices = np.zeros((N, 8, 8), dtype=np.uint8)
    for row in range(8):
        bp0 = tiles_raw[:, 2 * row].astype(np.uint16)
        bp1 = tiles_raw[:, 2 * row + 1].astype(np.uint16)
        bp2 = tiles_raw[:, 16 + 2 * row].astype(np.uint16)
        bp3 = tiles_raw[:, 16 + 2 * row + 1].astype(np.uint16)
        for px in range(8):
            bit = 7 - px
            pixel_indices[:, row, px] = (
                ((bp0 >> bit) & 1) |
                (((bp1 >> bit) & 1) << 1) |
                (((bp2 >> bit) & 1) << 2) |
                (((bp3 >> bit) & 1) << 3)
            ).astype(np.uint8)
    flat_indices = pixel_indices.reshape(N, 64)

    if tile_pal_offsets is not None:
        # Offset indices by per-tile sub-palette base for multi-palette lookup
        flat_indices = flat_indices.astype(np.uint16) + tile_pal_offsets[:, None]

    rgb = palette_rgb[flat_indices]  # (N, 64, 3)
    return rgb.reshape(N, 192)


def reduce_tiles(tile_file, tilemap_file, palette_file, max_tiles=MAX_TILES):
    """Reduce tile count to max_tiles using global greedy merge in RGB color space.

    SNES VRAM budget is $4000 bytes = 512 tiles at 4BPP. Video frames at
    256x160 can have up to 640 unique tiles. This function finds the most
    similar tile pairs across the ENTIRE image and merges them, distributing
    quality loss evenly rather than concentrating it in the bottom rows.

    Uses L2 distance on actual RGB color values (decoded through the frame's
    palette) for accurate visual similarity matching. Only merges tiles that
    share the same sub-palette to preserve color accuracy.
    """
    bytes_per_tile = 8 * BPP  # 32 for 4BPP

    with open(tile_file, 'rb') as f:
        tile_data = f.read()
    num_tiles = len(tile_data) // bytes_per_tile
    if num_tiles <= max_tiles:
        return  # nothing to do

    tiles = np.frombuffer(tile_data, dtype=np.uint8).reshape(num_tiles, bytes_per_tile)

    palette_rgb = read_snes_palette(palette_file)

    # Read tilemap to get per-tile palette assignment
    with open(tilemap_file, 'rb') as f:
        tilemap_raw = f.read()
    tilemap_arr = np.frombuffer(tilemap_raw, dtype=np.uint16).copy()
    tm_tile_indices = tilemap_arr & 0x3ff
    tm_pal_bits = (tilemap_arr >> 10) & 0x7

    # Determine palette for each unique tile (from first tilemap reference)
    tile_palettes = np.zeros(num_tiles, dtype=np.uint8)
    seen = np.zeros(num_tiles, dtype=bool)
    for i in range(len(tilemap_arr)):
        ti = int(tm_tile_indices[i])
        if ti < num_tiles and not seen[ti]:
            tile_palettes[ti] = tm_pal_bits[i]
            seen[ti] = True

    # Decode tiles to RGB using per-tile sub-palettes
    tile_pal_offsets = tile_palettes.astype(np.uint16) * 16
    pixels = decode_tiles_4bpp_rgb(tiles, palette_rgb, tile_pal_offsets)  # (N, 192)

    # Compute pairwise L2 squared distance matrix
    sq_norms = np.sum(pixels * pixels, axis=1)
    dot_products = pixels @ pixels.T
    dist = sq_norms[:, None] + sq_norms[None, :] - 2 * dot_products

    # Block cross-palette merges (set distance to infinity)
    same_pal = tile_palettes[:, None] == tile_palettes[None, :]
    dist = np.where(same_pal, dist, np.inf)

    # Get all unique pairs (i < j) sorted by distance
    rows_idx, cols_idx = np.triu_indices(num_tiles, k=1)
    pair_dists = dist[rows_idx, cols_idx]
    sort_order = np.argsort(pair_dists)

    # Greedy merge: iterate through closest pairs, merge when both alive
    to_remove = num_tiles - max_tiles
    alive = set(range(num_tiles))
    merge_target = list(range(num_tiles))
    removed = 0

    for idx in sort_order:
        if removed >= to_remove:
            break
        d = pair_dists[sort_order[removed]] if removed < len(sort_order) else 0
        i = int(rows_idx[idx])
        j = int(cols_idx[idx])
        if i not in alive or j not in alive:
            continue
        if not np.isfinite(dist[i, j]):
            break  # only inf-distance pairs remain
        alive.discard(j)
        merge_target[j] = i
        removed += 1

    # Resolve transitive merges
    for idx in range(num_tiles):
        target = merge_target[idx]
        while merge_target[target] != target:
            target = merge_target[target]
        merge_target[idx] = target

    # Re-index surviving tiles
    alive_sorted = sorted(alive)
    reindex = {}
    for new_i, old_i in enumerate(alive_sorted):
        reindex[old_i] = new_i

    final_remap = np.array([reindex[merge_target[i]] for i in range(num_tiles)],
                           dtype=np.uint16)

    # Update tilemap (preserve palette/flip flags)
    tile_indices = tilemap_arr & 0x3ff
    flags = tilemap_arr & 0xfc00
    new_indices = final_remap[tile_indices]
    tilemap_arr = flags | new_indices

    # Write reduced tiles
    new_tile_data = tiles[alive_sorted].tobytes()
    with open(tile_file, 'wb') as f:
        f.write(new_tile_data)

    with open(tilemap_file, 'wb') as f:
        f.write(tilemap_arr.tobytes())

def convert_frame_superfamiconv(png_path, num_palettes=PALETTES,
                                dither_method=DEFAULT_DITHER,
                                max_tiles=MAX_TILES, grayscale=False,
                                shared_palette=None,
                                palette_method='kmeans'):
    """Convert one PNG frame to SNES tiles/tilemap/palette.

    Uses per-tile sub-palette optimization with configurable dithering
    for smooth gradients and high color fidelity.
    """
    base = png_path[:-4]  # Remove .png
    pal_file = base + '.palette'
    tile_file = base + '.tiles'
    map_file = base + '.tilemap'

    try:
        per_tile_palette_optimize(png_path, pal_file, tile_file, map_file,
                                  num_palettes=num_palettes,
                                  dither_method=dither_method,
                                  grayscale=grayscale,
                                  shared_palette=shared_palette,
                                  palette_method=palette_method)
    except Exception as e:
        return False, str(e)

    # Reduce tiles to fit in VRAM buffer
    reduce_tiles(tile_file, map_file, pal_file, max_tiles=max_tiles)

    # Pad tilemap to 32x20 standard size
    pad_tilemap(map_file)

    return True, ""

def convert_chapter_frames(chapter_dir, max_workers=4, num_palettes=PALETTES,
                           dither_method=DEFAULT_DITHER, max_tiles=MAX_TILES,
                           grayscale=False, shared_palette_enabled=False,
                           palette_method='kmeans'):
    """Convert all PNG frames in a chapter directory to SNES tiles."""
    pngs = sorted(glob.glob(os.path.join(chapter_dir, "*.gfx_video.png")))
    if not pngs:
        return 0

    # Compute shared palette across chapter frames if enabled
    shared_pal = None
    if shared_palette_enabled:
        # Sample up to 20 evenly-spaced frames for palette computation
        sample_count = min(20, len(pngs))
        if sample_count > 0:
            step = max(1, len(pngs) // sample_count)
            sample_paths = pngs[::step][:sample_count]
            if palette_method == 'tileaware':
                shared_pal = compute_shared_palette_tileaware(
                    sample_paths, num_palettes=num_palettes, grayscale=grayscale)
            else:
                shared_pal = compute_shared_palette(
                    sample_paths, num_palettes=num_palettes, grayscale=grayscale)

    converted = 0
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(convert_frame_superfamiconv, p,
                                   num_palettes=num_palettes,
                                   dither_method=dither_method,
                                   max_tiles=max_tiles,
                                   grayscale=grayscale,
                                   shared_palette=shared_pal,
                                   palette_method=palette_method): p for p in pngs}
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
    parser.add_argument('--content-root', type=str, default=DEFAULT_CONTENT_ROOT,
                        help='Path to Daphne content directory (default: %(default)s)')
    parser.add_argument('--dither', type=str, default=DEFAULT_DITHER,
                        choices=[DITHER_NONE, DITHER_FLOYD_STEINBERG, DITHER_ORDERED],
                        help='Dithering method (default: %(default)s)')
    parser.add_argument('--palettes', type=int, default=PALETTES,
                        help='Number of sub-palettes per frame (default: %(default)s)')
    parser.add_argument('--max-tiles', type=int, default=MAX_TILES,
                        help='Maximum tiles per frame (default: %(default)s)')
    parser.add_argument('--grayscale', action='store_true',
                        help='Convert frames to grayscale before processing')
    parser.add_argument('--shared-palette', action='store_true',
                        help='Use shared palette across all frames in each chapter')
    parser.add_argument('--palette-method', type=str, default='tileaware',
                        choices=['kmeans', 'tileaware'],
                        help='Palette optimization method (default: %(default)s)')
    parser.add_argument('--scale-mode', type=str, default=SCALE_STRETCH,
                        choices=[SCALE_STRETCH, SCALE_FIT, SCALE_CROP],
                        help='Frame scaling mode (default: %(default)s)')
    parser.add_argument('--aspect-ratio', type=str, default=None,
                        help='Aspect ratio override for fit/crop modes (e.g. 16:9)')
    parser.add_argument('--scene', type=str, default=None,
                        choices=list(SCENE_PREFIXES.keys()),
                        help='Process only chapters belonging to a specific scene')
    args = parser.parse_args()

    # Resolve scene filter to chapter prefix
    scene_prefix = None
    if args.scene:
        scene_prefix = SCENE_PREFIXES.get(args.scene)
        if not scene_prefix:
            print(f"ERROR: Unknown scene '{args.scene}'")
            sys.exit(1)

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
    print(f"Dithering:    {args.dither}")
    print(f"Palette opt:  {args.palette_method}")
    print(f"Palettes:     {args.palettes}")
    print(f"Max tiles:    {args.max_tiles}")
    print(f"Scale mode:   {args.scale_mode}")
    if args.aspect_ratio:
        print(f"Aspect ratio: {args.aspect_ratio}")
    if args.grayscale:
        print(f"Grayscale:    Yes")
    if args.shared_palette:
        print(f"Shared pal:   Yes (per-chapter)")
    if args.scene:
        print(f"Scene filter: {args.scene} (prefix: {scene_prefix})")

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
        if scene_prefix and not chapter_name.startswith(scene_prefix):
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

            n = extract_chapter_frames_from_segment(info, cdir, daphne_segments,
                                                     scale_mode=args.scale_mode,
                                                     aspect_ratio=args.aspect_ratio)
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
        final_dir = str(DISTRIBUTION)
        os.makedirs(final_dir, exist_ok=True)
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

    # Phase 1d: Copy dragon roar PCM (track 900) to build and distribution directories
    if os.path.exists(DRAGON_ROAR_PCM):
        build_dir = os.path.dirname(OUTPUT_MSU)
        final_dir = str(DISTRIBUTION)
        os.makedirs(final_dir, exist_ok=True)
        roar_name = os.path.basename(DRAGON_ROAR_PCM)
        shutil.copy2(DRAGON_ROAR_PCM, os.path.join(build_dir, roar_name))
        shutil.copy2(DRAGON_ROAR_PCM, os.path.join(final_dir, roar_name))
        print(f"Copied dragon roar PCM (track 900) to build + distribution directories\n")
    else:
        print(f"WARNING: Dragon roar PCM not found at {DRAGON_ROAR_PCM}\n"
              f"  Run: python3 tools/convert_roar_pcm.py\n")


    # Phase 2: Convert frames to SNES tiles
    total_converted = 0
    if not args.skip_convert:
        print(f"--- Phase 2: Converting frames to SNES tiles ({args.dither} dither, {args.workers} workers) ---")
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

            n = convert_chapter_frames(cdir, max_workers=args.workers,
                                       num_palettes=args.palettes,
                                       dither_method=args.dither,
                                       max_tiles=args.max_tiles,
                                       grayscale=args.grayscale,
                                       shared_palette_enabled=args.shared_palette,
                                       palette_method=args.palette_method)
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

            # Copy to distribution folder
            final_path = os.path.normpath(FINAL_MSU_PATH)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            shutil.copy2(OUTPUT_MSU, final_path)
            print(f"Copied to: {final_path}")
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
