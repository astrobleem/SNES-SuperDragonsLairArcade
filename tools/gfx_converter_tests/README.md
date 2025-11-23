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

## Tilemap Format Differences

**superfamiconv** and **gracon.py** produce tilemaps of different sizes:

| Tool | Size | Layout | Notes |
| --- | --- | --- | --- |
| superfamiconv | 1792 bytes | 32×28 tiles | Exact screen size for 256×224 |
| gracon.py | 2048 bytes | 32×32 tiles | Padded to square grid |

### Padding Details

- **Difference:** 256 bytes (4 rows × 32 tiles × 2 bytes per entry)
- **Content:** gracon adds 4 rows of zero padding at the bottom
- **Purpose:** Makes tilemaps a consistent 32×32 square grid

### Compatibility

The game engine **supports both formats** via the `tilemap.length` field in the animation structure. However, if you need gracon-compatible padding with superfamiconv's speed:

```bash
python tools/gfx_converter.py --tool superfamiconv --input image.png \
  --output-base output_name --bpp 4 --pad-to-32x32
```

This pads the 1792-byte superfamiconv output to 2048 bytes, matching gracon's format exactly.

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
