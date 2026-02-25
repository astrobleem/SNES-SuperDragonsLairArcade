# Super Dragon's Lair Arcade (SNES)

![Complete Package](schwag/complete_package.png)

**Super Dragon's Lair Arcade** is a full-motion-video (FMV) game for the Super Nintendo Entertainment System, built on the [Super Road Blaster](https://github.com/snesdev0815/SNES-SuperRoadBlaster) engine by snesdev0815. It runs on real NTSC SNES hardware with MSU-1 audio/video on SD2SNES/FXPAK Pro.

This is a faithful recreation of the 1983 arcade classic — the legendary laserdisc adventure, now on your SNES, complete with authentic packaging and documentation that would feel right at home on a store shelf in 1993.

## Gameplay

![Gameplay Preview](SomeGamePlay.gif)

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
- Written purely in 65816 assembly with a custom object-oriented framework
- Dynamic allocation of work RAM, video RAM, color palettes, and DMA channels
- MSU-1 full-motion video playback at 23.976 fps with per-chapter audio tracks
- SPC700 audio engine with BRR sample playback
- Script system for cooperative game flow scheduling

### Dragon's Lair Arcade
- **516 chapters across 29 scenes** covering the complete Dragon's Lair arcade game
- **3 game modes** — Arcade Mode (13 randomized scenes + dragon finale), Boss Rush (5 boss encounters on loop), Oops, All Traps! (7 environmental hazard scenes on loop)
- **Randomized scene order** — each playthrough shuffles scenes so no two runs are the same
- **Full menu system** — Arcade Mode, Boss Rush, Oops All Traps!, Options (High Scores, Sound Test, Scene Select)
- **Scene select** — jump to any of the 29 scenes directly from the title screen
- **Attract mode** — automated demo playback after 60 seconds idle on the title screen
- **Credit/coin system** — SELECT inserts credits during gameplay, continue screen on game over with countdown timer
- **Pause menu overlay** — shows scene name, score, lives, credits, chapter, and current video frame
- **40+ event classes** for gameplay — directions, sequences, checkpoints, room transitions, cutscenes, plus scene-specific events (rolling balls, tentacle room, flying horse, giddy goons, and more)

## What You Get

- **All 29 scenes fully playable** across 3 game modes with randomized scene order per playthrough
- **28/28 automated scene tests passing** — every gameplay scene verified beatable with correct inputs
- **Tested and working on real NTSC SNES hardware** with SD2SNES / FXPAK Pro
- **Complete boot-to-gameplay loop** — Boot, MSU-1 init, losers screen, logo intro, title screen, gameplay

## Building

The project builds under Linux/WSL using `make` and a Python 3 toolchain. The assembler (WLA-DX 9.3) comes pre-built in the repo.

```bash
# Standard build (assembles the ROM in ~2-3 minutes)
make clean && make
```

The MSU-1 video data pipeline is a separate step that extracts video frames from Daphne laserdisc segment files and packages them for the SNES.

For full build instructions, prerequisites, video pipeline details, and troubleshooting, see **[`BUILD.md`](BUILD.md)**.

## How It Works

The game is written in 65816 assembly with an abstraction layer inspired by object-oriented programming. Almost everything — textlayers, sound, scores, sprites, keypress events — is an object that gets created, updated each frame, and destroyed when no longer needed. Resources like VRAM, palettes, and DMA channels are allocated dynamically.

The game flow is driven by **scripts** — cooperative routines that control what happens on screen. Each of the 29 scenes is made up of **chapters** (short video segments with timed events). When the player presses the right direction at the right moment, the game transitions to the next chapter. Miss, and Dirk meets a gruesome end.

```
Boot → MSU-1 init → losers screen → logo intro → title screen
  → level select → first chapter → [player input] → next chapter → ... → scene complete → next scene
```

Chapter events are generated from XML data files in `data/events/` — over 516 of them, covering every move in the original arcade game.

### Source Layout
- `src/` — all 65816 assembly source (core engine, objects, scripts)
- `data/events/` — 516 XML chapter definitions with timing and event data
- `data/chapters/` — generated assembly from the XML files
- `tools/` — Python utilities for video pipeline, graphics conversion, and XML parsing
- `schwag/` — print-ready packaging materials (manual, stickers, cards, etc.)

## Documentation

- **[`BUILD.md`](BUILD.md)** — Build instructions, troubleshooting, and ROM bank reference
- **[`QUICKREF.md`](QUICKREF.md)** — Quick reference card for common commands
- [`src/README.md`](src/README.md) — Script flow and engine architecture
- [`tools/README.md`](tools/README.md) — Asset pipeline tools and MSU-1 video generation
- [`data/events/README.md`](data/events/README.md) — Chapter XML reference
- [`data/sounds/README.md`](data/sounds/README.md) — Sound system and asset documentation
- [`data/backgrounds/README.md`](data/backgrounds/README.md) — Background asset status
- [`data/chapter_event_inventory.md`](data/chapter_event_inventory.md) — Event coverage tracking (516 chapters)

## Hardware Targets

- NTSC Super Nintendo with SD2SNES / FXPAK Pro (MSU-1 required for video playback)
- Also runs in Mesen 2, SNES9x, and bsnes for development and testing

## Credits

- **Engine:** [Super Road Blaster](https://github.com/snesdev0815/SNES-SuperRoadBlaster) by snesdev0815 — the 65816 OOP framework, MSU-1 video playback, SPC700 audio engine, and core infrastructure that makes this project possible
- **Game Data:** Dragon's Lair chapter timing and event data derived from [DirkSimple](https://github.com/icculus/DirkSimple) by icculus

## License

This project includes no commercial Dragon's Lair assets. All extracted assets must be supplied by the user. This repository contains engine code and converter tools only.
