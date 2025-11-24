# Quick Reference Card

## First-Time Setup (Run Once)

```bash
# 1. Install WSL dependencies
wsl sudo apt-get update
wsl sudo apt-get install -y python3 python3-pip python3-pil make build-essential

# 2. Build WLA-DX assembler
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade/tools/wla-dx-9.5-svn && chmod +x unix.sh && ./unix.sh 4"

# 3. (Optional) Install video tools
wsl sudo apt-get install -y ffmpeg gimp
```

## Common Build Commands

```bash
# Fast build (recommended)
build_with_superfamiconv.bat

# Standard build
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean && make"

# Clean build artifacts
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean"
```

## Video Processing

```bash
# 1. Convert Daphne to MP4
tools\convert_daphne.bat

# 2. Fix frame rate (29.97 → 23.976 fps)
tools\convert_video_fps.bat

# 3. Test one chapter
tools\test_chapter_extraction.bat

# 4. Extract all chapters (uncomment makefile line 413 first)
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make"
```

## Testing

```bash
# Quick dimension check (1 second)
wsl python3 tests/check_image_dimensions.py

# Full asset validation (~5 minutes)
wsl python3 tests/test_background_assets.py

# Run all tests
wsl python3 -m pytest tests/ -v
```

## Troubleshooting

```bash
# Check video frame rate
wsl ffprobe data/videos/dl_arcade.mp4

# Find what's processing
wsl ps aux | grep gracon

# Verify WLA-DX installed
wsl tools/wla-dx-9.5-svn/wla-65816 -h
```

## File Locations

- **ROM Output**: `build/SuperDragonsLairArcade.sfc`
- **Source Video**: `data/videos/dl_arcade.mp4`
- **Chapter XMLs**: `data/events/*.xml`
- **Extracted Chapters**: `data/chapters/*/`
- **Build Logs**: Check terminal output

## Disk Space

- ROM build only: ~150MB
- With video extraction: ~16GB

## Build Times

- Fast build (superfamiconv): ~2 minutes
- Standard build (gracon): ~15 minutes
- Full video extraction: ~2-8 hours
