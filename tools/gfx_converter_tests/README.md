# Graphics Converter Test Files

This directory contains test files and sample outputs generated during the development and verification of `gfx_converter.py` and `img_processor.py`.

## Contents

- `create_placeholder.py` - Script to generate a simple indexed test image (256x224)
- `create_large_image.py` - Script to generate a larger test image for resizing verification
- `high_score_placeholder.png` - Test image (256x224, indexed color)
- `large_test.png` - Large test image (500x500) for resize testing
- `processed_cover.png` - Result of processing large image with 'cover' mode
- Various `.palette`, `.tiles`, `.tilemap` files - Test outputs from both `superfamiconv` and `gracon.py`

## Test Outputs

The test outputs demonstrate:
- **superfamiconv** outputs: `test_sfc_new.*`
- **gracon** outputs: `test_gracon_new.*`
- Both tools produce `.palette`, `.tiles`, and `.tilemap` files with consistent naming

## Performance Comparison

| Tool | Processing Time | Output Quality |
| --- | --- | --- |
| superfamiconv | < 1s | Excellent |
| gracon.py | ~96s | Excellent |

**Recommendation:** Use `superfamiconv` via `gfx_converter.py` for faster builds.

## Quick Start Example

Process a background image for the build system:

```bash
# Step 1: Resize and quantize to 16 colors
python tools/img_processor.py \
  --input source_artwork.png \
  --output data/backgrounds/name.gfx_bg/name.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16

# Step 2: Build handles the rest
make
```

The build system will automatically convert all `*.gfx_bg` folders to `.animation` files.
