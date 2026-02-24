#!/usr/bin/env python3
"""
Generate per-scene Mesen Lua playthrough test scripts.

Parses chapter.data files to build a chapter graph, finds the "golden path"
(correct input sequence) for each of the 29 scenes via BFS, and generates
Lua test scripts that use scene select + input injection to verify each
scene is beatable.

Usage:
    python3 tools/generate_playthrough_tests.py [--scene N] [--dry-run]
"""

import os
import re
import sys
import argparse
from collections import deque
from pathlib import Path

from paths import PROJECT_ROOT, DISTRIBUTION

CHAPTERS_DIR = PROJECT_ROOT / "data" / "chapters"
SYM_FILE = PROJECT_ROOT / "build" / "SuperDragonsLairArcade.sym"
SFC_DIR = DISTRIBUTION

# Direction constants matching src/definition/snes.registers
JOY_DIR_UP    = 0x0800
JOY_DIR_DOWN  = 0x0400
JOY_DIR_LEFT  = 0x0200
JOY_DIR_RIGHT = 0x0100
JOY_BUTTON_A  = 0x0080

DIR_NAME_TO_MASK = {
    "JOY_DIR_UP":    JOY_DIR_UP,
    "JOY_DIR_DOWN":  JOY_DIR_DOWN,
    "JOY_DIR_LEFT":  JOY_DIR_LEFT,
    "JOY_DIR_RIGHT": JOY_DIR_RIGHT,
    "JOY_BUTTON_A":  JOY_BUTTON_A,
}

MASK_TO_NAME = {v: k for k, v in DIR_NAME_TO_MASK.items()}

# Scene table (matching title_screen.script sceneTable order, 1-indexed)
SCENE_TABLE = [
    (1,  "introduction",       "intr"),
    (2,  "vestibule",          "vest"),
    (3,  "snake_room",         "snkr"),
    (4,  "bower",              "bowr"),
    (5,  "fire_room",          "firm"),
    (6,  "throne_room",        "thrn"),
    (7,  "tilting_room",       "tltr"),
    (8,  "tentacle_room",      "tntr"),
    (9,  "wind_room",          "wndr"),
    (10, "giddy_goons",        "gg"),
    (11, "catwalk_bats",       "cwbt"),
    (12, "mudmen",             "mudm"),
    (13, "rolling_balls",      "rbal"),
    (14, "underground_river",  "ugr"),
    (15, "flaming_ropes",      "flrp"),
    (16, "flying_horse",       "fh"),
    (17, "bubbling_cauldron",  "bcld"),
    (18, "giant_bat",          "gbat"),
    (19, "crypt_creeps",       "cc"),
    (20, "alice_room",         "alrm"),
    (21, "robot_knight",       "rk"),
    (22, "smithee",            "sm"),
    (23, "smithee_reversed",   "smr"),
    (24, "grim_reaper",        "gr"),
    (25, "yellow_brick_road",  "ybr"),
    (26, "black_knight",       "bknt"),
    (27, "lizard_king",        "lzkg"),
    (28, "the_dragons_lair",   "tdl"),
    (29, "attract_mode",       "atmd"),
]


class Chapter:
    """Parsed chapter data."""
    def __init__(self, name):
        self.name = name
        self.chapter_id = None  # from chapter.id.NNN file
        self.default_result = None      # EventResult type string
        self.default_target = None      # target chapter name or 'none'
        self.default_chapter_id = None  # chapter ID from Event.chapter arg0
        self.default_endframe = 0       # endframe for the default Event.chapter
        self.directions = []  # list of (direction_mask, startFrame, endFrame, result, target)
        self.is_death = False  # True if EventResult.lastcheckpoint


def parse_chapter_data(chapter_dir):
    """Parse a chapter.data file and return a Chapter object."""
    data_file = chapter_dir / "chapter.data"
    if not data_file.exists():
        return None

    chapter_name = chapter_dir.name
    ch = Chapter(chapter_name)

    # Find chapter.id.NNN file
    for f in chapter_dir.iterdir():
        m = re.match(r"chapter\.id\.(\d+)", f.name)
        if m:
            ch.chapter_id = int(m.group(1))
            break

    text = data_file.read_text()
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or line.startswith(";") or line.endswith(":"):
            continue
        if line == ".dw 0":
            break

        # Parse .dw entries
        m = re.match(r"\.dw\s+(.*)", line)
        if not m:
            continue

        fields = [f.strip() for f in m.group(1).split(",")]
        if len(fields) < 7:
            continue

        event_type = fields[0]
        start_frame = int(fields[1].replace("$", "0x"), 0)
        end_frame = int(fields[2].replace("$", "0x"), 0)
        result = fields[3]
        target = fields[4]
        arg0_str = fields[5].strip()
        # arg1 = fields[6] (unused)

        if event_type == "Event.chapter.CLS.PTR":
            ch.default_result = result
            ch.default_target = target
            ch.default_endframe = end_frame
            # arg0 is the chapter ID for Event.chapter
            try:
                ch.default_chapter_id = int(arg0_str)
            except ValueError:
                ch.default_chapter_id = 0
            if result == "EventResult.lastcheckpoint":
                ch.is_death = True

        elif event_type == "Event.direction_generic.CLS.PTR":
            direction_mask = DIR_NAME_TO_MASK.get(arg0_str, 0)
            if direction_mask == 0:
                try:
                    direction_mask = int(arg0_str, 0)
                except ValueError:
                    pass
            ch.directions.append((direction_mask, start_frame, end_frame, result, target))

        elif event_type == "Event.checkpoint.CLS.PTR":
            pass  # ignored for pathfinding

    return ch


def load_all_chapters():
    """Load all chapter data from data/chapters/."""
    chapters = {}
    if not CHAPTERS_DIR.exists():
        print(f"ERROR: {CHAPTERS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    for d in sorted(CHAPTERS_DIR.iterdir()):
        if d.is_dir():
            ch = parse_chapter_data(d)
            if ch:
                chapters[ch.name] = ch

    return chapters


def find_golden_path(chapters, start_name, scene_prefix):
    """
    BFS from start_name to find a path that exits the scene.

    A path "exits" when it reaches a chapter whose default target has a
    different scene prefix (e.g., flrp_exit_room → flrr_start_alive),
    or when it reaches a chapter with no outgoing non-death edges.

    Returns a list of (chapter_name, chapter_id, direction_mask, inject_frame)
    tuples. direction_mask=0 means no input needed (routing/cutscene node).
    """
    if start_name not in chapters:
        return None

    # Build adjacency: for each chapter, list of (target, direction_mask, startFrame, endFrame)
    # direction_mask=0 means default transition (no input needed)

    # First pass: identify death chapters (reachable dead-ends)
    death_chapters = set()
    for name, ch in chapters.items():
        if ch.is_death:
            death_chapters.add(name)

    # Also mark chapters whose default leads transitively to death with no direction alternatives
    changed = True
    while changed:
        changed = False
        for name, ch in chapters.items():
            if name in death_chapters:
                continue
            if not ch.directions and ch.default_target in death_chapters:
                death_chapters.add(name)
                changed = True

    # BFS
    # State: current chapter name
    # Edge: (target_chapter, direction_mask, inject_frame)
    queue = deque()
    visited = {start_name: None}  # chapter -> (prev_chapter, direction_mask, inject_frame)
    queue.append(start_name)

    exit_chapter = None

    while queue:
        current = queue.popleft()
        ch = chapters.get(current)
        if not ch:
            continue

        # Check if this chapter's default exits the scene
        if ch.default_target and ch.default_target != "none":
            target_prefix = ch.default_target.split("_")[0]
            # Check if target belongs to a different scene
            if target_prefix != scene_prefix:
                exit_chapter = current
                break

        # Generate edges
        edges = []

        # Direction events (non-death targets)
        for direction_mask, sf, ef, result, target in ch.directions:
            if target == "none" or target in death_chapters:
                continue
            if result == "EventResult.lastcheckpoint":
                continue
            # Inject near the start of the success window, not the midpoint.
            # GLOBAL.currentFrame carries over to the next chapter during MSU-1
            # seek delay, so a late injection means the next chapter's events may
            # see a stale high frame number and expire immediately.
            inject_frame = min(sf + 2, ef - 1)
            edges.append((target, direction_mask, inject_frame))

        # Default transition (for routing/cutscene nodes)
        if ch.default_target and ch.default_target != "none":
            if ch.default_target not in death_chapters:
                if ch.default_result != "EventResult.lastcheckpoint":
                    # Only follow default if no direction events led somewhere useful,
                    # OR if this is a routing node (no direction events)
                    edges.append((ch.default_target, 0, 0))

        for target, dir_mask, inj_frame in edges:
            if target not in visited:
                visited[target] = (current, dir_mask, inj_frame)
                queue.append(target)

    if not exit_chapter:
        # Try to find any chapter that reaches outside scene
        for name in visited:
            ch = chapters.get(name)
            if ch and ch.default_target and ch.default_target != "none":
                target_prefix = ch.default_target.split("_")[0]
                if target_prefix != scene_prefix:
                    exit_chapter = name
                    break

    if not exit_chapter:
        return None

    # Reconstruct path as list of (source_name, source_id, dir_mask, inject_frame, target_name)
    # source_id is the chapter where the button must be pressed
    # inject_frame is the video frame within that chapter to press the button
    raw_path = []
    current = exit_chapter
    while current != start_name:
        prev_chapter, dir_mask, inj_frame = visited[current]
        raw_path.append((prev_chapter, current, dir_mask, inj_frame))
        current = prev_chapter
    raw_path.reverse()

    # Build final path with source chapter IDs
    path = []
    for source, target, dir_mask, inj_frame in raw_path:
        src_ch = chapters.get(source)
        src_id = src_ch.chapter_id if src_ch else 0
        # For Event.chapter default_chapter_id (used as the WRAM chapter ID)
        # The chapter ID that appears in GLOBAL.currentChapter is Event.chapter's arg0
        src_data_id = src_ch.default_chapter_id if src_ch else 0
        path.append((source, src_data_id, dir_mask, inj_frame, target))

    return path


def parse_sym_file():
    """Parse the .sym file to extract key addresses."""
    if not SYM_FILE.exists():
        print(f"ERROR: {SYM_FILE} not found. Run 'make' first.", file=sys.stderr)
        sys.exit(1)

    addresses = {}
    sym_text = SYM_FILE.read_text()

    patterns = {
        "core.error.trigger": r"^[0-9a-f]+:([0-9a-f]+)\s+core\.error\.trigger$",
        "_checkInputDevice": r"^[0-9a-f]+:([0-9a-f]+)\s+_checkInputDevice$",
        "abstract.Event.triggerResult": r"^[0-9a-f]+:([0-9a-f]+)\s+abstract\.Event\.triggerResult$",
        "EventResult.lastcheckpoint": r"^[0-9a-f]+:([0-9a-f]+)\s+EventResult\.lastcheckpoint$",
        "GLOBAL.currentFrame": r"^[0-9a-f]+:([0-9a-f]+)\s+GLOBAL\.currentFrame$",
        "GLOBAL.currentChapter": r"^[0-9a-f]+:([0-9a-f]+)\s+GLOBAL\.currentChapter$",
        "inputDevice.press": r"^[0-9a-f]+:([0-9a-f]+)\s+inputDevice\.press$",
        "inputDevice.trigger": r"^[0-9a-f]+:([0-9a-f]+)\s+inputDevice\.trigger$",
        "inputDevice.old": r"^[0-9a-f]+:([0-9a-f]+)\s+inputDevice\.old$",
    }

    for line in sym_text.split("\n"):
        line = line.strip()
        for key, pattern in patterns.items():
            m = re.match(pattern, line)
            if m:
                addr = int(m.group(1), 16)
                addresses[key] = addr

    # Validate all found
    missing = [k for k in patterns if k not in addresses]
    if missing:
        print(f"ERROR: Missing symbols in .sym: {missing}", file=sys.stderr)
        sys.exit(1)

    return addresses


def generate_lua_script(scene_idx, scene_name, scene_prefix, golden_path, addresses):
    """Generate a Lua test script for one scene."""

    # Address formatting
    error_trigger = 0xC00000 + addresses["core.error.trigger"]
    check_input_entry = addresses["_checkInputDevice"]
    check_input_rts = 0xC00000 + check_input_entry + 0x1E
    trigger_result = 0xC00000 + addresses["abstract.Event.triggerResult"]
    lastcheckpoint = 0xC00000 + addresses["EventResult.lastcheckpoint"]
    current_frame = addresses["GLOBAL.currentFrame"]
    current_chapter = addresses["GLOBAL.currentChapter"]
    input_press = addresses["inputDevice.press"]
    input_trigger = addresses["inputDevice.trigger"]
    input_old = addresses["inputDevice.old"]

    # Filter path to only steps that need direction input
    # Each step: (source_chapter_id, direction_mask, inject_frame, source_name, target_name)
    # source_chapter_id = the Event.chapter arg0 that GLOBAL.currentChapter shows
    input_steps = []
    for src_name, src_id, dir_mask, inj_frame, tgt_name in golden_path:
        if dir_mask != 0 and src_id is not None:
            dir_name = MASK_TO_NAME.get(dir_mask, f"0x{dir_mask:04X}")
            input_steps.append((src_id, dir_mask, inj_frame, src_name, dir_name))

    # Scene select navigation:
    # NO input during boot — msu1 splash auto-advances (pressing START delays it!).
    # losers screen auto-advances after 180-frame hold timer.
    # Title screen menu becomes active at ~frame 575 (verified by diagnostic).
    #
    # CRITICAL: Use SINGLE-FRAME injection windows. Multi-frame injection causes
    # the menu to process the button multiple times (e.g., 3 frames of DOWN
    # toggles cursor 0→1→0→1; 3 frames of A enters options THEN selects first item).
    #
    # Menu navigation: DOWN x3 → A (OPTIONS) → DOWN x2 → A (SCENE SELECT)
    #                  → RIGHT x (N-1) → A (launch)
    nav_lines = []
    frame = 600  # 25 frames after menu becomes active (~575)

    # DOWN x3 to OPTIONS (from ARCADE MODE, past BOSS RUSH and OOPS,ALL TRAPS!)
    for i in range(3):
        nav_lines.append(f"    {{{frame}, {frame}, 0x0400}},  -- DOWN to OPTIONS ({i+1}/3)")
        frame += 30
    # A to enter OPTIONS
    nav_lines.append(f"    {{{frame}, {frame}, 0x0080}},  -- A (enter OPTIONS)")
    frame += 30

    # DOWN x2 to SCENE SELECT (HIGH SCORES → SOUND TEST → SCENE SELECT)
    for i in range(2):
        nav_lines.append(f"    {{{frame}, {frame}, 0x0400}},  -- DOWN to scene select ({i+1}/2)")
        frame += 30

    # A to enter SCENE SELECT (starts at scene 1 = introduction)
    nav_lines.append(f"    {{{frame}, {frame}, 0x0080}},  -- A (enter SCENE SELECT)")
    frame += 30

    # RIGHT x (scene_idx-1) to reach target scene
    rights_needed = scene_idx - 1
    for i in range(rights_needed):
        nav_lines.append(f"    {{{frame}, {frame}, 0x0100}},  -- RIGHT ({i+1}/{rights_needed})")
        frame += 30

    # A to launch scene
    nav_lines.append(f"    {{{frame}, {frame}, 0x0080}},  -- A (launch scene)")
    frame += 30

    nav_schedule = "\n".join(nav_lines)

    # Golden path table for Lua
    path_lines = []
    for ch_id, dir_mask, inj_frame, name, dir_name in input_steps:
        path_lines.append(f"    {{{ch_id}, 0x{dir_mask:04X}, {inj_frame}, \"{name}\"}},  -- {dir_name}")

    golden_path_table = "\n".join(path_lines) if path_lines else "    -- No direction inputs needed (routing-only scene)"

    # Calculate timeout: navigation frames + generous per-chapter allowance
    # Each chapter video runs at ~24fps but Mesen PPU runs at 60fps
    # Allow ~300 PPU frames per chapter step, plus generous buffer
    max_frames = frame + len(golden_path) * 300 + 5000

    lua = f"""-- Scene {scene_idx}: {scene_name} (auto-generated by generate_playthrough_tests.py)
-- DO NOT EDIT - regenerate with: python3 tools/generate_playthrough_tests.py

-- ============ ADDRESSES (from build/SuperDragonsLairArcade.sym) ============
local ADDR_ERROR_TRIGGER   = 0x{error_trigger:06X}
local ADDR_CHECK_INPUT_RTS = 0x{check_input_rts:06X}  -- _checkInputDevice + $1E
local ADDR_TRIGGER_RESULT  = 0x{trigger_result:06X}
local ADDR_LASTCHECKPOINT  = 0x{lastcheckpoint:06X}
local ADDR_CURRENT_FRAME   = 0x{current_frame:06X}
local ADDR_CURRENT_CHAPTER = 0x{current_chapter:06X}
local ADDR_INPUT_PRESS     = 0x{input_press:06X}
local ADDR_INPUT_TRIGGER   = 0x{input_trigger:06X}
local ADDR_INPUT_OLD       = 0x{input_old:06X}

local MAX_FRAMES = {max_frames}

-- ============ HELPERS ============
local function readWord(addr)
    return emu.read(addr, emu.memType.snesMemory)
         + emu.read(addr + 1, emu.memType.snesMemory) * 256
end

local function writeWord(addr, val)
    emu.write(addr, val & 0xFF, emu.memType.snesMemory)
    emu.write(addr + 1, (val >> 8) & 0xFF, emu.memType.snesMemory)
end

-- ============ GOLDEN PATH ============
-- {{sourceChapterID, directionMask, injectAtFrame, sourceChapterName}}
-- sourceChapterID = GLOBAL.currentChapter value when this chapter is playing
-- Press directionMask when GLOBAL.currentFrame reaches injectAtFrame
local goldenPath = {{
{golden_path_table}
}}

-- ============ STATE ============
local gpInjectButton = 0   -- golden path injection (set by endFrame, used by exec)
local errorHit = false
local deathHit = false
local pathIndex = 1        -- current golden path step (1-indexed)
local lastChapter = -1     -- last seen GLOBAL.currentChapter
local chapterFrameWait = false  -- waiting for correct frame in current chapter
local navDone = false      -- scene select navigation complete
local testDone = false

-- ============ SCENE SELECT NAVIGATION ============
-- Single-frame windows to avoid double-press in menus
local navSchedule = {{
{nav_schedule}
}}

-- ============ INPUT INJECTION at _checkInputDevice RTS ============
-- This fires during NMI, BEFORE scripts run on the same frame.
-- For navigation: check ppuFrame directly in exec callback (no endFrame delay).
-- For golden path: use gpInjectButton set by previous endFrame (1-frame delay OK,
-- event windows are 20+ frames wide).
emu.addMemoryCallback(function()
    local frame = emu.getState()["ppu.frameCount"]
    local button = 0

    -- Phase 1: Check navigation schedule directly (no 1-frame delay)
    if not navDone then
        for _, s in ipairs(navSchedule) do
            if frame >= s[1] and frame <= s[2] then
                button = s[3]
                break
            end
        end
    end

    -- Phase 2: Golden path injection (set by endFrame callback)
    if button == 0 and gpInjectButton ~= 0 then
        button = gpInjectButton
    end

    if button ~= 0 then
        writeWord(ADDR_INPUT_PRESS, button)
        writeWord(ADDR_INPUT_TRIGGER, button)
        writeWord(ADDR_INPUT_OLD, 0)
    end
end, emu.callbackType.exec, ADDR_CHECK_INPUT_RTS)

-- ============ ERROR DETECTION ============
emu.addMemoryCallback(function()
    if errorHit then return end
    errorHit = true
    local state = emu.getState()
    local sp = state["cpu.sp"]
    local errCode = readWord(sp + 3)
    print(string.format("FAIL: error code=%d frame=%d", errCode, state["ppu.frameCount"]))
    emu.stop()
end, emu.callbackType.exec, ADDR_ERROR_TRIGGER)

-- ============ DEATH DETECTION ============
emu.addMemoryCallback(function()
    if testDone then return end
    deathHit = true
    local chap = readWord(ADDR_CURRENT_CHAPTER)
    local cf = readWord(ADDR_CURRENT_FRAME)
    local pf = emu.getState()["ppu.frameCount"]
    print(string.format("DEATH: chapter=%d videoFrame=%d ppuFrame=%d pathStep=%d/%d",
        chap, cf, pf, pathIndex, #goldenPath))
end, emu.callbackType.exec, ADDR_LASTCHECKPOINT)

-- ============ MAIN FRAME LOOP ============
emu.addEventCallback(function()
    if testDone then return end
    local ppuFrame = emu.getState()["ppu.frameCount"]
    gpInjectButton = 0

    -- Phase 1: Wait for navigation to finish
    if not navDone then
        local lastNav = navSchedule[#navSchedule]
        if ppuFrame > lastNav[2] + 30 then
            navDone = true
        end
        return
    end

    -- Phase 2: Golden path - monitor chapter transitions and inject inputs
    local curChap = readWord(ADDR_CURRENT_CHAPTER)
    local curFrame = readWord(ADDR_CURRENT_FRAME)

    -- Detect chapter transition
    if curChap ~= lastChapter then
        lastChapter = curChap
        chapterFrameWait = false

        -- Check if current chapter matches expected golden path step
        if pathIndex <= #goldenPath then
            local step = goldenPath[pathIndex]
            if curChap == step[1] then
                chapterFrameWait = true
            end
        end
    end

    -- Inject input at the correct frame
    if chapterFrameWait and pathIndex <= #goldenPath then
        local step = goldenPath[pathIndex]
        if curChap == step[1] and curFrame >= step[3] then
            gpInjectButton = step[2]
            -- Advance to next step after injection
            print(string.format("INJECT: chapter=%d (%s) dir=0x%04X frame=%d ppuFrame=%d step=%d/%d",
                step[1], step[4], step[2], curFrame, ppuFrame, pathIndex, #goldenPath))
            pathIndex = pathIndex + 1
            chapterFrameWait = false
        end
    end

    -- Check completion: all golden path steps done
    if pathIndex > #goldenPath and #goldenPath > 0 then
        if not testDone then
            testDone = true
            if deathHit then
                print(string.format("FAIL: scene {scene_name} - death occurred during playthrough (ppuFrame=%d)", ppuFrame))
            else
                print(string.format("PASS: scene {scene_name} - all %d inputs injected successfully (ppuFrame=%d)", #goldenPath, ppuFrame))
            end
            emu.stop()
        end
    end

    -- Timeout
    if ppuFrame >= MAX_FRAMES then
        print(string.format("TIMEOUT: scene {scene_name} at ppuFrame=%d pathStep=%d/%d chapter=%d videoFrame=%d",
            ppuFrame, pathIndex, #goldenPath, curChap, curFrame))
        emu.stop()
    end
end, emu.eventType.endFrame)

print("TEST: scene {scene_name} ({scene_idx}/29) - {len(input_steps)} direction inputs in golden path")
"""
    return lua


def main():
    parser = argparse.ArgumentParser(description="Generate per-scene Mesen Lua playthrough tests")
    parser.add_argument("--scene", type=int, help="Generate only for scene N (1-29)")
    parser.add_argument("--dry-run", action="store_true", help="Print golden paths without generating Lua")
    parser.add_argument("--output-dir", type=str, default=str(SFC_DIR),
                        help=f"Output directory for Lua scripts (default: {SFC_DIR})")
    args = parser.parse_args()

    print(f"Loading chapters from {CHAPTERS_DIR}...")
    chapters = load_all_chapters()
    print(f"  Loaded {len(chapters)} chapters")

    print(f"Parsing symbol file {SYM_FILE}...")
    addresses = parse_sym_file()
    for key, addr in sorted(addresses.items()):
        print(f"  {key} = 0x{addr:06X}")

    scenes_to_process = SCENE_TABLE
    if args.scene:
        scenes_to_process = [s for s in SCENE_TABLE if s[0] == args.scene]
        if not scenes_to_process:
            print(f"ERROR: Scene {args.scene} not found (valid: 1-29)", file=sys.stderr)
            sys.exit(1)

    results = []
    for scene_idx, scene_name, scene_prefix in scenes_to_process:
        start_name = f"{scene_prefix}_start_alive"
        if start_name not in chapters:
            print(f"  Scene {scene_idx:2d} ({scene_name}): SKIP - no {start_name}")
            results.append((scene_idx, scene_name, "SKIP", 0))
            continue

        golden_path = find_golden_path(chapters, start_name, scene_prefix)
        if not golden_path:
            print(f"  Scene {scene_idx:2d} ({scene_name}): NO PATH FOUND")
            results.append((scene_idx, scene_name, "NO_PATH", 0))
            continue

        # Count direction inputs (non-zero direction_mask)
        input_count = sum(1 for _, _, dm, _, _ in golden_path if dm != 0)
        # Show path: source chapters only, plus final target
        src_names = [src for src, _, _, _, _ in golden_path]
        if golden_path:
            src_names.append(golden_path[-1][4])  # final target
        path_display = " → ".join(src_names)
        print(f"  Scene {scene_idx:2d} ({scene_name}): {len(golden_path)} steps, {input_count} inputs")
        if args.dry_run:
            print(f"    Path: {path_display}")
            for src, src_id, dm, inj, tgt in golden_path:
                if dm != 0:
                    print(f"      {src} (id={src_id}): {MASK_TO_NAME.get(dm, '???')} at frame {inj} → {tgt}")
            results.append((scene_idx, scene_name, "OK", input_count))
            continue

        lua = generate_lua_script(scene_idx, scene_name, scene_prefix, golden_path, addresses)
        out_path = Path(args.output_dir) / f"test_scene_{scene_idx:02d}_{scene_name}.lua"
        out_path.write_text(lua)
        print(f"    → {out_path}")
        results.append((scene_idx, scene_name, "OK", input_count))

    # Summary
    print("\n=== SUMMARY ===")
    ok = sum(1 for _, _, s, _ in results if s == "OK")
    skip = sum(1 for _, _, s, _ in results if s == "SKIP")
    nopath = sum(1 for _, _, s, _ in results if s == "NO_PATH")
    print(f"  OK: {ok}  SKIP: {skip}  NO_PATH: {nopath}  Total: {len(results)}")

    if nopath > 0:
        print("\n  Scenes with no golden path found:")
        for idx, name, status, _ in results:
            if status == "NO_PATH":
                print(f"    Scene {idx}: {name}")


if __name__ == "__main__":
    main()
