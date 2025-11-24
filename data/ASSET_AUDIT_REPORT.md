# Asset Audit Report - Dragon's Lair SNES

**Date**: 2025-11-23  
**Status**: 12 assets out of specification, 0 missing

## Executive Summary

Great news! Most sprites are now correctly sized. The remaining issues are:
- **Transparency Format**: Some sprites use palette mode (P) instead of RGBA
- **Background Dimensions**: Several backgrounds are oversized source files that need downscaling

## ✅ Assets Meeting Specification (30)

### Sprites (26 files)
- `left_arrow.gfx_sprite/0.png` ✅ (32x32 RGBA)
- `right_arrow.gfx_sprite/0.png` ✅ (32x32 RGBA)
- `up_arrow.gfx_sprite/0.png` ✅ (32x32 RGBA)
- `down_arrow.gfx_sprite/0.png` ✅ (32x32 RGBA)
- `life_car.gfx_sprite/0.png` & `1.png` ✅ (24x16 RGBA)
- `life_counter.gfx_sprite/0.png` through `9.png` ✅ (16x16 RGBA)
- `points.normal.gfx_sprite/0.png` ✅ (32x8 RGBA)
- `points.extra.gfx_sprite/0.png` ✅ (32x8 RGBA)

### Backgrounds (4 files)
- `hiscore.gfx_bg/hiscore.gfx_bg.png` ✅ (256x224 P)
- `hiscore.gfx_bg/Screenshot-RoadBlaster.mp4-39.gfx_bg.png` ✅ (256x224 P)
- `hud.gfx_directcolor/hud_xcf.png` ✅ (256x224 RGBA)

## ❌ Assets Requiring Fixes (12)

### Priority 1: Transparency Fixes (6 files)
**Issue**: Missing alpha channel (using palette mode P). Needs conversion to RGBA for proper transparency.

| File | Current | Required | Action |
|------|---------|----------|--------|
| `bang.gfx_sprite/0.png` | 46x40 P | 46x40 RGBA | Convert to RGBA |
| `bang.gfx_sprite/1.png` | 46x40 P | 46x40 RGBA | Convert to RGBA |
| `bang.gfx_sprite/2.png` | 46x40 P | 46x40 RGBA | Convert to RGBA |
| `bang.gfx_sprite/3.png` | 46x40 P | 46x40 RGBA | Convert to RGBA |
| `bang.gfx_sprite/4.png` | 46x40 P | 46x40 RGBA | Convert to RGBA |
| `super.gfx_sprite/super_small.png` | 136x64 P | Variable RGBA | Convert to RGBA |

### Priority 2: Background Resizing (6 files)
**Issue**: Source files are oversized (1024px) or wrong aspect ratio.

| File | Current | Required | Action |
|------|---------|----------|--------|
| `titlescreen.gfx_bg/titlescreen.png` | 1024x559 RGB | 256x224 RGB | Downscale to SNES resolution |
| `logo.gfx_bg/logo.gfx_bg.original.png` | 1024x890 RGB | 256x224 RGB | Downscale to SNES resolution |
| `hiscore.gfx_bg/hall_of_fame.png` | 1024x559 RGB | 256x224 RGB | Downscale to SNES resolution |
| `scoreentry.gfx_bg/nameentry.png` | 1024x890 RGB | 256x224 RGB | Downscale to SNES resolution |
| `msu1.gfx_bg/msu1.gfx_bg.png` | 256x192 P | 256x224 RGB | Add 32px height (16px top/bottom) |
| `msu1.gfx_bg/msu1.png` | 1024x890 RGB | 256x224 RGB | Downscale to SNES resolution |

## Recommended Action Plan

### Phase 1: Convert Sprites to RGBA
Use `convert` (ImageMagick) or similar tool:
```bash
# Example
convert bang.gfx_sprite/0.png -alpha on -channel A -evaluate set 100% bang.gfx_sprite/0.png
```
*Note: Ensure the background color is actually transparent in the new file.*

### Phase 2: Resize Backgrounds
```bash
# Downscale oversized backgrounds to 256x224
convert titlescreen.png -resize 256x224! titlescreen.gfx_bg.png
convert logo.gfx_bg.original.png -resize 256x224! logo.gfx_bg.png
convert hall_of_fame.png -resize 256x224! hiscore.gfx_bg.png
convert nameentry.png -resize 256x224! scoreentry.gfx_bg.png
convert msu1.png -resize 256x224! msu1.gfx_bg.png
```

### Phase 3: Verification
After fixes, run:
```bash
python3 tools/check_assets.py
```
