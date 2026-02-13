# PUNCHLIST — Super Dragon's Lair Arcade

Outstanding issues, stubs, and incomplete work. Organized by priority.

---

## Category 1: Game Flow — Crash-on-Reach Stubs (CRITICAL)

| Item | File | Status |
|------|------|--------|
| ~~level2 through level9 are stubs~~ | ~~`src/level2.script` – `src/level9.script`~~ | **RESOLVED** — Deleted. Level system replaced by direct cross-scene transitions in chapter data via `data/scene_transitions.json`. |
| ~~game_over.script is a stub~~ | ~~`src/game_over.script`~~ | **RESOLVED** — Implemented: kills chapters/events/dash/HDMA/Msu1, resets screen mode, clears VRAM/CGRAM, launches title_screen. |
| none.script is a stub | `src/none.script` | `TRIGGER_ERROR E_Todo`. Referenced as a fallback; should either be implemented or all references removed. Left as diagnostic. |
| ~~Cross-scene transitions missing~~ | `data/scene_transitions.json` | **RESOLVED** — 30 terminal chapters now auto-transition to the next scene via `EventResult.playchapter`. Covers all 15 exit_room chapters + 14 traced success-path terminals + the_dragons_lair_endgame. `xmlsceneparser.py` reads `-scene_transitions` JSON to override `Event.chapter` results. |

## Category 2: Event Class Issues (MODERATE)

### 2a: Active stubs — fire during gameplay but do nothing

These 5 event types are referenced in chapter data tables but immediately self-kill. Chapters that rely on them will have missing interactions:

| Event Class | File | What It Should Do |
|-------------|------|-------------------|
| `Event.touch` | `src/object/event/Event.touch.65816` | Handle touch/sword input events |
| `Event.show_help` | `src/object/event/Event.show_help.65816` | Display help overlays during gameplay |
| `Event.change_dash` | `src/object/event/Event.change_dash.65816` | Modify HUD/dashboard state |
| `Event.target` | `src/object/event/Event.target.65816` | Target-tracking input events |
| `Event.hide_sunscreen` | `src/object/event/Event.hide_sunscreen.65816` | Hide screen overlay effect |

Each is `; debug, kill immediately` — a play() method that calls kill on itself.

### 2b: Implemented but unwired — 16 scene-specific event classes with full init/play/kill implementations that are never referenced in any chapter data table

The linker discards these because no chapter data `.dw`s their class pointer. They have real game logic but xmlsceneparser.py doesn't emit references to them (the XML events map to generic types like `direction_generic` instead). To activate them, chapter data tables would need entries pointing to their `CLS.PTR`.

| Event Class | File | Scene |
|-------------|------|-------|
| `Event.crypt_creeps` | `Event.crypt.65816` | Crypt Creeps |
| `Event.falling_plat_phase` | `Event.falling_platform_phase.65816` | Catwalk Bats |
| `Event.flame_rope_haz` | `Event.flaming_ropes_hazard.65816` | Flaming Ropes |
| `Event.flame_rope_rt` | `Event.flaming_ropes_route.65816` | Flaming Ropes |
| `Event.flying_horse_col` | `Event.flying_horse_collision.65816` | Flying Horse |
| `Event.fly_horse_lane` | `Event.flying_horse_lane.65816` | Flying Horse |
| `Event.gid_goon_grap` | `Event.giddy_goons_grapple.65816` | Giddy Goons |
| `Event.gid_goon_swarm` | `Event.giddy_goons_swarm.65816` | Giddy Goons |
| `Event.roll_ball_ball` | `Event.rolling_balls_ball.65816` | Rolling Balls |
| `Event.roll_ball_crush` | `Event.rolling_balls_crush.65816` | Rolling Balls |
| `Event.tent_room_grab` | `Event.tentacle_room_grab.65816` | Tentacle Room |
| `Event.tent_room_path` | `Event.tentacle_room_path.65816` | Tentacle Room |
| `Event.throne_state` | `Event.throne_room_state.65816` | Throne Room |
| `Event.tilting_room_nav` | `Event.tilting_room_navigation.65816` | Tilting Room |
| `Event.under_river_chain` | `Event.underground_river_chain.65816` | Underground River |
| `Event.under_river_phase` | `Event.underground_river_phase.65816` | Underground River |

### 2c: Dead code — 26 cutscene event classes compiled but never referenced

All 26 are in `Event.cutscene.65816` (one file, 27 CLASS macros — the 27th `Event.cutscene` base class IS used). These are scene-specific death/transition cutscenes. Same root cause as 2b: xmlsceneparser.py maps cutscene XML events to the generic `Event.cutscene` class rather than the scene-specific subclasses.

Discarded classes: `attract_mode_attract_movie`, `attract_mode_insert_coins`, `introduction_castle_exterior`, `alice_room_drinks_potion`, `alice_room_burned_to_death`, `crypt_creeps_captured_by_ghouls`, `crypt_creeps_overpowered_by_skulls`, `flaming_ropes_burns_hands`, `flaming_ropes_fall_to_death`, `flaming_ropes_misses_landing`, `flying_horse_burned_to_death`, `giddy_goons_fall_to_death`, `rolling_balls_pit_in_ground`, `tentacle_room_squeeze_to_death`, `tentacle_room_squeeze_to_death_by_door`, `tilting_room_catches_fire`, `tilting_room_falls_to_death`, `tilting_room_wrong_door`, `falling_platform_long_fell_to_death`, `falling_platform_short_fell_to_death`, `vestibule_fell_to_death`, `vestibule_stagger`, `bower_trapped_in_wall`, `throne_room_on_throne`, `wind_room_sucked_in`, `the_dragons_lair_endgame`.

## Category 3: Audio Issues

| Item | File | Issue |
|------|------|-------|
| SPC sample overflow | `src/object/audio/spcinterface.h` | Only 6 of 11 WAVs are in the build (~42 KB of 57.5 KB budget). `dragon_roar` + `sword_clank` overflow. `dl_accept`, `dl_buzz`, `dl_credit` not registered. Need to either swap legacy samples (brake/turbo) for DL-themed ones, or find smaller BRR encodings. |
| Legacy sample names | `src/object/audio/spcinterface.h` | Enum names still `SAMPLE.0.SHURIKEN`, `SAMPLE.0.TECHNIQUE` — should be renamed to Dragon's Lair equivalents. |
| SpcPlaySoundEffectObjectXPos stub | `src/object/audio/spcinterface.65816:1013` | Panning sound effect method is `TRIGGER_ERROR E_Todo`. Not currently called, but would crash if used. |
| Brightness.fadeTo range guard | `src/object/brightness/brightness.65816:46` | Out-of-range brightness value triggers `E_Todo` instead of clamping. Defensive code that crashes on invalid input. |

## Category 4: OOP / Identity Issues

| Item | File | Issue |
|------|------|-------|
| ~65 event classes default OBJID $ffff | Generated event `.h` files | Most auto-generated event classes have `OBJID.$ffff` which collides with `oopCreateNoPtr`. Works because OBJIDs are only used for `kill.byId` lookups (not used for events), but technically incorrect. Of these, 42 are linker-discarded dead code (see Cat 2b/2c) — their $FFFF OBJIDs never appear in the ROM. The remaining ~23 are active classes whose $FFFF OBJIDs could cause issues if `kill.byId` were ever used on events. |
| Event.Test_Script uses $FFFF | `src/object/event/Event.Test_Script.h:8` | Template file with explicit `$FFFF` and a TODO comment. Should be deleted or given a real ID. |

## Category 5: Build & Tooling

| Item | File | Issue |
|------|------|-------|
| Hardcoded user paths in generate_msu_data.py | `tools/generate_msu_data.py:50-51` | FFmpeg paths hardcoded to `C:\Users\chad\...`. Non-portable. |
| Hardcoded paths in batch_convert_msu.py | `tools/batch_convert_msu.py:17-19` | All paths hardcoded to `/mnt/e/gh/` and chad's user directory. |
| Hardcoded paths in generate_manifest.py | `tools/generate_manifest.py:22` | Output path hardcoded; track count hardcoded to 206. |
| Makefile commented-out code | `Makefile:94,144,223` | Unused `convertedframefolder` var, MSU excluded from datafiles, commented-out chapter processing. Unclear "hack" comments at lines 92, 220. Note: `temp_artifacts/build.log` references Makefile lines 341-407, but current Makefile is only 236 lines — that log is stale (from an older Makefile with duplicate rule definitions). The ~312 "overriding recipe" warnings it contains likely no longer occur. |
| animationWriter_sfc.py disabled multi-palette | `tools/animationWriter_sfc.py:263-264` | Multi-palette color calculation commented out. Feature incomplete or intentionally disabled without documentation. |
| xmlsceneparser.py leftover DEBUG log | `tools/xmlsceneparser.py:534` | `logging.warning("DEBUG: self.type became direction_generic!...")` — development artifact producing log spam. |
| gfx_converter.py duplicate print | `tools/gfx_converter.py:45,47` | Same padding message printed twice (copy-paste error). |
| xmlsceneparser.py symbol length warning | `tools/xmlsceneparser.py:467` | Warns when event type names exceed 13 characters (wla-dx symbol length risk). No actual breakage observed, but threshold and risk undocumented. |
| Stale build logs | `temp_artifacts/build.log`, `build_output.log` | Captured from previous builds. `temp_artifacts/build.log` references old Makefile line numbers (341-407 vs current 236). `build_output.log` may contain fixed FIX_REFERENCES errors. Consider deleting or regenerating after a fresh build. |

## Category 6: Assets

| Item | Location | Issue |
|------|----------|-------|
| Legacy sprites still present | `data/sprites/` | dashboard, steering_wheel (3 variants), turbo, brake sprites are unused but still compiled into the ROM. Could save ROM space by excluding. |
| ROM header checksums hardcoded | `src/core/boot.65816:112-113` | `.dw $F9D8` and `.dw $0627` — "Invalid Checksum" in emulators. Known limitation of wla-dx `.snesheader` workaround. |
