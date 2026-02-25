# Tools Overview

This folder contains all helper utilities for the SNES Super Dragon's Lair Arcade build pipeline. Scripts are written in Python 3 (requires Pillow and NumPy); external dependencies such as WLA-DX and superfamiconv are included as pre-built binaries.

Install Python dependencies with `pip install -r requirements.txt`.

## Quick Reference Table

| Tool | Purpose |
| --- | --- |
| **Core Pipeline** | |
| `lua_scene_exporter.py` | Export DirkSimple `game.lua` scene data to XML event files with frame-accurate timing |
| `xmlsceneparser.py` | Convert XML chapter events to assembly `.script` + `.data` files (516 chapters) |
| `generate_msu_data.py` | Full MSU-1 video pipeline: Daphne .m2v extraction, tile conversion, .msu packaging |
| `generate_segment_timing.py` | Generate per-segment cumulative timing offsets from Daphne framefile + ffprobe |
| `generate_playthrough_tests.py` | Generate per-scene Mesen Lua test scripts with golden path BFS |
| `build_dist.sh` | Full distribution build: ROM + MSU-1 video/audio + frame preservation |
| **Graphics & Assets** | |
| `animationWriter_sfc.py` | Convert PNG frames to SNES animation format via superfamiconv (sprites/backgrounds) |
| `animationWriter.py` | Legacy animation writer using gracon.py instead of superfamiconv |
| `gfx_converter.py` | Unified wrapper for superfamiconv/gracon with consistent output naming |
| `gracon.py` | Legacy Python SNES graphics converter with tile deduplication |
| `img_processor.py` | Resize/crop/quantize images for SNES resolutions (256x224, 16 colors) |
| `check_assets.py` | Validate sprite/background dimensions and transparency |
| `rotate_arrow_sprite.py` | Rotate arrow sprite PNG for directional variants |
| `jpeg_to_png.py` | Convert JPEG images to PNG with colorspace normalization |
| `gimp-batch-convert-indexed.scm` | GIMP Script-Fu for batch indexed color conversion |
| **MSU-1 Audio & Data** | |
| `msu1blockwriter.py` | Package chapter tile/tilemap/palette data into .msu file format |
| `msu1pcmwriter.py` | Validate WAV and prepend MSU-1 PCM header (44.1 kHz stereo 16-bit) |
| `batch_convert_msu.py` | Batch convert Daphne .ogg audio files to MSU-1 PCM format |
| `convert_roar_pcm.py` | Convert dragon roar WAV to MSU-1 PCM (track 900) |
| `generate_manifest.py` | Generate manifest.xml for bsnes/higan MSU-1 emulation |
| `verify_msu.py` | Verify .msu binary consistency against chapter.id files |
| **Video Source Processing** | |
| `convert_daphne.py` / `.bat` | Convert Daphne .m2v/.ogg segments to concatenated MP4 |
| `convert_video_fps.sh` / `.bat` | Re-encode video from 29.97 fps to 23.976 fps (laserdisc rate) |
| `analyze_segments.py` | Analyze Daphne framefile segment-to-frame mapping |
| `generate_ld_frame_table.py` | Generate chapter_ld_frames.inc ROM lookup table from chapter IDs |
| `refresh_frames.sh` | Copy extracted video frames to data/videos/frames for preservation |
| **Event & Chapter Management** | |
| `create_event.py` | Generate boilerplate .h + .65816 for new Event classes |
| `remove_event.py` | Delete Event class files |
| `chapter_event_inventory.py` | Inventory all event types across 516 chapters, generate coverage report |
| `expand_cutscene_events.py` | Expand cutscene event macros with boilerplate method code |
| `extract_death_frames.py` | Extract sample frames from death segments for analysis |
| `regen_chapters.sh` | Regenerate chapter include files from all XMLs |
| **FXPAK Pro Hardware** | |
| `fxpak_push.py` | Push ROM to FXPAK Pro via QUsb2Snes and boot it |
| `fxpak_debug.py` | Read SNES memory via QUsb2Snes: OOP stack, allocations, crash diagnostics |
| `fxpak_crash_dump.py` | Quick WRAM capture for post-crash analysis |
| **Testing & Automation** | |
| `mesen_mcp_server.py` | MCP server for Mesen automation: symbol lookup, build, test generation/execution |
| `test_chapter_extraction.sh` / `.bat` | Test single chapter extraction for timing verification |
| `start_build.sh` | Background ROM build with logging |
| `batch_process_video.py` | Concurrent batch execution of xmlsceneparser.py across XML files |
| **Development Utilities** | |
| `find_dupes.py` | Find duplicate macro definitions in macros.inc |
| `find_long_paths.py` | Find file paths exceeding length limits in chapter.include |
| `deduplicate_chapters.py` | Remove duplicate .include lines from chapter.include |
| `clean_macros.py` | Remove duplicate macro definitions from macros.inc |
| `fix_macros.py` | Fix macros.inc by removing lines before .ifndef guard |
| `fix_macros_final.py` | Add missing helper macros (EVENT_ACTION_PRIMARY, etc.) |
| `create_missing_headers.py` | Create missing .h headers for Event .65816 files |
| `rename_long_paths.py` | Rename chapter files to fit within path length limits |
| `compare_anim.py` | Compare animation file headers between two .sp files |
| `cleanup_git_tracking.sh` | Remove build artifacts from git tracking |
| `revert_wladx.sh` | Downgrade WLA-DX from 9.5 to 9.3 (project requires 9.3) |
| **Shared Helpers** | |
| `userOptions.py` | Lightweight CLI option parser for legacy tools |
| `debugLog.py` | Recursive data structure logging for debugging |
| `create_template.py` | Legacy template generator for chapter handler parameters |
| `exporter.py` | Generic export helper |
| `mod2snes.py` | Convert ProTracker MOD to SNES SPC format with BRR samples (legacy) |
| **Bundled Binaries** | |
| `superfamiconv/` | Fast C++ SNES graphics converter (tiles, palettes, tilemaps) |
| `snesbrr-2006-12-13/` | BRR encoder/decoder for SNES audio samples |
| `wla-dx-9.5-svn/` | WLA-DX 9.3 assembler/linker for 65816/SPC700 (pre-built) |

## Core Pipeline

### lua_scene_exporter.py

Exports DirkSimple `game.lua` scene data to XML event files in `data/events/`. Resolves laserdisc frame numbers to per-segment video timing using `data/segment_timing.json` for frame-accurate chapter seeking. Also derives chapter exit routing (`scene_router` for most scenes, direct transitions for introduction and finale).

```bash
wsl -e bash -c "cd <wsl-project-root> && python3 tools/lua_scene_exporter.py"
```

**Important:** Must be re-run before `make` when changing scene routing. `make` only runs `xmlsceneparser.py` (XML to assembly), not this tool.

### xmlsceneparser.py

Converts XML chapter event definitions from `data/events/` into assembly source. Each XML produces:
- `chapter.script` — CHAPTER macro + 24-bit pointer to event data + DIE (~10 bytes)
- `chapter.data` — event data table: 7 words (14 bytes) per event, terminated by `.dw 0`

```bash
python3 tools/xmlsceneparser.py data/events/black_knight_seq2.xml
```

Type normalization: `direction` + `type="left"` becomes `Event.direction_generic` with `JOY_DIR_LEFT`, sequence events become `Event.seq_generic`, etc.

### generate_msu_data.py

Orchestrates the full MSU-1 video pipeline from Daphne .m2v/.ogg source segments:

1. **Phase 1a:** Extract 256x192 PNG frames via ffmpeg (CPU decode, yadif deinterlace, 23.976 fps)
2. **Phase 1b:** Extract audio from paired .ogg segments to WAV then MSU-1 PCM
3. **Phase 1c:** Copy PCM files to build/ and sfc/ directories
4. **Phase 1d:** Copy dragon roar PCM (track 900) from data/sounds/
5. **Phase 1e:** Generate blank frames for zero-duration routing chapters
6. **Phase 2:** Convert each PNG to SNES palette/tiles/tilemap via superfamiconv, then merge 768 unique tiles to 384 per frame using RGB-space L2-distance greedy reduction
7. **Phase 3:** Package all chapters into single `.msu` file via msu1blockwriter.py

```bash
# Full pipeline (~1hr with 8 workers)
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_msu_data.py --workers 8"

# Skip frame extraction, reuse existing PNGs (~23 min)
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_msu_data.py --skip-extract --workers 8"

# Audio-only (skip video extraction, conversion, and packaging)
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_msu_data.py --skip-extract --skip-convert --skip-package --workers 8"
```

**Key constraints:**
- `OPENBLAS_NUM_THREADS=1` set automatically to prevent BLAS thread corruption
- superfamiconv requires RELATIVE paths (not absolute `/mnt/` paths)
- 16 colors per frame (1 sub-palette); CGRAM limited to 8 BG palettes
- `make clean` DELETES `data/chapters/` — run MSU generation AFTER final build
- Requires Daphne framefile at `data/laserdisc/dl_lair.txt`

**Output:** `build/SuperDragonsLairArcade.msu` (~516 MB) + per-chapter `.pcm` files

### generate_segment_timing.py

Parses the Daphne framefile (`data/laserdisc/dl_lair.txt`), probes each .m2v segment with ffprobe for actual duration, and builds a cumulative timing table. Output: `data/segment_timing.json`.

```bash
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_segment_timing.py"
```

Run once; only re-run if Daphne source segments change.

### generate_playthrough_tests.py

Generates per-scene Mesen Lua test scripts that verify every gameplay scene is beatable. Parses 518 `chapter.data` files, builds directed chapter graphs, finds golden paths via BFS, and reads `.sym` file for current ROM addresses.

```bash
# Generate all 28 scene test scripts
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_playthrough_tests.py"

# Single scene
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_playthrough_tests.py --scene 15"

# Dry-run (show golden paths without generating files)
wsl -e bash -c "cd <wsl-project-root> && python3 tools/generate_playthrough_tests.py --dry-run"
```

**Must regenerate after every build** because ROM addresses shift. Reads `build/SuperDragonsLairArcade.sym` automatically.

### build_dist.sh

Full distribution build: clean ROM build, MSU-1 video/audio generation, frame preservation, and output packaging.

```bash
wsl -e bash -c "cd <wsl-project-root> && bash tools/build_dist.sh"
```

## Graphics & Assets

### animationWriter_sfc.py

Converts PNG animation frames to SNES sprite/background animation format (`.animation` files with `SP` header) using superfamiconv for tile/palette conversion. Forces `-P 1` (single sub-palette) to prevent CGRAM overflow.

Called automatically by the makefile for `*.gfx_bg` and `*.gfx_sprite` directories.

### gfx_converter.py

Unified wrapper for superfamiconv or gracon.py with consistent output naming (`.palette`, `.tiles`, `.tilemap`).

```bash
python tools/gfx_converter.py --tool superfamiconv --input image.png --output-base output_name --bpp 4
```

**Palette rule:** `-palettes` must match the image's color count / 16 (e.g., 16 colors = `-palettes 1`).

### img_processor.py

Resize, crop, and quantize images for SNES target resolutions.

```bash
python tools/img_processor.py --input art/hiscore.png --output processed.png \
  --width 256 --height 224 --mode cover --colors 16
```

**Modes:** `cover` (fill + crop center), `contain` (fit + pad), `stretch` (exact dimensions)

### check_assets.py

Validates sprite and background image dimensions and transparency against specifications (arrows 32x32 transparent, backgrounds 256x224 opaque, etc.).

### rotate_arrow_sprite.py

Rotates a source arrow sprite PNG to generate directional variants (90 degrees clockwise for up, counter-clockwise for down).

## MSU-1 Audio & Data

### msu1blockwriter.py

Assembles per-chapter frame data (tiles, tilemaps, palettes) into a single `.msu` data file with header, pointer table, and chapter entries. Also writes per-chapter `.pcm` audio files.

```bash
python3 msu1blockwriter.py -bpp 4 -infilebase build/chapters \
  -outfile build/SuperDragonsLairArcade.msu -title "SUPER DRAGON'S LAIR" -fps 24
```

### msu1pcmwriter.py

Validates WAV audio (must be stereo, 16-bit, 44.1 kHz RIFF PCM) and prepends the MSU-1 PCM header with optional loop point.

```bash
python3 msu1pcmwriter.py -infile audio/scene1.wav -outfile build/scene1-1.pcm -loopstart 0
```

### convert_roar_pcm.py

Converts the dragon roar WAV (`roar.sfx_normal.wav`) to MSU-1 PCM format as track 900 for the MSU-1 splash screen. Output: `data/sounds/SuperDragonsLairArcade-900.pcm`. Only re-run if the source WAV changes.

### batch_convert_msu.py

Batch converts all Daphne `.ogg` audio files to MSU-1 PCM format. Finds `.ogg` files in the Daphne CDROM directory, converts each to WAV, then wraps in PCM with sequential track numbering.

### generate_manifest.py

Generates `manifest.xml` for bsnes/higan MSU-1 emulation by scanning for actual PCM files in the output directory and listing track IDs.

### verify_msu.py

Verifies `.msu` binary consistency: reads header, pointer table, and chapter entries, comparing against `chapter.id.*` files to ensure all chapters are present and frame counts match.

## Event & Chapter Management

### create_event.py / remove_event.py

Generate or remove boilerplate for new Event classes. Creates both `.h` (ZP struct, flags, properties) and `.65816` (init/play/kill methods with CLASS macro).

```bash
python tools/create_event.py Event.IntroScene
python tools/remove_event.py Event.IntroScene
```

### chapter_event_inventory.py

Scans all event XMLs and inventories referenced event types, comparing against actual Event class implementations. Generates `data/chapter_event_inventory.md` coverage report.

### regen_chapters.sh

Clears stale chapter include files and re-runs `xmlsceneparser.py` on all XMLs in `data/events/` to regenerate `chapter.include` and `chapter_data.include`.

```bash
wsl -e bash -c "cd <wsl-project-root> && bash tools/regen_chapters.sh"
```

## FXPAK Pro Hardware

### fxpak_push.py

Pushes the built ROM to FXPAK Pro via QUsb2Snes websocket (localhost:23074) and boots it. Requires QUsb2Snes running and FXPAK connected via USB.

```bash
python tools/fxpak_push.py
```

### fxpak_debug.py

Reads SNES memory via QUsb2Snes for live debugging and crash analysis. Features include OOP stack dump (all 48 object slots), WRAM allocation tables, exception state readout, fingerprint mismatch diagnostics, and memory region inspection.

```bash
python tools/fxpak_debug.py
```

### fxpak_crash_dump.py

Quick WRAM capture from FXPAK for post-crash analysis. Dumps key memory regions (exception state, OOP stack, input registers) immediately after a crash.

```bash
python tools/fxpak_crash_dump.py
```

## Testing & Automation

### mesen_mcp_server.py

FastMCP-based automation server for Mesen 2 emulator. Provides tools for:
- `lookup_symbol` / `lookup_symbols` — auto-calculates `$C0xxxx` Mesen addresses from `.sym` file
- `build_rom` — trigger WSL build from Windows
- `generate_test` — generate playthrough test for a specific scene
- `run_test` — execute a Mesen Lua test script
- `run_lua_snippet` — run arbitrary Lua in Mesen testrunner mode
- `take_screenshot` — capture emulator screen

Configured in `.mcp.json`. Runs on Windows Python, delegates to WSL for builds and test generation.

### test_chapter_extraction.sh / .bat

Tests extraction of a single chapter to verify video/audio timing alignment before running the full pipeline.

## Video Source Processing

### convert_daphne.py / .bat

Parses the Daphne framefile and converts `.m2v` video segments to a concatenated MP4.

### convert_video_fps.sh / .bat

Re-encodes video from 29.97 fps (Daphne interlaced) to 23.976 fps (laserdisc rate) to align with XML chapter timings.

### analyze_segments.py

Analyzes mapping between Daphne framefile laserdisc frame numbers and cumulative positions across concatenated .m2v segments.

### generate_ld_frame_table.py

Generates `chapter_ld_frames.inc` ROM lookup table mapping chapter IDs to laserdisc start frames by scanning XML and `chapter.id.*` files.

### refresh_frames.sh

Copies extracted video frames from `data/chapters/` subdirectories to `data/videos/frames/` for preservation across `make clean` builds.

## Development Utilities

| Tool | Purpose |
| --- | --- |
| `find_dupes.py` | Find duplicate CLASS_NOEXPORT macros in macros.inc |
| `find_long_paths.py` | Find paths > 60 chars in chapter.include (Windows limit awareness) |
| `rename_long_paths.py` | Rename chapter files to fit within path length limits |
| `deduplicate_chapters.py` | Remove duplicate .include lines from chapter.include |
| `clean_macros.py` | Remove duplicate macro definitions from macros.inc |
| `fix_macros.py` | Fix macros.inc guard structure |
| `fix_macros_final.py` | Add missing helper macros (EVENT_ACTION_PRIMARY, etc.) |
| `create_missing_headers.py` | Create missing .h headers for Event .65816 files |
| `compare_anim.py` | Compare animation file headers between two .sp files |
| `cleanup_git_tracking.sh` | Remove build artifacts from git tracking |
| `revert_wladx.sh` | Downgrade WLA-DX to 9.3 (project requirement) |

## Bundled Binaries

### superfamiconv/

Fast C++ SNES graphics converter for tiles, palettes, and tilemaps. Primary converter for the build pipeline (~100x faster than gracon.py). Pre-built Linux binary included.

### snesbrr-2006-12-13/

BRR encoder/decoder for SNES audio samples with loop handling. Ships Windows `snesbrr.exe`; build from `src/` on Linux.

### wla-dx-9.5-svn/

WLA-DX 9.3 macro assembler/linker for 65816 and SPC700. Pre-built binaries included.

**Important:** Despite the directory name `9.5-svn`, the actual version is **9.3**. Version 9.4+ breaks the build.

## Not Needed for Normal Builds

These tools are legacy, one-time-use, or optional:

- `animationWriter.py` — legacy animation writer (superseded by `animationWriter_sfc.py`)
- `gracon.py` — legacy graphics converter (superseded by superfamiconv)
- `mod2snes.py` — MOD to SPC conversion (bypassed by MSU-1 audio)
- `debugLog.py` — recursive data structure logging helper
- `userOptions.py` — lightweight CLI option parser for legacy tools
- `create_template.py` — legacy chapter handler template generator
- `exporter.py` — generic export helper
- `gimp-batch-convert-indexed.scm` — optional GIMP palette conversion
- `jpeg_to_png.py` — one-time JPEG to PNG conversion

## Platform Notes

- Python tooling requires **Python 3.10+** with Pillow and NumPy (`pip install -r requirements.txt`)
- Build tools run under **WSL** (Ubuntu); FXPAK tools run on **Windows Python**
- `mesen_mcp_server.py` runs on Windows Python, delegates WSL for builds
- Audio scripts use the standard library (`wave`); no external encoders required
