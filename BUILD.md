# Build System & Troubleshooting Guide

This document details the build process for **SNES-SuperDragonsLairArcade**, including the tools used, the makefile structure, and common troubleshooting steps.

## Build System Overview

The project uses a standard `make` based build system that orchestrates several tools to convert assets and compile the code.

> [!WARNING]
> **WLA-DX Version:** This project requires **WLA-DX 9.3** (wlalink 5.6). Pre-built binaries are included in `tools/wla-dx-9.5-svn/`. Version 9.4+ breaks the build due to changed branch reference handling that causes FIX_REFERENCES errors on code with long macro expansions.

> [!WARNING]
> **`make clean` deletes `data/chapters/`** — this wipes all extracted video frame data. If you have generated MSU-1 video frames, use `make` without `clean` to preserve them. A full re-extraction takes ~1 hour.

### Core Tools
1.  **WLA-DX 9.3 (Assembler/Linker):**
    *   `wla-65816`: Assembler for the SNES 65816 CPU.
    *   `wla-spc700`: Assembler for the Sony SPC700 audio chip.
    *   `wlalink`: Linker that combines object files into the final ROM.
    *   **Important:** The SPC700 and 65816 assemblers share `.o` files in the same directory. You must `make clean` between building each target if switching between them manually.
2.  **Graphics Converters:**
    *   `superfamiconv`: High-performance C++ tool for converting PNGs to SNES tiles/palettes (~100x faster than gracon.py).
    *   `gracon.py`: Legacy Python-based converter. Slower but functional.
3.  **Asset Processors:**
    *   `animationWriter_sfc.py`: Wraps `superfamiconv` to process animation folders (default pipeline).
    *   `xmlsceneparser.py`: Converts DirkSimple XML scenes to assembly event scripts.
    *   `msu1blockwriter.py`: Packages video tile data for MSU-1.
4.  **MSU-1 Video Pipeline:**
    *   `generate_msu_data.py`: Orchestrates the full video conversion pipeline (ffmpeg → superfamiconv → tile reduction → msu1blockwriter.py). Produces the ~568 MB `.msu` file.

## The Makefile Explained

The `makefile` handles dependency tracking and tool invocation. Here are key variables and flags:

### Assembler Flags (`wla-65816`)
*   **`-o`**: Output object file.
*   **`-I` (Include Path):** WLA-DX searches for included files relative to the current directory. The makefile runs from the project root, so paths in `.include` directives should be relative to the root (e.g., `.include "src/config/config.inc"`).
    *   *Troubleshooting:* If you see "File not found", check if the path is relative to the project root.

### Linker Flags (`wlalink`)
*   **`-d`**: Discard unused symbols (helps reduce ROM size).
*   **`-s`**: Silent mode (reduces output clutter).
*   **`-r`**: Real SNES checksum calculation (fixes the header checksum).
*   **`-v`**: Verbose mode (useful for debugging linking errors).

## ROM Bank Reference

| ROM Banks | Size (Hex) | Size (Decimal) | Size (Display) |
|-----------|------------|----------------|----------------|
| 4         | 0x40000    | 262144         | 256 KB         |
| 8         | 0x80000    | 524288         | 512 KB         |
| **16**    | **0x100000** | **1048576**  | **1 MB**       |
| 32        | 0x200000   | 2097152        | 2 MB           |

The project uses 16 banks (1 MB), configured as HiROM+FastROM. ROM size byte in header = `0x0a`.

## Common Build Errors & Fixes

### 1. "Unknown Label" or "Symbol Not Found"
*   **Cause:** The assembler cannot find a label referenced in your code.
*   **Fix:**
    *   Ensure the label is exported (`.export`) if it's in a different file.
    *   Check for typos.
    *   Labels starting with `_` are LOCAL to the compilation unit — they cannot be referenced across `.o` files. Remove the `_` prefix for cross-file labels.
    *   If it's a generated event label (e.g., `T_CLSS_...`), the event name might be too long (see below).

### 2. "Symbol Name Too Long"
*   **Cause:** WLA-DX has a limit on symbol lengths (approx 30 chars).
*   **Fix:** Keep event names and labels short (under 13 chars for events).
    *   *Bad:* `Event.falling_platform_long_fell_to_death`
    *   *Good:* `Event.fall_plat_die`

### 3. "Redefinition of Symbol"
*   **Cause:** A label or struct is defined in multiple places.
*   **Fix:**
    *   Use include guards (`.ifndef MY_FILE_H ...`) in header files.
    *   **Do not** define `struct vars` in headers included by multiple files. Define them in `.65816` files instead.
    *   **`.def` cannot redefine** — a second `.def X Z` after `.def X Y` is silently ignored. Use `.redefine` or `.undefine`+`.define` for redefinition.

### 4. "Bank Overflow" or "Section too large"
*   **Cause:** You are trying to fit too much code/data into a single ROM bank (32KB or 64KB).
*   **Fix:** Move large data tables or code to a different bank using `.section ... superfree` or by adjusting the memory map in `src/config/memory.inc`.

### 5. "Out of section numbers"
*   **Cause:** WLA-DX has a maximum of ~512 sections per compilation unit.
*   **Fix:** Combine data into fewer, larger sections (e.g., one `superfree` section for all chapter data instead of one per chapter).

### 6. "Too large distance" (branch out of range)
*   **Cause:** A conditional branch (`beq`, `bne`, etc.) exceeds the 127-byte limit. Commonly happens when NEW/CALL macros expand to many bytes between the branch and its target.
*   **Fix:** Replace `beq far_target` with `bne _skip / jmp far_target / _skip:`. Use named labels instead of anonymous `+`/`++` labels for clarity — `+`, `++`, `+++` are distinct tiers in WLA-DX.

### 7. "FIX_REFERENCES" errors at link time
*   **Cause:** Usually a `_` prefixed label being referenced across compilation units (local scope), or using WLA-DX 9.4+ (changed branch reference semantics).
*   **Fix:** Remove `_` prefix from cross-file labels. Ensure you are using WLA-DX 9.3.

### 8. "Make: *** No rule to make target..."
*   **Cause:** `make` cannot find a source file required to build a target.
*   **Fix:**
    *   Check if you deleted or renamed a file.
    *   Run `make clean` to remove stale dependency files.

## Build Warnings That Are Normal
*   `DIRECTIVE_ERROR` about redefined `__init`/`__play`/`__kill` — from CLASS macro in event files.
*   `DISCARD` messages — unused event sections stripped by the `-d` linker flag.
*   "Invalid Checksum" in emulators — checksums are hardcoded in the ROM header; this is expected.

## Debugging Tips
*   **Verbose Build:** Run `make -d` to see exactly why make is rebuilding a target.
*   **Linker File:** Check `build/lnk/linkobjs.lst` to see exactly which object files are being linked.
*   **Map File:** WLA-DX can generate a map file (add `-M` to flags) to see where symbols are placed in memory.
*   **Symbol Table:** After each build, `build/SuperDragonsLairArcade.sym` contains all symbol addresses.
