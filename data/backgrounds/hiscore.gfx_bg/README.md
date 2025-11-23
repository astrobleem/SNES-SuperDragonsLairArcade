# High Score Background

This folder contains the assets for the high score screen background in Dragon's Lair.

## Files in This Directory

| File | Purpose | Size | Notes |
| --- | --- | --- | --- |
| `hiscore.gfx_bg.png` | **Processed background image** | 11,940 bytes | 256×224, 16 colors indexed |
| `hiscore.gfx_bg.png.original` | Original high-res artwork | 5.4 MB | Backup of source before processing |
| `hiscore.gfx_bg.txt` | Design spec/prompt | 633 bytes | Describes intended look and constraints |
| `Screenshot-RoadBlaster.mp4-39.gfx_bg.png` | Reference screenshot | 17,750 bytes | Reference from RoadBlaster |

## How It Works

### 1. Image Preparation

The original high-resolution image (`hiscore.gfx_bg.png.original`) was processed to SNES specifications:

```bash
python tools/img_processor.py \
  --input data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.png.original \
  --output data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.png \
  --width 256 --height 224 --mode cover --colors 16
```

**Processing steps:**
- **Resize:** 256×224 pixels (SNES background resolution)
- **Mode:** `cover` - maintains aspect ratio, crops to fill
- **Quantize:** 16 colors (single 4bpp palette)

### 2. Build Process

When you run `make`, the build system:

1. **Finds** the `*.gfx_bg` folder
2. **Scans** for PNG files inside (in this case, just `hiscore.gfx_bg.png`)
3. **Converts** using `animationWriter.py`:
   - Calls `gracon.py` with `gfx_bg_flags` settings
   - Generates tiles (deduplicated 8×8 pixel blocks)
   - Creates palette data
   - Builds tilemap (which tiles go where)
4. **Packs** everything into: `build/data/backgrounds/hiscore.gfx_bg.animation`

### 3. Output Format

The final `.animation` file contains:

```
[Header: 9 bytes]
  "SP" magic
  Max tile size
  Max palette size
  Frame count (1 for static backgrounds)
  Bits per pixel
  
[Frame data]
  Tiles: Deduplicated 8×8 pixel blocks in SNES bitplane format
  Tilemap: 32×32 grid (2048 bytes) mapping tiles to screen positions
  Palette: 16 colors in SNES RGB555 format (32 bytes)
```

## Technical Constraints

### SNES Background Mode 1 (4bpp)

- **Resolution:** 256×224 pixels
- **Tile size:** 8×8 pixels
- **Grid:** 32×28 tiles (32×32 with padding)
- **Colors:** 16 colors per palette, up to 8 palettes (128 total)
- **This image:** Single palette (16 colors)

### Why 16 Colors?

Using a single palette (16 colors) ensures:
- Simple palette swaps possible
- Minimal VRAM usage
- Clean quantization without palette bleeding
- Compatible with text overlays

### Makefile Settings

From `makefile` line 26:
```makefile
gfx_bg_flags := $(verify) -optimize on -tilethreshold 15 -palettes 8 -bpp 4 -mode bg
```

- `optimize on`: Removes duplicate tiles
- `tilethreshold 15`: Aggressive deduplication tolerance
- `palettes 8`: Allows up to 8 palettes (128 colors)
- `bpp 4`: 4 bits per pixel (16 colors per palette)
- `mode bg`: Background mode (vs sprite mode)

## Modifying This Background

To replace with new artwork:

1. **Prepare your image** (any resolution, any colors):
   ```bash
   python tools/img_processor.py \
     --input your_artwork.png \
     --output data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.png \
     --width 256 --height 224 --mode cover --colors 16
   ```

2. **Rebuild:**
   ```bash
   make
   ```

3. **Test** the ROM with your new background

## Design Notes

From `hiscore.gfx_bg.txt`:
- Emphasize large flat panels for clean palette quantization
- Leave vertical padding for score text overlays
- Keep parchment center light and low-detail for readability
- Medieval/castle theme matching Dragon's Lair aesthetic

## See Also

- `tools/README.md` - Full documentation of graphics tools
- `tools/img_processor.py` - Image preparation tool
- `tools/animationWriter.py` - Animation/background packer
- `tools/gracon.py` - SNES graphics converter
