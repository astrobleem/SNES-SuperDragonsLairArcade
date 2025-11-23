# Tools Overview

This folder contains the helper utilities used to prepare assets and builds for the SNES Dragon's Lair/RoadBlaster pipeline. The scripts are written for Python 3; Pillow is required for image tools, and audio scripts rely on the Python standard library. External dependencies such as GIMP (for batch palette conversion) and WLA-DX (for assembly) are included where possible.

**Note:** All Python tools have been modernized for Python 3 compatibility. Critical performance fixes have been applied to `gracon.py` to handle large images efficiently. Install dependencies with `pip install -r requirements.txt` before using these tools.

## Quick Reference Table
| Tool | Purpose | Input Formats | Output Formats | Pipeline Usage |
| --- | --- | --- | --- | --- |
| `animationWriter.py` | Packs ordered frame images into a custom sprite animation file with tiles, tilemaps, and palettes. | Indexed or true-color frame images (`.png`, `.gif`, `.bmp`) in a folder. | Custom binary animation bundle (`SP` header) containing tile/palette chunks. | Sprite cutscenes and in-game animations.
| `debugLog.py` | Helper to recursively log nested data structures for debugging. | Python data structures. | Text log output. | Shared helper for the legacy Python tools.
| `gfx_converter.py` | **NEW** Unified wrapper for `superfamiconv` or `gracon.py` with consistent output naming. | Any Pillow-supported image (PNG, GIF, etc.). | `.palette`, `.tiles`, `.tilemap` binary files. | Replacement for direct `gracon.py` calls; allows swapping converters without changing build scripts.
| `jpeg_to_png.py` | Converts JPEG images to PNG with optional colorspace normalization and overwrite protection. | `.jpg`, `.jpeg`. | `.png`. | Quick standalone conversion before SNES-specific processing.
| `gimp-batch-convert-indexed.scm` | GIMP batch script that converts matching images to indexed palettes with Gaussian blur pre-pass. | Any GIMP-loadable images matching a pattern. | In-place indexed images. | Pre-processing art assets before tile conversion when manual palette control is needed.
| `gracon.py` | Converts images into SNES bitplane graphics, palettes, and tilemaps for backgrounds or sprites with optional deduplication. | Any Pillow-supported image (PNG, GIF, etc.). | Bitplane tile data, palette data, and tilemaps; optional PNG verification. | Core background/sprite converter for RoadBlaster.
| `img_processor.py` | **NEW** Resizes and crops images to SNES resolutions with color quantization. | Any Pillow-supported image. | Processed PNG at target resolution with optional color reduction. | Pre-processing artwork to 256x224 and reducing to 16 colors before conversion.
| `mod2snes.py` | Converts ProTracker MOD files into SNES-friendly SPC module format with BRR samples. | `.mod` tracker modules. | `.spcmod` binary plus embedded BRR sample data. | Legacy music path; bypassed when using MSU1 audio.
| `msu1blockwriter.py` | Packages chapter folders (converted frames, tilemaps, palettes) and chapter audio into MSU1 data and per-chapter PCM files. | Chapter directories containing frame binaries; associated PCM audio per chapter. | MSU1 data file with scene/frame pointers plus chapter `.pcm` audio streams. | Bundling MSU video/audio chapters for playback.
| `msu1pcmwriter.py` | Validates a WAV file (stereo, 16-bit, 44.1 kHz) and prepends MSU1 PCM headers with optional loop points. | WAV/RIFF PCM audio. | `.pcm` audio with MSU1 header and loop offset. | Preparing MSU1 background music or chapter audio.
| `superfamiconv/` | **NEW** Fast C++ SNES graphics converter (tiles, palettes, maps). | PNG images. | Binary `.chr`/`.map`/`.pal` or custom extensions. | Alternative to `gracon.py`; ~100x faster for large images.
| `userOptions.py` | Lightweight command-line option parser used by other scripts. | CLI arguments. | Sanitized option dictionary. | Shared helper for Python tooling.
| `xmlsceneparser.py` | Parses Dragon's Lair iPhone XML to emit scene event lists, frame folders, and audio references. | iPhone XML descriptor plus video/audio paths. | Extracted frame/audio listings written to folders. | Driving chapter/frame extraction ahead of tile conversion and MSU packaging.
| `lua_scene_exporter.py` | Converts DirkSimple-style `game.lua` scene tables into readable chapter scripts for regression tests. | Trimmed `game.lua` inputs containing `scenes` tables. | Textual `chapter.script` summaries listing sequences, actions, and timeouts. | Validating scene metadata before running full conversion.
| `snesbrr-2006-12-13/` | BRR encoder/decoder for SNES samples with loop handling. | WAV PCM audio. | BRR sample blocks or decoded WAV. | Building SPC sound effects or MOD sample banks.
| `wla-dx-9.5-svn/` | Cross-platform macro assembler/linker suite for 65816/SPC700 and related CPUs. | Assembly source, object/library files. | Object files, linked ROM/SRAM binaries. | Main code build toolchain for SNES ROM and SPC binaries.

## Tool Details and Usage

### img_processor.py
* **Purpose:** Resize, crop, and quantize images for SNES target resolutions (typically 256x224). Essential for preparing high-resolution artwork for conversion.
* **Inputs/Outputs:** Any Pillow-supported image; outputs processed PNG at target dimensions with optional color reduction.
* **Example:**
  ```bash
  # Resize and quantize to 16 colors (4bpp single palette)
  python tools/img_processor.py --input art/hiscore.png --output processed.png \
    --width 256 --height 224 --mode cover --colors 16
  ```
* **Modes:**
  - `cover`: Resize to fill dimensions maintaining aspect ratio, then crop center (best for backgrounds)
  - `contain`: Resize to fit within dimensions, pad with background color
  - `stretch`: Resize to exact dimensions ignoring aspect ratio
* **Pipeline:** First step for processing high-resolution artwork before SNES conversion.

### jpeg_to_png.py
* **Purpose:** Lightweight converter for turning JPEGs into PNGs with optional colorspace normalization (e.g., force RGBA) and overwrite protection.
* **Inputs/Outputs:** JPEG input; PNG output.
* **Example:**
  ```bash
  python tools/jpeg_to_png.py --input photos/frame.jpg --colorspace RGBA
  ```
* **Pipeline:** Quick prep step when you receive JPEG assets but need lossless PNGs before running `img_processor.py` or `gfx_converter.py`.

### gfx_converter.py
* **Purpose:** Unified wrapper for `superfamiconv` or `gracon.py` providing consistent output naming (`.palette`, `.tiles`, `.tilemap`).
* **Inputs/Outputs:** PNG images; binary SNES data files with standardized extensions.
* **Example:**
  ```bash
  # Using superfamiconv (fast)
  python tools/gfx_converter.py --tool superfamiconv --input image.png \
    --output-base output_name --bpp 4
  
  # Using superfamiconv with gracon-compatible padding
  python tools/gfx_converter.py --tool superfamiconv --input image.png \
    --output-base output_name --bpp 4 --pad-to-32x32
  
  # Using gracon (slower but compatible)
  python tools/gfx_converter.py --tool gracon --input image.png \
    --output-base output_name --bpp 4
  ```
* **Options:**
  - `--pad-to-32x32`: Pads superfamiconv tilemaps from 32×28 (1792 bytes) to 32×32 (2048 bytes) for compatibility with code expecting gracon's padded format. Only affects superfamiconv output.
* **Pipeline:** Use this instead of calling converters directly to allow easy switching between tools.
* **Note:** `superfamiconv` is ~100x faster than `gracon.py` for most images.

### superfamiconv
* **Purpose:** High-performance C++ SNES graphics converter supporting tiles, palettes, and tilemaps.
* **Inputs/Outputs:** PNG images; binary SNES formats.
* **Location:** `tools/superfamiconv/superfamiconv.exe` (Windows binary included)
* **Pipeline:** Called via `gfx_converter.py` wrapper; direct usage not recommended.
* **Performance:** Processes images in < 1s vs ~96s for `gracon.py`.

## Background Graphics Workflow

For processing background images (e.g., `data/backgrounds/hiscore.gfx_bg/`):

1. **Prepare Image** - Use `img_processor.py` to resize and quantize:
   ```bash
   python tools/img_processor.py \
     --input data/backgrounds/name.gfx_bg/source.png \
     --output data/backgrounds/name.gfx_bg/name.gfx_bg.png \
     --width 256 --height 224 --mode cover --colors 16
   ```

2. **Build System Handles Conversion** - The makefile automatically processes `*.gfx_bg` folders:
   - `animationWriter.py` finds all PNG files in the folder
   - Converts them using `gracon.py` with settings from `gfx_bg_flags` variable
   - Outputs `.animation` file with packed tiles/palette/tilemap

3. **Directory Structure:**
   ```
   data/backgrounds/name.gfx_bg/
     name.gfx_bg.png        ← Processed image (256x224, ≤16 colors)
     name.gfx_bg.txt        ← Metadata/description
     name.gfx_bg.png.original  ← Optional backup of source
   ```

4. **Build Output:**
   ```
   build/data/backgrounds/name.gfx_bg.animation  ← Final packaged asset
   ```

**Key Points:**
- Use 16 colors max for single palette 4bpp backgrounds
- Use 128 colors max for 8-palette 4bpp backgrounds (requires `-palettes 8` flag)
- The build system expects PNG files in `*.gfx_bg/` folders
- File must be named `<folder_name>.png` (e.g., `hiscore.gfx_bg.png` in `hiscore.gfx_bg/`)

### animationWriter.py
* **Purpose:** Convert a folder of ordered frame images into a packed sprite animation binary (`SP` header) containing tiles, palettes, and frame pointers. First frame determines the palette unless overridden.
* **Inputs/Outputs:** Accepts `.png`, `.gif`, or `.bmp` frames; writes a binary animation file with frame headers, tiles, tilemaps, and palettes.
* **Example:**
  ```bash
  python3 animationWriter.py -infolder assets/sprites/dragon_run \
    -outfile build/dragon_run.anim -palettes 4 -tilesizex 8 -tilesizey 8 -optimize on
  ```
* **Pipeline:** Use after sprite frames are prepared to create VRAM-ready animation bundles.
* **Tests:** Comprehensive test in `tests/test_tools.py::test_animation_writer` validates the SP header format, frame count, and binary structure using real sprite frames from `data/sprites/bang.gfx_sprite/`. Run with `python -m pytest tests/test_tools.py::test_animation_writer -v`.

### debugLog.py
* **Purpose:** Recursively pretty-prints nested lists/dicts to the logging output for inspection.
* **Inputs/Outputs:** Any Python objects; outputs debug logs.
* **Pipeline:** Import from other scripts when troubleshooting option parsing or tile deduplication.

### gimp-batch-convert-indexed.scm
* **Purpose:** Batch-convert images matching a glob pattern to indexed color using GIMP’s non-interactive mode, with a Gaussian blur pre-pass to improve palette reduction.
* **Inputs/Outputs:** All files matching a pattern; saves converted images in place.
* **Example:**
  ```bash
  gimp -i -b '(batch-convert-indexed "assets/bg/*.png" 64)' -b '(gimp-quit 0)'
  ```
* **Pipeline:** Optional pre-step to clamp palettes before running `gracon.py` for backgrounds or sprites.

### gracon.py
* **Purpose:** Convert images to SNES bitplane tiles, palettes, and tilemaps for backgrounds or sprites; supports palette limits, transparent color selection, and tile deduplication.
* **Inputs/Outputs:** Pillow-supported images; outputs binary tile/tilemap/palette data and optional PNG verification.
* **Example:**
  ```bash
  # Show help and options
  python3 gracon.py --help
  
  # Convert an image
  python3 gracon.py -mode bg -bpp 4 -palettes 8 -transcol 0x7C1F \
    -verify on -tilethreshold 2 input/title.png output/title
  ```
* **Pipeline:** Primary converter for RoadBlaster background layers and sprite sheets before animation packing or VRAM layout.

### mod2snes.py
* **Purpose:** Translate ProTracker `.mod` music into an SPC-friendly format with BRR sample conversion and pattern data.
* **Inputs/Outputs:** `.mod` input; `.spcmod` output (and implicit BRR samples in the binary).
* **Example:**
  ```bash
  python3 mod2snes.py music/roadblaster.mod build/roadblaster
  ```
* **Pipeline:** Legacy SPC music path; keep in mind MSU1 audio may replace it for final builds.

### msu1blockwriter.py
* **Purpose:** Assemble per-chapter frame data (tiles, tilemaps, palettes) and accompanying PCM into an MSU1 data stream with scene/frame pointers.
* **Inputs/Outputs:** Chapter directories containing frame binaries; writes a consolidated MSU data file plus chapter-specific `.pcm` audio files.
* **Example:**
  ```bash
  python3 msu1blockwriter.py -bpp 4 -infilebase build/chapters \
    -outfile build/roadblaster.msu -title "ROADBLASTER" -fps 24
  ```
* **Pipeline:** Final packaging step for MSU1 video chapters after frame conversion.

### msu1pcmwriter.py
* **Purpose:** Validate WAV files (stereo, 16-bit, 44.1 kHz, uncompressed) and prepend the MSU1 PCM header with an optional loop start offset.
* **Inputs/Outputs:** WAV input; `.pcm` output.
* **Example:**
  ```bash
  python3 msu1pcmwriter.py -infile audio/scene1.wav -outfile build/scene1-1.pcm -loopstart 0
  ```
* **Pipeline:** Produces MSU1-ready audio streams for chapters or background music.

### userOptions.py
* **Purpose:** Minimal CLI option parser shared by multiple tools; handles type checking and bounds enforcement for `-option value` pairs.
* **Inputs/Outputs:** Raw CLI arguments; returns sanitized option values.
* **Pipeline:** Utility dependency for `animationWriter.py`, `gracon.py`, `msu1blockwriter.py`, and others.

### xmlsceneparser.py
* **Purpose:** Parse Dragon’s Lair iPhone XML descriptors and emit frame/audio listings per chapter, creating output folders for subsequent conversion.
* **Inputs/Outputs:** XML scene definition and related media paths; writes scene event lists and organizes frame/audio references in folders.
* **Pipeline:** Early extraction step before running image converters and MSU1 packers.

### lua_scene_exporter.py
* **Purpose:** Read DirkSimple-style `game.lua` scene tables and write a readable `chapter.script` summary that captures timings, timeouts, actions, and single-frame markers.
* **Inputs/Outputs:** `game.lua` input; writes `chapter.script` text to the requested destination path.
* **Tests:** `python -m pytest tests/test_lua_scene_exporter.py`

### snesbrr-2006-12-13
* **Purpose:** Standalone SNES BRR encoder/decoder supporting loop points and optional Gaussian filtering.
* **Inputs/Outputs:** WAV to BRR (encode), BRR to WAV (decode), or WAV→BRR→WAV transcoding.
* **Example:**
  ```bash
  ./snesbrr-2006-12-13/snesbrr.exe --encode sample.wav sample.brr --loop-start 0
  ```
* **Pipeline:** Used when generating SPC sound effects or MOD instrument banks; not needed for pure MSU1 audio workflows.

### wla-dx-9.5-svn
* **Purpose:** Macro assembler/linker suite targeting 65816 and SPC700 among others; required for compiling the SNES ROM and SPC binaries.
* **Inputs/Outputs:** Assembly sources and object files; produces linked ROM/SRAM outputs.
* **Example (Linux):**
  ```bash
  cd wla-dx-9.5-svn
  make -f makefile
  ./wla-65816 -o obj/main.o ../../src/main.asm
  ./wlalink -S linkfile project.sfc
  ```
* **Pipeline:** Core build dependency for the game code and any SPC driver binaries.

## Planned Tool Usage for Dragon’s Lair
* **Backgrounds:** Use `gracon.py` (bg mode) to generate tiles, palettes, and tilemaps for final assets; quick-preview helpers like `snes_convert.py` were removed.
* **Sprites/Animations:** Prepare sprite sheets with `gracon.py` (sprite mode) and package sequences with `animationWriter.py` for VRAM-ready animation files.
* **Tilemaps:** `gracon.py` emits tilemaps for both backgrounds and sprites; these feed directly into VRAM layout and MSU1 chapter bundles.
* **MSU1 Audio/Video:** Convert WAV sources with `msu1pcmwriter.py`, organize chapter frames, and package everything via `msu1blockwriter.py`. `xmlsceneparser.py` supplies frame/audio references.

## Tools Likely Not Needed Immediately
* `mod2snes.py` and `snesbrr-2006-12-13/` are only required if we ship SPC music/effects instead of MSU1 audio.
* `debugLog.py` is a helper for troubleshooting and is not part of the normal pipeline.
* `gimp-batch-convert-indexed.scm` is optional if palette tuning is handled entirely in Pillow-based converters.

## Known Gaps and Follow-ups
* There is no orchestration script that chains `xmlsceneparser.py` → `gracon.py` → `animationWriter.py`/`msu1blockwriter.py`; running conversions still requires manual per-folder commands.
* Palette limiting across entire chapters (multiple frames sharing palettes) is manual; a batch palette optimizer would prevent redundant palettes during MSU1 packing.
* Automated regression checks for tilemap limits (size/VRAM budgets) are missing; conversions currently rely on manual inspection.

## Removed helper scripts
Legacy helpers that were rarely used—such as `snes_convert.py` and Lua-to-XML generators—were removed alongside the RoadBlaster XML set. Rely on the remaining converters and chapter XMLs in `data/events/` when preparing assets.

## Platform Notes
* Python tooling expects Pillow; ensure it is installed (`pip install -r requirements.txt`).
* Audio scripts rely on the standard library (`wave`); no external encoders are bundled.
* `gimp-batch-convert-indexed.scm` requires a GIMP installation with Script-Fu enabled (`gimp -i -b ...`).
* `snesbrr-2006-12-13` ships a Windows `snesbrr.exe`; build from `src/` on Linux if native execution is required.
* `wla-dx-9.5-svn` includes Unix `makefile` and Windows batch files; compile the assembler/linker before building the ROM.
