# Tools Overview

This folder contains the helper utilities used to prepare assets and builds for the SNES Dragon's Lair/RoadBlaster pipeline. The scripts are written for Python 3; Pillow and NumPy are required for image tools, and audio scripts rely on the Python standard library. External dependencies such as WLA-DX (for assembly) are included.

Install dependencies with `pip install -r requirements.txt` before using these tools.

## Quick Reference Table
| Tool | Purpose | Input Formats | Output Formats | Pipeline Usage |
| --- | --- | --- | --- | --- |
| `generate_msu_data.py` | **MSU-1 video pipeline orchestrator**: extracts video frames via ffmpeg (CUDA GPU), converts to SNES tiles via superfamiconv, reduces tiles from 768→512 per frame, packages into `.msu` file. | MP4 video + chapter XMLs. | `.msu` data file (~568 MB for 516 chapters). | Full MSU-1 video generation. |
| `animationWriter_sfc.py` | Packs ordered frame images into a custom animation file using superfamiconv for tile/palette conversion. | Indexed or true-color frame images (`.png`, `.gif`, `.bmp`) in a folder. | Custom binary animation bundle (`SP` header). | Default build pipeline for sprites and backgrounds. |
| `animationWriter.py` | Legacy version of animationWriter_sfc.py using gracon.py instead of superfamiconv. | Same as above. | Same as above. | Legacy fallback. |
| `xmlsceneparser.py` | Converts DirkSimple game data XML to assembly chapter scripts and event data tables. | Chapter XML files from `data/events/`. | `chapter.script` (code) + `chapter.data` (event table) per chapter. | Chapter/event generation for all 516 chapters. |
| `create_event.py` | Generates boilerplate code for new Event classes. | Event name. | `.h` and `.65816` files. | Rapid development of new game events. |
| `remove_event.py` | Deletes Event class files. | Event name. | Deletes files. | Cleanup of unused events. |
| `msu1blockwriter.py` | Packages chapter tile/tilemap/palette data into MSU-1 data stream with scene/frame pointers. | Chapter directories with frame binaries. | `.msu` data file. | Called by `generate_msu_data.py` as final packaging step. |
| `msu1pcmwriter.py` | Validates WAV files and prepends MSU-1 PCM headers with optional loop points. | WAV/RIFF PCM audio. | `.pcm` audio with MSU-1 header. | Preparing MSU-1 background music or chapter audio. |
| `gfx_converter.py` | Unified wrapper for `superfamiconv` or `gracon.py` with consistent output naming. | Any Pillow-supported image. | `.palette`, `.tiles`, `.tilemap` binary files. | Allows swapping converters without changing build scripts. |
| `img_processor.py` | Resizes and crops images to SNES resolutions with color quantization. | Any Pillow-supported image. | Processed PNG at target resolution. | Pre-processing artwork to 256x224 and reducing to 16 colors. |
| `gracon.py` | Legacy Python-based SNES graphics converter with tile deduplication. | Any Pillow-supported image. | Bitplane tile data, palette data, tilemaps. | Legacy converter; superseded by superfamiconv. |
| `mod2snes.py` | Converts ProTracker MOD files into SNES-friendly SPC format with BRR samples. | `.mod` tracker modules. | `.spcmod` binary. | Legacy music path; bypassed when using MSU-1 audio. |
| `convert_daphne.py` / `.bat` | Converts Daphne CDROM laserdisc files to a single MP4 video. | Daphne framefile (`.TXT`) + `.m2v`/`.ogg` segments. | Single concatenated MP4 file. | One-time source video conversion. |
| `convert_video_fps.sh` / `.bat` | Re-encodes video from 29.97 fps (Daphne) to 23.976 fps (DirkSimple XML). | MP4 video file. | Re-encoded MP4 at 23.976 fps. | Ensures video timing matches XML chapter events. |
| `test_chapter_extraction.sh` / `.bat` | Tests single chapter extraction to verify video/audio timing alignment. | Chapter XML + video file. | Test folder with extracted frames and audio. | Verification before full extraction. |
| `debugLog.py` | Helper to recursively log nested data structures for debugging. | Python data structures. | Text log output. | Shared helper for legacy Python tools. |
| `jpeg_to_png.py` | Converts JPEG images to PNG with optional colorspace normalization. | `.jpg`, `.jpeg`. | `.png`. | Quick conversion before SNES processing. |
| `gimp-batch-convert-indexed.scm` | GIMP batch script for converting images to indexed palettes. | Any GIMP-loadable images. | In-place indexed images. | Optional pre-processing. |
| `lua_scene_exporter.py` | Converts DirkSimple `game.lua` scene tables into chapter script summaries. | `game.lua` inputs. | Textual chapter summaries. | Validating scene metadata. |
| `userOptions.py` | Lightweight command-line option parser. | CLI arguments. | Option dictionary. | Shared helper for Python tooling. |
| `snesbrr-2006-12-13/` | BRR encoder/decoder for SNES samples with loop handling. | WAV PCM audio. | BRR sample blocks. | Building SPC sound effects. |
| `superfamiconv/` | Fast C++ SNES graphics converter (tiles, palettes, maps). | PNG images. | Binary tile/map/palette files. | Primary graphics converter (~100x faster than gracon.py). |
| `wla-dx-9.5-svn/` | WLA-DX 9.3 macro assembler/linker for 65816/SPC700 (pre-built binaries). | Assembly source files. | Object files, linked ROM binaries. | Main build toolchain. |

## Tool Details and Usage

### generate_msu_data.py
* **Purpose:** Orchestrates the full MSU-1 video conversion pipeline: extracts 256x192 frames from source video using ffmpeg (CUDA GPU acceleration), converts each frame to SNES tiles/palettes via superfamiconv, reduces 768 unique tiles to 512 (VRAM limit) using RGB-space greedy merge, and packages everything into a single `.msu` file via msu1blockwriter.py.
* **Example:**
  ```bash
  # Full pipeline (frame extraction + conversion + packaging)
  python3 tools/generate_msu_data.py --workers 8

  # Skip frame extraction (use existing PNGs)
  python3 tools/generate_msu_data.py --skip-extract --workers 8
  ```
* **Key constraints:**
  - Requires `OPENBLAS_NUM_THREADS=1` (set automatically) to prevent BLAS thread corruption in tile reduction
  - superfamiconv requires RELATIVE paths (not absolute `/mnt/` paths)
  - 16 colors per frame (1 sub-palette); 32 colors fails in superfamiconv tile step
  - Uses `-T 512` max tiles flag to prevent VRAM buffer overflow
* **Output:** `build/SuperDragonsLairArcade.msu` (~568 MB for 516 chapters, ~31K frames)

### img_processor.py
* **Purpose:** Resize, crop, and quantize images for SNES target resolutions (typically 256x224).
* **Example:**
  ```bash
  python tools/img_processor.py --input art/hiscore.png --output processed.png \
    --width 256 --height 224 --mode cover --colors 16
  ```
* **Modes:** `cover` (fill + crop center), `contain` (fit + pad), `stretch` (exact dimensions)

### xmlsceneparser.py
* **Purpose:** Parses DirkSimple game data XML to generate assembly chapter scripts and event data tables. Each XML produces a `chapter.script` (code) and `chapter.data` (event table with 7 words per event).
* **Example:**
  ```bash
  python3 tools/xmlsceneparser.py data/events/black_knight_seq2.xml
  ```

### create_event.py / remove_event.py
* **Purpose:** Generate or remove boilerplate for new Event classes (header + source files).
* **Example:**
  ```bash
  python tools/create_event.py Event.IntroScene
  python tools/remove_event.py Event.IntroScene
  ```

### gfx_converter.py
* **Purpose:** Unified wrapper for `superfamiconv` or `gracon.py` with consistent output naming.
* **Example:**
  ```bash
  python tools/gfx_converter.py --tool superfamiconv --input image.png \
    --output-base output_name --bpp 4
  ```
* **Palette rule:** The `-palettes` parameter must match the image's actual color count divided by 16 (e.g., 16 colors → `-palettes 1`, 32 colors → `-palettes 2`). Mismatches cause "No matching palette for tile" errors.

### Background Asset Pipeline

1. **Prepare artwork** with `img_processor.py` (resize to 256x224, quantize to 16 colors)
2. **Build system handles conversion** — the makefile automatically processes `*.gfx_bg` folders via `animationWriter_sfc.py`
3. **Directory structure:**
   ```
   data/backgrounds/name.gfx_bg/
     name.gfx_bg.png        <- Processed image (256x224, <=16 colors)
     name.gfx_bg.txt        <- Metadata/description
   ```
4. **Build output:** `build/data/backgrounds/name.gfx_bg.animation`

**Key points:**
- Use 16 colors max for single palette 4bpp backgrounds
- File must be named `<folder_name>.png` (e.g., `hiscore.gfx_bg.png` in `hiscore.gfx_bg/`)

### msu1blockwriter.py
* **Purpose:** Assemble per-chapter frame data into an MSU-1 data stream with scene/frame pointers.
* **Example:**
  ```bash
  python3 msu1blockwriter.py -bpp 4 -infilebase build/chapters \
    -outfile build/SuperDragonsLairArcade.msu -title "SUPER DRAGON'S LAIR" -fps 24
  ```

### msu1pcmwriter.py
* **Purpose:** Validate WAV files (stereo, 16-bit, 44.1 kHz) and prepend MSU-1 PCM header.
* **Example:**
  ```bash
  python3 msu1pcmwriter.py -infile audio/scene1.wav -outfile build/scene1-1.pcm -loopstart 0
  ```

### wla-dx-9.5-svn
* **Purpose:** WLA-DX 9.3 macro assembler/linker suite for 65816 and SPC700. Pre-built binaries included.
* **Important:** Despite the directory name `9.5-svn`, the actual version is **9.3**. Version 9.4+ breaks the build.

## Tools Not Needed for Normal Builds
* `mod2snes.py` and `snesbrr-2006-12-13/` — only required for SPC music/effects, not MSU-1 audio.
* `debugLog.py` — helper for troubleshooting, not part of the normal pipeline.
* `gimp-batch-convert-indexed.scm` — optional if palette tuning is handled in Pillow-based converters.

## Platform Notes
* Python tooling requires Pillow and NumPy; install with `pip install -r requirements.txt`.
* Audio scripts rely on the standard library (`wave`); no external encoders are bundled.
* `snesbrr-2006-12-13` ships a Windows `snesbrr.exe`; build from `src/` on Linux if native execution is required.
