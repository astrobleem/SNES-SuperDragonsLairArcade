#!/usr/bin/env bash
#
# build_dist.sh - Full distribution build pipeline
#
# Builds the ROM, generates MSU-1 video/audio data, preserves extracted
# video frames, and produces a complete distribution folder.
#
# Usage (from WSL):
#   cd /mnt/e/gh/SNES-SuperDragonsLairArcade
#   bash tools/build_dist.sh [--skip-extract] [--skip-convert] [--workers N]
#
# Output:
#   distribution/  (distribution folder)
#     SuperDragonsLairArcade.sfc       (ROM)
#     SuperDragonsLairArcade.msu       (video data, ~568 MB)
#     SuperDragonsLairArcade-*.pcm     (audio tracks, ~476 files)
#     manifest.xml                     (bsnes/higan track list)
#
# Preserved frames:
#   data/videos/frames/               (all extracted PNGs, survives make clean)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$PROJECT_DIR/distribution"
FRAMES_ARCHIVE="$PROJECT_DIR/data/videos/frames"
WORKERS=8
SKIP_EXTRACT=""
SKIP_CONVERT=""
SKIP_ROM=""
CLEAN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --workers) WORKERS="$2"; shift 2 ;;
        --skip-extract) SKIP_EXTRACT="--skip-extract"; shift ;;
        --skip-convert) SKIP_CONVERT="--skip-convert"; shift ;;
        --skip-rom) SKIP_ROM=1; shift ;;
        --clean) CLEAN="--clean"; shift ;;
        -h|--help)
            echo "Usage: $0 [--workers N] [--skip-extract] [--skip-convert] [--skip-rom] [--clean]"
            echo ""
            echo "  --workers N       Tile conversion workers (default: 8)"
            echo "  --skip-extract    Skip ffmpeg frame extraction (use cached PNGs)"
            echo "  --skip-convert    Skip superfamiconv tile conversion (use cached tiles)"
            echo "  --skip-rom        Skip make clean && make (use existing ROM)"
            echo "  --clean           Force re-extraction of frames and audio"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_DIR"

echo "============================================================"
echo "  Super Dragon's Lair Arcade - Full Distribution Build"
echo "============================================================"
echo "  Project:  $PROJECT_DIR"
echo "  Dist:     $DIST_DIR"
echo "  Workers:  $WORKERS"
echo ""

# ---- Step 1: Build ROM ----
if [[ -z "$SKIP_ROM" ]]; then
    echo "--- Step 1: Building ROM (make clean && make) ---"
    echo "  WARNING: make clean deletes data/chapters/"
    echo ""
    make clean && make
    echo ""
    echo "  ROM built: build/SuperDragonsLairArcade.sfc"
    echo ""
else
    echo "--- Step 1: Skipping ROM build (--skip-rom) ---"
    if [[ ! -f build/SuperDragonsLairArcade.sfc ]]; then
        echo "  ERROR: ROM not found at build/SuperDragonsLairArcade.sfc"
        exit 1
    fi
    echo ""
fi

# ---- Step 2: Generate MSU-1 video + audio data ----
echo "--- Step 2: Generating MSU-1 video and audio data ---"
echo "  This extracts video frames, audio, converts tiles, and packages .msu"
echo ""

MSU_ARGS="--workers $WORKERS"
[[ -n "$SKIP_EXTRACT" ]] && MSU_ARGS="$MSU_ARGS --skip-extract"
[[ -n "$SKIP_CONVERT" ]] && MSU_ARGS="$MSU_ARGS --skip-convert"
[[ -n "$CLEAN" ]] && MSU_ARGS="$MSU_ARGS --clean"

python3 tools/generate_msu_data.py $MSU_ARGS
echo ""

# ---- Step 3: Preserve video frames ----
echo "--- Step 3: Preserving extracted video frames ---"
echo "  Copying PNGs to $FRAMES_ARCHIVE"
mkdir -p "$FRAMES_ARCHIVE"

frame_count=0
for chapter_dir in data/chapters/*/; do
    chapter_name="$(basename "$chapter_dir")"
    pngs=( "$chapter_dir"video_*.gfx_video.png 2>/dev/null ) || true
    if [[ -e "${pngs[0]:-}" ]]; then
        chapter_frame_dir="$FRAMES_ARCHIVE/$chapter_name"
        mkdir -p "$chapter_frame_dir"
        cp "$chapter_dir"video_*.gfx_video.png "$chapter_frame_dir/"
        frame_count=$((frame_count + ${#pngs[@]}))
    fi
done

echo "  Preserved $frame_count frames across $(ls -d "$FRAMES_ARCHIVE"/*/ 2>/dev/null | wc -l) chapters"
echo ""

# ---- Step 4: Generate manifest.xml ----
echo "--- Step 4: Generating manifest.xml ---"
python3 tools/generate_manifest.py "$DIST_DIR"
echo ""

# ---- Step 5: Verify distribution ----
echo "--- Step 5: Distribution summary ---"
echo ""

sfc_file="$DIST_DIR/SuperDragonsLairArcade.sfc"
msu_file="$DIST_DIR/SuperDragonsLairArcade.msu"
manifest_file="$DIST_DIR/manifest.xml"
pcm_count=$(ls "$DIST_DIR"/SuperDragonsLairArcade-*.pcm 2>/dev/null | wc -l)

if [[ -f "$sfc_file" ]]; then
    sfc_size=$(du -h "$sfc_file" | cut -f1)
    echo "  ROM:      $sfc_file ($sfc_size)"
else
    echo "  ROM:      MISSING!"
fi

if [[ -f "$msu_file" ]]; then
    msu_size=$(du -h "$msu_file" | cut -f1)
    echo "  MSU:      $msu_file ($msu_size)"
else
    echo "  MSU:      MISSING!"
fi

echo "  PCM:      $pcm_count audio tracks"

if [[ -f "$manifest_file" ]]; then
    echo "  Manifest: $manifest_file"
else
    echo "  Manifest: MISSING!"
fi

echo "  Frames:   $FRAMES_ARCHIVE ($frame_count PNGs preserved)"
echo ""
echo "============================================================"
echo "  Distribution build complete!"
echo "============================================================"
