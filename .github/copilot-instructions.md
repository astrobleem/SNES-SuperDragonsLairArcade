# GitHub Copilot Instructions for SNES Super Dragon's Lair Arcade

This repository contains a complete SNES ROM project that recreates Dragon's Lair arcade as a full-motion-video game using the MSU-1 enhancement chip.

## Project Overview

**Super Dragon's Lair Arcade** is an FMV retheme of RoadBlaster for SNES, targeting real NTSC hardware with MSU-1 audio/video support on SD2SNES/FXPAK Pro. The project includes:
- 65816 assembly code for SNES ROM
- SPC700 assembly for audio processor
- Python-based asset processing pipeline
- MSU-1 video/audio packaging tools
- Comprehensive build system using Make and WLA-DX assembler

## Critical Context

### Build System
- **Platform:** Linux/WSL (Ubuntu) required
- **Assembler:** WLA-DX 9.5-svn (included, must be compiled: `./tools/wla-dx-9.5-svn/unix.sh 4`)
- **Primary Build:** `make` or `make clean && make`
- **Fast Build:** `USE_SUPERFAMICONV=1 make` (100× faster graphics conversion)
- **Output:** `build/SuperDragonsLairArcade.sfc` (SNES ROM file)
- **Pre-build validation:** `python3 tests/check_image_dimensions.py` (1 second check)

### Python Toolchain (Python 3.10+)
All Python scripts are **Python 3 compatible**. Key tools:
- `tools/animationWriter.py` - Converts graphics to SNES animation format (SP format)
- `tools/animationWriter_sfc.py` - Version optimized for superfamiconv workflow
- `tools/gracon.py` - Python-based graphics converter (legacy, slow but reliable)
- `tools/gfx_converter.py` - Unified wrapper for superfamiconv or gracon
- `tools/img_processor.py` - Image resizing/quantization to SNES specs
- `tools/mod2snes.py` - MOD music to SPC700 format converter
- `tools/msu1blockwriter.py` - Packages MSU-1 data files
- `tools/msu1pcmwriter.py` - Converts WAV to MSU-1 PCM format
- `tools/xmlsceneparser.py` - Chapter/event XML processor

Install dependencies: `pip install -r requirements.txt` (primarily Pillow for image processing)

### Asset Pipeline

#### Graphics (SNES native format)
1. **Backgrounds:** 256×224 pixels, 16 colors (4bpp), processed via `img_processor.py`
2. **Sprites:** 4bpp with 2 palettes, optimized for OAM
3. **Direct Color:** 8bpp mode for HUD overlays
4. **Conversion:** Build system auto-converts `.png` files using `animationWriter.py`
5. **Performance:** superfamiconv is ~100× faster than gracon.py (1s vs 96s per image)

#### Audio
- **SPC700:** MOD format songs converted via `mod2snes.py`
- **BRR:** Sound effects in `.brr` format (SNES ADPCM), converted from WAV
- **MSU-1:** CD-quality PCM audio for video tracks
- **Registration:** All sounds must be registered in `src/object/audio/spcinterface.h`

#### Video (MSU-1)
- Chapters defined in `data/events/*.xml` (516 total chapters)
- Frame conversion pipeline: ffmpeg → gracon.py → animationWriter.py → msu1blockwriter.py
- MSU-1 data files packaged with ROM for SD2SNES/FXPAK Pro
- **Video timing:** Must be 23.976 fps (not 29.97 fps from Daphne sources)

### File Structure
```
src/           - 65816 assembly source code
data/
  backgrounds/ - PNG images for title/score screens (9 backgrounds)
  sprites/     - PNG sprites for arrows/effects (16 sprite types)
  sounds/      - WAV/BRR audio files
  chapters/    - Chapter definitions and event markers
  events/      - XML chapter scripts (516 files)
tools/         - Python asset converters and build utilities
tests/         - Test suite (pytest)
  fixtures/    - Test data (dirk_standin.png, etc.)
build/         - Generated output (ROM, intermediate files)
schwag/        - Marketing materials and documentation
```

### Testing Strategy
- **Framework:** pytest for Python tools
- **Coverage:** Test files in `tests/` directory
- **Key tests:**
  - `tests/check_image_dimensions.py` - Asset validation (fast, 1 second)
  - `tests/test_background_assets.py` - Full conversion test (slow, ~5 minutes)
  - `tests/test_tools.py` - Tool integration tests (animationWriter, MSU1 tools)
  - `tests/test_tools_smoke.py` - Basic --help functionality
  - `tests/test_gracon_conversion.py` - End-to-end gracon test
  - `tests/test_lua_scene_exporter.py` - Lua scene conversion
- **Run tests:** `pytest` or `python3 -m pytest`
- **Timeout protection:** Tests include 30s timeouts to prevent hanging

### Code Style and Conventions

#### Assembly (65816/SPC700)
- Follow WLA-DX syntax
- Use `.65816` extension for SNES CPU code
- Use `.spc700` extension for audio processor code
- Include files use `.inc` extension
- Respect existing memory map and register usage
- When adding sprites: Create both asset directory and code files (`src/object/sprite/<name>.65816` and `.h`)
- Register sprites in `src/object/sprite/abstract.Sprite.h` in the `SpriteAnimationLUT`

#### Python
- **Python 3.10+ only** (all tools migrated from Python 2)
- Follow PEP 8 style guidelines
- Use `black` for formatting, `flake8` for linting
- Add docstrings for public functions
- Handle binary/text properly (bytes vs strings)
- No silent try/except wrappers - fix root causes

#### Common Pitfalls
- **TabError:** Scripts were normalized, but verify with `python -m tabnanny <file>`
- **Integer division:** Use `//` not `/` for integer division
- **Bytes/strings:** Python 3 requires explicit encoding/decoding
- **Image processing:** Pillow methods may return different types (RGB vs indexed)
- **Video timing:** Daphne videos are 29.97 fps but XMLs expect 23.976 fps (requires conversion)
- **ffmpeg parameters:** `-ss` and `-t` must come BEFORE `-i` for proper chapter extraction

### Documentation Structure
- `README.md` - Project overview, status, quick start
- `BUILD.md` - Detailed build instructions and troubleshooting
- `AGENTS.md` - Repository-wide agent guidance and historical log
- `CONTRIBUTING.md` - Contribution guidelines
- `tools/README.md` - Complete graphics tools documentation
- `tools/gfx_converter_tests/README.md` - Graphics converter comparison and testing
- `tests/README.md` - Complete test documentation with coverage details
- `data/backgrounds/README.md` - Background asset status
- `data/sprites/README.md` - Sprite inventory and system integration
- `data/sounds/README.md` - Sound system and asset documentation
- `data/events/README.md` - Chapter XML reference
- `data/chapter_event_inventory.md` - Event coverage tracking (516 chapters, 0 unmapped)
- `src/README.md` - Code flow documentation
- `schwag/README.md` - Marketing materials documentation

### Current Project Status

#### Completed ✅
- WLA-DX assembler built and working
- Superfamiconv integration (100× faster builds)
- Python 3 migration complete for all tools
- Graphics pipeline modernized (img_processor.py, gfx_converter.py)
- Asset descriptions updated to Dragon's Lair theme
- Sound system audited and registered
- Chapter event inventory complete (516 chapters, 0 unmapped)
- Comprehensive test suite with real data validation
- Video timing verification tools and bug fixes

#### In Progress 🔄
- Background artwork generation (9 backgrounds described, 1 processed)
- Sprite artwork generation (16 sprites described, placeholders in use)

#### Future Work ⏳
- Dragon's Lair video capture and processing
- Dragon's Lair audio extraction and MSU-1 packaging
- Complete FMV/audio integration

### Important Constraints

1. **No commercial assets included** - Users must provide Dragon's Lair video/audio
2. **SNES hardware limits:**
   - 256×224 resolution (NTSC)
   - 4bpp (16 colors) or 8bpp (256 colors) modes
   - 512 tiles maximum per frame for video
   - BRR audio format for SPC700
   - 64KB SPC700 RAM for all audio code, music, and samples
3. **MSU-1 requirements:**
   - SD2SNES or FXPAK Pro hardware
   - PCM audio files alongside ROM
   - MSU data files for video streaming

### Working with This Repository

#### Making Changes
1. **Test existing build first:** `make clean && make` to establish baseline
2. **Validate assets:** Run `python3 tests/check_image_dimensions.py` before building
3. **Use fast builds:** Set `USE_SUPERFAMICONV=1` for development iteration
4. **Run tests:** `pytest` after Python tool changes
5. **Check for regressions:** Build and test ROM in emulator (snes9x/bsnes)

#### Adding New Assets

**Backgrounds:**
```bash
# Step 1: Process with img_processor.py
python tools/img_processor.py \
  --input source_artwork.png \
  --output data/backgrounds/name.gfx_bg/name.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

# Step 2: Build handles the rest
make
```

**Sprites:**
1. Create directory: `data/sprites/<name>.gfx_sprite/`
2. Add frame PNG files (sorted alphabetically for animation order)
3. Create code files: `src/object/sprite/<name>.65816` and `.h`
4. Register in `src/object/sprite/abstract.Sprite.h`
5. Build with `make`

**Sounds:**
1. Add WAV file to `data/sounds/` (use naming: `name.sfx_normal.wav` or `name.sfx_loop.wav`)
2. Register in `src/object/audio/spcinterface.h`:
   - Add enum entry to `SAMPLE.0.*`
   - Add export statement
   - Create sample header (volume, pitch, ADSR, gain)
   - Add `.incbin` line in `SamplePack0`
3. Build with `make`

#### Debugging
- **Build failures:** Check WLA-DX output for assembly errors
- **Graphics issues:** Verify dimensions (256×224), color count (≤16), and file format (PNG)
- **Python errors:** Check Python 3 compatibility (bytes/strings, integer division)
- **Asset validation:** Run `tests/check_image_dimensions.py` for quick diagnosis
- **Video timing:** Use `tools/test_chapter_extraction.sh` to verify frame extraction

### Animation Format Details

The `animationWriter.py` tool produces binary files in "SP" format:
- **Header:** Magic bytes `b'SP'` followed by 7-byte metadata
- **Structure:** Frame count, max tile size, max palette size, bpp
- **Frame pointers:** 2 bytes per frame pointing to frame data
- **Validation:** Tests check header integrity and data presence

### Tilemap Format Compatibility

**superfamiconv** and **gracon.py** produce different tilemap sizes:
- superfamiconv: 1792 bytes (32×28 tiles, exact screen size)
- gracon.py: 2048 bytes (32×32 tiles, padded)

The engine supports both via `tilemap.length` field. Use `--pad-to-32x32` flag with gfx_converter.py for gracon-compatible output.

### References
- **Main README:** `/README.md` - Start here for project overview
- **Build guide:** `/BUILD.md` - Detailed build instructions
- **Agent log:** `/AGENTS.md` - Historical notes and lessons learned
- **Tools guide:** `/tools/README.md` - Complete asset pipeline documentation
- **Test guide:** `/tests/README.md` - Complete test documentation

### Notes for AI Assistants
- Always reference existing documentation before making changes
- Preserve the Dragon's Lair theme in assets and code comments
- Maintain compatibility with NTSC SNES hardware constraints
- Test changes in both emulator and consider real hardware behavior
- Keep the legacy RoadBlaster engine intact while swapping assets
- Update the Agent Log in AGENTS.md when completing significant work
- When adding sprites or sounds, remember BOTH asset and code registration are required
- Video timing is critical: verify 23.976 fps conversion for chapter extraction
- Use real test data (from data/ directory) in tests, not just synthetic data
- Include timeouts in tests to prevent hanging during CI runs
- Legacy sounds/sprites (brake, turbo, steering wheels) are marked but retained for reference
