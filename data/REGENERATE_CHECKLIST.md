# Assets to Regenerate - Quick Reference

## HIGH PRIORITY - Transparency Fixes (Convert to RGBA)

### Bang Effect - 46x40 RGBA transparent (5 frames)
- [ ] `data/sprites/bang.gfx_sprite/0.png`
- [ ] `data/sprites/bang.gfx_sprite/1.png`
- [ ] `data/sprites/bang.gfx_sprite/2.png`
- [ ] `data/sprites/bang.gfx_sprite/3.png`
- [ ] `data/sprites/bang.gfx_sprite/4.png`

**Prompt**: `data/sprites/bang.txt`

### Super Indicator - Variable RGBA transparent
- [ ] `data/sprites/super.gfx_sprite/super_small.png` (or rename to 0.png)

**Prompt**: `data/sprites/super.txt`

---

## BACKGROUNDS - 256x224 RGB (solid, no transparency)

### Title Screen
- [ ] `data/backgrounds/titlescreen.gfx_bg/titlescreen.gfx_bg.png`

**Prompt**: `data/backgrounds/titlescreen.gfx_bg/titlescreen.gfx_bg.txt`

### Logo Screen
- [ ] `data/backgrounds/logo.gfx_bg/logo.gfx_bg.png`

**Prompt**: `data/backgrounds/logo.gfx_bg/logo.gfx_bg.txt`

### High Score Screen
- [ ] `data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.png` (already exists, but verify)

**Prompt**: `data/backgrounds/hiscore.gfx_bg/hiscore.gfx_bg.txt`

### Score Entry
- [ ] `data/backgrounds/scoreentry.gfx_bg/scoreentry.gfx_bg.png`

**Prompt**: `data/backgrounds/scoreentry.gfx_bg/scoreentry.gfx_bg.txt`

### MSU1 Placeholder
- [ ] `data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.png`

**Prompt**: `data/backgrounds/msu1.gfx_bg/msu1.gfx_bg.txt`

---

## Already Correct ✅

### Sprites
- ✅ Directional Arrows (32x32 RGBA)
- ✅ Life Icons (24x16 RGBA)
- ✅ Life Counter Digits (16x16 RGBA)
- ✅ Points Popups (32x8 RGBA)

### Backgrounds
- ✅ `hud.gfx_directcolor/hud_xcf.png` - 256x224 RGBA

---

## Generation Checklist

For each asset:

1. [ ] Read the prompt from the corresponding `.txt` file
2. [ ] Generate at the exact size specified above
3. [ ] For sprites: Ensure transparent background using alpha channel (RGBA mode)
4. [ ] For backgrounds: Ensure solid background (RGB mode, no alpha)
5. [ ] Save with exact filename shown above
6. [ ] Run `python3 tools/check_assets.py` to verify

---

## Quick Commands

### Check all assets
```bash
python3 tools/check_assets.py
```

### Rebuild after updating assets
```bash
make clean
make USE_SUPERFAMICONV=1
```
