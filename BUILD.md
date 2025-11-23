# Build System Documentation

## Quick Build

### Standard Build (using gracon.py)
```bash
wsl bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make"
```

### Fast Build (using superfamiconv - ~100x faster)
**Windows:**
```cmd
build_with_superfamiconv.bat
```

**WSL/Linux:**
```bash
export USE_SUPERFAMICONV=1
make
```

## Pre-Build Validation

Test all background assets before building to catch conversion errors early:

```bash
# From Windows PowerShell
wsl python3 tests/test_background_assets.py

# From WSL
python3 tests/test_background_assets.py
```

This will:
- Test all background images in `data/backgrounds/`
- Catch recursion errors, timeouts, and other conversion issues
- Report which specific assets are problematic
- Complete in ~30 seconds vs waiting for full build to fail

## Graphics Converter Options

The Makefile supports two graphics converters:

### gracon.py (default)
- Pure Python implementation
- Slower (~100s per large image)
- More compatible with edge cases
- Use when superfamiconv has issues

### superfamiconv (optional)
- Fast C++ implementation (~1s per image)
- Requires `--pad-to-32x32` flag for compatibility
- Enable via `USE_SUPERFAMICONV=1` environment variable

## Switching Converters

The Makefile automatically detects the `USE_SUPERFAMICONV` environment variable:

```makefile
ifdef USE_SUPERFAMICONV
gfxconverter := ./tools/gfx_converter.py --tool superfamiconv --pad-to-32x32
endif
```

Both converters produce identical output when using the `--pad-to-32x32` flag.

## Build Output

Successful build creates:
- `build/SuperDragonsLairArcade.sfc` - SNES ROM file
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

### Build hangs on graphics conversion
- Switch to superfamiconv for faster builds
- Or check `ps aux | grep gracon` to see which file is processing
