# Sound Assets & System Documentation

## Sound Assets Audit

The following sound files live in this directory (`data/sounds/`). The build system automatically converts `.wav` files to SNES `.brr` format.

| Sound File | Status | Description |
| --- | --- | --- |
| `ok.sfx_normal.wav` | ✅ **Keep** | Generic confirmation cue (used after name entry, menu selections). |
| `shuriken.sfx_normal.wav` | ✅ **Keep** | Dirk's shuriken throw cue. |
| `technique.sfx_normal.wav` | ✅ **Keep** | Special move / power-up activation cue. |
| `turn.sfx_loop.wav` | ✅ **Keep** | Turn left/right cue. |
| `dragon_roar.sfx_normal.wav` | 🆕 **New** | Deep, resonant dragon roar for boss intros or victory scenes. |
| `sword_clank.sfx_normal.wav` | 🆕 **New** | Metallic sword-clank for hit feedback. |
| `brake.sfx_loop.wav` | ⚠️ **Legacy** | RoadBlaster brake/duck cue (unused in Dragon's Lair). |
| `turbo.sfx_loop.wav` | ⚠️ **Legacy** | RoadBlaster turbo cue (unused in Dragon's Lair). |

> **Note:** Legacy sounds are retained for reference and to prevent build errors with existing code, but they are ignored by the Dragon's Lair engine.

## How the Sound System Works

The SNES audio subsystem (SPC700) has limited RAM (64KB) for all code, music, and samples. Sounds are organized into **Sample Packs** to manage this memory.

### 1. File Naming Convention
The build system uses filenames to determine processing flags:
- `*.sfx_normal.wav`: One-shot sound effect.
- `*.sfx_loop.wav`: Looping sound effect.

### 2. Registration (`spcinterface.h`)
To make a sound available to the engine, it must be registered in `src/object/audio/spcinterface.h`:

1.  **Enum Entry:** Added to the `SAMPLE.0.*` enum list (e.g., `SAMPLE.0.DRAGON_ROAR`).
2.  **Export:** Exported as a symbol (e.g., `.export SAMPLE.0.DRAGON_ROAR`).
3.  **Sample Header:** A header block defining volume, pitch, ADSR, and gain (e.g., `Sample6Header`).
4.  **Binary Include:** The converted `.brr` file is included in the `SamplePack0` section (e.g., `.incbin "build/data/sounds/dragon_roar.sfx_normal.brr"`).

### 3. Adding a New Sound
1.  Place the `.wav` file in `data/sounds/`.
2.  Update `src/object/audio/spcinterface.h` to register the new sample index and header.
3.  Run `make`. The build system will convert the wav to brr and link it.
4.  Trigger it in code using `NEW Spc.CLS.PTR` and `CALL Spc.SpcPlaySoundEffect.MTD`.
