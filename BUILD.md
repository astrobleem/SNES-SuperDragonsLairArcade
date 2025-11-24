# Build System Documentation

## Bill of Materials (Dependencies)

### Required Software

| Component | Version | Purpose | Installation |
|-----------|---------|---------|--------------|
| **WSL (Ubuntu)** | 20.04+ | Linux environment for build tools | Windows Store → Ubuntu |
| **Python** | 3.10+ | Tooling scripts | Pre-installed in Ubuntu |
| **Python Pillow** | Latest | Image processing | `sudo apt-get install python3-pil` |
| **Make** | Any | Build orchestration | `sudo apt-get install make` |
| **GCC** | Any | Compiling WLA-DX | `sudo apt-get install build-essential` |
| **WLA-DX** | 9.5-svn | 65816/SPC700 assembler | Included (build required) |

### Optional Software (For Video/Audio Processing)

| Component | Version | Purpose | Installation |
|-----------|---------|---------|--------------|
| **ffmpeg** | 4.0+ | Video/audio extraction | `sudo apt-get install ffmpeg` |
| **GIMP** | 2.10+ | Frame optimization (optional) | `sudo apt-get install gimp` |

### Included Tools

| Tool | Location | Purpose |
|------|----------|---------|
| **superfamiconv** | `tools/superfamiconv/` | Fast graphics converter (Windows binary included) |
| **WLA-DX source** | `tools/wla-dx-9.5-svn/` | Assembler/linker (requires compilation) |
| **snesbrr** | `tools/snesbrr-2006-12-13/` | BRR audio encoder (Windows binary included) |

## Initial Setup (One-Time)

### 1. Install WSL and Ubuntu

```powershell
# From Windows PowerShell (Administrator)
wsl --install -d Ubuntu-20.04
```

Restart your computer after installation.

### 2. Install Core Dependencies

```bash
# From WSL/Ubuntu terminal
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-pil \
  make \
  build-essential
```

### 3. Install Python Dependencies

```bash
# From project root in WSL
pip install -r requirements.txt
```

Or manually:
```bash
pip install Pillow
```

### 4. Build WLA-DX Assembler

```bash
# From project root in WSL
cd tools/wla-dx-9.5-svn
chmod +x unix.sh
./unix.sh 4
cd ../..
```

Verify installation:
```bash
tools/wla-dx-9.5-svn/wla-65816 -h
```

### 5. (Optional) Install Video Processing Tools

Only needed if extracting video/audio from source files:

```bash
sudo apt-get install -y ffmpeg gimp
```

## Quick Build

### Standard Build (using gracon.py)
```bash
# From Windows PowerShell
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean && make"

# Or from WSL
make clean
make
```

### Fast Build (using superfamiconv - ~100x faster)
**Windows:**
```cmd
build_with_superfamiconv.bat
```

**WSL/Linux:**
```bash
export USE_SUPERFAMICONV=1
make clean
make
```

## Pre-Build Validation

### Quick Dimension Check (1 second)
```bash
wsl python3 tests/check_image_dimensions.py
```

### Full Asset Validation (~5 minutes)
```bash
wsl python3 tests/test_background_assets.py
```

This will:
- Test all background images in `data/backgrounds/`
- Catch recursion errors, timeouts, and other conversion issues
- Report which specific assets are problematic
- Complete in ~5 minutes vs waiting for full build to fail

## Video/Audio Processing (Optional)

### Converting Daphne Source Video

If you have Daphne CDROM files:

```bash
# Windows
tools\convert_daphne.bat

# WSL/Linux
bash tools/convert_daphne.py \
  --framefile "path/to/dlcdrom.TXT" \
  --output "data/videos/dl_arcade.mp4"
```

### Converting Video Frame Rate

**Critical:** Daphne videos are 29.97 fps but DirkSimple XMLs expect 23.976 fps.

```bash
# Windows
tools\convert_video_fps.bat

# WSL/Linux
bash tools/convert_video_fps.sh
```

This re-encodes the video to match XML timing (takes ~15-30 minutes).

### Testing Video Timing

Before extracting all 516 chapters, test one:

```bash
# Windows
tools\test_chapter_extraction.bat

# WSL/Linux
bash tools/test_chapter_extraction.sh
```

Expected results:
- ~140 PNG frames (5.8 seconds)
- ~1MB WAV audio file
- Timing matches XML (0:53 to 0:58)

### Extracting All Chapters

1. Uncomment line 413 in `makefile`:
   ```makefile
   $(xmlchapterconverter) -infile $< -outfolder $(chapterfolder) -videofile $(videofile) -convertedframefolder $(convertedframefolder) -convertedoutfolder $(builddir)/$(chapterfolder)
   ```

2. Run make:
   ```bash
   make
   ```

This will extract video frames and audio for all 516 chapters (takes several hours).

## Graphics Converter Options

The Makefile supports two graphics converters:

### gracon.py (default)
- Pure Python implementation
- Slower (~96s per large image)
- More compatible with edge cases
- Use when superfamiconv has issues

### superfamiconv (recommended)
- Fast C++ implementation (~1s per image)
- Requires `--pad-to-32x32` flag for compatibility
- Enable via `USE_SUPERFAMICONV=1` environment variable
- ~100x faster than gracon.py

## Build Output

Successful build creates:
- `build/SuperDragonsLairArcade.sfc` - SNES ROM file (~2MB)
- `build/data/` - Converted graphics, sounds, sprites
- `build/src/` - Assembled object files

## Troubleshooting

### "RecursionError: maximum recursion depth exceeded"
- Run `python3 tests/test_background_assets.py` to identify problematic images
- Replace complex images with simpler versions
- Or increase recursion limit in `tools/gracon.py`

### "ModuleNotFoundError: No module named 'PIL'"
```bash
wsl sudo apt-get install python3-pil
```

### "wla-65816: command not found"
Build WLA-DX assembler:
```bash
cd tools/wla-dx-9.5-svn
chmod +x unix.sh
./unix.sh 4
```

### "ffmpeg: command not found"
```bash
wsl sudo apt-get install ffmpeg
```

### "gimp: not found" (during video extraction)
```bash
wsl sudo apt-get install gimp
```

Note: GIMP is optional; frames will extract without it, just won't be optimized.

### Build hangs on graphics conversion
- Switch to superfamiconv for faster builds
- Or check `ps aux | grep gracon` to see which file is processing

### Video extraction produces wrong number of frames
- Verify video is 23.976 fps: `ffprobe data/videos/dl_arcade.mp4`
- If not, run `tools\convert_video_fps.bat` to re-encode
- Test with `tools\test_chapter_extraction.bat` before full extraction

## Clean Build

### Standard Clean
```bash
make clean
```
Removes: `build/` directory, `data/chapters/`, Python cache

### Deep Clean
```bash
make clean-all
```
Removes: Everything from standard clean + WLA-DX build artifacts

## Disk Space Requirements

| Component | Size | Notes |
|-----------|------|-------|
| Source code | ~50MB | Repository |
| Build output | ~100MB | ROM + converted assets |
| Video source | ~750MB | `dl_arcade.mp4` |
| Extracted chapters | ~15GB | All 516 chapters (frames + audio) |
| **Total (with video)** | **~16GB** | Full build with video extraction |
| **Total (ROM only)** | **~150MB** | Without video extraction |

## Build Time Estimates

| Task | gracon.py | superfamiconv | Notes |
|------|-----------|---------------|-------|
| Clean ROM build | ~15 min | ~2 min | No video extraction |
| Single chapter test | ~1 min | ~10 sec | Test extraction only |
| Full video extraction | ~8 hours | ~2 hours | All 516 chapters |

## Platform Notes

- **Windows**: Use WSL for all build commands
- **Linux**: All commands work natively
- **macOS**: Should work but untested; may need to build WLA-DX manually

## Next Steps After Build

1. **Test ROM**: Load `build/SuperDragonsLairArcade.sfc` in SNES9x
2. **Verify graphics**: Check backgrounds and sprites render correctly
3. **Test gameplay**: Ensure controls and timing work
4. **(Optional) Extract video**: For full MSU-1 experience with FMV
