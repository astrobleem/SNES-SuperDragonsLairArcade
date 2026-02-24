#!/usr/bin/env python3
"""Mesen MCP Server — automates sym lookup, build, test generation, and test execution.

Runs on Windows Python (NOT WSL). Calls into WSL only for make and test generation.
"""

import base64
import re
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from paths import PROJECT_ROOT, DISTRIBUTION, windows_to_wsl

PROJECT = PROJECT_ROOT
SFC_DIR = DISTRIBUTION
SYM_FILE = PROJECT / "build" / "SuperDragonsLairArcade.sym"
MESEN = PROJECT / "mesen" / "Mesen.exe"

mcp = FastMCP("mesen")


def _parse_sym_line(line: str):
    """Parse one sym file line into (bank, addr, name) or None."""
    m = re.match(r"^([0-9a-fA-F]+):([0-9a-fA-F]+)\s+(.+)$", line.strip())
    if not m:
        return None
    bank = int(m.group(1), 16)
    addr = int(m.group(2), 16)
    name = m.group(3)
    full = bank * 0x10000 + addr
    return bank, addr, name, full


@mcp.tool()
def lookup_symbol(pattern: str) -> str:
    """Search the sym file for symbols matching a regex pattern.

    Returns matching symbols with their addresses. ROM addresses include
    the $C0 bank prefix needed for Mesen exec callbacks.
    """
    if not SYM_FILE.exists():
        return f"ERROR: {SYM_FILE} not found. Run build_rom() first."

    results = []
    regex = re.compile(pattern, re.IGNORECASE)
    for line in SYM_FILE.read_text().split("\n"):
        parsed = _parse_sym_line(line)
        if not parsed:
            continue
        bank, addr, name, full = parsed
        if regex.search(name):
            # ROM addresses (banks $00-$3F) need $C0 prefix for Mesen exec callbacks
            if bank <= 0x3F:
                mesen_addr = 0xC00000 + full
                results.append(f"  {name}: ${full:06X} (Mesen: 0x{mesen_addr:06X})")
            else:
                results.append(f"  {name}: ${full:06X}")

    if not results:
        return f"No symbols matching '{pattern}' found."
    return f"Found {len(results)} match(es):\n" + "\n".join(results[:50])


@mcp.tool()
def lookup_symbols(symbols: list[str]) -> str:
    """Batch lookup multiple exact symbol names in the sym file.

    Returns each symbol's address with $C0 bank prefix for ROM addresses.
    Useful for updating all addresses in a Lua test script at once.
    """
    if not SYM_FILE.exists():
        return f"ERROR: {SYM_FILE} not found. Run build_rom() first."

    sym_map: dict[str, tuple[int, int, int]] = {}
    for line in SYM_FILE.read_text().split("\n"):
        parsed = _parse_sym_line(line)
        if not parsed:
            continue
        bank, addr, name, full = parsed
        sym_map[name] = (bank, addr, full)

    results = []
    for sym in symbols:
        if sym in sym_map:
            bank, addr, full = sym_map[sym]
            if bank <= 0x3F:
                mesen_addr = 0xC00000 + full
                results.append(f"  {sym}: ${full:06X} (Mesen: 0x{mesen_addr:06X})")
            else:
                results.append(f"  {sym}: ${full:06X}")
        else:
            # Try partial match
            matches = [n for n in sym_map if sym in n]
            if matches:
                results.append(f"  {sym}: NOT FOUND (did you mean: {', '.join(matches[:3])}?)")
            else:
                results.append(f"  {sym}: NOT FOUND")

    return "\n".join(results)


@mcp.tool()
def build_rom(clean: bool = True) -> str:
    """Build the ROM via WSL make. Returns build output.

    Args:
        clean: If True, runs 'make clean && make'. If False, runs 'make' only.
    """
    make_cmd = "make clean && make" if clean else "make"
    wsl_project = windows_to_wsl(str(PROJECT))
    wsl_cmd = f'wsl -e bash -c "cd {wsl_project} && {make_cmd}"'

    try:
        result = subprocess.run(
            wsl_cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        output = result.stdout + result.stderr

        # Check for success indicators
        if result.returncode == 0:
            # Verify ROM exists
            rom = PROJECT / "build" / "SuperDragonsLairArcade.sfc"
            if rom.exists():
                size_kb = rom.stat().st_size // 1024
                return f"BUILD SUCCESS ({size_kb} KB ROM)\n\n{output[-2000:]}"
            return f"BUILD WARNING: make returned 0 but ROM not found\n\n{output[-2000:]}"
        return f"BUILD FAILED (exit code {result.returncode})\n\n{output[-2000:]}"
    except subprocess.TimeoutExpired:
        return "BUILD TIMEOUT (>300s)"
    except Exception as e:
        return f"BUILD ERROR: {e}"


@mcp.tool()
def generate_test(scene: int | None = None, dry_run: bool = False) -> str:
    """Generate Mesen Lua playthrough test scripts via WSL.

    Args:
        scene: Scene number (1-29) to generate, or None for all scenes.
        dry_run: If True, show golden paths without generating Lua files.
    """
    args = ""
    if scene is not None:
        args += f" --scene {scene}"
    if dry_run:
        args += " --dry-run"

    wsl_project = windows_to_wsl(str(PROJECT))
    wsl_cmd = (
        f'wsl -e bash -c "cd {wsl_project} && '
        f'python3 tools/generate_playthrough_tests.py{args}"'
    )

    try:
        result = subprocess.run(
            wsl_cmd, shell=True, capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr

        if not dry_run and result.returncode == 0:
            # Copy generated test scripts to sfc dir
            copied = []
            for lua_file in (PROJECT / "build").glob("test_scene_*.lua"):
                dest = SFC_DIR / lua_file.name
                shutil.copy2(lua_file, dest)
                copied.append(lua_file.name)

            if copied:
                output += f"\n\nCopied {len(copied)} test script(s) to {SFC_DIR}:\n"
                output += "\n".join(f"  {f}" for f in sorted(copied))

        return output[-3000:]
    except subprocess.TimeoutExpired:
        return "GENERATE TIMEOUT (>120s)"
    except Exception as e:
        return f"GENERATE ERROR: {e}"


@mcp.tool()
def run_test(script_name: str, timeout: int = 120) -> str:
    """Execute a Mesen testrunner Lua script and return the output.

    Args:
        script_name: Lua script filename (e.g. 'test_scene_02_vestibule.lua').
                     Must exist in the sfc directory.
        timeout: Max seconds to wait for Mesen to finish.
    """
    script_path = SFC_DIR / script_name
    if not script_path.exists():
        available = sorted(f.name for f in SFC_DIR.glob("test_scene_*.lua"))
        msg = f"ERROR: {script_name} not found in {SFC_DIR}"
        if available:
            msg += f"\n\nAvailable tests:\n" + "\n".join(f"  {f}" for f in available)
        return msg

    out_file = SFC_DIR / "out.txt"
    cmd = (
        f'cd /d "{SFC_DIR}" && "{MESEN}" --testrunner '
        f'SuperDragonsLairArcade.sfc {script_name} > out.txt 2>&1'
    )

    try:
        subprocess.run(
            f'cmd.exe /c "{cmd}"', shell=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return f"MESEN TIMEOUT (>{timeout}s). Partial output:\n{_read_out_file(out_file)}"
    except Exception as e:
        return f"MESEN ERROR: {e}"

    output = _read_out_file(out_file)

    # Parse result
    if "PASS" in output:
        status = "PASS"
    elif "FAIL" in output:
        status = "FAIL"
    elif "TIMEOUT" in output:
        status = "TIMEOUT"
    else:
        status = "INCONCLUSIVE"

    return f"Result: {status}\n\n{output}"


@mcp.tool()
def run_lua_snippet(lua_code: str, timeout: int = 60) -> str:
    """Write ad-hoc Lua code to a temp file and run it in Mesen testrunner.

    Args:
        lua_code: The Lua script contents to execute.
        timeout: Max seconds to wait.
    """
    script_path = SFC_DIR / "_mcp_snippet.lua"
    script_path.write_text(lua_code)

    out_file = SFC_DIR / "out.txt"
    cmd = (
        f'cd /d "{SFC_DIR}" && "{MESEN}" --testrunner '
        f'SuperDragonsLairArcade.sfc _mcp_snippet.lua > out.txt 2>&1'
    )

    try:
        subprocess.run(
            f'cmd.exe /c "{cmd}"', shell=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return f"MESEN TIMEOUT (>{timeout}s). Partial output:\n{_read_out_file(out_file)}"
    except Exception as e:
        return f"MESEN ERROR: {e}"

    return _read_out_file(out_file)


@mcp.tool()
def read_test_output(file: str = "out.txt") -> str:
    """Read previous test output from the sfc directory.

    Args:
        file: Output filename to read (default: out.txt).
    """
    path = SFC_DIR / file
    if not path.exists():
        return f"ERROR: {path} not found"
    return path.read_text()[-3000:]


def _argb_to_png(width: int, height: int, argb_lines: list[str]) -> bytes:
    """Convert ARGB hex pixel data (from getScreenBuffer) to a PNG file."""
    # Parse all ARGB values from the hex lines
    pixels = []
    for line in argb_lines:
        for hex_val in line.strip().split():
            pixels.append(int(hex_val, 16))

    if len(pixels) != width * height:
        raise ValueError(f"Expected {width*height} pixels, got {len(pixels)}")

    # Build raw RGBA scanlines with filter byte 0 (None) per row
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter byte
        for x in range(width):
            argb = pixels[y * width + x]
            r = (argb >> 16) & 0xFF
            g = (argb >> 8) & 0xFF
            b = argb & 0xFF
            raw.extend((r, g, b))

    # Minimal PNG encoder
    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    idat_data = zlib.compress(bytes(raw))

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr_data)
    png += png_chunk(b"IDAT", idat_data)
    png += png_chunk(b"IEND", b"")
    return png


# Lua base64 encoder + screenshot script template.
# Two strategies: try emu.takeScreenshot() first (returns PNG binary),
# fall back to emu.getScreenBuffer() (returns ARGB pixel array).
_SCREENSHOT_LUA = r"""
-- Pure-Lua base64 encoder
local b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
local function b64encode(data)
    local out = {}
    local len = #data
    for i = 1, len, 3 do
        local a = string.byte(data, i) or 0
        local b = (i + 1 <= len) and string.byte(data, i + 1) or 0
        local c = (i + 2 <= len) and string.byte(data, i + 2) or 0
        local n = a * 65536 + b * 256 + c
        out[#out + 1] = string.sub(b64chars, math.floor(n / 262144) + 1, math.floor(n / 262144) + 1)
        out[#out + 1] = string.sub(b64chars, math.floor(n / 4096) % 64 + 1, math.floor(n / 4096) % 64 + 1)
        if i + 1 <= len then
            out[#out + 1] = string.sub(b64chars, math.floor(n / 64) % 64 + 1, math.floor(n / 64) % 64 + 1)
        else
            out[#out + 1] = "="
        end
        if i + 2 <= len then
            out[#out + 1] = string.sub(b64chars, n % 64 + 1, n % 64 + 1)
        else
            out[#out + 1] = "="
        end
    end
    return table.concat(out)
end

local TARGET_FRAME = {target_frame}
local screenshotDone = false

{lua_preamble}

emu.addEventCallback(function()
    if screenshotDone then return end
    local frame = emu.getState()["ppu.frameCount"]
    if frame < TARGET_FRAME then return end
    screenshotDone = true

    -- Strategy 1: try emu.takeScreenshot() (returns PNG binary string)
    local ok, pngData = pcall(emu.takeScreenshot)
    if ok and pngData and #pngData > 0 then
        print("SCREENSHOT_PNG_BASE64_START")
        -- Print in chunks to avoid line-length issues
        local encoded = b64encode(pngData)
        local chunkSize = 4000
        for i = 1, #encoded, chunkSize do
            print(string.sub(encoded, i, i + chunkSize - 1))
        end
        print("SCREENSHOT_PNG_BASE64_END")
        emu.stop()
        return
    end

    -- Strategy 2: fall back to getScreenBuffer() ARGB array
    local buf = emu.getScreenBuffer()
    if not buf or #buf == 0 then
        print("SCREENSHOT_ERROR: no screen buffer available")
        emu.stop()
        return
    end
    local size = emu.getScreenSize()
    local w = size.width or 256
    local h = size.height or 224

    print(string.format("SCREENSHOT_ARGB_START %d %d", w, h))
    -- Print 16 hex values per line to keep output manageable
    local line = {}
    for i = 1, #buf do
        line[#line + 1] = string.format("%08X", buf[i])
        if #line >= 16 then
            print(table.concat(line, " "))
            line = {}
        end
    end
    if #line > 0 then
        print(table.concat(line, " "))
    end
    print("SCREENSHOT_ARGB_END")
    emu.stop()
end, emu.eventType.endFrame)
"""


@mcp.tool()
def take_screenshot(
    wait_frames: int = 600,
    lua_preamble: str = "",
    timeout: int = 60,
) -> str:
    """Take a screenshot of the emulator at a specific PPU frame.

    Runs a Lua script in Mesen that waits until the target frame, captures the
    screen, base64-encodes it, and prints to stdout. The PNG is saved to the
    sfc directory and the file path is returned.

    Args:
        wait_frames: PPU frame number at which to capture (default 600 = ~title screen).
        lua_preamble: Optional Lua code inserted before the screenshot logic
                      (e.g., menu navigation callbacks, input injection setup).
        timeout: Max seconds to wait for Mesen.

    Returns:
        Path to the saved PNG file, or an error message.
    """
    lua_code = _SCREENSHOT_LUA.replace("{target_frame}", str(wait_frames))
    lua_code = lua_code.replace("{lua_preamble}", lua_preamble)

    script_path = SFC_DIR / "_mcp_screenshot.lua"
    script_path.write_text(lua_code)

    out_file = SFC_DIR / "out.txt"
    cmd = (
        f'cd /d "{SFC_DIR}" && "{MESEN}" --testrunner '
        f'SuperDragonsLairArcade.sfc _mcp_screenshot.lua > out.txt 2>&1'
    )

    try:
        subprocess.run(f'cmd.exe /c "{cmd}"', shell=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"MESEN TIMEOUT (>{timeout}s). Partial output:\n{_read_out_file(out_file)}"
    except Exception as e:
        return f"MESEN ERROR: {e}"

    output = out_file.read_text()
    png_path = SFC_DIR / "screenshot.png"

    # Strategy 1: PNG via takeScreenshot()
    if "SCREENSHOT_PNG_BASE64_START" in output and "SCREENSHOT_PNG_BASE64_END" in output:
        start = output.index("SCREENSHOT_PNG_BASE64_START") + len("SCREENSHOT_PNG_BASE64_START")
        end = output.index("SCREENSHOT_PNG_BASE64_END")
        b64_data = output[start:end].replace("\n", "").replace("\r", "").strip()
        try:
            png_bytes = base64.b64decode(b64_data)
            png_path.write_bytes(png_bytes)
            return f"Screenshot saved: {png_path} ({len(png_bytes)} bytes)"
        except Exception as e:
            return f"ERROR decoding PNG base64: {e}\nFirst 200 chars: {b64_data[:200]}"

    # Strategy 2: ARGB pixel buffer
    if "SCREENSHOT_ARGB_START" in output and "SCREENSHOT_ARGB_END" in output:
        header_line = output[output.index("SCREENSHOT_ARGB_START"):].split("\n")[0]
        parts = header_line.split()
        width = int(parts[1]) if len(parts) > 1 else 256
        height = int(parts[2]) if len(parts) > 2 else 224

        start = output.index("SCREENSHOT_ARGB_START")
        start = output.index("\n", start) + 1  # skip header line
        end = output.index("SCREENSHOT_ARGB_END")
        argb_text = output[start:end].strip().split("\n")

        try:
            png_bytes = _argb_to_png(width, height, argb_text)
            png_path.write_bytes(png_bytes)
            return f"Screenshot saved: {png_path} ({len(png_bytes)} bytes, from ARGB buffer)"
        except Exception as e:
            return f"ERROR converting ARGB to PNG: {e}"

    # Neither strategy produced output
    if "SCREENSHOT_ERROR" in output:
        return output
    return f"INCONCLUSIVE — no screenshot data in output.\n\n{output[-1000:]}"


def _read_out_file(path: Path) -> str:
    """Safely read an output file, returning last 3000 chars."""
    try:
        return path.read_text()[-3000:]
    except Exception:
        return "(could not read output file)"


if __name__ == "__main__":
    mcp.run()
