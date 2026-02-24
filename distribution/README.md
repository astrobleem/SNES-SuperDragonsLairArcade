# Distribution Directory

This directory holds the final ROM, MSU-1 video data, and PCM audio tracks
ready for use on real hardware (SD2SNES/FXPAK Pro) or emulators with MSU-1
support.

## Contents (after build + MSU generation)

- `SuperDragonsLairArcade.sfc` — ROM (copied by `make`)
- `SuperDragonsLairArcade.msu` — MSU-1 video data (from `generate_msu_data.py`)
- `SuperDragonsLairArcade-*.pcm` — MSU-1 audio tracks (per chapter)
- `manifest.xml` — emulator manifest (for bsnes/higan)
- `test_scene_*.lua` — Mesen playthrough test scripts

## Usage

**Emulator testing (Mesen 2):**
```bat
cmd.exe /c "cd /d <project>\distribution && <project>\mesen\Mesen.exe --testrunner SuperDragonsLairArcade.sfc test_scene_02_vestibule.lua > out.txt 2>&1"
```

**SD2SNES/FXPAK Pro:** Copy all files to the SD card root or a subdirectory.
