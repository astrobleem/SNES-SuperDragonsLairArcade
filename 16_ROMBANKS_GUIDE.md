# SuperDragonsLair: Full 16 ROM Banks Conversion Guide

## Overview

This guide shows how to properly configure SuperDragonsLair for 16 ROM banks (1MB) and generate the required manifest.

## 1. ROM Bank Configuration

### File: `src/config/config.inc`

Update the ROMBANKS setting:

```assembly
.ROMBANKSIZE $10000    ; Every ROM bank is 64 KBytes in size
.ROMBANKS 16           ; 8Mbits = 1MB (16 banks x 64KB)
```

**Key Points:**
- `.ROMBANKS 16` = 1MB ROM (16 × 64KB)
- `.ROMBANKS 4` = 256KB ROM (4 × 64KB) ← Original design
- The comment should reflect this is for Dragon's Lair expansion

## 2. Manifest Generation

### What is a Manifest?

The `manifest.xml` tells emulators (like bsnes/higan) how to load your ROM, including:
- ROM size and memory mapping
- MSU-1 audio track locations
- Save RAM configuration

### Creating manifest.xml for SuperDragonsLair

Create `e:\gh\SNES-SuperDragonsLairArcade\SuperDragonsLairArcade.sfc\manifest.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<cartridge region="NTSC">
  <rom name="SuperDragonsLairArcade.sfc" size="0x100000">
    <map mode="linear" address="40-7f:0000-ffff"/>
    <map mode="linear" address="c0-ff:0000-ffff"/>
    <map mode="shadow" address="00-3f:8000-ffff"/>
    <map mode="shadow" address="80-bf:8000-ffff"/>
  </rom>
  <map address="00-3f:8000-ffff" id="rom" mode="shadow"/>
  <map address="80-bf:8000-ffff" id="rom" mode="shadow"/>
  <msu1>
    <!-- Add your audio tracks here -->
    <track number="1">
      <name>SuperDragonsLairArcade-1.pcm</name>
    </track>
    <track number="2">
      <name>SuperDragonsLairArcade-2.pcm</name>
    </track>
    <!-- Add more tracks as needed -->
  </msu1>
</cartridge>
```

**Important Values:**
- `size="0x100000"` = 1MB (matches 16 ROM banks)
- `region="NTSC"` or `"PAL"` depending on your version
- ROM name must match your actual .sfc filename

### Size Reference Table

| ROM Banks | Size (Hex) | Size (Decimal) | Size (Display) |
|-----------|------------|----------------|----------------|
| 4         | 0x40000    | 262144         | 256KB          |
| 8         | 0x80000    | 524288         | 512KB          |
| 16        | 0x100000   | 1048576        | 1MB            |
| 32        | 0x200000   | 2097152        | 2MB            |

## 3. Full Directory Structure

For SuperDragonsLair with MSU-1, you need:

```
e:\gh\SNES-SuperDragonsLairArcade\SuperDragonsLairArcade.sfc\
├── SuperDragonsLairArcade.sfc          (1MB ROM)
├── SuperDragonsLairArcade.msu          (MSU-1 descriptor)
├── SuperDragonsLairArcade-1.pcm        (Audio track 1)
├── SuperDragonsLairArcade-2.pcm        (Audio track 2)
├── SuperDragonsLairArcade-N.pcm        (More tracks...)
└── manifest.xml                        (This file)
```

## 4. Verification Steps

After setting to 16 ROM banks and creating manifest:

1. **Build the ROM**:
   ```bash
   cd e:\gh\SNES-SuperDragonsLairArcade
   make clean
   make
   ```

2. **Check ROM size**:
   ```bash
   wsl bash -c "stat -c '%s' build/SuperDragonsLairArcade.sfc"
   ```
   - Should output: `1048576` (1MB)

3. **Verify ROM header**:
   ```bash
   wsl bash -c "dd if=build/SuperDragonsLairArcade.sfc bs=1 skip=65472 count=64 2>/dev/null | hexdump -C"
   ```
   - Should show ROM size byte = `0x0a` (1MB HiROM)

4. **Test in emulator**:
   - Load with bsnes/higan (native manifest support)
   - Or SNES9x with MSU-1 enabled

## 5. Common Issues

### Issue: "ROM too large" error
**Solution**: Make sure ROMBANKS is set to 16 in config.inc

### Issue: Emulator doesn't find MSU files
**Solution**: 
- Verify all files are in same directory
- ROM name in manifest matches actual filename
- .pcm files follow naming convention

### Issue: Checksum errors
**Solution**: WLA-DX auto-calculates checksums, ignore warnings unless ROM won't boot

## 6. MSU-1 Audio Track Naming

The MSU-1 standard requires specific naming:
- Base name: `SuperDragonsLairArcade`  
- Data file: `SuperDragonsLairArcade.msu`
- Tracks: `SuperDragonsLairArcade-1.pcm`, `SuperDragonsLairArcade-2.pcm`, etc.

**All files must use the EXACT same base name!**

## Quick Checklist

- [ ] Set `.ROMBANKS 16` in `src/config/config.inc`
- [ ] Build ROM with `make clean && make`
- [ ] Verify ROM is 1048576 bytes (1MB)
- [ ] Create `manifest.xml` with `size="0x100000"`
- [ ] Place ROM, .msu, .pcm files, and manifest in same directory
- [ ] Test in emulator
