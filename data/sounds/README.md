# Sound Assets & System Documentation

## Sound Assets

The following sound files live in this directory (`data/sounds/`). The build system automatically converts `.wav` files to SNES `.brr` format.

| Sound File | Build Status | Description |
| --- | --- | --- |
| `ok.sfx_normal.wav` | **Active** (SPC build) | Generic confirmation cue (menu selections, name entry). |
| `shuriken.sfx_normal.wav` | **Active** (SPC build) | Action cue (attack/throw sound effect). |
| `technique.sfx_normal.wav` | **Active** (SPC build) | Special move / power-up activation cue. |
| `turn.sfx_loop.wav` | **Active** (SPC build) | Turn left/right looping cue. |
| `brake.sfx_loop.wav` | **Active** (SPC build) | Legacy RoadBlaster brake/duck cue (retained in build). |
| `turbo.sfx_loop.wav` | **Active** (SPC build) | Legacy RoadBlaster turbo cue (retained in build). |
| `dl_accept.sfx_normal.wav` | WAV only | Dragon's Lair accept/confirm cue (not yet registered in SPC build). |
| `dl_buzz.sfx_normal.wav` | WAV only | Dragon's Lair error/buzz cue (not yet registered in SPC build). |
| `dl_credit.sfx_normal.wav` | WAV only | Dragon's Lair credit insert cue (not yet registered in SPC build). |

> **Note:** The SPC700 has only 64 KB RAM total (~57.5 KB available for samples after engine code). The 6 active samples use ~42 KB of BRR data. `dragon_roar` + `sword_clank` WAVs were deleted because they overflowed SPC RAM (~65 KB total). The `dl_accept`, `dl_buzz`, and `dl_credit` sounds are candidates for future integration if space allows.

## How the Sound System Works

The SNES audio subsystem (SPC700) has limited RAM (64 KB) for all code, music, and samples. Sounds are organized into **Sample Packs** to manage this memory.

### 1. File Naming Convention
The build system uses filenames to determine processing flags:
- `*.sfx_normal.wav`: One-shot sound effect.
- `*.sfx_loop.wav`: Looping sound effect.

### 2. Registration (`spcinterface.h`)
To make a sound available to the engine, it must be registered in `src/object/audio/spcinterface.h`:

1.  **Enum Entry:** Added to the `SAMPLE.0.*` enum list (e.g., `SAMPLE.0.OK`).
2.  **Export:** Exported as a symbol (e.g., `.export SAMPLE.0.OK`).
3.  **Sample Header:** A header block defining volume, pitch, ADSR, and gain.
4.  **Binary Include:** The converted `.brr` file is included in the `SamplePack0` section.

Currently 6 samples are registered: BRAKE, TECHNIQUE, TURBO, TURN, OK, SHURIKEN.

### 3. Adding a New Sound
1.  Place the `.wav` file in `data/sounds/`.
2.  **Check total BRR size** — all samples in `SamplePack0` must fit within ~57.5 KB of SPC RAM.
3.  Update `src/object/audio/spcinterface.h` to register the new sample index and header.
4.  Run `make`. The build system will convert the WAV to BRR and link it.
5.  Trigger it in code using `NEW Spc.CLS.PTR` and `CALL Spc.SpcPlaySoundEffect.MTD`.
