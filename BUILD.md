# Build System & Troubleshooting Guide

This document details the build process for **SNES-SuperDragonsLairArcade**, including the tools used, the makefile structure, and common troubleshooting steps.

## Build System Overview

The project uses a standard `make` based build system that orchestrates several tools to convert assets and compile the code.

### Core Tools
1.  **WLA-DX (Assembler/Linker):**
    *   `wla-65816`: Assembler for the SNES 65816 CPU.
    *   `wla-spc700`: Assembler for the Sony SPC700 audio chip.
    *   `wlalink`: Linker that combines object files into the final ROM.
2.  **Graphics Converters:**
    *   `superfamiconv`: (Recommended) High-performance C++ tool for converting PNGs to SNES tiles/palettes.
    *   `gracon.py`: (Legacy) Python-based converter. Slower but functional.
3.  **Asset Processors:**
    *   `animationWriter_sfc.py`: Wraps `superfamiconv` to process animation folders.
    *   `xmlsceneparser.py`: Converts DirkSimple XML/Lua scenes to assembly event scripts.
    *   `msu1blockwriter.py`: Packages video/audio for MSU-1.

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

### Environment Variables
*   **`USE_SUPERFAMICONV=1`**: Enables the modern, fast build pipeline. Without this, the build defaults to the slower `gracon.py`.

## Common Build Errors & Fixes

### 1. "Unknown Label" or "Symbol Not Found"
*   **Cause:** The assembler cannot find a label referenced in your code.
*   **Fix:**
    *   Ensure the label is exported (`.export`) if it's in a different file.
    *   Check for typos.
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

### 4. "Bank Overflow" or "Section too large"
*   **Cause:** You are trying to fit too much code/data into a single ROM bank (32KB or 64KB).
*   **Fix:** Move large data tables or code to a different bank using `.section ... superfree` or by adjusting the memory map in `src/config/memory.inc`.

### 5. "Make: *** No rule to make target..."
*   **Cause:** `make` cannot find a source file required to build a target.
*   **Fix:**
    *   Check if you deleted or renamed a file.
    *   Run `make clean` to remove stale dependency files.
    *   Check `task.md` or `lessons_learned.md` for missing legacy assets (e.g., `levelcomplete.0`).

## Debugging Tips
*   **Verbose Build:** Run `make -d` to see exactly why make is rebuilding a target.
*   **Linker File:** Check `build/lnk/linkobjs.lst` to see exactly which object files are being linked.
*   **Map File:** WLA-DX can generate a map file (add `-M` to flags) to see where symbols are placed in memory.
