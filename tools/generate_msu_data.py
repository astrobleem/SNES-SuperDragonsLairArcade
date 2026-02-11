#!/usr/bin/env python3
"""
generate_msu_data.py - Generate MSU-1 .msu video data file from dl_arcade.mp4

Pipeline:
1. Parse chapter XMLs for timing info
2. Extract video frames from MP4 per chapter (ffmpeg with CUDA GPU accel)
3. Convert frames to SNES tiles/tilemap/palette (superfamiconv)
4. Package into .msu file (msu1blockwriter.py)

Usage (from project root, in WSL or Windows):
  python3 tools/generate_msu_data.py [--workers N] [--chapter NAME] [--skip-extract] [--skip-convert] [--skip-package]
"""

import os
import sys
import xml.dom.minidom
import subprocess
import concurrent.futures
import time
import glob
import argparse
import shutil

# ---------- Configuration ----------
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_DIR = os.path.join(PROJECT_DIR, 'data', 'events')
CHAPTERS_DIR = os.path.join(PROJECT_DIR, 'data', 'chapters')
VIDEO_FILE = os.path.join(PROJECT_DIR, 'data', 'videos', 'dl_arcade.mp4')
TOOLS_DIR = os.path.join(PROJECT_DIR, 'tools')
SUPERFAMICONV = os.path.join(TOOLS_DIR, 'superfamiconv', 'superfamiconv.exe')
MSU_WRITER = os.path.join(TOOLS_DIR, 'msu1blockwriter.py')

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

OUTPUT_MSU = os.path.join(PROJECT_DIR, 'build', 'SuperDragonsLairArcade.msu')
FINAL_MSU_PATH = os.path.join(PROJECT_DIR, '..', 'SuperDragonsLairArcade.sfc', 'SuperDragonsLairArcade.msu')

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
    timestart = parse_time(timeline.getElementsByTagName('timestart')[0])
    timeend = parse_time(timeline.getElementsByTagName('timeend')[0])
    return {
        'name': chapter.getAttribute('name'),
        'timestart_ms': timestart,
        'timeend_ms': timeend,
        'duration_ms': max(0, timeend - timestart),
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

def extract_chapter_frames(chapter_info, chapter_dir, use_gpu=True):
    """Extract video frames for one chapter using ffmpeg."""
    if chapter_info['duration_ms'] <= 0:
        return 0

    ts = format_time(chapter_info['timestart_ms'])
    dur = format_time(chapter_info['duration_ms'])

    ffmpeg_path, needs_win_paths, has_cuda = get_ffmpeg()

    if needs_win_paths:
        # Windows ffmpeg needs Windows paths
        out_pattern = to_win_path(os.path.join(chapter_dir, "video_%06d.gfx_video.png"))
        video_path = to_win_path(VIDEO_FILE)
    else:
        out_pattern = os.path.join(chapter_dir, "video_%06d.gfx_video.png")
        video_path = VIDEO_FILE

    filter_str = (
        f'scale={FRAME_WIDTH}:{FRAME_HEIGHT}[s];'
        f'[s]split[s1][s2];'
        f'[s1]palettegen=max_colors={MAX_COLORS}:stats_mode=single[p];'
        f'[s2][p]paletteuse=new=1:dither=bayer'
    )

    cmd = [ffmpeg_path, '-y']
    if use_gpu and has_cuda:
        cmd += ['-hwaccel', 'cuda']
    cmd += [
        '-ss', ts,
        '-t', dur,
        '-i', video_path,
        '-filter_complex', filter_str,
        '-f', 'image2',
        out_pattern
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            if use_gpu:
                # Fallback to CPU
                return extract_chapter_frames(chapter_info, chapter_dir, use_gpu=False)
            return -1
    except subprocess.TimeoutExpired:
        return -1

    return len(glob.glob(os.path.join(chapter_dir, "video_*.gfx_video.png")))

# ---------- Tile Conversion ----------
def pad_tilemap(tilemap_file):
    """Pad tilemap to 32x32 (2048 bytes) for SNES compatibility."""
    with open(tilemap_file, 'rb') as f:
        data = f.read()
    if len(data) < TILEMAP_TARGET_SIZE:
        with open(tilemap_file, 'wb') as f:
            f.write(data)
            f.write(b'\x00' * (TILEMAP_TARGET_SIZE - len(data)))

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

    # 2. Tile conversion (limit to MAX_TILES to fit in VRAM buffer)
    r = subprocess.run([sfc, 'tiles', '-i', rel_png, '-p', rel_pal, '-d', rel_tile, '-B', str(BPP),
                        '-T', str(MAX_TILES)], **run_kw)
    if r.returncode != 0:
        return False, f"tiles: {r.stderr.strip()}"

    # 3. Tilemap generation (same tile limit for consistent mapping)
    r = subprocess.run([sfc, 'map', '-i', rel_png, '-p', rel_pal, '-t', rel_tile, '-d', rel_map, '-B', str(BPP),
                        '-T', str(MAX_TILES)], **run_kw)
    if r.returncode != 0:
        return False, f"map: {r.stderr.strip()}"

    # 4. Pad tilemap to 32x32
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
    parser.add_argument('--clean', action='store_true',
                        help='Remove existing video frames before extraction')
    args = parser.parse_args()

    print("=" * 60)
    print("MSU-1 Video Data Generator")
    print("=" * 60)
    print(f"Video source: {VIDEO_FILE}")
    print(f"Chapters dir: {CHAPTERS_DIR}")
    print(f"Output MSU:   {OUTPUT_MSU}")
    print(f"Workers:      {args.workers}")

    ffmpeg_path, needs_win_paths, has_cuda = get_ffmpeg()
    print(f"ffmpeg:       {ffmpeg_path}")
    print(f"CUDA GPU:     {'Yes' if has_cuda else 'No (CPU fallback)'}")
    print(f"superfamiconv: {SUPERFAMICONV}")
    print()

    if not os.path.exists(VIDEO_FILE):
        print(f"ERROR: Video file not found: {VIDEO_FILE}")
        sys.exit(1)

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

    # Phase 1: Extract video frames
    total_frames = 0
    extract_errors = 0
    if not args.skip_extract:
        print("--- Phase 1: Extracting video frames (ffmpeg + CUDA) ---")
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

            n = extract_chapter_frames(info, cdir)
            if n < 0:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: EXTRACTION ERROR")
                extract_errors += 1
            elif n == 0:
                print(f"[{i+1:3d}/{len(chapters)}] {name}: 0 frames")
            else:
                total_frames += n
                print(f"[{i+1:3d}/{len(chapters)}] {name}: {n} frames extracted")

        extract_elapsed = time.time() - extract_start
        print(f"\nExtraction done: {total_frames} frames in {extract_elapsed:.1f}s "
              f"({extract_errors} errors)\n")
    else:
        for name, cdir, xml in chapters:
            total_frames += len(glob.glob(os.path.join(cdir, "*.gfx_video.png")))
        print(f"Skipping extraction. {total_frames} existing PNG frames found.\n")

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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
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
    print(f"  Tiles converted:  {total_converted}")
    if os.path.exists(OUTPUT_MSU):
        print(f"  MSU file size:    {os.path.getsize(OUTPUT_MSU) / 1024 / 1024:.1f} MB")
    print("=" * 60)


if __name__ == '__main__':
    main()
