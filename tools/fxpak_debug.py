#!/usr/bin/env python3
"""
FXPAK Pro USB debugger - reads SNES memory via QUsb2Snes WebSocket API.
Dumps OOP stack, allocation tables, exception state, and other key state
for crash diagnosis.

Usage: python tools/fxpak_debug.py
Requires: QUsb2Snes running and FXPAK connected via USB.
"""

import asyncio
import struct
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

# QUsb2Snes WebSocket endpoint
WS_URL = "ws://localhost:23074"

# USB2SNES address mapping: SNES $7Exxxx (WRAM) -> USB2SNES $F5xxxx
# Formula: usb2snes_addr = 0xF50000 + (snes_addr - 0x7E0000)
def snes_to_usb(snes_addr):
    if snes_addr >= 0x7E0000:
        return 0xF50000 + (snes_addr - 0x7E0000)
    # For zero-page / low RAM ($0000-$1FFF), map through bank 7E
    if snes_addr < 0x2000:
        return 0xF50000 + snes_addr
    raise ValueError(f"Cannot map SNES address ${snes_addr:06X}")

# ============================================================================
# Key WRAM addresses — UPDATE THESE from build/SuperDragonsLairArcade.sym
# after every build that changes RAMSECTIONs!
# ============================================================================
ADDR = {
    # OOP Stack (48 slots * 16 bytes = 768 bytes)
    'OopStack':                 0x7E6988,

    # VRAM allocation
    'VRAM_alloc_id':            0x7E6E8F,  # currentVramAllocationId (byte)
    'VRAM_alloc_blocks':        0x7E6E9A,  # 256 bytes
    'VRAM_alloc_end':           0x7E6F9A,  # = HdmaSpcBuffer start

    # HdmaSpcBuffer (256 bytes after resize)
    'HdmaSpcBuffer':            0x7E6F9A,

    # DMA Queue
    'DMA_QUEUE_start':          0x7E709A,

    # CGRAM allocation
    'CGRAM_alloc_id':           0x7E711F,  # currentCgramAllocationId
    'CGRAM_alloc_blocks':       0x7E712C,  # 64 bytes
    'CGRAM_alloc_end':          0x7E716C,

    # WRAM allocation
    'WRAM_alloc_id':            0x7E716C,  # currentWramAllocationId
    'WRAM_alloc_blocks':        0x7E7175,

    # OOP dispatch state
    'currentObject':            0x7E720F,  # GLOBAL.currentObject (word)
    'currentMethod':            0x7E7211,  # GLOBAL.currentMethod (word)
    'currentClass':             0x7E7213,  # GLOBAL.currentClass (word)
    'currentObjectStr':         0x7E7215,  # 3 bytes (ptr + bank)
    'currentMethodStr':         0x7E7218,  # 3 bytes
    'currentClassStr':          0x7E721B,  # 3 bytes

    # Hardware state
    'HDMA_channel_enable':      0x7E71E5,  # GLOBAL.HDMA.CHANNEL.ENABLE

    # Game state (these are in bank 0 ZP area, $0000-$1FFF)
    'sceneRow':                 0x001A00,  # GLOBAL.sceneRow (word)
    'gameMode':                 0x001A02,  # GLOBAL.gameMode (word)

    # Exception handler state (slot 2 / ZP area)
    'excStack':                 0x001A04,  # 2 bytes - saved stack pointer
    'excA':                     0x001A06,  # 2 bytes - accumulator at crash
    'excY':                     0x001A08,  # 2 bytes - Y register at crash
    'excX':                     0x001A0A,  # 2 bytes - X register at crash
    'excDp':                    0x001A0C,  # 2 bytes - direct page at crash
    'excDb':                    0x001A0E,  # 1 byte  - data bank
    'excPb':                    0x001A0F,  # 1 byte  - program bank
    'excFlags':                 0x001A10,  # 1 byte  - P register
    'excPc':                    0x001A11,  # 2 bytes - PC (of TRIGGER_ERROR, NOT BRK location)
    'excErr':                   0x001A13,  # 2 bytes - error code (E_xxx enum)
    'excArgs':                  0x001A15,  # 8 bytes - arguments / BRK interrupt frame

    # OOP ZP pool
    'OopObjRam':                0x000010,  # start of OOP zero page pool
}

# Error code names (from error.h, errStrt=10)
ERROR_NAMES = {
    10: 'E_ObjLstFull',
    11: 'E_ObjRamFull',
    12: 'E_StackTrash',
    13: 'E_Brk',
    14: 'E_StackOver',
    15: 'E_Sa1IramCode',
    16: 'E_Sa1IramClear',
    17: 'E_Sa1Test',
    18: 'E_Sa1NoIrq',
    19: 'E_Todo',
    20: 'E_SpcTimeout',
    21: 'E_ObjBadHash',
    22: 'E_ObjBadMethod',
    23: 'E_BadScript',
    24: 'E_StackUnder',
    25: 'E_Cop',
    26: 'E_ScriptStackTrash',
    27: 'E_UnhandledIrq',
    28: 'E_Sa1BWramClear',
    29: 'E_Sa1NoBWram',
    30: 'E_Sa1BWramToSmall',
    31: 'E_Sa1DoubleIrq',
    32: 'E_SpcNoStimulusCallback',
    33: 'E_Msu1NotPresent',
    34: 'E_Msu1FileNotPresent',
    35: 'E_Msu1SeekTimeout',
    36: 'E_Msu1InvalidFrameRequested',
    37: 'E_DmaQueueFull',
    38: 'E_InvalidDmaTransferType',
    39: 'E_InvalidDmaTransferLength',
    40: 'E_VallocBadStepsize',
    41: 'E_VallocEmptyDeallocation',
    42: 'E_UnitTestComplete',
    43: 'E_UnitTestFail',
    44: 'E_VallocInvalidLength',
    45: 'E_CGallocInvalidLength',
    46: 'E_CGallocBadStepsize',
    47: 'E_CGallocInvalidStart',
    48: 'E_CGallocEmptyDeallocation',
    49: 'E_ObjNotFound',
    50: 'E_BadParameters',
    51: 'E_OutOfVram',
    52: 'E_OutOfCgram',
    53: 'E_InvalidException',
    54: 'E_Msu1InvalidFrameCycle',
    55: 'E_Msu1InvalidChapterRequested',
    56: 'E_Msu1InvalidChapter',
    57: 'E_Msu1AudioSeekTimeout',
    58: 'E_Msu1AudioPlayError',
    59: 'E_ObjStackCorrupted',
    60: 'E_BadEventResult',
    61: 'E_abstractClass',
    62: 'E_NoChapterFound',
    63: 'E_NoCheckpointFound',
    64: 'E_BadSpriteAnimation',
    65: 'E_AllocatedVramExceeded',
    66: 'E_AllocatedCgramExceeded',
    67: 'E_InvalidDmaChannel',
    68: 'E_DmaChannelEmpty',
    69: 'E_NoDmaChannel',
    70: 'E_VideoMode',
    71: 'E_BadBgAnimation',
    72: 'E_BadBgLayer',
    73: 'E_NtscUnsupported',
    74: 'E_WallocBadStepsize',
    75: 'E_WallocEmptyDeallocation',
    76: 'E_OutOfWram',
    77: 'E_BadInputDevice',
    78: 'E_ScoreTest',
    79: 'E_Msu1FrameBad',
    80: 'E_BadIrq',
    81: 'E_NoIrqCallback',
    82: 'E_BadIrqCallback',
    83: 'E_SramBad',
}

# OOP slot structure (16 bytes per slot)
OOP_SLOT_SIZE = 16
OOP_NUM_SLOTS = 48


async def read_memory(ws, snes_addr, size):
    """Read `size` bytes from SNES address via QUsb2Snes."""
    usb_addr = snes_to_usb(snes_addr)
    cmd = {
        "Opcode": "GetAddress",
        "Space": "SNES",
        "Operands": [format(usb_addr, 'X'), format(size, 'X')]
    }
    await ws.send(str(cmd).replace("'", '"'))

    # Collect binary response chunks
    data = b""
    while len(data) < size:
        chunk = await ws.recv()
        if isinstance(chunk, str):
            print(f"  Unexpected text response: {chunk}")
            break
        data += chunk
    return data[:size]


def parse_oop_slot(data, slot_num):
    """Parse a 16-byte OOP stack slot."""
    if len(data) < 16:
        return None
    flags = data[0]
    obj_id = data[1]
    num = struct.unpack_from('<H', data, 2)[0]
    void = struct.unpack_from('<H', data, 4)[0]
    properties = struct.unpack_from('<H', data, 6)[0]
    dp = struct.unpack_from('<H', data, 8)[0]
    init = struct.unpack_from('<H', data, 10)[0]
    play = struct.unpack_from('<H', data, 12)[0]
    kill = struct.unpack_from('<H', data, 14)[0]
    return {
        'slot': slot_num,
        'flags': flags,
        'id': obj_id,
        'num': num,
        'void': void,
        'properties': properties,
        'dp': dp,
        'init': init,
        'play': play,
        'kill': kill
    }


def format_properties(props):
    """Format object properties bitmask."""
    names = []
    if props & 0x0001: names.append('isScript')
    if props & 0x0002: names.append('isChapter')
    if props & 0x0004: names.append('isEvent')
    if props & 0x0008: names.append('isHdma')
    if props & 0x0010: names.append('isSprite')
    if props & 0x0020: names.append('isBackground')
    if props & 0x0040: names.append('isAnimation')
    if props & 0x0080: names.append('isCheckpoint')
    if props & 0x1000: names.append('isSerializable')
    return '|'.join(names) if names else f'${props:04X}'


def format_flags(flags):
    """Format object flags. Bit positions from src/config/globals.inc."""
    names = []
    if flags & 0x80: names.append('Present')
    if flags & 0x08: names.append('DeleteScheduled')
    if flags & 0x04: names.append('InitOk')
    if flags & 0x02: names.append('Persistent')
    if flags & 0x01: names.append('Singleton')
    return '|'.join(names) if names else 'None'


def format_p_register(p):
    """Format 65816 P (status) register."""
    flags = []
    if p & 0x80: flags.append('N')
    if p & 0x40: flags.append('V')
    if p & 0x20: flags.append('M(8bit-A)')
    if p & 0x10: flags.append('X(8bit-XY)')
    if p & 0x08: flags.append('D')
    if p & 0x04: flags.append('I')
    if p & 0x02: flags.append('Z')
    if p & 0x01: flags.append('C')
    return '|'.join(flags) if flags else 'none'


# Load class ID->name mapping from sym file
def load_class_names():
    """Load OBJID mappings from sym file."""
    names = {}
    try:
        with open('build/SuperDragonsLairArcade.sym', 'r') as f:
            for line in f:
                line = line.strip()
                if 'OBJID.' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        addr_str = parts[0]  # e.g., "0000:004c"
                        name = parts[1]      # e.g., "OBJID.Sprite.life_counter"
                        # Parse the value (after colon)
                        val = int(addr_str.split(':')[1], 16)
                        class_name = name.replace('OBJID.', '')
                        names[val] = class_name
    except Exception as e:
        print(f"  Warning: Could not load class names: {e}")
    return names


# Load method ID->name mappings for a given class
def load_method_names():
    """Load method name mappings (classname.methodname.MTD) from sym file."""
    methods = {}  # {class_name: {method_id: method_name}}
    try:
        with open('build/SuperDragonsLairArcade.sym', 'r') as f:
            for line in f:
                line = line.strip()
                if '.MTD' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        addr_str = parts[0]
                        name = parts[1]  # e.g., "Sprite.score.init.MTD"
                        val = int(addr_str.split(':')[1], 16)
                        # Remove .MTD suffix, split into class.method
                        base = name.replace('.MTD', '')
                        # Find last dot to separate class from method
                        dot_idx = base.rfind('.')
                        if dot_idx > 0:
                            class_name = base[:dot_idx]
                            method_name = base[dot_idx+1:]
                            if class_name not in methods:
                                methods[class_name] = {}
                            methods[class_name][val] = method_name
    except Exception:
        pass
    return methods


async def main():
    class_names = load_class_names()
    method_names = load_method_names()
    print(f"Loaded {len(class_names)} class name mappings from sym file")
    print(f"Connecting to QUsb2Snes at {WS_URL}...")

    try:
        async with websockets.connect(WS_URL) as ws:
            # List devices
            await ws.send('{"Opcode":"DeviceList","Space":"SNES"}')
            resp = await ws.recv()
            print(f"Devices: {resp}")

            # Parse device name from response
            import json
            devices = json.loads(resp)
            if not devices.get('Results'):
                print("ERROR: No devices found. Is FXPAK connected?")
                return
            device = devices['Results'][0]
            print(f"Attaching to: {device}")

            # Attach
            await ws.send(f'{{"Opcode":"Attach","Space":"SNES","Operands":["{device}"]}}')
            await asyncio.sleep(0.5)

            # Get device info
            await ws.send('{"Opcode":"Info","Space":"SNES"}')
            info = await ws.recv()
            print(f"Device info: {info}")

            print("\n" + "="*80)
            print("  FXPAK CRASH STATE DUMP")
            print("="*80)

            # ================================================================
            # EXCEPTION STATE (most important for crash diagnosis)
            # ================================================================
            print("\n--- EXCEPTION STATE ---")
            exc_data = await read_memory(ws, ADDR['excStack'], 0x18)  # 24 bytes covers all exc fields
            exc_stack = struct.unpack_from('<H', exc_data, 0)[0]      # excStack
            exc_a     = struct.unpack_from('<H', exc_data, 2)[0]      # excA
            exc_y     = struct.unpack_from('<H', exc_data, 4)[0]      # excY
            exc_x     = struct.unpack_from('<H', exc_data, 6)[0]      # excX
            exc_dp    = struct.unpack_from('<H', exc_data, 8)[0]      # excDp
            exc_db    = exc_data[10]                                   # excDb
            exc_pb    = exc_data[11]                                   # excPb
            exc_flags = exc_data[12]                                   # excFlags
            exc_pc    = struct.unpack_from('<H', exc_data, 13)[0]     # excPc
            exc_err   = struct.unpack_from('<H', exc_data, 15)[0]     # excErr
            exc_args  = exc_data[17:25]                                # excArgs (8 bytes)

            err_name = ERROR_NAMES.get(exc_err & 0xFF, f'Unknown(${exc_err:04X})')
            print(f"  Error code: {exc_err} = {err_name}")
            print(f"  TRIGGER_ERROR PC: ${exc_pc:04X}")
            print(f"  CPU at crash: A=${exc_a:04X} X=${exc_x:04X} Y=${exc_y:04X}")
            print(f"  Direct Page:  DP=${exc_dp:04X}")
            print(f"  Banks:        DB=${exc_db:02X} PB=${exc_pb:02X}")
            print(f"  Flags (P):    ${exc_flags:02X} = {format_p_register(exc_flags)}")
            print(f"  Stack at crash: SP=${exc_stack:04X}")
            print(f"  excArgs: {' '.join(f'{b:02X}' for b in exc_args)}")

            # For BRK/COP: extract crash PC from BRK interrupt frame in excArgs
            # BRK native mode pushes: PBR(1), PC+2(2), P(1) to stack
            # core.error.trigger reads stack offsets 6-12 into excArgs:
            #   excArgs[0] = BRK P register
            #   excArgs[1] = BRK PC+2 low byte
            #   excArgs[2] = BRK PC+2 high byte
            #   excArgs[3] = BRK PBR (program bank)
            if (exc_err & 0xFF) in (13, 25):  # E_Brk=13, E_Cop=25
                brk_p = exc_args[0]
                brk_pc_plus2 = exc_args[1] | (exc_args[2] << 8)
                brk_pbr = exc_args[3]
                brk_pc = (brk_pc_plus2 - 2) & 0xFFFF
                print(f"\n  *** {'BRK' if (exc_err & 0xFF) == 13 else 'COP'} CRASH LOCATION ***")
                print(f"  BRK/COP instruction at: ${brk_pbr:02X}:{brk_pc:04X}")
                print(f"  BRK P register: ${brk_p:02X} = {format_p_register(brk_p)}")
                print(f"  (Look up ${brk_pc:04X} in build/SuperDragonsLairArcade.sym)")

            # ================================================================
            # OOP DISPATCH STATE
            # ================================================================
            print("\n--- OOP DISPATCH STATE ---")
            dispatch_data = await read_memory(ws, ADDR['currentObject'], 18)
            cur_object = struct.unpack_from('<H', dispatch_data, 0)[0]
            cur_method = struct.unpack_from('<H', dispatch_data, 2)[0]
            cur_class  = struct.unpack_from('<H', dispatch_data, 4)[0]

            obj_name = class_names.get(cur_object & 0xFF, f'?${cur_object:02X}')
            cls_name = class_names.get(cur_class & 0xFF, f'?${cur_class:02X}')

            # Try to find method name
            meth_name = '?'
            cls_methods = method_names.get(obj_name, {})
            if cur_method in cls_methods:
                meth_name = cls_methods[cur_method]
            else:
                # Method 0=init, 1=play, 2=kill are standard
                meth_name = {0: 'init', 1: 'play', 2: 'kill'}.get(cur_method, f'?{cur_method}')

            print(f"  Last dispatched: {cls_name}::{meth_name}() (object={obj_name})")
            print(f"  GLOBAL.currentObject = ${cur_object:04X} ({obj_name})")
            print(f"  GLOBAL.currentClass  = ${cur_class:04X} ({cls_name})")
            print(f"  GLOBAL.currentMethod = ${cur_method:04X} ({meth_name})")

            # If direct page is in OOP ZP range, figure out which object it belongs to
            if 0x0010 <= exc_dp < 0x1810:
                print(f"\n  DP ${exc_dp:04X} is in OOP ZP pool (${ADDR['OopObjRam']:04X}-$1810)")

            # ================================================================
            # OOP STACK
            # ================================================================
            print("\n--- OOP STACK (48 slots) ---")
            oop_data = await read_memory(ws, ADDR['OopStack'], OOP_SLOT_SIZE * OOP_NUM_SLOTS)
            active_count = 0
            for i in range(OOP_NUM_SLOTS):
                offset = i * OOP_SLOT_SIZE
                slot = parse_oop_slot(oop_data[offset:offset+OOP_SLOT_SIZE], i+1)
                if slot and slot['flags'] != 0:
                    active_count += 1
                    cname = class_names.get(slot['id'], f'?${slot["id"]:02X}')
                    print(f"  Slot {slot['slot']:2d}: flags={format_flags(slot['flags']):28s} "
                          f"id=${slot['id']:02X}({cname:30s}) "
                          f"props={format_properties(slot['properties']):20s} "
                          f"dp=${slot['dp']:04X}")
            print(f"  Active slots: {active_count}/{OOP_NUM_SLOTS}")

            # ================================================================
            # VRAM ALLOCATION
            # ================================================================
            print("\n--- VRAM ALLOCATION TABLE (256 blocks) ---")
            vram_id_data = await read_memory(ws, ADDR['VRAM_alloc_id'], 1)
            vram_data = await read_memory(ws, ADDR['VRAM_alloc_blocks'], 256)
            print(f"  currentVramAllocationId = ${vram_id_data[0]:02X}")
            used_blocks = []
            for i, b in enumerate(vram_data):
                if b != 0:
                    used_blocks.append((i, b))
            if used_blocks:
                print(f"  Used blocks ({len(used_blocks)}):")
                groups = []
                current_id = None
                start = None
                prev_idx = 0
                for idx, bid in used_blocks:
                    if bid != current_id:
                        if current_id is not None:
                            groups.append((start, prev_idx, current_id))
                        current_id = bid
                        start = idx
                    prev_idx = idx
                if current_id is not None:
                    groups.append((start, prev_idx, current_id))
                for gstart, gend, gid in groups:
                    vram_start = gstart * 0x100
                    vram_end = (gend + 1) * 0x100
                    print(f"    blocks {gstart:3d}-{gend:3d} (VRAM ${vram_start:04X}-${vram_end:04X}): id=${gid:02X}")
            else:
                print("  All blocks free")

            # VRAM overlap check
            id_ranges = {}
            for i, b in enumerate(vram_data):
                if b != 0:
                    if b not in id_ranges:
                        id_ranges[b] = []
                    id_ranges[b].append(i)
            for aid, blocks in sorted(id_ranges.items()):
                if len(blocks) > 1:
                    gaps = []
                    for j in range(1, len(blocks)):
                        if blocks[j] != blocks[j-1] + 1:
                            gaps.append((blocks[j-1], blocks[j]))
                    if gaps:
                        print(f"  WARNING: VRAM id ${aid:02X} has non-contiguous blocks: {blocks}")

            # ================================================================
            # CGRAM ALLOCATION
            # ================================================================
            print("\n--- CGRAM ALLOCATION TABLE (64 blocks) ---")
            cgram_id_data = await read_memory(ws, ADDR['CGRAM_alloc_id'], 1)
            cgram_data = await read_memory(ws, ADDR['CGRAM_alloc_blocks'], 64)
            print(f"  currentCgramAllocationId = ${cgram_id_data[0]:02X}")
            cgram_used = [(i, b) for i, b in enumerate(cgram_data) if b != 0]
            if cgram_used:
                print(f"  Used blocks ({len(cgram_used)}):")
                for idx, bid in cgram_used:
                    cgram_addr = idx * 8
                    print(f"    block {idx:2d} (CGRAM ${cgram_addr:03X}): id=${bid:02X}")
            else:
                print("  All blocks free")

            # ================================================================
            # WRAM ALLOCATION
            # ================================================================
            print("\n--- WRAM ALLOCATION TABLE (first 64 blocks) ---")
            wram_id_data = await read_memory(ws, ADDR['WRAM_alloc_id'], 1)
            wram_blocks = await read_memory(ws, ADDR['WRAM_alloc_blocks'], 64)
            print(f"  currentWramAllocationId = ${wram_id_data[0]:02X}")
            wram_used = [(i, b) for i, b in enumerate(wram_blocks) if b != 0]
            if wram_used:
                print(f"  Used blocks ({len(wram_used)}):")
                for idx, bid in wram_used:
                    print(f"    block {idx:2d}: id=${bid:02X}")
            else:
                print("  All blocks free (suspicious if objects are active!)")

            # ================================================================
            # GAME STATE
            # ================================================================
            print("\n--- GAME STATE ---")
            scene_data = await read_memory(ws, ADDR['sceneRow'], 4)
            scene_row = struct.unpack_from('<H', scene_data, 0)[0]
            game_mode = struct.unpack_from('<H', scene_data, 2)[0]
            mode_names = {0: 'Arcade', 1: 'Boss Rush', 2: 'Oops All Traps'}
            print(f"  sceneRow = {scene_row}")
            print(f"  gameMode = {game_mode} ({mode_names.get(game_mode, '???')})")

            hdma_data = await read_memory(ws, ADDR['HDMA_channel_enable'], 1)
            print(f"  HDMA.CHANNEL.ENABLE = ${hdma_data[0]:02X}")

            # ================================================================
            # MEMORY BOUNDARY CHECKS
            # ================================================================
            print("\n--- VRAM/HDMA BOUNDARY CHECK ---")
            boundary_data = await read_memory(ws, ADDR['HdmaSpcBuffer'], 16)
            print(f"  HdmaSpcBuffer first 16 bytes:")
            print(f"    {' '.join(f'{b:02X}' for b in boundary_data)}")

            # DMA queue area (check for corruption)
            # Header: currentDmaQueueSlot(db) + channel.id(db) + channel.flag(db) + channel.index(dw) = 5 bytes
            # Slot struct (8 bytes): transferLength(dw) + targetAdress(dw) + transferType(db) + sourceAdress(3)
            # ACTIVE flag = $40 (bit 6 of transferType byte)
            print("\n--- DMA QUEUE STATE ---")
            dma_data = await read_memory(ws, ADDR['DMA_QUEUE_start'], 133)  # 5 header + 16*8 queue
            dma_slot_ptr = dma_data[0]  # currentDmaQueueSlot is db (1 byte)
            dma_ch_id = dma_data[1]
            dma_ch_flag = dma_data[2]
            dma_ch_idx = struct.unpack_from('<H', dma_data, 3)[0]
            print(f"  currentDmaQueueSlot = ${dma_slot_ptr:02X}")
            print(f"  DMA channel: id=${dma_ch_id:02X} flag=${dma_ch_flag:02X} index=${dma_ch_idx:04X}")
            # Check each DMA queue slot (8 bytes each, starting at offset 5)
            for i in range(16):
                slot_off = 5 + i * 8
                if slot_off + 8 <= len(dma_data):
                    xfer_len = struct.unpack_from('<H', dma_data, slot_off)[0]
                    tgt_addr = struct.unpack_from('<H', dma_data, slot_off + 2)[0]
                    xfer_type = dma_data[slot_off + 4]  # transferType is db (1 byte)
                    src_lo = struct.unpack_from('<H', dma_data, slot_off + 5)[0]
                    src_hi = dma_data[slot_off + 7]
                    if xfer_type & 0x40:  # DMA_TRANSFER.OPTION.ACTIVE = $40
                        type_base = xfer_type & 0x1F  # mask off option flags
                        type_names = {0: 'VRAM', 1: 'OAM', 2: 'CGRAM'}
                        type_name = type_names.get(type_base, f'?${type_base:02X}')
                        flags_str = []
                        if xfer_type & 0x80: flags_str.append('FIXED')
                        if xfer_type & 0x20: flags_str.append('REVERSE')
                        flag_suffix = f" [{','.join(flags_str)}]" if flags_str else ""
                        print(f"  Slot {i:2d}: ACTIVE {type_name}{flag_suffix} "
                              f"src=${src_hi:02X}:{src_lo:04X} tgt=${tgt_addr:04X} len=${xfer_len:04X}")
                    elif xfer_type != 0:
                        # Non-zero but not ACTIVE — possible corruption
                        raw = ' '.join(f'{dma_data[slot_off+j]:02X}' for j in range(8))
                        print(f"  Slot {i:2d}: SUSPICIOUS type=${xfer_type:02X} (not active but non-zero) raw: {raw}")

            # ================================================================
            # STACK PAGE
            # ================================================================
            print("\n--- STACK PAGE ($0100-$01FF) ---")
            stack_data = await read_memory(ws, 0x0100, 256)
            sp_guess = 255
            while sp_guess > 0 and stack_data[sp_guess] == 0:
                sp_guess -= 1
            print(f"  Apparent stack top: ~$01{sp_guess+1:02X} (SP ~ ${0x0100 + sp_guess:04X})")
            start_row = max(0, sp_guess - 31)
            end_row = min(256, sp_guess + 17)
            for row_start in range(start_row, end_row, 16):
                row_end = min(row_start + 16, 256)
                hex_str = ' '.join(f'{stack_data[i]:02X}' for i in range(row_start, row_end))
                print(f"  ${0x0100 + row_start:04X}: {hex_str}")

            # ================================================================
            # DIRECT PAGE of crashed object
            # ================================================================
            if 0x0010 <= exc_dp < 0x1810:
                print(f"\n--- ZERO PAGE at DP=${exc_dp:04X} (108 bytes) ---")
                zp_data = await read_memory(ws, exc_dp, 108)
                for row_start in range(0, 108, 16):
                    row_end = min(row_start + 16, 108)
                    hex_str = ' '.join(f'{zp_data[i]:02X}' for i in range(row_start, row_end))
                    print(f"  ${exc_dp + row_start:04X}: {hex_str}")

            # ================================================================
            # SUMMARY
            # ================================================================
            print("\n" + "="*80)
            print("  CRASH SUMMARY")
            print("="*80)
            print(f"  Error: {err_name} (code {exc_err})")
            print(f"  Last dispatched method: {cls_name}::{meth_name}()")
            if (exc_err & 0xFF) in (13, 25):
                brk_p = exc_args[0]
                brk_pc_plus2 = exc_args[1] | (exc_args[2] << 8)
                brk_pbr = exc_args[3]
                brk_pc = (brk_pc_plus2 - 2) & 0xFFFF
                print(f"  {'BRK' if (exc_err & 0xFF) == 13 else 'COP'} at: ${brk_pbr:02X}:{brk_pc:04X}")
            print(f"  CPU: A=${exc_a:04X} X=${exc_x:04X} Y=${exc_y:04X} DP=${exc_dp:04X} SP=${exc_stack:04X}")
            print(f"  Game mode: {mode_names.get(game_mode, '???')} (row {scene_row})")
            print(f"  Active OOP objects: {active_count}/{OOP_NUM_SLOTS}")
            print(f"  VRAM alloc blocks used: {len(used_blocks)}/256 (id=${vram_id_data[0]:02X})")
            print(f"  CGRAM alloc blocks used: {len(cgram_used)}/64 (id=${cgram_id_data[0]:02X})")
            print(f"  WRAM alloc ID: ${wram_id_data[0]:02X}")

    except ConnectionRefusedError:
        print("ERROR: Cannot connect to QUsb2Snes.")
        print("Make sure QUsb2Snes.exe is running and FXPAK is connected.")
        print(f"Expected WebSocket at {WS_URL}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
