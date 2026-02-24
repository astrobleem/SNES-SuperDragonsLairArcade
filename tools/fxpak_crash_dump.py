#!/usr/bin/env python3
"""Read WRAM regions from FXPAK Pro via QUsb2Snes to analyze a crash state."""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

WS_URL = "ws://localhost:23074"

# FXPAK maps WRAM bank $7E at $F50000 on the QUsb2Snes SNES bus.
WRAM_BASE = 0xF50000


def hex_dump(data: bytes, base_addr: int):
    """Print hex dump with 16 bytes per line and ASCII sidebar."""
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        hex_part = hex_part.ljust(47)  # 16*3-1 = 47
        ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
        addr = base_addr + offset
        print(f"  ${addr:04X}: {hex_part}  |{ascii_part}|")


async def read_wram(ws, wram_offset: int, size: int) -> bytes:
    """Read `size` bytes from WRAM at $7E:wram_offset via QUsb2Snes."""
    bus_addr = WRAM_BASE + wram_offset
    cmd = json.dumps({
        "Opcode": "GetAddress",
        "Space": "SNES",
        "Operands": [hex(bus_addr), hex(size)]
    })
    await ws.send(cmd)
    data = await ws.recv()
    if isinstance(data, str):
        # Unexpected text response (error message?)
        print(f"  WARNING: got text response: {data}")
        return b""
    return data


async def main():
    print(f"Connecting to QUsb2Snes at {WS_URL}...")

    async with websockets.connect(WS_URL) as ws:
        # List devices
        await ws.send('{"Opcode":"DeviceList","Space":"SNES"}')
        resp = await ws.recv()
        devices = json.loads(resp)
        if not devices.get("Results"):
            print("ERROR: No devices found")
            return
        device = devices["Results"][0]
        print(f"Attaching to: {device}")

        # Attach
        await ws.send(json.dumps({
            "Opcode": "Attach",
            "Space": "SNES",
            "Operands": [device]
        }))
        await asyncio.sleep(0.5)

        # ---- Region 1: Stack area around SP=$1982 ----
        print("\n" + "=" * 72)
        print("REGION 1: Stack area $7E:1970-$7E:1994 (36 bytes, SP~$1982)")
        print("=" * 72)
        data = await read_wram(ws, 0x1970, 36)
        hex_dump(data, 0x1970)

        # ---- Region 2: HdmaSpcBuffer extended ----
        print("\n" + "=" * 72)
        print("REGION 2: HdmaSpcBuffer extended $7E:6F80-$7E:7100 (384 bytes)")
        print("=" * 72)
        data = await read_wram(ws, 0x6F80, 384)
        hex_dump(data, 0x6F80)

        # ---- Region 3: Sprite.score ZP ----
        print("\n" + "=" * 72)
        print("REGION 3: Sprite.score ZP $7E:03A7-$7E:03F7 (80 bytes, dp=$03A7)")
        print("=" * 72)
        data = await read_wram(ws, 0x03A7, 80)
        hex_dump(data, 0x03A7)

        # ---- Region 4: First Script ZP ----
        print("\n" + "=" * 72)
        print("REGION 4: First Script ZP $7E:0010-$7E:006F (96 bytes, dp=$0010)")
        print("=" * 72)
        data = await read_wram(ws, 0x0010, 96)
        hex_dump(data, 0x0010)

        # ---- Region 5: OopStack slots 1-6 ----
        print("\n" + "=" * 72)
        print("REGION 5: OopStack slots 1-6 $7E:6988-$7E:69E8 (96 bytes)")
        print("=" * 72)
        data = await read_wram(ws, 0x6988, 96)
        hex_dump(data, 0x6988)

        # ---- Region 6: $55 corruption scan ----
        print("\n" + "=" * 72)
        print("REGION 6: $55 corruption scan (chunks with >8 bytes of $55)")
        print("=" * 72)

        scan_ranges = [
            (0x0000, 0x1A00),  # low WRAM: ZP, stack, globals
            (0x6900, 0x7200),  # OOP area, HDMA buffers
        ]

        found_any = False
        for range_start, range_end in scan_ranges:
            total_size = range_end - range_start
            chunk_size = 256

            for chunk_offset in range(0, total_size, chunk_size):
                addr = range_start + chunk_offset
                read_size = min(chunk_size, range_end - addr)
                data = await read_wram(ws, addr, read_size)

                count_55 = sum(1 for b in data if b == 0x55)
                if count_55 > 8:
                    found_any = True
                    print(f"\n  --- $7E:{addr:04X}-${addr + read_size - 1:04X}"
                          f"  ({count_55} bytes of $55) ---")
                    hex_dump(data, addr)

        if not found_any:
            print("  No chunks with >8 bytes of $55 found.")

        print("\n" + "=" * 72)
        print("Crash dump complete.")
        print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
