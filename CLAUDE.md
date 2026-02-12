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
- `emu.setInput` does NOT inject into hardware JOY1L — NMI's `_checkInputDevice` overwrites WRAM from hardware. To inject input, use an exec callback at `_checkInputDevice`'s RTS address to write WRAM directly: press=`$6B46`, trigger=`$6B48`, old=`$6B4C`
- `_checkInputDevice` address shifts between builds — look it up in `build/SuperDragonsLairArcade.sym` after each rebuild
- `io.open` does not work in testrunner mode; use `print()` with output redirect
- MSU-1 requires ROM in same folder as .msu/.pcm files. Debug scripts in `mesen/` directory.

## Architecture

### Memory Map
- HiROM+FastROM, 16 banks x 64KB = 1MB ROM
- Slot 0: $0000-$FFFF (ROM), Slot 1: $7E2000 (Work RAM), Slot 2: zero page
- Checksum values hardcoded in header — "Invalid Checksum" in emulators is expected

### OOP System (`src/core/oop.65816`)
Custom object system with 36 concurrent object slots. Each object has init/play/kill methods, a direct page (ZP) allocation, and properties bitmask.

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
boot.65816 → main.script → msu1.script → logo_intro.script → title_screen.script → level1.script → ...
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
+12: .dw {ARG1}                 (event-specific)
```

**Type normalization** by xmlsceneparser.py:
- `direction` + `type="left"` → `Event.direction_generic` with arg0=`JOY_DIR_LEFT`
- `direction` + `type="right"` → arg0=`JOY_DIR_RIGHT`, etc.
- `seq2`, `seq3` → `Event.seq_generic` with arg0=sequence number
- `room_transition` subtypes (enter_room, start_alive, start_dead) → encoded arg0 (0-7)
- Hyphens in chapter names → underscores (e.g., `alice-room` → `alice_room`)

**Frame timing**: XML uses min/sec/ms, converted to frame numbers at 23.9777 fps. Startframe/endframe are chapter-relative (event frame - chapter start frame), clamped to 16-bit.

### Chapter Initialization and Event Results

**`_CHAPTER.init`** (`src/object/script/script.h`): Sets properties to `isChapter`, kills other chapters (only one active at a time), kills all events, reads 24-bit inline pointer to event data, loops creating event objects from the data table via `core.object.create`.

**EventResult handlers** (`src/object/event/abstract.Event.65816`):
- **`EventResult.none`** — kill self, no further action
- **`EventResult.playchapter`** — create new chapter Script from resultTarget label (the primary scene transition mechanism)
- **`EventResult.restartchapter`** — restart current chapter from last checkpoint
- **`EventResult.lastcheckpoint`** — player loses a life; if game over → `game_over` script; else restart from checkpoint

**Scene transitions**: When an event's endframe is reached (or player input triggers it), `abstract.Event.checkResult` calls the EventResult handler. `EventResult.playchapter` creates a new Script with the target chapter label, which kills the old chapter via `killOthers(isChapter)`.

### Event/Chapter File Aggregation

All chapter scripts are aggregated in `data/chapters/chapter.include`, all data in `data/chapters/chapter_data.include`. Chapter data goes in ONE `superfree` section in `chapter_data.65816` (wla-dx has a ~512 section-per-file limit).

**36+ event classes** for gameplay: `direction_generic`, `direction_left/right`, `chapter`, `checkpoint`, `room_transition`, `seq_generic`, `cutscene`, `accelerate`, `brake`, `shake`, `touch`, `target`, `confirm`, plus scene-specific events (rolling_balls, flying_horse, tentacle_room, etc.). Create new events with `python tools/create_event.py Event.myname`.

### Title Screen Menu and Scene Select

The title screen (`src/title_screen.script`) has a full menu system:
- **Main menu**: START GAME, OPTIONS, ATTRACT MODE
- **Options submenu**: SOUND TEST, SCENE SELECT, BACK
- **Sound test**: L/R selects sample 0-5, A plays it
- **Scene select**: L/R selects scene 1-29, A launches it via `_title_screen.sceneTable`

**Transition pattern** (must use dedicated SavePC): After fadeTo black, a `jsr SavePC` creates a new resume point. Each frame polls `Brightness.isDone`; when done, cleanup kills objects, clears VRAM/CGRAM, creates target Script, and DIEs. The inline SavePC replaces the menu's SavePC — menu input stops during transition.

### MSU-1 Video Data Pipeline

Video frames from `data/videos/dl_arcade.mp4` are converted to SNES tile data and packaged into a `.msu` file for MSU-1 hardware playback.

```bash
# Generate .msu video data (~23 min with 8 workers, requires existing PNG frames)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --skip-extract --workers 8"

# Full pipeline including frame extraction (~1hr+ first time, uses ffmpeg CUDA)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --workers 8"

# Output: build/SuperDragonsLairArcade.msu (~568 MB)
# Also copied to: E:\gh\SuperDragonsLairArcade.sfc\SuperDragonsLairArcade.msu
```

**Pipeline steps** (per frame):
1. ffmpeg extracts 256x192 PNG frames (16-color palette, CUDA GPU accelerated)
2. superfamiconv converts each PNG to SNES palette/tiles/tilemap
3. `reduce_tiles()` merges 768 unique tiles down to 512 (VRAM limit) using global greedy merge with RGB-space L2 distance
4. msu1blockwriter.py packages all chapters into a single `.msu` file

**Key constraints:**
- VRAM tile buffer = $4000 bytes = 512 tiles at 4BPP. Each 256x192 frame has up to 768 unique tiles, requiring lossy tile reduction.
- MSU title in `.msu` file must exactly match ROM header title (`SUPER DRAGON'S LAIR`) or `_isMsu1FilePresent` rejects it.
- `make clean` DELETES `data/chapters/` — wipes all extracted video frames. Run MSU generation AFTER final build, or use `make` without `clean`.
- BLAS thread safety: `OPENBLAS_NUM_THREADS=1` must be set before `import numpy` in generate_msu_data.py — multi-threaded BLAS corrupts results when called from concurrent Python threads.

## Critical Pitfalls

### wla-dx `.def` Cannot Redefine
**`.def X Y` followed by `.def X Z` → the second definition is SILENTLY IGNORED.** This has caused hash pointer collision bugs. `script.h` predefines: `objBrightness` at `hashPtr+12` (=hashPtr.4), `objPlayer` at `hashPtr+16` (=hashPtr.5). Scripts must work around these slots, not try to redefine them. Use `.redefine` or `.undefine`+`.define` if redefinition is truly needed.

### Hash Pointer Collisions
Each script has 9 hash pointer slots (hashPtr.1 through hashPtr.9). If two `.def` symbols resolve to the same hashPtr slot, the second `NEW` overwrites the first's hash, causing `CALL` to dispatch to the wrong object (silent failure, no crash).

### `oopCreateNoPtr` = $FFFF
Used as null pointer for the hash system. `CALL` with hash pntr=$FFFF dispatches to `dispatchObjMethodHashVoid` (safe no-op). Never use hash pntr=0 — it matches OopStack slot 0.

### SPC700 Audio Constraints
SPC700 has 64KB RAM total. Engine code ~6.5KB, leaving ~57.5KB for BRR samples. Adding samples requires checking total BRR size stays under this limit.

### CGRAM (Palette) Limits
SNES has 8 BG palettes max for 4BPP mode ($100 bytes). The `animationWriter_sfc.py` ignores the `-palettes` flag (line 259 commented out), so backgrounds may use more sub-palettes than intended. CGRAM allocation failure in `abstract.Background.65816` is non-fatal (falls back to palette position 0).

### wla-dx `_` Prefix = Local Labels
Labels starting with `_` are LOCAL to the compilation unit (.o file). They cannot be referenced from other .o files — causes FIX_REFERENCES at link time. Use labels without `_` prefix for cross-file references.

### wla-dx Section Limit Per File
wla-dx has a maximum of ~512 sections per compilation unit. Exceeding this gives "Out of section numbers. Please start a new file." — solved by combining data into fewer, larger sections.

### Class File Pattern
Every class has a `.h` (header) and `.65816` (implementation). The header defines the ZP struct layout, `CLASS.FLAGS`, `CLASS.PROPERTIES`, `CLASS.ZP_LENGTH`, and optionally `CLASS.IMPLEMENTS`. The `.65816` file includes the `.h`, opens a `.section`, uses `METHOD init`/`play`/`kill` to define methods, and ends with `CLASS ClassName [extraMethods]` + `.ends`.

## Key Files

| File | Purpose |
|------|---------|
| `src/config/macros.inc` | All macros: CLASS, METHOD, NEW, CALL, SCRIPT, EVENT, etc. |
| `src/config/globals.inc` | Object properties, flags, global enums |
| `src/config/structs.inc` | Data structures: iteratorStruct, animationStruct, eventStruct |
| `src/core/oop.65816` | Object creation, singleton handling, method dispatch |
| `src/core/oop.h` | OBJID enum, OopClassLut (class registration) |
| `src/core/error.h` | Error code enum (E_ObjLstFull through E_SramBad) |
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
| `src/level1.script` – `src/level9.script` | Level entry points (each creates a starting chapter) |
| `src/title_screen.script` | Title screen with menu system and scene select |
| `tools/generate_msu_data.py` | Full MSU-1 video pipeline: ffmpeg → superfamiconv → tile reduction → .msu |
| `tools/msu1blockwriter.py` | Packages tile/tilemap/palette data into .msu file format |
| `build/SuperDragonsLairArcade.sym` | Symbol table — look up addresses here after each build |
