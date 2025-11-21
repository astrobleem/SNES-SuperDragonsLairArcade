# SNES-SuperDragonsLairArcade
# Super Dragon’s Lair Arcade (SNES)

Super Dragon’s Lair Arcade is a full-motion-video (FMV) game for the Super Nintendo Entertainment System, targeting real NTSC SNES hardware and the SD2SNES/FXPAK Pro MSU-1 enhancement chip.

This project is a conversion/translation of the existing
SuperRoadBlaster
 engine into a SNES version of Dragon’s Lair (Arcade) — preserving the look, flow, and timing of the arcade original as closely as the SNES/MSU-1 hardware allows.

The RoadBlaster engine already supports:

MSU-1 FMV playback (tile-streaming)

MSU-1 PCM audio

Scene scripting

Tilemap backgrounds

Sprite overlays

Controller input windows

Full build system

This project focuses primarily on asset replacement, not engine changes.

🎯 Project Goals

Recreate the original Dragon’s Lair arcade experience on the SNES

Retain RoadBlaster’s battle-tested MSU-1 FMV engine

Replace all RoadBlaster assets with Dragon’s Lair equivalents:

FMV scenes

Backgrounds

Sprites

UI elements

Audio tracks

Input prompts

Maintain original arcade scene timings and player cues

Produce a fully playable SNES ROM + MSU-1 PCM set

🕹️ Hardware Targets

This project runs on real hardware:

NTSC Super Nintendo

SD2SNES / FXPAK Pro (required for MSU-1)

SNES9x / bsnes for debugging and dev-iteration

We test against both real hardware and accurate emulators.

📁 Repository Structure
/src/           65816 assembly source (core engine, scene tables, logic)
/data/          Graphics, tilemaps, FMV frames, audio (Dragon’s Lair assets)
/tools/         Utilities for converting images, tiles, maps, audio, XML -> binary
/tests/         ROM tests and automated validation
makefile        Full build pipeline (ROM + MSU1)
README.md       You’re reading it



🔄 What We Replace (Top-Level Checklist)
Component	Status	Description
FMV Sequences	☐	Replace all RoadBlaster MSU-1 video frames with Dragon’s Lair scenes
PCM Audio	☐	Convert arcade audio to MSU-1 PCM
Backgrounds	☐	Generate SNES-compatible 4bpp backgrounds from DL art
HUD / UI	☐	Title logo, menus, prompts, “Quest Advanced” cards
Sprites	☐	Replace RoadBlaster overlays with Dirk/Daphne cues
Scene Scripts	☐	Update XML input windows + scene flow
Build System	✔	Working via original RoadBlaster makefile

This checklist mirrors the project board and planned GitHub issues.

🧩 Development Workflow

Extract Dragon’s Lair arcade assets

Convert assets into SNES formats using tools in /tools

Replace RoadBlaster data files in /data/

Regenerate scene tables (xml2bin)

Build ROM + MSU1 pack (make)

Test on real hardware (SD2SNES)

Adjust timings → repeat

Most of the heavy lifting is asset preparation rather than code changes.

🧪 Building

Requirements:

make

WLA-DX toolchain

Python (for some tools)

Works on Linux, macOS, and Windows (WSL recommended)

Build the ROM and MSU1 pack:

make clean
make


Outputs appear in bin/.

🚧 Status

Early stages.
The RoadBlaster engine is functioning and fully buildable.
We are presently:

Cataloging all RoadBlaster assets

Documenting tools

Setting up the Dragon’s Lair asset pipeline

Beginning first background/splash-screen conversions

📌 License

This project includes no commercial Dragon’s Lair assets.
All extracted assets must be supplied by the user.
This repository contains ONLY engine code and converter tools
