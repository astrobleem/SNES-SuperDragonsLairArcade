#!/usr/bin/env python3
"""Push ROM to FXPAK Pro via QUsb2Snes and boot it."""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

from paths import DISTRIBUTION, wsl_to_windows

WS_URL = "ws://localhost:23074"
ROM_PATH = wsl_to_windows(str(DISTRIBUTION / "SuperDragonsLairArcade.sfc"))
FXPAK_ROM_PATH = "/SuperDragonsLair/SuperDragonsLairArcade.sfc"

async def main():
    print(f"Connecting to QUsb2Snes at {WS_URL}...")

    async with websockets.connect(WS_URL) as ws:
        # List devices
        await ws.send('{"Opcode":"DeviceList","Space":"SNES"}')
        resp = await ws.recv()
        devices = json.loads(resp)
        if not devices.get('Results'):
            print("ERROR: No devices found")
            return
        device = devices['Results'][0]
        print(f"Attaching to: {device}")

        # Attach
        await ws.send(f'{{"Opcode":"Attach","Space":"SNES","Operands":["{device}"]}}')
        await asyncio.sleep(0.5)

        # Read ROM file
        with open(ROM_PATH, 'rb') as f:
            rom_data = f.read()
        print(f"ROM size: {len(rom_data)} bytes ({len(rom_data)//1024} KB)")

        # Upload ROM
        size_hex = format(len(rom_data), 'X')
        print(f"Uploading to {FXPAK_ROM_PATH}...")
        await ws.send(f'{{"Opcode":"PutFile","Space":"SNES","Operands":["{FXPAK_ROM_PATH}","{size_hex}"]}}')

        # Send data in 1024-byte chunks
        offset = 0
        chunk_size = 1024
        while offset < len(rom_data):
            end = min(offset + chunk_size, len(rom_data))
            await ws.send(rom_data[offset:end])
            offset = end
            if offset % (64 * 1024) == 0:
                print(f"  {offset // 1024} KB / {len(rom_data) // 1024} KB")

        print(f"Upload complete ({offset} bytes)")
        await asyncio.sleep(1)

        # Boot the ROM
        print(f"Booting {FXPAK_ROM_PATH}...")
        await ws.send(f'{{"Opcode":"Boot","Space":"SNES","Operands":["{FXPAK_ROM_PATH}"]}}')
        await asyncio.sleep(1)

        print("Done! ROM should be running on SNES.")

if __name__ == '__main__':
    asyncio.run(main())
