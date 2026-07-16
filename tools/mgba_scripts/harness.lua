-- Seaglass Character Mode — reusable test harness (mgba-headless).
--
-- This is the closed-binary port of Pokemon ROWE's testing methodology.
-- ROWE (full C source) compiled an in-game DEBUG MENU into the ROM
-- (src/debug.c: Give Pokemon, set VAR_CHARACTER_ID, warp, heal party,
-- toggle FLAG_SYS_NO_CATCHING, access PC) and drove it by hand through
-- mgba-qt with xdotool keypresses + screenshots. See docs/TESTING.md for
-- the full method-by-method mapping and what does/doesn't port.
--
-- We cannot compile a C menu into a closed binary. Instead every debug-menu
-- CAPABILITY is reproduced here from OUTSIDE the ROM, via mGBA's scripting
-- API: direct RAM read/write (= "Give Pokemon"/"set var"/"set flag"),
-- scripted controller input (= the human pressing buttons), breakpoints on
-- ROM addresses (= something ROWE's menu could NOT do at all), and state
-- assertions. Everything runs headless and deterministically, so unlike
-- ROWE's one-off manual playtests these are repeatable regression tests.
--
-- Usage from another script:
--   local H = dofile("tools/mgba_scripts/harness.lua")
--   H.onFrame(function(f) ... end)
--   H.press(H.KEY.A, 4)          -- press A for 4 frames, then release
--   H.sequence({{H.KEY.A, 4}, {H.KEY.DOWN, 2}})
--   H.log("something")
--   H.assertEq("party count", H.rd8(addr), 1)
--   H.finish()                   -- prints PASS/FAIL summary
--
-- Run:
--   ./tools/mgba_src/build/mgba-headless --script <yourscript.lua> \
--     [-t savestate] "rom/seaglass v3.0.gba" 2>&1 | grep -E "HARNESS|PASS|FAIL"
--
-- All API calls used here were empirically verified against this exact
-- mgba-headless build (see CLAUDE.md's Toolchain section) — emu:setBreakpoint,
-- emu:addKey/clearKey (genuinely drives the emulated pad, confirmed via
-- getKeys() observing 0->1->0), emu:read8/16/32, console:log.

local H = {}

-- GBA key bit indices, from mgba's include/mgba/internal/gba/input.h
H.KEY = {
    A = 0, B = 1, SELECT = 2, START = 3,
    RIGHT = 4, LEFT = 5, UP = 6, DOWN = 7,
    R = 8, L = 9,
}

-- ---------------------------------------------------------------- RAM anchors
--
-- CONFIRMED (this session, empirically, on rom/seaglass v3.0.gba @ rom.sha1):
--   The three most-referenced consecutive IWRAM words in the whole ROM are
--   0x030051B8 / 0x030051BC / 0x030051C0. All three read 0x00000000 at boot
--   and hold EWRAM pointers (0x0200C960 / 0x0200B9B0 / 0x0200FF74) by frame
--   240 — i.e. runtime-initialized pointers into EWRAM. This is exactly the
--   shape of pokeemerald-expansion's gSaveBlock2Ptr / gSaveBlock1Ptr /
--   gPokemonStoragePtr trio.
--
--   DISAMBIGUATED (this session, via probe_saveblock.lua on the truck state):
--     0x030051B8 -> gSaveBlock1Ptr    (header read as pos.x/y + WarpData
--                                       location: in the truck it read
--                                       x=2 y=2 map=25.40 — the truck map)
--     0x030051BC -> gSaveBlock2Ptr    (starts with the 8-byte playerName field)
--     0x030051C0 -> gPokemonStoragePtr (all zero at new game = empty PC)
--   SaveBlock1 layout confirmed vanilla: +0x00 s16 pos.x, +0x02 s16 pos.y,
--   +0x04 u8 mapGroup, +0x05 u8 mapNum, +0x06 u8 warpId. These give live
--   player coords + current map — the robust nav/scene-detection signal used
--   by nav_coords.lua (truck exit detected as map 25.40 -> 0.9 Littleroot).
H.SAVEBLOCK_PTRS = { 0x030051B8, 0x030051BC, 0x030051C0 }
H.gSaveBlock1Ptr = 0x030051B8
H.gSaveBlock2Ptr = 0x030051BC
H.gPokemonStoragePtr = 0x030051C0
-- SaveBlock1 field offsets (vanilla pokeemerald struct SaveBlock1):
H.SB1_POS_X   = 0x00  -- s16
H.SB1_POS_Y   = 0x02  -- s16
H.SB1_MAPGRP  = 0x04  -- u8
H.SB1_MAPNUM  = 0x05  -- u8

-- TODO / NOT YET CONFIRMED — these are what unlock the *state-mutation* half
-- of the ROWE debug-menu port ("Give Pokemon", "set var", "toggle catching").
-- They are much easier to find from a save that actually HAS a party than by
-- static analysis, which is why find_ram_anchors.lua exists: run it against a
-- savestate with Pokemon in the party and it will locate gPlayerParty by
-- scanning EWRAM for real 100-byte Pokemon structs. Until then, leave nil —
-- every helper below that needs one will fail loudly rather than poke a
-- guessed address (poking the wrong EWRAM address is exactly how you get a
-- "bug" that isn't real).
H.gPlayerParty = nil       -- EWRAM base of the 6x100-byte party array
H.gPlayerPartyCount = nil  -- u8 party count
H.gSaveBlock1 = nil        -- resolved (deref'd) save block 1 base
H.VAR_BLOCK = nil          -- base of the vars array (for VAR_CHARACTER_ID-alike)
H.FLAG_BLOCK = nil         -- base of the flags bitfield (for catching toggle)

-- ------------------------------------------------------------------- plumbing

local frame = 0
local frameHooks = {}
local passes, failures = 0, {}

function H.log(msg)
    console:log("HARNESS " .. tostring(msg))
end

function H.frame() return frame end

function H.onFrame(fn)
    table.insert(frameHooks, fn)
end

-- ------------------------------------------------------------------- memory

function H.rd8(a)  return emu:read8(a)  end
function H.rd16(a) return emu:read16(a) end
function H.rd32(a) return emu:read32(a) end

-- Writes are the "debug menu" half — give a Pokemon, set a var, flip a flag.
-- mGBA exposes write8/16/32 on the same emu object as the reads.
function H.wr8(a, v)  emu:write8(a, v)  end
function H.wr16(a, v) emu:write16(a, v) end
function H.wr32(a, v) emu:write32(a, v) end

function H.hex(v, width)
    return string.format("0x%0" .. (width or 8) .. "X", v)
end

-- Deref the save-block pointer trio (they're pointers, not the blocks).
function H.saveBlocks()
    local out = {}
    for i, p in ipairs(H.SAVEBLOCK_PTRS) do
        out[i] = emu:read32(p)
    end
    return out
end

-- ------------------------------------------------------------------ assertions

function H.assertEq(what, got, want)
    if got == want then
        passes = passes + 1
        H.log("PASS " .. what .. " = " .. tostring(got))
        return true
    end
    local msg = what .. ": got " .. tostring(got) .. ", want " .. tostring(want)
    table.insert(failures, msg)
    H.log("FAIL " .. msg)
    return false
end

function H.assertTrue(what, cond)
    return H.assertEq(what, cond and true or false, true)
end

function H.finish()
    H.log("---- SUMMARY ----")
    H.log(string.format("PASSED %d, FAILED %d", passes, #failures))
    for _, f in ipairs(failures) do
        H.log("  FAILURE: " .. f)
    end
    if #failures == 0 then
        H.log("RESULT: PASS")
    else
        H.log("RESULT: FAIL")
    end
end

-- ---------------------------------------------------------------------- input
--
-- Scripted controller input. This replaces ROWE's xdotool-driven manual
-- keypresses (their CLAUDE.md notes >=0.4s holds were needed for the real
-- GUI to register). Here we drive the emulated pad directly, so timing is
-- exact and deterministic in frames — no flakiness, no host focus stealing.

local pending = {}   -- queue of {key=, frames=} steps
local active = nil
local activeUntil = 0

-- Queue a keypress: hold `key` for `frames`, then release and wait `gap`.
function H.press(key, frames, gap)
    table.insert(pending, { key = key, frames = frames or 4, gap = gap or 6 })
end

-- Queue a whole sequence: {{KEY.A, 4}, {KEY.DOWN, 2}, ...}
function H.sequence(steps)
    for _, s in ipairs(steps) do
        H.press(s[1] or s.key, s[2] or s.frames, s[3] or s.gap)
    end
end

-- Mash a key every `every` frames from `fromFrame` to `toFrame`. Useful for
-- clicking through dialogue of unknown length (ROWE's tests had the same
-- problem and solved it by holding A repeatedly).
function H.mash(key, fromFrame, toFrame, every)
    every = every or 20
    local held = false
    H.onFrame(function(f)
        if f >= fromFrame and f <= toFrame and (f % every) == 0 then
            if held then emu:clearKey(key) else emu:addKey(key) end
            held = not held
        elseif f == toFrame + 1 and held then
            emu:clearKey(key)
            held = false
        end
    end)
end

local function pumpInput()
    if active then
        if frame >= activeUntil then
            emu:clearKey(active.key)
            activeUntil = frame + active.gap
            active = nil
        end
        return
    end
    if frame < activeUntil then return end  -- inter-press gap
    local step = table.remove(pending, 1)
    if step then
        emu:addKey(step.key)
        active = step
        activeUntil = frame + step.frames
    end
end

-- ------------------------------------------------------------------ breakpoints
--
-- Something ROWE's in-game debug menu could not do at all: halt on an
-- arbitrary ROM address and inspect CPU state. This is the core tool for
-- the Phase 1 routine-mapping work (see docs/ROUTINE_MAP.md).

function H.breakpoint(name, addr, fn)
    emu:setBreakpoint(function()
        local pc = emu:readRegister("pc")
        H.log(string.format("BP %-16s frame=%-5d pc=%s r0=%s r1=%s r2=%s",
            name, frame, H.hex(pc), H.hex(emu:readRegister("r0")),
            H.hex(emu:readRegister("r1")), H.hex(emu:readRegister("r2"))))
        if fn then fn(frame) end
    end, addr)
end

-- ---------------------------------------------------------------------- driver

callbacks:add("frame", function()
    frame = frame + 1
    pumpInput()
    for _, fn in ipairs(frameHooks) do
        fn(frame)
    end
end)

return H
