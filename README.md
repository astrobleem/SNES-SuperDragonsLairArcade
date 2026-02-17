# Super Dragon's Lair Arcade (SNES)

![Complete Package](schwag/complete_package.png)

**Super Dragon's Lair Arcade** is a full-motion-video (FMV) game for the Super Nintendo Entertainment System, built on the [Super Road Blaster](https://github.com/snesdev0815/SNES-SuperRoadBlaster) engine by snesdev0815. It targets real NTSC SNES hardware with MSU-1 audio/video on SD2SNES/FXPAK Pro.

This faithful recreation of the 1983 arcade classic brings the legendary laserdisc adventure to your SNES console, complete with authentic packaging and documentation reminiscent of the 16-bit era.

## What's in the Box

Your complete Super Dragon's Lair Arcade package includes:

- **Game Cartridge** - The SNES ROM with MSU-1 enhancement chip support
- **User Manual** - Complete 4-page instruction booklet with story, controls, and survival guide
- **Holographic Trading Card** - Collectible card featuring Dirk the Daring
- **Soundtrack CD** - Original arcade audio tracks in CD quality
- **Sticker Sheet** - Dragon's Lair themed stickers
- **Warranty Card** - Official product registration
- **Upcoming Releases Preview** - Sneak peek at future titles

> [!NOTE]
> All schwag materials are available in the [`schwag/`](schwag) directory for your enjoyment and nostalgia.

## Features

### Engine (inherited from Super Road Blaster)
- Written purely in 65816 assembly with an object-oriented abstraction layer
- Dynamic allocation of work RAM, video RAM, color palettes, and DMA channels
- Class system with init/play/kill methods, instantiation via macro system (NEW/CALL/CLASS)
- Property-based object grouping for generalized selection and processing
- Iterator system for looping over objects by class ID or properties
- Singleton pattern for shared objects (Brightness, Spc, Msu1)
- Hash-based object references that auto-adjust when objects move on the stack
- Script system for controlling game flow with per-frame cooperative scheduling (SavePC/WAIT)
- MSU-1 full-motion video playback at 23.976 fps with per-chapter audio tracks
- SPC700 audio engine with BRR sample playback

### Dragon's Lair Arcade additions
- **516 chapters across 29 scenes** covering the complete Dragon's Lair arcade game
- **40+ event classes** — direction, sequence, checkpoint, room transition, cutscene, plus scene-specific events (rolling balls, tentacle room, flying horse, giddy goons, etc.)
- **MSU-1 video pipeline overhaul** — Daphne .m2v/.ogg source with ffmpeg deinterlacing, superfamiconv tile conversion, and RGB-space tile reduction (768 unique tiles merged to 512 per frame via greedy L2 distance)
- **Title screen with full menu system** — Start Game, Options submenu (High Scores, Attract Mode, Sound Test, Scene Select)
- **Scene select** — jump to any of the 29 scenes directly from the title screen
- **Attract mode** — automated demo playback with START to interrupt
- **Credit/coin system** — SELECT inserts credits during gameplay, continue screen on game over with countdown timer
- **Pause menu overlay** — displays scene name, score, lives, credits, chapter ID, and current video frame
- **Cross-scene transition system** — data-driven routing from terminal chapters to next scene via `scene_transitions.json`
- **Per-segment video timing** — cumulative offsets from Daphne framefile for frame-accurate chapter seeking (replaces fixed global offset)
- **48 concurrent object slots** (up from 36) to handle simultaneous video, event, and UI objects
- **7 SPC700 sound effects** in BRR format within the 57.5 KB sample RAM budget, plus MSU-1 PCM dragon roar
- **Blank frame generation** for zero-duration routing chapters (INSERT COIN, GAME OVER overlays)
- **Python 3 toolchain** — all build tools modernized from Python 2

## Current Status

- **All 29 Scenes Playable** — 9 levels spanning introduction through the dragon's lair, with full chapter-to-chapter transitions driven by player input
- **MSU-1 Video Pipeline Complete** — all 516 chapters converted to SNES tile data (~568 MB `.msu` file)
- **Complete Boot Sequence** — Boot → MSU-1 init → losers screen → logo intro → title screen → gameplay
- **Chapter/Event System** — data-table architecture with `xmlsceneparser.py` generating assembly from 516 XML chapter definitions
- **Dragon's Lair Themed Assets** — backgrounds, sprites, and UI elements themed for the arcade experience

## Build at a Glance

### Requirements
- **OS:** Linux/WSL (Ubuntu) or Windows with WSL
- **Assembler:** WLA-DX 9.3 (pre-built binaries included in `tools/wla-dx-9.5-svn/`)
- **Python:** Python 3.10+ with Pillow and NumPy
  ```bash
  pip install -r requirements.txt
  ```

### Build Commands
```bash
# Standard build (clean + build, ~2-3 min)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make clean && make"

# Fast rebuild (skip clean if only .65816/.script files changed)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && make"
```

> [!WARNING]
> `make clean` deletes `data/chapters/` — this wipes all extracted video frames. Use `make` without `clean` if you need to preserve them.

**Output:** ROM binary at `build/SuperDragonsLairArcade.sfc` (1 MB, 16 banks, HiROM+FastROM)

### MSU-1 Video Data Generation
```bash
# Generate .msu video data (~23 min with 8 workers, requires existing PNG frames)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --skip-extract --workers 8"

# Full pipeline including frame extraction (~1hr+ first time)
wsl -e bash -c "cd /mnt/e/gh/SNES-SuperDragonsLairArcade && python3 tools/generate_msu_data.py --workers 8"
```

**See [`BUILD.md`](BUILD.md) for detailed build instructions and troubleshooting.**

## Architecture

### General Concept

This game is written purely in 65816 assembly with an abstraction layer that takes ideas from object-oriented programming to enhance flexibility. Resources such as work RAM, video RAM, color palettes, and DMA channels are allocated dynamically to optimize usage and reduce micro-management.

Almost everything in the game — textlayers, sound interface, scores, sprites, and keypress events — is represented by objects. This makes it possible to generate any number of instances whenever required, and objects presenting uniform interfaces can be grouped, selected, and processed in a generalized fashion.

### Key Concepts

- **Class** — a set of named methods coupled with variable members. Has at least three default methods: init (constructor), play (called once every frame), kill (destructor). Defined with the `CLASS` macro.
- **Object** — instantiation of a class, with a private slice of zero-page RAM. Created with `NEW`, methods called with `CALL`. Lives until explicitly killed.
- **Object Hash** — unique reference to an object (class ID + pointer + instantiation counter). Auto-adjusts if the object moves on the object stack.
- **Properties** — bitflags on each object used for selection and grouping (isSprite, isEvent, isChapter, isHdma, isSerializable, etc.)
- **Script** — an object controlling logical game flow. Each chapter, the title screen, and the highscore screen have their own script.
- **Iterator** — provision for generically looping over sets of objects by class ID or properties.

### Program Flow
```
boot.65816 → main.script → msu1.script → losers.script → logo_intro.script
  → title_screen.script → level1.script → introduction_start_alive (chapter)
  → [player input] → next chapter → ... → scene complete → next scene
```

Chapter transitions are driven by events in the currently active chapter script. Each chapter's events are generated from XML files in `data/events/` by `xmlsceneparser.py`.

### Source Structure
- `src/config/` — global definitions, macros (CLASS, METHOD, NEW, CALL, SCRIPT, EVENT), structs
- `src/core/` — boot, IRQ handling, dynamic memory allocation (WRAM, VRAM, CGRAM, DMA)
- `src/object/` — game object classes (backgrounds, sprites, HDMA effects, MSU-1 interface, audio, player, events, etc.)
- `src/text/` — text string variables and rendering
- `src/*.script` — top-level control scripts (main, title_screen, levels, game_over, continue_screen)
- `data/events/` — 516 XML chapter definitions with timing and event data
- `data/chapters/` — generated assembly: chapter scripts + event data tables
- `tools/` — Python utilities for graphics conversion, video pipeline, audio handling, and XML parsing

## Documentation Map
- `README.md` (this file) — Project overview and status
- **[`BUILD.md`](BUILD.md)** — Build instructions, troubleshooting, and ROM bank reference
- **[`QUICKREF.md`](QUICKREF.md)** — Quick reference card for common commands
- `src/README.md` — Boot/title/score/MSU1 script flow and architecture
- `tools/README.md` — Asset pipeline tools and MSU-1 video generation
- `data/backgrounds/README.md` — Background asset status
- `data/sprites/README.md` — Sprite inventory and descriptions
- `data/sounds/README.md` — Sound system and asset documentation
- `data/events/README.md` — Chapter XML reference
- `data/chapter_event_inventory.md` — Event coverage tracking (516 chapters)

## Hardware Targets
- NTSC Super Nintendo hardware
- SD2SNES / FXPAK Pro (MSU-1 required for video playback)
- Mesen 2, SNES9x, bsnes for debugging and iteration

## Credits
- **Engine:** [Super Road Blaster](https://github.com/snesdev0815/SNES-SuperRoadBlaster) by snesdev0815 — the 65816 OOP framework, MSU-1 video playback, SPC700 audio engine, and core infrastructure that makes this project possible
- **Game Data:** Dragon's Lair chapter timing and event data derived from [DirkSimple](https://github.com/icculus/DirkSimple) by icculus

## License
This project includes no commercial Dragon's Lair assets. All extracted assets must be supplied by the user. This repository contains engine code and converter tools only.
