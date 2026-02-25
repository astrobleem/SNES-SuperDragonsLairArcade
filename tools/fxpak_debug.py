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
    'currentObject':            0x7E7211,  # GLOBAL.currentObject (word)
    'currentMethod':            0x7E7213,  # GLOBAL.currentMethod (word)
    'currentClass':             0x7E7215,  # GLOBAL.currentClass (word)
    'currentObjectStr':         0x7E7217,  # 3 bytes (ptr + bank)
    'currentMethodStr':         0x7E721A,  # 3 bytes
    'currentClassStr':          0x7E721D,  # 3 bytes

    # Hardware state
    'HDMA_channel_enable':      0x7E71E5,  # GLOBAL.HDMA.CHANNEL.ENABLE

    # Game state (these are in bank 0 ZP area, $0000-$1FFF)
    'sceneRow':                 0x001A3B,  # GLOBAL.sceneRow (word)
    'gameMode':                 0x001A3D,  # GLOBAL.gameMode (word)

    # Exception handler state (slot 2 / ZP area)
    'excStack':                 0x001993,  # 2 bytes - saved stack pointer
    'excA':                     0x001995,  # 2 bytes - accumulator at crash
    'excY':                     0x001997,  # 2 bytes - Y register at crash
    'excX':                     0x001999,  # 2 bytes - X register at crash
    'excDp':                    0x00199B,  # 2 bytes - direct page at crash
    'excDb':                    0x00199D,  # 1 byte  - data bank
    'excPb':                    0x00199E,  # 1 byte  - program bank
    'excFlags':                 0x00199F,  # 1 byte  - P register
    'excPc':                    0x0019A0,  # 2 bytes - PC (of TRIGGER_ERROR, NOT BRK location)
    'excErr':                   0x0019A2,  # 2 bytes - error code (E_xxx enum)
    'excArgs':                  0x0019A4,  # 8 bytes - arguments / BRK interrupt frame

    # BRK/COP crash-site diagnostics (saved by enhanced BRK handler before error handler)
    'crashSP':                  0x0019AC,  # 2 bytes - SP after BRK hw pushes (add 4 for pre-BRK SP)
    'crashPC':                  0x0019AE,  # 2 bytes - crash-site PC+2 from BRK interrupt frame
    'crashPB':                  0x0019B0,  # 1 byte  - crash-site program bank
    'crashP':                   0x0019B1,  # 1 byte  - crash-site processor status
    'crashA':                   0x0019B2,  # 2 bytes - crash-site accumulator
    'crashX':                   0x0019B4,  # 2 bytes - crash-site X register
    'crashY':                   0x0019B6,  # 2 bytes - crash-site Y register
    'crashDP':                  0x0019B8,  # 2 bytes - crash-site direct page register
    'crashTmp':                 0x0019BA,  # 2 bytes - kernel ZP tmp (OopHandlerExecute method addr)

    # Fingerprint diagnostics (E_ObjStackCorrupted)
    'fpExpectedId':             0x0019BC,  # 2 bytes - expected id from CPU stack
    'fpExpectedNum':            0x0019BE,  # 2 bytes - expected num from CPU stack
    'fpActualId':               0x0019C0,  # 2 bytes - actual OopStack.id[X] & $FF
    'fpActualNum':              0x0019C2,  # 2 bytes - actual OopStack.num[X]
    'fpSlotIndex':              0x0019C4,  # 2 bytes - X register (OopStack slot offset)
    'fpCrashSP':                0x0019C6,  # 2 bytes - CPU stack pointer at fingerprint failure

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


def load_kernel_zp():
    """Load the kernel ZP base address from sym file (label 'ZP')."""
    try:
        with open('build/SuperDragonsLairArcade.sym', 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == 'ZP':
                    addr_str = parts[0]
                    val = int(addr_str.split(':')[1], 16)
                    return val
    except Exception:
        pass
    return None


def load_sym_addresses():
    """Load ROM symbol addresses for method/function lookup."""
    syms = {}
    try:
        with open('build/SuperDragonsLairArcade.sym', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('['):
                    continue
                parts = line.split()
                if len(parts) >= 2 and ':' in parts[0]:
                    bank_str, addr_str = parts[0].split(':')
                    try:
                        addr = int(addr_str, 16)
                        name = parts[1]
                        syms[addr] = name
                    except ValueError:
                        pass
    except Exception:
        pass
    return syms


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
    kernel_zp = load_kernel_zp()
    sym_addrs = load_sym_addresses()
    print(f"Loaded {len(class_names)} class name mappings from sym file")
    if kernel_zp is not None:
        print(f"Kernel ZP base: ${kernel_zp:04X}")
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
                print(f"\n  *** {'BRK' if (exc_err & 0xFF) == 13 else 'COP'} CRASH LOCATION (from excArgs) ***")
                print(f"  BRK/COP instruction at: ${brk_pbr:02X}:{brk_pc:04X}")
                print(f"  BRK P register: ${brk_p:02X} = {format_p_register(brk_p)}")
                print(f"  (Look up ${brk_pc:04X} in build/SuperDragonsLairArcade.sym)")

                # Also read dedicated crash diagnostics (saved by enhanced BRK handler)
                crash_data = await read_memory(ws, ADDR['crashSP'], 16)
                crash_sp = struct.unpack_from('<H', crash_data, 0)[0]
                crash_pc = struct.unpack_from('<H', crash_data, 2)[0]
                crash_pb = crash_data[4]
                crash_p  = crash_data[5]
                crash_a  = struct.unpack_from('<H', crash_data, 6)[0]
                crash_x  = struct.unpack_from('<H', crash_data, 8)[0]
                crash_y  = struct.unpack_from('<H', crash_data, 10)[0]
                crash_dp = struct.unpack_from('<H', crash_data, 12)[0]
                crash_tmp = struct.unpack_from('<H', crash_data, 14)[0]
                pre_brk_sp = (crash_sp + 4) & 0xFFFF
                # crash_pc is PC+2 (BRK pushes address after BRK + signature byte)
                crash_pc_actual = (crash_pc - 2) & 0xFFFF
                print(f"\n  *** BRK CRASH DIAGNOSTICS (dedicated WRAM) ***")
                print(f"  Crash instruction at: ${crash_pb:02X}:{crash_pc_actual:04X}")
                print(f"  Crash PC+2 (raw):     ${crash_pb:02X}:{crash_pc:04X}")
                print(f"  Pre-BRK SP:           ${pre_brk_sp:04X}")
                print(f"  SP after BRK pushes:  ${crash_sp:04X}")
                print(f"  Crash P register:     ${crash_p:02X} = {format_p_register(crash_p)}")
                print(f"  Crash registers:      A=${crash_a:04X} X=${crash_x:04X} Y=${crash_y:04X}")
                print(f"  Crash DP:             ${crash_dp:04X}")
                print(f"  Kernel ZP tmp:        ${crash_tmp:04X}")

                # Analyze crash-site DP
                if kernel_zp is not None and crash_dp == kernel_zp:
                    print(f"  DP analysis:          DP = kernel ZP -> crash in dispatch/play loop code")
                elif 0x0010 <= crash_dp < 0x1810:
                    print(f"  DP analysis:          DP in OOP ZP pool -> crash inside object method")
                else:
                    print(f"  DP analysis:          DP=${crash_dp:04X} (unexpected, not kernel ZP or OOP pool)")

                # Analyze crash-site X as OopStack slot pointer
                oop_base = ADDR['OopStack'] & 0xFFFF
                oop_end = oop_base + OOP_NUM_SLOTS * OOP_SLOT_SIZE
                if oop_base <= crash_x < oop_end:
                    slot_idx = (crash_x - oop_base) // OOP_SLOT_SIZE
                    slot_off = slot_idx * OOP_SLOT_SIZE
                    slot = parse_oop_slot(oop_data[slot_off:slot_off+OOP_SLOT_SIZE], slot_idx)
                    if slot:
                        cname = class_names.get(slot['id'], f'?${slot["id"]:02X}')
                        print(f"  X as OopStack slot:   slot {slot_idx} = {cname} "
                              f"(flags={format_flags(slot['flags'])}, play=${slot['play']:04X})")
                elif crash_x < 0x8000:
                    print(f"  X=${crash_x:04X} (not a valid OopStack pointer)")

                # Analyze kernel ZP tmp as method address
                if crash_tmp != 0:
                    sym_name = sym_addrs.get(crash_tmp, None)
                    if sym_name:
                        print(f"  tmp as method addr:   ${crash_tmp:04X} = {sym_name}")
                    else:
                        print(f"  tmp as method addr:   ${crash_tmp:04X} (no exact sym match)")
                else:
                    print(f"  tmp as method addr:   $0000 (null — possibly cleared WRAM)")

                print(f"  (Look up ${crash_pc_actual:04X} in build/SuperDragonsLairArcade.sym)")

            # For E_ObjStackCorrupted: show fingerprint mismatch diagnostics
            if (exc_err & 0xFF) == 59:  # E_ObjStackCorrupted
                fp_data = await read_memory(ws, ADDR['fpExpectedId'], 12)
                fp_exp_id   = struct.unpack_from('<H', fp_data, 0)[0]
                fp_exp_num  = struct.unpack_from('<H', fp_data, 2)[0]
                fp_act_id   = struct.unpack_from('<H', fp_data, 4)[0]
                fp_act_num  = struct.unpack_from('<H', fp_data, 6)[0]
                fp_slot_idx = struct.unpack_from('<H', fp_data, 8)[0]
                fp_crash_sp = struct.unpack_from('<H', fp_data, 10)[0]

                # Calculate OopStack slot number from byte offset
                oop_base = ADDR['OopStack'] & 0xFFFF
                slot_num = fp_slot_idx // OOP_SLOT_SIZE if fp_slot_idx < OOP_NUM_SLOTS * OOP_SLOT_SIZE else -1

                exp_id_name = class_names.get(fp_exp_id & 0xFF, f'?${fp_exp_id:02X}')
                act_id_name = class_names.get(fp_act_id & 0xFF, f'?${fp_act_id:02X}')

                print(f"\n  *** E_ObjStackCorrupted FINGERPRINT DIAGNOSTICS ***")
                print(f"  OopStack slot offset:  X=${fp_slot_idx:04X} (slot #{slot_num})")
                print(f"  Expected id  (stack):  ${fp_exp_id:04X} ({exp_id_name})")
                print(f"  Actual id    (OopSt):  ${fp_act_id:04X} ({act_id_name})")
                print(f"  Expected num (stack):  ${fp_exp_num:04X}")
                print(f"  Actual num   (OopSt):  ${fp_act_num:04X}")
                print(f"  CPU SP at failure:     ${fp_crash_sp:04X}")

                # Determine what changed
                id_match = (fp_exp_id == fp_act_id)
                num_match = (fp_exp_num == fp_act_num)
                if not id_match and not num_match:
                    print(f"  >>> BOTH id AND num changed — possible stack corruption or slot reuse")
                elif not id_match:
                    print(f"  >>> Only id changed ({exp_id_name} -> {act_id_name}) — slot may have been reused")
                elif not num_match:
                    print(f"  >>> Only num changed (${fp_exp_num:04X} -> ${fp_act_num:04X}) — slot may have been reused")

                # Check for $55/$AA pattern (uninitialized DRAM)
                if fp_exp_id in (0x5555, 0x55AA, 0xAA55) or fp_exp_num in (0x5555, 0x55AA, 0xAA55):
                    print(f"  >>> $55/$AA PATTERN in expected values — CPU STACK CORRUPTION likely!")
                    print(f"      (Stack pop read uninitialized DRAM instead of pushed fingerprint)")
                if fp_act_id in (0x5555, 0x55AA, 0xAA55) or fp_act_num in (0x5555, 0x55AA, 0xAA55):
                    print(f"  >>> $55/$AA PATTERN in OopStack values — OopStack MEMORY CORRUPTION!")

                # Check if actual values look like valid object data
                if fp_act_id == 0 and fp_act_num == 0:
                    print(f"  >>> Actual id+num are ZERO — slot was cleared (object killed during its own method?)")
                elif fp_act_id == 0xFF or (fp_act_id & 0xFF) > 0x60:
                    print(f"  >>> Actual id=${fp_act_id:04X} is out of valid OBJID range — CORRUPTION")

            # For E_ObjBadHash: crash diagnostic fields hold hash pointer info
            if (exc_err & 0xFF) == 21:  # E_ObjBadHash
                crash_data = await read_memory(ws, ADDR['crashSP'], 6)
                hash_ptr_addr = struct.unpack_from('<H', crash_data, 0)[0]
                hash_id_count = struct.unpack_from('<H', crash_data, 2)[0]
                hash_pntr = struct.unpack_from('<H', crash_data, 4)[0]
                hash_id = hash_id_count & 0xFF
                hash_count = (hash_id_count >> 8) & 0xFF
                print(f"\n  *** E_ObjBadHash DIAGNOSTICS (from crash WRAM) ***")
                print(f"  Hash pointer addr (X): ${hash_ptr_addr:04X}")
                print(f"  Hash.id:               ${hash_id:02X} (MAXOBJID=${0x50:02X}, {'VALID' if hash_id < 0x50 else 'INVALID'})")
                print(f"  Hash.count:            ${hash_count:02X}")
                print(f"  Hash.pntr:             ${hash_pntr:04X} (OopStack range: $0000-$02FF)")
                if hash_pntr >= 0x0300:
                    print(f"  *** Hash.pntr OUT OF RANGE (>= $0300) ***")
                if hash_id == 0x55 or hash_pntr == 0x5555:
                    print(f"  *** $55 CORRUPTION PATTERN DETECTED ***")

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
                print(f"  {'BRK' if (exc_err & 0xFF) == 13 else 'COP'} at (excArgs): ${brk_pbr:02X}:{brk_pc:04X}")
                # Dedicated crash diagnostics
                crash_data = await read_memory(ws, ADDR['crashSP'], 16)
                crash_sp = struct.unpack_from('<H', crash_data, 0)[0]
                crash_pc_raw = struct.unpack_from('<H', crash_data, 2)[0]
                crash_pb = crash_data[4]
                crash_a  = struct.unpack_from('<H', crash_data, 6)[0]
                crash_x  = struct.unpack_from('<H', crash_data, 8)[0]
                crash_y  = struct.unpack_from('<H', crash_data, 10)[0]
                crash_dp = struct.unpack_from('<H', crash_data, 12)[0]
                crash_tmp = struct.unpack_from('<H', crash_data, 14)[0]
                crash_pc_actual = (crash_pc_raw - 2) & 0xFFFF
                pre_brk_sp = (crash_sp + 4) & 0xFFFF
                print(f"  BRK at (dedicated):   ${crash_pb:02X}:{crash_pc_actual:04X}  (pre-BRK SP=${pre_brk_sp:04X})")
                print(f"  Crash regs: A=${crash_a:04X} X=${crash_x:04X} Y=${crash_y:04X} DP=${crash_dp:04X} tmp=${crash_tmp:04X}")
            if (exc_err & 0xFF) == 21:  # E_ObjBadHash
                crash_data = await read_memory(ws, ADDR['crashSP'], 6)
                h_addr = struct.unpack_from('<H', crash_data, 0)[0]
                h_id = crash_data[2]
                h_count = crash_data[3]
                h_pntr = struct.unpack_from('<H', crash_data, 4)[0]
                print(f"  Corrupted hash: addr=${h_addr:04X} id=${h_id:02X} count=${h_count:02X} pntr=${h_pntr:04X}")
                if h_id == 0x55 or h_pntr == 0x5555:
                    print(f"  *** $55 CORRUPTION PATTERN ***")
            if (exc_err & 0xFF) == 59:  # E_ObjStackCorrupted
                fp_data = await read_memory(ws, ADDR['fpExpectedId'], 12)
                fp_exp_id   = struct.unpack_from('<H', fp_data, 0)[0]
                fp_exp_num  = struct.unpack_from('<H', fp_data, 2)[0]
                fp_act_id   = struct.unpack_from('<H', fp_data, 4)[0]
                fp_act_num  = struct.unpack_from('<H', fp_data, 6)[0]
                fp_slot_idx = struct.unpack_from('<H', fp_data, 8)[0]
                fp_crash_sp = struct.unpack_from('<H', fp_data, 10)[0]
                slot_num = fp_slot_idx // OOP_SLOT_SIZE if fp_slot_idx < OOP_NUM_SLOTS * OOP_SLOT_SIZE else -1
                exp_name = class_names.get(fp_exp_id & 0xFF, f'?${fp_exp_id:02X}')
                act_name = class_names.get(fp_act_id & 0xFF, f'?${fp_act_id:02X}')
                print(f"  Fingerprint: expected id=${fp_exp_id:04X}({exp_name}) num=${fp_exp_num:04X}")
                print(f"               actual   id=${fp_act_id:04X}({act_name}) num=${fp_act_num:04X}  slot={slot_num} SP=${fp_crash_sp:04X}")
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
