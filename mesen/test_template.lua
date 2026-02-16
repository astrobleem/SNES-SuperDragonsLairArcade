-- ============================================================================
-- Test Template for SNES Super Dragon's Lair Arcade
-- ============================================================================
-- Copy this file to E:\gh\SuperDragonsLairArcade.sfc\ and rename it.
--
-- Run:
--   cmd.exe /c "cd /d E:\gh\SuperDragonsLairArcade.sfc && ^
--     E:\gh\SNES-SuperDragonsLairArcade\mesen\Mesen.exe --testrunner ^
--     SuperDragonsLairArcade.sfc test_myscript.lua > out.txt 2>&1"
--
-- After EVERY build, update ROM addresses from build/SuperDragonsLairArcade.sym:
--   grep -E 'core\.error\.trigger$|_checkInputDevice$' build/*.sym
--   _checkInputDevice RTS = entry + $1E, then add $C0 bank prefix.
-- ============================================================================

-- ===== ROM ADDRESSES (shift every build — grep sym file!) ====================
local ADDR_ERROR_TRIGGER   = 0xC059BD  -- core.error.trigger
local ADDR_CHECK_INPUT_RTS = 0xC0741F  -- _checkInputDevice + $1E
-- Optional hooks (uncomment as needed):
-- local ADDR_TRIGGER_RESULT  = 0xC066F0  -- abstract.Event.triggerResult
-- local ADDR_LASTCHECKPOINT  = 0xC06732  -- EventResult.lastcheckpoint
-- local ADDR_PLAYCHAPTER     = 0xC06714  -- EventResult.playchapter
-- local ADDR_OBJ_CREATE      = 0xC02EAE  -- core.object.create

-- ===== WRAM ADDRESSES (stable across builds) =================================
local ADDR_INPUT_PRESS     = 0x7E6C46  -- inputDevice.press
local ADDR_INPUT_TRIGGER   = 0x7E6C48  -- inputDevice.trigger
local ADDR_INPUT_OLD       = 0x7E6C4C  -- inputDevice.old
local ADDR_OOP_STACK       = 0x7E6388  -- OopStack base (36 slots x 16 bytes)
local ADDR_CURRENT_FRAME   = 0x7E6C62  -- GLOBAL.currentFrame

-- ===== BUTTON CONSTANTS (SNES JOY1L format) ==================================
local JOY_B     = 0x8000; local JOY_Y      = 0x4000
local JOY_SEL   = 0x2000; local JOY_START  = 0x1000
local JOY_UP    = 0x0800; local JOY_DOWN   = 0x0400
local JOY_LEFT  = 0x0200; local JOY_RIGHT  = 0x0100
local JOY_A     = 0x0080; local JOY_X      = 0x0040
local JOY_L     = 0x0020; local JOY_R      = 0x0010

-- ===== OOP CONSTANTS =========================================================
local OOP_ENTRY_SIZE  = 0x10
local OOP_SLOT_COUNT  = 36
-- Key OBJIDs: Script=$08, Player=$43, Brightness=$42, Spc=$07, Msu1=$09,
--             Background.generic=$41, Event.chapter=$10, Event.direction=$1D

-- ===== COMMON UTILITIES ======================================================
local MAX_FRAMES = 2000
local errorHit = false

local function readWord(addr)
    return emu.read(addr, emu.memType.snesMemory)
         + emu.read(addr + 1, emu.memType.snesMemory) * 256
end

local function writeWord(addr, val)
    emu.write(addr, val & 0xFF, emu.memType.snesMemory)
    emu.write(addr + 1, (val >> 8) & 0xFF, emu.memType.snesMemory)
end

--- Search OopStack for an object by OBJID. Returns its DP (ZP base), or nil.
local function findObjectDP(objId)
    for i = 0, OOP_SLOT_COUNT - 1 do
        local base = ADDR_OOP_STACK + i * OOP_ENTRY_SIZE
        local flags = emu.read(base, emu.memType.snesMemory)
        if flags ~= 0 then
            local id = emu.read(base + 1, emu.memType.snesMemory)
            if id == objId then return readWord(base + 8) end
        end
    end
    return nil
end

--- Dump all active OopStack entries (for diagnostics).
local function dumpOopStack()
    for i = 0, OOP_SLOT_COUNT - 1 do
        local base = ADDR_OOP_STACK + i * OOP_ENTRY_SIZE
        local flags = emu.read(base, emu.memType.snesMemory)
        if flags ~= 0 then
            local id = emu.read(base + 1, emu.memType.snesMemory)
            local dp = readWord(base + 8)
            print(string.format("  slot %02d: flags=%02X id=%02X dp=%04X", i, flags, id, dp))
        end
    end
end

-- ===== INPUT INJECTION =======================================================
local injectButton = 0

emu.addMemoryCallback(function()
    if injectButton ~= 0 then
        writeWord(ADDR_INPUT_PRESS, injectButton)
        writeWord(ADDR_INPUT_TRIGGER, injectButton)
        writeWord(ADDR_INPUT_OLD, 0)
    end
end, emu.callbackType.exec, ADDR_CHECK_INPUT_RTS)

-- ===== ERROR DETECTION =======================================================
emu.addMemoryCallback(function()
    if errorHit then return end; errorHit = true
    local state = emu.getState()
    local errCode = readWord(state["cpu.sp"] + 3)
    local frame = state["ppu.frameCount"]
    print(string.format("FAIL: error code=%d frame=%d", errCode, frame))
    dumpOopStack()
    emu.stop()
end, emu.callbackType.exec, ADDR_ERROR_TRIGGER)

-- ===== INPUT SCHEDULE ========================================================
-- Each entry: {startFrame, endFrame, button}
-- IMPORTANT: Use 1-frame windows {f, f, btn} for sequential inputs to avoid
-- the double-advance bug (2-frame windows cause same-button consecutive steps
-- to advance twice, desynchronizing multi-step sequences like Konami code).
-- Use 3-frame windows {f, f+2, btn} only for isolated presses (e.g. START skip).
local schedule = {
    -- Example: skip MSU-1 splash with START presses
    -- {20, 22, JOY_START},
    -- {35, 37, JOY_START},
}

-- ===== MAIN FRAME HANDLER ===================================================
emu.addEventCallback(function()
    local frame = emu.getState()["ppu.frameCount"]

    -- Apply input schedule
    injectButton = 0
    for _, s in ipairs(schedule) do
        if frame >= s[1] and frame <= s[2] then
            injectButton = s[3]
            break
        end
    end

    -- TODO: Add test-specific logic here
    -- Example: check for a condition and report PASS/FAIL
    -- if frame == 500 then
    --     local dp = findObjectDP(0x43)  -- Player
    --     if dp then print("PASS: Player found") else print("FAIL: no Player") end
    --     print("TEST COMPLETE")
    --     emu.stop()
    --     return
    -- end

    if frame >= MAX_FRAMES then
        print(string.format("TIMEOUT at frame %d", frame))
        emu.stop()
    end
end, emu.eventType.endFrame)
