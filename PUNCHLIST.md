# PUNCHLIST — Super Dragon's Lair Arcade

All items below are cosmetic or low-priority. None are release blockers. The game is fully playable on real hardware across all 3 game modes with 28/28 automated scene tests passing.

Outstanding issues, stubs, and incomplete work. Organized by priority.

---

## Category 1: Event Stubs (MODERATE)

4 event types are referenced in chapter data tables but immediately self-kill. Chapters that rely on them have missing interactions (the chapter always falls through to its default timeout result):

| Event Class | File | What It Should Do |
|-------------|------|-------------------|
| `Event.target` | `Event.target.65816` | Target-tracking input events |
| `Event.show_help` | `Event.show_help.65816` | Display help overlays during gameplay |
| `Event.change_dash` | `Event.change_dash.65816` | Modify HUD/dashboard state |
| `Event.hide_sunscreen` | `Event.hide_sunscreen.65816` | Hide screen overlay effect |

Each has a play() method that immediately kills itself (`; debug, kill immediately`).

## Category 2: Dead Code

### 2a: 16 scene-specific event classes — compiled but linker-discarded

These have full init/play/kill implementations but no chapter data table references them. The linker strips them from the ROM (visible as DISCARD messages during build). They would need chapter data entries pointing to their `CLS.PTR` to activate.

Files: `Event.crypt.65816`, `Event.falling_platform_phase.65816`, `Event.flaming_ropes_hazard.65816`, `Event.flaming_ropes_route.65816`, `Event.flying_horse_collision.65816`, `Event.flying_horse_lane.65816`, `Event.giddy_goons_grapple.65816`, `Event.giddy_goons_swarm.65816`, `Event.rolling_balls_ball.65816`, `Event.rolling_balls_crush.65816`, `Event.tentacle_room_grab.65816`, `Event.tentacle_room_path.65816`, `Event.throne_room_state.65816`, `Event.tilting_room_navigation.65816`, `Event.underground_river_chain.65816`, `Event.underground_river_phase.65816`

### 2b: 26 cutscene subclasses — compiled but linker-discarded

All in `Event.cutscene.65816`. Scene-specific death/transition cutscenes that are never referenced because `xmlsceneparser.py` maps all cutscene events to the generic `Event.cutscene` class.

### 2c: Other dead code

| Item | File | Notes |
|------|------|-------|
| `none.script` | `src/none.script` | `TRIGGER_ERROR E_Todo`. Included but never referenced at runtime. Diagnostic placeholder. |
| `Event.Test_Script` | `Event.Test_Script.65816` | Template file, linker-discarded. |
| `Event.touch` | `Event.touch.65816` | Stub event class with zero chapter data references. Sword/action input handled by `Event.direction_generic`. |

## Category 3: Minor Code Issues

| Item | File | Issue |
|------|------|-------|
| Legacy sample enum names | `spcinterface.h` | Names still `SAMPLE.0.SHURIKEN`, `SAMPLE.0.TECHNIQUE`, etc. from RoadBlaster. Cosmetic only. |
| `SpcPlaySoundEffectObjectXPos` stub | `spcinterface.65816:1012` | Panning method is `TRIGGER_ERROR E_Todo`. Never called, but would crash if used. |
| `Brightness.fadeTo` range guard | `brightness.65816:46` | Out-of-range brightness triggers `E_Todo` instead of clamping. Defensive crash on invalid input. |
| ~23 active event classes have OBJID `$ffff` | Generated `.h` files | Collides with `oopCreateNoPtr`. Harmless because `kill.byId` is never used on events, but technically incorrect. |

## Category 4: Build & Tooling

| Item | File | Issue |
|------|------|-------|
| ~~Hardcoded user paths~~ | ~~`tools/*.py`~~ | ~~RESOLVED: All scripts now use `tools/paths.py` for shared path resolution. FFmpeg, Daphne, and output paths configurable via `project.conf` or env vars.~~ |
| `generate_manifest.py` obsolete | `tools/generate_manifest.py` | Superseded by dynamic PCM scanning. Can be deleted. |
| Makefile commented-out code | `Makefile:94,223` | Unused `convertedframefolder` var, commented-out chapter processing line. |
| `gfx_converter.py` duplicate print | `tools/gfx_converter.py:45,47` | Same padding message printed twice. |
| `xmlsceneparser.py` symbol length warning | `tools/xmlsceneparser.py:580` | Warns when event type exceeds 13 chars. No actual breakage, but noisy (fires for every `direction_generic` event). |

## Category 5: Assets

| Item | Location | Issue |
|------|----------|-------|
| Legacy sprites | `data/sprites/` | Dashboard, steering_wheel (3 variants), brake sprites are unused but compiled into ROM. |
| ROM header checksums hardcoded | `src/core/boot.65816:112-113` | "Invalid Checksum" in emulators. Known wla-dx `.snesheader` workaround. |

## Category 6: MSU-1 Video Frame Alignment (LOW)

Video frames extracted from Daphne .m2v segments show minor misalignment in some chapters — displayed content doesn't precisely match expected laserdisc frame.

**Possible causes:**
- `fps=24000/1001` filter converts 29.97i to 23.976p before `trim` — rounding error at segment boundaries
- Cumulative duration drift across 204 segments in `generate_segment_timing.py`
- DirkSimple frame numbers may not map 1:1 to Daphne segment internal frame positions
- `yadif` field order assumption (TFF vs BFF) could shift frames by half a field
