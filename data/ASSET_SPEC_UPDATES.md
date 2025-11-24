# Asset Specification Updates - Transparency Fix

## Summary

Updated all sprite and background asset specification files (`.txt` files) to clarify that assets must use **transparent PNGs with alpha channels**, NOT purple/magenta color keys for transparency. This addresses the issue where the title screen and other assets appeared with purple artifacts instead of proper transparency.

## Key Changes

### 1. Removed Color Key References
- **Removed**: References to purple/magenta as transparency colors
- **Changed**: `titlescreen.gfx_bg.txt` - Changed "glowing magenta and gold" to "glowing gold and cyan"
- **Changed**: `logo.gfx_bg.txt` - Changed "deep purple backdrop" to "deep blue backdrop"

### 2. Added Technical Specifications

All asset specification files now include:

#### For Sprites (Transparent Assets):
```
Asset Format: Transparent PNG (use alpha channel, NOT purple/magenta color key)
Required Size: [dimensions] pixels
Color Depth: 4bpp (16 colors max per palette, up to 2 palettes)
```

#### For Backgrounds (Solid Assets):
```
Asset Format: PNG image (NOT transparent - solid background)
Required Size: 256x224 pixels
Color Depth: 4bpp with up to 8 palettes (16 colors each, keep totals under 128 colors)
```

#### For HUD Overlay (Transparent Background):
```
Asset Format: Transparent PNG (use alpha channel for transparent center, NOT purple/magenta color key)
Required Size: 256x224 pixels
Color Depth: 8bpp direct color mode (mode 3/4) - allows full 256 colors but no palette effects
```

## Sprite Size Requirements

Updated sprite specifications with appropriate dimensions based on their usage:

| Sprite | Size | Notes |
|--------|------|-------|
| **Directional Arrows** (left, right, up, down) | 32x32 | Main action prompts (original size) |
| **Life Icon** | 24x16 | Small HUD sprite (original size) |
| **Life Counter Digit** | 16x16 | Small HUD digit ✅ |
| **Points (Normal & Extra)** | 32x8 | Wide text sprites (original size) |
| **Bang/Impact Effect** | 46x40 | Per frame (5-frame animation, original size) |
| **Super Bonus Indicator** | Variable | Text banner (original size) |

**Note**: These sizes reflect the original RoadBlaster assets that are currently working. The SNES supports 8x8, 16x16, 32x32, and 64x64 sprites - the current 32x32 arrows are perfectly valid.

## Background Size Requirements

All backgrounds are standardized to **256x224 pixels** (SNES resolution):

- Title Screen
- Logo Screen
- High Score Screen
- Score Entry Screen
- MSU1 Video Placeholder
- HUD Overlay (Direct Color)

## Files Updated

### Sprites (11 active + legacy)
- ✅ `left_arrow.txt`
- ✅ `right_arrow.txt`
- ✅ `up_arrow.txt`
- ✅ `down_arrow.txt`
- ✅ `life_car.txt`
- ✅ `life_counter.txt`
- ✅ `points.normal.txt`
- ✅ `points.extra.txt`
- ✅ `bang.txt`
- ✅ `super.txt`
- Legacy files (brake, dashboard, turbo, steering_wheel.*) - kept for reference

### Backgrounds (6 files)
- ✅ `titlescreen.gfx_bg/titlescreen.gfx_bg.txt`
- ✅ `logo.gfx_bg/logo.gfx_bg.txt`
- ✅ `hiscore.gfx_bg/hiscore.gfx_bg.txt`
- ✅ `scoreentry.gfx_bg/scoreentry.gfx_bg.txt`
- ✅ `msu1.gfx_bg/msu1.gfx_bg.txt`
- ✅ `hud.gfx_directcolor/hud.gfx_directcolor.txt`

## Next Steps

To regenerate assets with proper transparency:

1. **For Sprites**: Generate new transparent PNG files with alpha channels at the specified dimensions
   - Use the updated prompts in each `.txt` file
   - Ensure transparent backgrounds use alpha channel, not color keys
   - Place frames in corresponding `.gfx_sprite` directories

2. **For Backgrounds**: Generate new solid PNG backgrounds at 256x224
   - Use the updated prompts (without purple/magenta references)
   - These should NOT be transparent (solid backgrounds)
   - Place in corresponding `.gfx_bg` or `.gfx_directcolor` directories

3. **For HUD Overlay**: Generate transparent PNG with alpha channel
   - Center area must be fully transparent (alpha = 0)
   - Border decorations should be opaque
   - Uses 8bpp direct color mode for richer colors

4. **Rebuild**: Run `make USE_SUPERFAMICONV=1` to rebuild with new assets

## Technical Notes

- The build system uses `superfamiconv` which properly handles PNG alpha channels
- Transparency is handled at the PNG level, not through color key substitution
- Sprites use 4bpp (16 colors) with up to 2 palettes
- Backgrounds use 4bpp (16 colors per palette) with up to 8 palettes
- HUD overlay uses 8bpp direct color mode (256 colors, no palettes)
- All assets use 8x8 tile-based rendering
