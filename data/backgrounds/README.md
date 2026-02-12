# Background Assets

The following background assets live under `data/backgrounds/`:

| Directory | Status | Description |
|-----------|--------|-------------|
| `hiscore.gfx_bg/` | Dragon's Lair art | High score / hall of fame screen |
| `logo.gfx_bg/` | Dragon's Lair art | Logo screen shown during boot intro |
| `losers.gfx_bg/` | Dragon's Lair art | Credits/losers screen |
| `msu1.gfx_bg/` | Dragon's Lair art | MSU-1 splash/init screen |
| `titlescreen.gfx_bg/` | Dragon's Lair art | Title screen background (behind menu) |
| `scoreentry.gfx_bg/` | Needs replacement | Score/name entry screen (still RoadBlaster capture) |
| `hud.gfx_directcolor/` | Custom | HUD overlay (8bpp direct color, transparent center) |
| `levelcomplete.0.gfx_bg/` | Dragon's Lair art | Level complete screen variant 0 |
| `levelcomplete.1.gfx_bg/` | Dragon's Lair art | Level complete screen variant 1 |
| `levelcomplete.2.gfx_bg/` | Dragon's Lair art | Level complete screen variant 2 |

## Recreation Workflow

To create or replace a background:
1. Prepare a 256x224 image with no more than 16 colors (4bpp, single palette):
   ```bash
   python tools/img_processor.py --input source.png \
     --output data/backgrounds/name.gfx_bg/name.gfx_bg.png \
     --width 256 --height 224 --mode cover --colors 16
   ```
2. Run `make` — the build system converts `*.gfx_bg` folders automatically via `animationWriter_sfc.py`.

## Quality Checks
- Verify palette alignment with SNES 4bpp limits and ensure 8x8 tile seams are not visible after conversion.
- Title and logo backgrounds display at boot — confirm gradients band cleanly.
- High score and score entry backgrounds host text overlays — confirm readability.
- Level complete sets are referenced by the level completion script — confirm banners sit above HUD-safe regions.
