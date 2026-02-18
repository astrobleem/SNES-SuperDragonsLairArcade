# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SNES Super Dragon's Lair Arcade — a full-motion-video (FMV) retheme of RoadBlaster for the Super Nintendo, targeting real NTSC SNES hardware with MSU-1 audio/video on SD2SNES/FXPAK Pro. Written in 65816 assembly with a custom OOP framework.

## Build Commands

Build runs under WSL. The project uses WLA-DX v9.3 assembler (v9.4+ breaks the build).

```bash
# Standard build (clean + build, ~2-3 min)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean && make"

# Fast rebuild (skip clean if only .65816/.script files changed)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make"

# Build output
# ROM: build/SuperDragonsLairArcade.sfc
# Also copied to: E:\gh\SuperDragonsLairArcade.sfc\SuperDragonsLairArcade.sfc
```

**Build warnings that are normal:**
- `DIRECTIVE_ERROR` about redefined `__init`/`__play`/`__kill` — from CLASS macro in event files
- `DISCARD` messages — unused event sections stripped by `-d` linker flag

**Emulator testing with Mesen 2:**
```bat
:: Mesen.exe is at mesen\Mesen.exe (inside the project)
:: Use cmd.exe redirect for reliable output capture (PowerShell Out-String can truncate)
cmd.exe /c "cd /d E:\gh\SNES-SuperDragonsLairArcade\mesen && Mesen.exe --testrunner ..\build\SuperDragonsLairArcade.sfc script.lua > out.txt 2>&1"
```

**Mesen Lua API quirks:**
- `emu.getState()` returns a flat table with dot-separated string keys: use `state["cpu.a"]` NOT `state.cpu.a`
- `emu.setInput({a = true})` — no port number argument, just a table
- `emu.setInput` does NOT inject into hardware JOY1L — NMI's `_checkInputDevice` overwrites WRAM from hardware. To inject input, use an exec callback at `_checkInputDevice`'s RTS address to write WRAM directly: press=`$6D06`, trigger=`$6D08`, old=`$6D0C` (verify in .sym — shifts when maxNumberOopObjs changes)
- `_checkInputDevice` address shifts between builds — look it up in `build/SuperDragonsLairArcade.sym` after each rebuild
- `io.open` does not work in testrunner mode; use `print()` with output redirect
- MSU-1 requires ROM in same folder as .msu/.pcm files. Debug scripts in `mesen/` directory.

**CRITICAL: ROM addresses shift on EVERY code change.** Any change to `.65816`, `.script`, or `.h` files (even adding a comment) can shift all symbol addresses in `build/SuperDragonsLairArcade.sym`. WRAM addresses (`$7E****`) are stable, but ROM code addresses are NOT. After every build, you MUST re-read the sym file to update Mesen Lua test scripts. Hardcoded addresses in test scripts will silently break (callbacks never fire, tests appear to hang or produce no output). This is the #1 cause of "inconclusive" test results.

## Architecture

### Memory Map
- HiROM+FastROM, 16 banks x 64KB = 1MB ROM
- Slot 0: $0000-$FFFF (ROM), Slot 1: $7E2000 (Work RAM), Slot 2: zero page
- Checksum values hardcoded in header — "Invalid Checksum" in emulators is expected

### OOP System (`src/core/oop.65816`)
Custom object system with 48 concurrent object slots. Each object has init/play/kill methods, a direct page (ZP) allocation, and properties bitmask.

**Key macros** (defined in `src/config/macros.inc`):
- `CLASS name method1 method2...` — defines a class with method table
- `METHOD name` — defines an instance method
- `NEW class.CLS.PTR hashPtr args...` — creates object instance, stores hash pointer
- `CALL class.method.MTD hashPtr args...` — dispatches method call via hash pointer
- `TRIGGER_ERROR E_code` — expands to `pea E_code; jsr core.error.trigger` (fatal, calls stp)

**Object properties** (`src/config/globals.inc`):
- `isScript=$0001`, `isChapter=$0002`, `isEvent=$0004`, `isHdma=$0008`, `isSerializable=$1000`
- `killOthers` uses bitmask AND matching — ALL requested bits must be present

**Singleton objects**: Brightness, Spc have `OBJECT.FLAGS.Singleton`. Creating a singleton that already exists returns the existing instance WITHOUT calling init again.

### Script System (`src/object/script/`)
Scripts are 65816 code that runs synchronously during init (via `bra _play`) until the first `jsr SavePC`, then resumes one iteration per frame. Key macros: `SCRIPT`, `DIE`, `SavePC`, `WAIT`.

**Script ZP layout** (96 bytes total):
- iteratorStruct (28 bytes, offset 0) — self, properties, target, index, count, sort fields
- scriptStruct (4 bytes, offset 28) — timestamp, initAddress
- vars (28 bytes, offset 32) — _tmp[16], currPC, buffFlags, buffBank, buffA/X/Y, buffStack
- hashPtr (36 bytes, offset 60) — 9 hash pointers x 4 bytes each (id, count, pntr)

**Hash pointer access**: `hashPtr.N` is 1-indexed. `hashPtr.1` = offset 60, `hashPtr.N` = offset 60 + (N-1)*4.

### Game Flow
```
boot.65816 → main.script → msu1.script → losers.script → logo_intro.script → title_screen.script → level1.script → ...
```
Each script creates the next via `NEW Script.CLS.PTR oopCreateNoPtr nextScript` then `DIE`.

### Scene/Chapter System

The game is divided into 29 scenes (rooms), each containing multiple chapters (short video segments with events). Chapters chain together via EventResult handlers based on player input.

**Scene flow**: `title_screen` → `level1.script` → `introduction_start_alive` (chapter) → player input triggers → next chapter → ... → scene complete → next scene

**Level scripts** (`src/level1.script` through `src/level9.script`) are minimal entry points:
```asm
SCRIPT level1
NEW Script.CLS.PTR oopCreateNoPtr introduction_start_alive
DIE
```

**29 scenes** (selectable from title screen's scene select menu):
introduction, vestibule, snake_room, bower, fire_room, throne_room, tilting_room, tentacle_room, wind_room, giddy_goons, catwalk_bats, mudmen, rolling_balls, underground_river, flaming_ropes, flying_horse, bubbling_cauldron, giant_bat, crypt_creeps, alice_room, robot_knight, smithee, smithee_reversed, grim_reaper, yellow_brick_road, black_knight, lizard_king, the_dragons_lair, attract_mode

### XML Event Files and Conversion Pipeline

**Source**: XML files in `data/events/*.xml` (516+ files, generated from DirkSimple game data)

Each XML defines one chapter with a timeline and events:
```xml
<chapter name="black_knight_seq2">
  <timeline><timestart min="17" sec="38" ms="768"/><timeend min="17" sec="42" ms="307"/></timeline>
  <events>
    <event type="direction" automacro="direction">
      <timeline><timestart min="17" sec="39" ms="372"/><timeend min="17" sec="41" ms="703"/></timeline>
      <params><str key="type" value="left"/></params>
      <result><playchapter name="black_knight_seq3"/></result>
    </event>
    <!-- more events -->
  </events>
  <result><playchapter name="black_knight_seq7"/></result>  <!-- default if no input -->
</chapter>
```

**Conversion tool**: `tools/xmlsceneparser.py` converts each XML into two assembly files:
```bash
python3 tools/xmlsceneparser.py data/events/black_knight_seq2.xml
```

**Output per chapter** (in `data/chapters/<name>/`):
- **`chapter.script`** — code (~10 bytes): `CHAPTER` macro + 24-bit pointer to event data + `DIE`
- **`chapter.data`** — event data table: 7 words per event (14 bytes), terminated by `.dw 0`

**Event data format** (per entry, 14 bytes):
```
+0: .dw Event.{TYPE}.CLS.PTR    (class pointer for event object)
+2: .dw STARTFRAME              (chapter-relative, 16-bit)
+4: .dw ENDFRAME                (chapter-relative, 16-bit)
+6: .dw EventResult.{RESULT}    (result handler: playchapter, restartchapter, lastcheckpoint, none)
+8: .dw {RESULT_TARGET}         (target chapter label, or 'none')
+10: .dw {ARG0}                 (event-specific: direction mask, sequence number, etc.)
+12: .dw {ARG1}                 (event-specific: for direction events, bit 0 = hide arrow sprite)
```

**Type normalization** by xmlsceneparser.py:
- `direction` + `type="left"` → `Event.direction_generic` with arg0=`JOY_DIR_LEFT`
- `direction` + `type="right"` → arg0=`JOY_DIR_RIGHT`, etc.
- `seq2`, `seq3` → `Event.seq_generic` with arg0=sequence number
- `room_transition` subtypes (enter_room, start_alive, start_dead) → encoded arg0 (0-7)
- Hyphens in chapter names → underscores (e.g., `alice-room` → `alice_room`)

**Frame timing**: XML uses min/sec/ms, converted to frame numbers at 23.9777 fps. Startframe/endframe are chapter-relative (event frame - chapter start frame), clamped to 16-bit.

### Chapter Initialization and Event Results

**`_CHAPTER.init`** (`src/object/script/script.h`): First kills all events from the previous chapter via `kill.byProperties(isEvent)`, then sets properties to `isChapter` and kills other chapter scripts via `killOthers`. Reads 24-bit inline pointer to event data, loops creating event objects from the data table via `core.object.create`.

**EventResult handlers** (`src/object/event/abstract.Event.65816`):
- **`EventResult.none`** — kill self, no further action
- **`EventResult.playchapter`** — create new chapter Script from resultTarget label (the primary scene transition mechanism)
- **`EventResult.restartchapter`** — restart current chapter from last checkpoint
- **`EventResult.lastcheckpoint`** — player loses a life; if game over → `game_over` script; else restart from checkpoint

**Scene transitions**: When a player presses the correct input during a direction event's active window, `abstract.Event.triggerResult` calls the EventResult handler. `EventResult.playchapter` creates a new chapter Script, whose `_CHAPTER.init` kills all old events and the old chapter. If no input is given, `Event.chapter` fires its default result (usually death/restart) when the chapter's endframe is reached.

### Event/Chapter File Aggregation

All chapter scripts are aggregated in `data/chapters/chapter.include`, all data in `data/chapters/chapter_data.include`. Chapter data goes in ONE `superfree` section in `chapter_data.65816` (wla-dx has a ~512 section-per-file limit).

**36+ event classes** for gameplay: `direction_generic`, `direction_left/right`, `chapter`, `checkpoint`, `room_transition`, `seq_generic`, `cutscene`, `accelerate`, `brake`, `shake`, `touch`, `target`, `confirm`, plus scene-specific events (rolling_balls, flying_horse, tentacle_room, etc.). Create new events with `python tools/create_event.py Event.myname`.

### Title Screen Menu and Scene Select

The title screen (`src/title_screen.script`) has a full menu system:
- **Main menu**: START GAME, OPTIONS
- **Options submenu**: HIGH SCORES, ATTRACT MODE, SOUND TEST, SCENE SELECT
- **Sound test**: L/R selects sample 0-6, A plays it
- **Scene select**: L/R selects scene 1-29, A launches it via `_title_screen.sceneTable`

Menu items start at tilemap position `$286` (row 20, col 6). Copyright text at `$306`/`$324` (rows 24-25). Cursor drawn at `$286 + cursor * 32`.

**Transition pattern** (must use dedicated SavePC): After fadeTo black, a `jsr SavePC` creates a new resume point. Each frame polls `Brightness.isDone`; when done, cleanup kills objects, clears VRAM/CGRAM, creates target Script, and DIEs. The inline SavePC replaces the menu's SavePC — menu input stops during transition.

### MSU-1 Video Data Pipeline

Video frames are extracted directly from **Daphne .m2v/.ogg segment files** (NOT an intermediate MP4). The Daphne framefile (`data/laserdisc/dl_lair.txt`) maps laserdisc frame numbers to 204 MPEG-2 video segments and paired Ogg Vorbis audio segments. There is no MP4 fallback — the framefile is mandatory.

**Video source**: Daphne .m2v segments (interlaced 29.97fps MPEG-2), deinterlaced and rate-converted by ffmpeg.

```bash
# Full pipeline: extract frames + audio from .m2v/.ogg, convert tiles, package .msu
# (~1hr first time with 8 workers, CPU-only ffmpeg decode)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --workers 8"

# Clean + full pipeline (re-extracts everything from scratch)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --clean --workers 8"

# Skip extraction (use existing PNG frames), only convert tiles + package .msu (~23 min)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --skip-extract --workers 8"

# Output: build/SuperDragonsLairArcade.msu (~516 MB)
# Also copied to: E:\gh\SuperDragonsLairArcade.sfc\SuperDragonsLairArcade.msu
```

```bash
# Audio-only extraction + PCM file numbering (~30s, no video processing needed)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --skip-extract --skip-convert --skip-package --workers 8"
# Output: build/SuperDragonsLairArcade-{chapterID}.pcm (473 files)
# Also copied to: E:\gh\SuperDragonsLairArcade.sfc\
```

**Frame extraction details**: Each .m2v segment is decoded CPU-only (no CUDA) with this ffmpeg filter chain:
```
yadif,fps=24000/1001,trim=start={offset_s}:duration={dur_s},setpts=PTS-STARTPTS,scale=256:192
```
- `yadif` deinterlaces the 29.97fps interlaced MPEG-2
- `fps=24000/1001` converts to 23.976fps (laserdisc rate) BEFORE trimming
- `trim` selects the frame range (no `-ss` seeking — decode from start for accuracy)
- `setpts=PTS-STARTPTS` resets timestamps after trim
- Output: 16-color paletted PNGs via split/palettegen/paletteuse

**Frame timing resolution**: `lua_scene_exporter.py` resolves laserdisc frame numbers for each chapter using:
1. Direct frame numbers from DirkSimple sequence data
2. Timeout predecessor chains (sequence A times out → sequence B)
3. Action predecessor chains (player presses right in sequence A → sequence B)
4. Segment timing from `data/segment_timing.json` (generated by `tools/generate_segment_timing.py`)

473 of 516 chapters have frame attributes. The remaining 43 are zero-duration routing nodes (`start_alive` chapters) that don't need video frames.

**Frame inspection**: After extraction, frames are copied to `data/videos/frames/{chapter_name}/` for per-chapter visual debugging. Each subdirectory contains the PNG frames for that chapter.

**MSU-1 audio track numbering**: PCM files are named `SuperDragonsLairArcade-{chapterID}.pcm` where chapterID matches the chapter's index in the .msu pointer table (from `chapter.id.NNN` files in each chapter directory). The ROM passes `this.currentChapter` as the audio track number to MSU-1 hardware. `msu1blockwriter.py` also writes PCM files during .msu packaging (Phase 3). `generate_msu_data.py` Phase 1c copies them to build/ and sfc/ directories.

**manifest.xml**: Required by some emulators (bsnes/higan) to map MSU-1 PCM tracks. Located at `E:\gh\SuperDragonsLairArcade.sfc\manifest.xml`. Must list only tracks that have corresponding PCM files. Regenerate after any MSU data change by scanning actual PCM files in the sfc directory.

**Pipeline steps** (per chapter):
1. ffmpeg extracts 256x192 PNG frames from .m2v segment (CPU decode, yadif+trim filter chain)
2. ffmpeg extracts audio from paired .ogg segment → WAV → PCM
3. superfamiconv converts each PNG to SNES palette/tiles/tilemap
4. `reduce_tiles()` merges 768 unique tiles down to 512 (VRAM limit) using global greedy merge with RGB-space L2 distance
5. msu1blockwriter.py packages all chapters into a single `.msu` file + per-chapter `.pcm` files

**Key constraints:**
- VRAM tile buffer = $4000 bytes = 512 tiles at 4BPP. Each 256x192 frame has up to 768 unique tiles, requiring lossy tile reduction.
- MSU title in `.msu` file must exactly match ROM header title (`SUPER DRAGON'S LAIR`) or `_isMsu1FilePresent` rejects it.
- `make clean` DELETES `data/chapters/` — wipes all extracted video frames. Run MSU generation AFTER final build, or use `make` without `clean`.
- BLAS thread safety: `OPENBLAS_NUM_THREADS=1` must be set before `import numpy` in generate_msu_data.py — multi-threaded BLAS corrupts results when called from concurrent Python threads.
- Daphne framefile (`data/laserdisc/dl_lair.txt`) is REQUIRED — there is no MP4 fallback.

## Critical Pitfalls

### wla-dx `.def` Cannot Redefine
**`.def X Y` followed by `.def X Z` → the second definition is SILENTLY IGNORED.** This has caused hash pointer collision bugs. `script.h` predefines: `objBrightness` at `hashPtr+12` (=hashPtr.4), `objPlayer` at `hashPtr+16` (=hashPtr.5). Scripts must work around these slots, not try to redefine them. Use `.redefine` or `.undefine`+`.define` if redefinition is truly needed.

### Hash Pointer Collisions
Each script has 9 hash pointer slots (hashPtr.1 through hashPtr.9). If two `.def` symbols resolve to the same hashPtr slot, the second `NEW` overwrites the first's hash, causing `CALL` to dispatch to the wrong object (silent failure, no crash).

### `oopCreateNoPtr` = $FFFF
Used as null pointer for the hash system. `CALL` with hash pntr=$FFFF dispatches to `dispatchObjMethodHashVoid` (safe no-op). Never use hash pntr=0 — it matches OopStack slot 0.

### SPC700 Audio Constraints
SPC700 has 64KB RAM total. Engine code ~6.5KB, leaving ~57.5KB for BRR samples. 7 samples currently (~53 KB BRR), ~4 KB headroom. Adding samples requires checking total BRR size stays under this limit.

### MSU-1 Sound Effects
Dragon roar plays as MSU-1 PCM track 900 during the MSU-1 splash screen (`msu1.script`). Too large for SPC (5.8s = ~144 KB BRR), so it uses the MSU-1 audio hardware instead. Source WAV converted to MSU-1 PCM format (44100 Hz stereo 16-bit LE with `MSU1` header). The `Msu1.audio` singleton auto-mutes when the track ends via `_checkTrackEnd`.

### CGRAM (Palette) Limits
SNES has 8 BG palettes max for 4BPP mode ($100 bytes). `animationWriter_sfc.py` now forces `-P 1` (single sub-palette) in superfamiconv palette generation to prevent CGRAM overflow. CGRAM allocation failure in `abstract.Background.65816` is non-fatal (falls back to palette position 0). Default BG palettes in makefile reduced from 8 to 3.

### wla-dx `_` Prefix = Local Labels
Labels starting with `_` are LOCAL to the compilation unit (.o file). They cannot be referenced from other .o files — causes FIX_REFERENCES at link time. Use labels without `_` prefix for cross-file references.

### wla-dx Section Limit Per File
wla-dx has a maximum of ~512 sections per compilation unit. Exceeding this gives "Out of section numbers. Please start a new file." — solved by combining data into fewer, larger sections.

### wla-dx Anonymous Label Pitfalls
`+`, `++`, `+++` etc. are DISTINCT label tiers in wla-dx — `+` only matches `+`, `++` only matches `++`. A `bra ++` does NOT mean "second `+` forward" — it means "next `++` label forward". Long macro expansions (NEW, CALL) generate many bytes; branches over them easily exceed the 8-bit 127-byte limit. Use named labels or `jmp` for long forward references. The `bne label / jmp target / label:` pattern replaces a too-far `beq target`.

### Event kill Methods Must Use `jmp`, Not `jsr`
Event kill methods that delegate to `Event.template.kill` MUST use `jmp`, not `jsr`. `Event.template.kill` uses `sta 3,s` to write `OBJR_kill` to the stack. With `jsr`, the extra return address shifts the stack so `OBJR_kill` overwrites the wrong location, then `rts` returns to the call site and falls through into CLASS macro binary data, hitting `$00` = BRK → E_Brk crash. Correct pattern: `METHOD kill / jmp Event.template.kill`.

### Class File Pattern
Every class has a `.h` (header) and `.65816` (implementation). The header defines the ZP struct layout, `CLASS.FLAGS`, `CLASS.PROPERTIES`, `CLASS.ZP_LENGTH`, and optionally `CLASS.IMPLEMENTS`. The `.65816` file includes the `.h`, opens a `.section`, uses `METHOD init`/`play`/`kill` to define methods, and ends with `CLASS ClassName [extraMethods]` + `.ends`.

### Stack-Relative Addressing in Subroutines
When reading `OBJECT.CALL.ARG.N,s` from a subroutine called via `jsr` from an init/play method, add +2 to compensate for the extra return address on the stack. `OBJECT.CALL.ARG` offsets assume the reader is the DIRECT callee of `OopHandlerExecute`'s `jsr (0,x)`. `Event.template.initCommon` uses `OBJECT.CALL.ARG.N+2,s` for this reason. Event classes that read args directly in their init method (Event.chapter, Event.cutscene) do NOT need the +2.

### `core.string.parse_from_object` Overwrites String Arguments
`core.string.parse_from_object` (called by `Background.textlayer.8x8.print`) reads CALL stack arguments and writes them to `GLOBAL.CORE.STRING.argument.0` through `.3`. **Any values written to those globals before the print CALL will be overwritten.** To pass values for `TC_dToS`/`TC_hToS` display, push them on the stack before the CALL (deepest push → argument.2, shallowest → argument.0), and pop them after. Example:
```asm
pha           ; push chapter (→ argument.2, deepest)
pha           ; push lives   (→ argument.1)
pha           ; push score   (→ argument.0, shallowest)
lda #T_pause.PTR
CALL Background.textlayer.8x8.print.MTD this.textlayer
pla           ; pop score
pla           ; pop lives
pla           ; pop chapter
```

### Cross-Unit RAMSECTION Addresses Are 24-bit
RAMSECTION labels referenced from a different compilation unit resolve to full 24-bit addresses (e.g., `$7E699C`). `sta.w` and `pea` with such labels cause `COMPUTE_PENDING_CALCULATIONS: out of 16bit range`. Either use `sta.l` (long addressing) or keep the data in ROM within the same section and reference it with local labels + `:label` for the bank byte.

### 16-bit `lda` on `db` (byte) Fields
In 16-bit accumulator mode (`rep #$20`), `lda zp_offset` reads 2 bytes. If a `db` field is at the end of the ZP allocation (offset = zpLen - 1), the second byte reads into the adjacent object's ZP, producing a garbage high byte. Always mask with `and #$00FF` after reading, or use `sep #$20` to switch to 8-bit mode. Similarly, use `sep #$20` / `lda #value` / `sta field` / `rep #$20` when writing byte fields.

## Key Files

| File | Purpose |
|------|---------|
| `src/config/macros.inc` | All macros: CLASS, METHOD, NEW, CALL, SCRIPT, EVENT, etc. |
| `src/config/globals.inc` | Object properties, flags, global enums |
| `src/config/structs.inc` | Data structures: iteratorStruct, animationStruct, eventStruct |
| `src/core/oop.65816` | Object creation, singleton handling, method dispatch |
| `src/core/oop.h` | OBJID enum, OopClassLut (class registration) |
| `src/core/error.h` | Error code enum, hardcoded grey font palette ($6318 BGR555) |
| `src/core/boot.65816` | Entry point, main loop, interrupt vectors |
| `src/object/script/script.h` | Script class definition, hash pointer defaults |
| `src/object/brightness/brightness.65816` | Screen fade control (singleton) |
| `src/object/iterator/abstract.Iterator.65816` | killOthers, each.byProperties, setProperties |
| `src/object/event/abstract.Event.65816` | Base event class, EventResult handlers (playchapter, restartchapter, etc.) |
| `src/object/script/chapter_data.65816` | All chapter event data tables (one superfree section) |
| `tools/xmlsceneparser.py` | XML chapter events → assembly `.script` + `.data` files |
| `tools/create_event.py` | Generate boilerplate for new Event classes |
| `data/events/*.xml` | 516+ XML scene definitions (from DirkSimple game data) |
| `data/chapters/chapter.include` | Aggregates all generated chapter.script files |
| `data/chapters/chapter_data.include` | Aggregates all generated chapter.data files |
| `src/losers.script` | Credits/losers screen (shown after MSU-1 init) |
| `src/level1.script` – `src/level9.script` | Level entry points (each creates a starting chapter) |
| `src/object/player/pause.65816` | Pause menu overlay — shows scene name, score, lives, credits, chapter, frame |
| `src/title_screen.script` | Title screen with menu system and scene select |
| `tools/generate_msu_data.py` | Full MSU-1 video pipeline: Daphne .m2v → ffmpeg → superfamiconv → tile reduction → .msu |
| `tools/lua_scene_exporter.py` | Exports DirkSimple game.lua scene data to XML events with frame timing |
| `tools/generate_segment_timing.py` | Generates `data/segment_timing.json` from Daphne framefile + ffprobe |
| `tools/msu1blockwriter.py` | Packages tile/tilemap/palette data into .msu file format |
| `data/laserdisc/dl_lair.txt` | Daphne framefile — maps laserdisc frames to .m2v/.ogg segment files |
| `data/segment_timing.json` | Per-segment cumulative timing offsets for frame-accurate seeking |
| `build/SuperDragonsLairArcade.sym` | Symbol table — look up addresses here after each build |
| `E:\gh\SuperDragonsLairArcade.sfc\manifest.xml` | MSU-1 track manifest for emulators (lists PCM files by chapter ID) |
| `tools/generate_playthrough_tests.py` | Generates per-scene Mesen Lua test scripts that verify every scene is beatable |

## Mesen Lua Test Runner — MANDATORY

**Mesen path**: `E:\gh\SNES-SuperDragonsLairArcade\mesen\Mesen.exe`

**Run command** (ROM MUST load from the sfc directory where .msu/.pcm files live, NOT from build/):
```bat
cmd.exe /c "cd /d E:\gh\SuperDragonsLairArcade.sfc && E:\gh\SNES-SuperDragonsLairArcade\mesen\Mesen.exe --testrunner SuperDragonsLairArcade.sfc test_myscript.lua > out.txt 2>&1"
```
Loading from `build/` will crash at frame ~4 with an MSU-1 error (no .msu/.pcm files there). Copy test scripts to `E:\gh\SuperDragonsLairArcade.sfc\` before running. Output via `print()` only (`io.open` is broken in testrunner mode).

**WRAM addresses** (shift when `maxNumberOopObjs` changes — verify in .sym after slot count changes):
- `$7E6D06` — inputDevice.press (current buttons)
- `$7E6D08` — inputDevice.trigger (newly pressed this frame)
- `$7E6D0C` — inputDevice.old (previous frame)
- `$7E6388` — OopStack base (stable)
- `$7E6D22` — GLOBAL.currentFrame

**Addresses that CHANGE every rebuild** — look up in `build/SuperDragonsLairArcade.sym`:
- `core.error.trigger` — hook for fatal error detection
- `_checkInputDevice` — entry point; the RTS is at a fixed offset from entry (currently +$1E bytes)
- `abstract.Event.triggerResult` — hook to watch chapter transitions
- `EventResult.lastcheckpoint` — hook for death path monitoring
- `core.object.create` — hook for object creation tracking
- `_playVideo` — MSU-1 video entry point
- `_initScriptNotInvalid` — hook for Script.init validation
- Chapter labels (`introduction_castle_exterior`, `vestibule_start_alive`, `game_over`, etc.)

**CRITICAL: Address update procedure after EVERY build:**
1. Grep the sym file for each address used in your test script
2. For `_checkInputDevice`, add +$1E to the entry address to get the RTS address
3. Add `$C0` bank prefix to all ROM addresses (e.g. sym `$7412` → `0xC07412`)
4. Update ALL address constants in the Lua test script before running
5. If a test produces no output or "INCONCLUSIVE", stale addresses are the most likely cause

**CRITICAL mistakes to avoid:**
1. **`emu.write()` is SINGLE BYTE.** Joypad values are 16-bit (e.g. `JOY_START=0x1000`). You MUST write two bytes with a `writeWord()` helper — see template below.
2. **Hook at the RTS, not the entry point.** `_checkInputDevice`'s body reads hardware JOY1L and overwrites WRAM. If you hook the entry, the function body runs AFTER your write and clobbers it. Hook the `rts` at the END of the function.
3. **Exec callbacks need `$C0xxxx` bank.** Sym shows `$7412` → use `0xC07412`. Without `$C0` prefix the callback never fires.
4. **Use `emu.memType.snesMemory`**, not `cpuDebug` or `workRam`, for WRAM reads/writes.
5. **Use `state["ppu.frameCount"]`** for timing, not a manual counter. Mesen's `emu.getState()` returns flat string-keyed tables: `state["cpu.a"]` not `state.cpu.a`.
6. **Stale addresses = silent failure.** ROM code addresses shift on every build. Test scripts with old addresses produce "INCONCLUSIVE" results (callbacks never fire). Always re-read the sym file after building.
7. **Single-frame injection windows for menus.** The title screen processes one input per frame. Multi-frame injection (e.g. `{600,602,JOY_DOWN}`) causes 3 separate presses — DOWN toggles cursor back and forth, A enters options then immediately selects the first item. Use `{frame, frame, button}` for menus.
8. **No START during boot.** msu1.script's SavePC 59 LOOPS when START/A is pressed (`beq +; rts; +`). Pressing START delays the splash instead of skipping it. Let it auto-advance (~128 frames via `SCRIPT.MAX_AGE.DEFAULT`). Boot sequence takes ~575 PPU frames total to reach the title screen menu.
9. **Put navigation logic in exec callback, not endFrame.** `endFrame` fires AFTER the frame's main loop; `exec` at `_checkInputDevice` RTS fires during the NEXT frame's NMI. Using `endFrame` to set a button variable introduces a 1-frame delay. For menu navigation (where timing is exact), check `ppu.frameCount` directly inside the exec callback.

**Standard test script template:**
```lua
-- ============ ADDRESSES (MUST update after every build from .sym file) ============
local ADDR_ERROR_TRIGGER   = 0xC05905  -- grep 'core.error.trigger' build/*.sym
local ADDR_CHECK_INPUT_RTS = 0xC07412  -- _checkInputDevice entry + $1E
local ADDR_TRIGGER_RESULT  = 0xC06638  -- abstract.Event.triggerResult
local ADDR_INPUT_PRESS     = 0x7E6D06
local ADDR_INPUT_TRIGGER   = 0x7E6D08
local ADDR_INPUT_OLD       = 0x7E6D0C

local JOY_START = 0x1000; local JOY_A = 0x0080
local JOY_DOWN = 0x0400;  local JOY_RIGHT = 0x0100
local JOY_LEFT = 0x0200;  local JOY_UP = 0x0800
local MAX_FRAMES = 6000

local function readWord(addr)
    return emu.read(addr, emu.memType.snesMemory)
         + emu.read(addr + 1, emu.memType.snesMemory) * 256
end
local function writeWord(addr, val)
    emu.write(addr, val & 0xFF, emu.memType.snesMemory)
    emu.write(addr + 1, (val >> 8) & 0xFF, emu.memType.snesMemory)
end

local injectButton = 0
local errorHit = false

-- Input injection at _checkInputDevice RTS
emu.addMemoryCallback(function()
    if injectButton ~= 0 then
        writeWord(ADDR_INPUT_PRESS, injectButton)
        writeWord(ADDR_INPUT_TRIGGER, injectButton)
        writeWord(ADDR_INPUT_OLD, 0)
    end
end, emu.callbackType.exec, ADDR_CHECK_INPUT_RTS)

-- Error detection
emu.addMemoryCallback(function()
    if errorHit then return end; errorHit = true
    local state = emu.getState()
    local sp = state["cpu.sp"]
    local errCode = readWord(sp + 3)
    print(string.format("FAIL: error code=%d frame=%d", errCode, state["ppu.frameCount"]))
    emu.stop()
end, emu.callbackType.exec, ADDR_ERROR_TRIGGER)

-- Scene select: no START during boot (auto-advances ~575 frames).
-- Single-frame windows: DOWN, A (OPTIONS), DOWN x3, A (SCENE SELECT), RIGHT x N, A
-- Menu active at ~frame 575. Start nav at frame 600.
local navSchedule = {
    {600,600,JOY_DOWN},                         -- DOWN to OPTIONS
    {630,630,JOY_A},                            -- A enter OPTIONS
    {660,660,JOY_DOWN},{690,690,JOY_DOWN},      -- DOWN x3 to SCENE SELECT
    {720,720,JOY_DOWN},{750,750,JOY_A},         -- A enter SCENE SELECT
    -- RIGHT x N for scene N+1 (omit for scene 1 = introduction)
    {780,780,JOY_RIGHT},                        -- scene 2 = vestibule
    {810,810,JOY_A},                            -- launch
}

-- For menus: put nav logic in exec callback to avoid 1-frame delay
emu.addMemoryCallback(function()
    local frame = emu.getState()["ppu.frameCount"]
    for _, s in ipairs(navSchedule) do
        if frame >= s[1] and frame <= s[2] then
            writeWord(ADDR_INPUT_PRESS, s[3])
            writeWord(ADDR_INPUT_TRIGGER, s[3])
            writeWord(ADDR_INPUT_OLD, 0)
            return
        end
    end
    -- Golden path injection (set by endFrame, 1-frame delay OK for wide event windows)
    if injectButton ~= 0 then
        writeWord(ADDR_INPUT_PRESS, injectButton)
        writeWord(ADDR_INPUT_TRIGGER, injectButton)
        writeWord(ADDR_INPUT_OLD, 0)
    end
end, emu.callbackType.exec, ADDR_CHECK_INPUT_RTS)

emu.addEventCallback(function()
    local frame = emu.getState()["ppu.frameCount"]
    injectButton = 0
    -- (golden path frame monitoring goes here)
    if frame >= MAX_FRAMES then print("TIMEOUT"); emu.stop() end
end, emu.eventType.endFrame)
```

## Automated Playthrough Tests

`tools/generate_playthrough_tests.py` generates per-scene Mesen Lua test scripts that verify every gameplay scene is beatable with the correct inputs. It parses all 518 `chapter.data` files, builds directed chapter graphs, finds golden paths via BFS, and reads the `.sym` file for current ROM addresses.

```bash
# Generate all 28 scene test scripts (scene 29 attract_mode has no gameplay path)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_playthrough_tests.py"

# Generate for a specific scene only
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_playthrough_tests.py --scene 15"

# Dry-run: show golden paths without generating Lua files
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_playthrough_tests.py --dry-run"

# Run one test (from sfc directory where .msu/.pcm files live)
cmd.exe /c "cd /d E:\gh\SuperDragonsLairArcade.sfc && E:\gh\SNES-SuperDragonsLairArcade\mesen\Mesen.exe --testrunner SuperDragonsLairArcade.sfc test_scene_15_flaming_ropes.lua > out_15.txt 2>&1"
```

**IMPORTANT**: Regenerate test scripts after every build (`make`) because ROM addresses shift. The generator reads `build/SuperDragonsLairArcade.sym` automatically.

**Golden path algorithm**: BFS from `{prefix}_start_alive`, following non-death direction events and default chapter transitions. Death chapters (EventResult.lastcheckpoint targets) and their transitive predecessors are excluded. For each direction event on the path, injects the button at the midpoint of the event's startFrame-endFrame window.

**Test output**: Each test prints `PASS`, `FAIL` (with error code or death info), or `TIMEOUT`. Example:
```
INJECT: chapter=134 (flrp_enter_room) dir=0x0100 frame=40 ppuFrame=1304 step=1/4
INJECT: chapter=140 (flrp_rope1) dir=0x0100 frame=35 ppuFrame=1381 step=2/4
PASS: scene flaming_ropes - all 4 inputs injected successfully (ppuFrame=1523)
```
