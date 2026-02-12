# Quick Reference Card

## First-Time Setup (Run Once)

```bash
# 1. Install WSL dependencies
wsl sudo apt-get update
wsl sudo apt-get install -y python3 python3-pip python3-pil make

# 2. Install Python dependencies
wsl pip install -r requirements.txt

# 3. (Optional) Install video tools for MSU-1 generation
wsl sudo apt-get install -y ffmpeg
```

> **Note:** WLA-DX 9.3 pre-built binaries are included in `tools/wla-dx-9.5-svn/` — no compilation needed.

## Common Build Commands

```bash
# Standard build (clean + build, ~2-3 min)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean && make"

# Fast rebuild (skip clean, ~30 sec if only assembly changed)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make"

# Clean build artifacts only
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean"
```

> **Warning:** `make clean` deletes `data/chapters/` — wipes all extracted video frames!

## MSU-1 Video Data Generation

```bash
# Generate .msu from existing PNG frames (~23 min with 8 workers)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --skip-extract --workers 8"

# Full pipeline: extract frames + convert + package (~1hr+ first time)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --workers 8"
```

## Emulator Testing

```bat
:: Mesen 2 testrunner (from Windows)
cmd.exe /c "cd /d E:\gh\SNES-SuperDragonsLairArcade\mesen && Mesen.exe --testrunner ..\build\SuperDragonsLairArcade.sfc script.lua > out.txt 2>&1"
```

## Troubleshooting

```bash
# Check video frame rate
wsl ffprobe data/videos/dl_arcade.mp4

# Verify WLA-DX version (should be 9.3)
wsl tools/wla-dx-9.5-svn/wla-65816 -h

# Check ROM size (should be 1048576 = 1MB)
wsl bash -c "stat -c '%s' build/SuperDragonsLairArcade.sfc"
```

## File Locations

- **ROM Output**: `build/SuperDragonsLairArcade.sfc`
- **MSU-1 Data**: `build/SuperDragonsLairArcade.msu`
- **Symbol Table**: `build/SuperDragonsLairArcade.sym`
- **Source Video**: `data/videos/dl_arcade.mp4`
- **Chapter XMLs**: `data/events/*.xml`
- **Extracted Chapters**: `data/chapters/*/`

## Disk Space

- ROM build only: ~150 MB
- With MSU-1 video data: ~600 MB (.msu file)
- With extracted video frames: ~16 GB

## Build Times

- Fast rebuild (assembly only): ~30 seconds
- Clean build (assets + assembly): ~2-3 minutes
- MSU-1 video generation (from PNGs): ~23 minutes (8 workers)
- Full MSU-1 pipeline (frame extraction + conversion): ~1 hour+
