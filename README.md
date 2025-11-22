# Super Dragon’s Lair Arcade (SNES)

Super Dragon’s Lair Arcade is a full-motion-video (FMV) game for the Super Nintendo Entertainment System, targeting real NTSC SNES hardware and the SD2SNES/FXPAK Pro MSU-1 enhancement chip.

The game translates the battle-tested RoadBlaster engine into a faithful, MSU-1–powered take on the arcade original. Engineering is largely settled; our current focus is preparing Dragon’s Lair–appropriate assets and wiring them into the existing scene system.

🎯 Project Goals

- Recreate the original Dragon’s Lair arcade experience on the SNES.
- Retain RoadBlaster’s battle-tested MSU-1 FMV engine.
- Replace all RoadBlaster assets with Dragon’s Lair equivalents (video, audio, sprites, UI, input prompts).
- Maintain original arcade scene timings and player cues.
- Produce a fully playable SNES ROM + MSU-1 PCM set.

📈 Current Progress

- Chapter XMLs in `data/events/` capture the current Dragon’s Lair scene list (e.g., `crypt_creeps`, `rolling_balls`, `throne_room`).
- Root engine scripts are now documented with theming guidance in `src/README.md`, including notes to retheme remaining martial-arts SFX on the title screen.
- Chapter event coverage has been inventoried across 40 scenes; 352 unique event types are referenced, with 14 implemented and 351 still needing object handlers.

🎮 Prompt Control Standard

- Directional prompts are bound to the D-pad: left/right stay horizontal, while up corresponds to RoadBlasters’ old **accelerate** cue and down to the **brake** cue.
- The action/turbo prompt uses button A as the canonical action button; button B should be treated as an incorrect defensive tap when action is expected.
- The legacy RoadBlasters prompt names `Event.accelerate` and `Event.brake` remain for compatibility but are considered deprecated; use them as up/down inputs until Dragon’s Lair–specific prompt handlers replace them.

🧭 Documentation Map

- `src/README.md` – High-level tour of the boot/title/score/MSU1 scripts plus theming expectations.
- `data/events/README.md` – Overview of the curated Dragon’s Lair chapter XMLs now tracked in this repo.
- `data/chapter_event_inventory.md` – Chapter-by-chapter event coverage and gaps to implement in the engine.
- `tools/README.md` – Python 2.7 tooling notes and converter usage (image, tile, XML, PCM).

🕹️ Hardware Targets

This project runs on real hardware:

NTSC Super Nintendo

SD2SNES / FXPAK Pro (required for MSU-1)

SNES9x / bsnes for debugging and dev-iteration

We test against both real hardware and accurate emulators.

📁 Repository Structure

- `src/` – 65816 assembly source (core engine, scene tables, logic).
- `data/` – Backgrounds, HUD assets, audio, chapter XMLs, and other converted data. See `data/backgrounds/README.md` for the current audit of RoadBlaster placeholders.
- `data/events/` – Dragon’s Lair chapter XML descriptors used by the toolchain (legacy RoadBlaster XMLs have been removed).
- `tools/` – Utilities for converting images, tiles, maps, audio, XML -> binary (extraneous helper scripts have been trimmed).
- `tests/` – ROM tests and automated validation.
- `makefile` – Full build pipeline (ROM + MSU1).
- `README.md` – You’re reading it.



🔄 What We Replace (Top-Level Checklist)

| Component     | Status      | Notes |
| ---           | ---         | --- |
| FMV Sequences | In progress | Chapter scripts exist per scene in `resources/`; frame conversion and MSU1 packaging remain. |
| PCM Audio     | Planned     | Use MSU1 PCM once chapter audio is extracted and normalized. |
| Backgrounds   | In progress | Audit of remaining RoadBlaster captures lives in `data/backgrounds/README.md`; replacements needed for title, high score, level-complete, and score entry screens. |
| HUD / UI      | In progress | Title/logo and prompt replacements tracked alongside background updates. |
| Sprites       | Planned     | Sprite overlays still reference RoadBlaster cues and need Dirk/Daphne equivalents. |
| Scene Scripts | In progress | Event coverage inventoried; most event object types still need implementations. |
| Build System  | ✅ Done     | RoadBlaster makefile builds the ROM and MSU1 pack. |

This checklist mirrors the project board and planned GitHub issues.

🧩 Development Workflow

Extract Dragon’s Lair arcade assets

Convert assets into SNES formats using tools in /tools

Replace RoadBlaster data files in /data/ (legacy RoadBlaster XMLs and unused helper scripts have already been removed)

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

The RoadBlaster engine is functioning and fully buildable. Current focus:

- Replace RoadBlaster-branded backgrounds called out in `data/backgrounds/README.md`.
- Implement the missing scene events captured in `data/chapter_event_inventory.md` and wire them to engine objects.
- Retime title/audio cues to match the lair theme noted in `src/README.md`.

📌 License

This project includes no commercial Dragon’s Lair assets.
All extracted assets must be supplied by the user.
This repository contains ONLY engine code and converter tools
