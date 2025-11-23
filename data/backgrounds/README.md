# Background assets audit

The following background sources live under `data/backgrounds/`:

- `hiscore.gfx_bg/Screenshot-RoadBlaster.mp4-39.gfx_bg.png` *(RoadBlaster capture, needs Dragon's Lair replacement)*
- `hud.gfx_directcolor/hud_xcf.png`
- `final_rescue.gfx_bg/final_rescue.gfx_bg.txt` *(Dragon's Lair victory screen description)*
- `logo.gfx_bg/logo.gfx_bg.png`
- `msu1.gfx_bg/msu1.gfx_bg.png`
- `scoreentry.gfx_bg/Screenshot-RoadBlaster.mp4-25.png` *(RoadBlaster capture, needs Dragon's Lair replacement)*
- `titlescreen.gfx_bg/Screenshot-RoadBlaster.mp4-24.png` *(RoadBlaster capture, needs Dragon's Lair replacement)*

RoadBlaster-derived captures must be replaced with Dragon's Lair visuals. Prompts and SNES-ready constraints for each scene live in the per-directory `.gfx_bg.txt` files.

Recreation workflow:
- Pull a matching Dragon's Lair arcade frame as composition reference, then feed the paired prompt into your image generator to produce a 256x224 output.
- Quantize to 4bpp with no more than 8 palettes (16 colors each, <=128 colors total) and verify the art stays tile-friendly before running `make` so the converter emits `.animation` data.

Spot-check guidance once new art is produced:
- Verify palette alignment with the SNES 4bpp/8-palette limits and ensure 8x8 tile seams are not visible after conversion.
- Title and logo backgrounds display immediately at boot; confirm gradients remain banded cleanly.
- High score and score entry backgrounds host text overlays—confirm readability and that the parchment center tiles without seams.
- Level complete sets are referenced by the level completion script; confirm banners sit above HUD-safe regions and that palette cycling or tiling stays stable across transitions.
