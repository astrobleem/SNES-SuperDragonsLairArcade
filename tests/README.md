# Tests

This directory contains automated tests for the SNES Dragon's Lair Arcade tooling and conversion pipeline. Tests are written using pytest and can be run individually or as a suite.

## Running Tests

### Prerequisites
```bash
# Install pytest if not already installed
pip install pytest

# Or install all requirements
pip install -r ../requirements.txt
```

### Run All Tests
```bash
# From project root
python -m pytest tests/ -v

# Or from tests directory
python -m pytest -v
```

### Run Specific Test Files
```bash
# Tool integration tests
python -m pytest tests/test_tools.py -v

# Smoke tests (basic --help functionality)
python -m pytest tests/test_tools_smoke.py -v

# Gracon conversion tests
python -m pytest tests/test_gracon_conversion.py -v

# Lua scene exporter tests
python -m pytest tests/test_lua_scene_exporter.py -v
```

### Run Individual Tests
```bash
# Test a specific tool
python -m pytest tests/test_tools.py::test_animation_writer -v
python -m pytest tests/test_tools.py::test_msu1pcmwriter -v
python -m pytest tests/test_tools.py::test_msu1blockwriter -v
```

## Test Coverage

### Tool Integration Tests (`test_tools.py`)

#### `test_animation_writer`
**Purpose:** Comprehensive validation of `animationWriter.py` using real sprite frames.

**What it tests:**
- Uses 5 real PNG frames from `data/sprites/bang.gfx_sprite/` (not synthetic test data)
- Validates the binary output format according to the SP header specification:
  - Header magic bytes (`b'SP'`)
  - Header structure (9 bytes total)
  - Frame count (5 frames)
  - Max tile size, max palette size, and bpp fields
  - Frame pointer table (2 bytes per frame)
  - File contains actual data beyond headers
- Includes 30-second timeout to prevent hanging (addressing Python 2→3 conversion issues)

**Why it matters:** This test ensures the animation writer produces valid binary files that the SNES engine can load, catching format regressions early.

#### `test_msu1pcmwriter`
**Purpose:** Validates MSU1 PCM audio file generation.

**What it tests:**
- Creates a synthetic WAV file
- Converts it to MSU1 PCM format
- Validates the MSU1 header (`b'MSU1'`)

#### `test_msu1blockwriter`
**Purpose:** Validates MSU1 video block packaging.

**What it tests:**
- Creates mock chapter data (tiles, tilemap, palette, audio)
- Packages into MSU1 format
- Validates the S-MSU1 header

### Smoke Tests (`test_tools_smoke.py`)

Basic sanity checks that tools can be invoked with `--help` without crashing:
- `gracon.py --help`
- `xmlsceneparser.py --help`
- `mod2snes.py --help`
- `animationWriter.py --help`
- `msu1blockwriter.py --help`

These tests verify Python 3 compatibility and catch syntax/import errors.

### Gracon Conversion Tests (`test_gracon_conversion.py`)

#### `test_conversion_defaults`
**Purpose:** End-to-end test of `gracon.py` with real image conversion.

**What it tests:**
- Converts a test image (`fixtures/dirk_standin.png`)
- Validates output files exist (`.tiles`, `.palette`, `.tilemap`, `.sample.png`)
- Checks that tile data is non-empty

**Why it matters:** Gracon had significant Python 2→3 performance issues that were fixed; this test ensures conversions complete successfully.

### Lua Scene Exporter Tests (`test_lua_scene_exporter.py`)

Tests the `lua_scene_exporter.py` tool that converts DirkSimple-style `game.lua` scene tables into chapter scripts.

## Test Data

### Fixtures (`fixtures/`)
- `dirk_standin.png` - Test image for gracon conversion tests
- Other test assets as needed

### Real Data
Tests use real project data where appropriate:
- `data/sprites/bang.gfx_sprite/*.png` - Real sprite animation frames for animationWriter tests
- This ensures tests validate actual use cases, not just synthetic scenarios

## Timeout Protection

Several tests include timeout protection (typically 30 seconds) to prevent hanging:
- `test_animation_writer` - 30s timeout
- `test_gracon_conversion` - No explicit timeout (relies on pytest defaults)

**Why:** During Python 2→3 conversion, tools like `gracon.py` had performance regressions that caused hanging. Timeouts ensure tests fail fast rather than blocking CI/development.

## Known Issues and Considerations

### Python 2→3 Conversion (COMPLETE ✅)
All tools were originally written for Python 2 and have been successfully migrated to Python 3. Key issues that were fixed:
- **mod2snes.py**: Fixed bytes/string comparison in MOD file validation and integer division for repeat start calculations  
- **gracon.py**: Replaced `chr()` with `bytes()` for binary file writes in legacy functions
- **xmlsceneparser.py**: Fixed integer division in time formatting for ffmpeg commands
- **String/bytes handling**: Proper encoding/decoding in binary file operations across all tools
- **Performance**: Optimizations to `gracon.py` for efficient large image processing

All tools now run correctly on Python 3.10+. Tests help catch any regressions.

### Test Isolation
Tests use pytest's `tmp_path` fixture to ensure:
- No pollution of the project directory
- Parallel test execution is safe
- Easy cleanup after test runs

## Adding New Tests

When adding tests for new tools or features:

1. **Use real data when possible** - Tests with synthetic data often miss real-world edge cases
2. **Validate output format** - Don't just check file existence; validate structure and content
3. **Include timeouts** - Prevent hanging, especially for tools that process images or large data
4. **Document what you're testing** - Add docstrings explaining the test's purpose and what it validates
5. **Use descriptive assertions** - Include error messages that show expected vs. actual values

Example:
```python
def test_my_tool(tmp_path):
    """Test myTool with real input data and validate output format."""
    # Setup with real data
    source_data = ROOT / "data" / "real_asset.png"
    
    # Run with timeout
    result = subprocess.run(
        [sys.executable, str(TOOLS / "myTool.py"), ...],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # Validate with descriptive assertions
    assert result.returncode == 0, f"Tool failed: {result.stderr}"
    assert output.exists(), "Output file not created"
    
    # Validate format
    with open(output, "rb") as f:
        header = f.read(4)
        assert header == b"MYMT", f"Expected magic 'MYMT', got {header}"
```

## Continuous Integration

Tests are designed to run in CI environments:
- No interactive prompts
- Deterministic output
- Fast execution (< 2 minutes for full suite)
- Clear failure messages

## Future Test Improvements

- [ ] Add tests for `xmlsceneparser.py` with real XML fixtures
- [x] Add tests for `mod2snes.py` with sample MOD files - COMPLETE (uses `trans_atlantic.mod`)
- [ ] Add performance regression tests for gracon.py
- [ ] Add integration tests for full pipeline (XML → gracon → animationWriter → MSU1)
- [ ] Add tests for edge cases (empty frames, oversized images, invalid palettes)

