-- Seaglass Character Mode: catch-mechanic disambiguation trace.
--
-- WHY THIS EXISTS: docs/ROUTINE_MAP.md's "Catch mechanic" section found 6
-- candidate call sites (FUN_0811ff44, FUN_08120304/534/8d4/cd0/db8) that all
-- write a "next battle string" index into a shared 0x28-byte-stride struct
-- right before some battle message is displayed via the gBattleStringsTable
-- -equivalent (base 0x004C9A44). Static disassembly (Ghidra, -noanalysis)
-- can't recover the indirect jump table that would say which one is
-- catch-success ("Gotcha! ... was caught!") vs. a sibling case (faint,
-- status-cured, etc). This script breakpoints all 6 and logs which one(s)
-- fire, so a human playing the ROM can correlate hits against what's on
-- screen. This needs a live human catch attempt — it's not something that
-- can be scripted/automated from outside the emulator.
--
-- Addresses are pinned to rom/seaglass v3.0.gba, SHA1 in rom.sha1 (see
-- docs/ROM_INFO.md). Re-verify against docs/ROUTINE_MAP.md if the ROM
-- changes.
--
-- HOW TO USE:
--   1. mGBA (mgba-qt) -> Tools -> Scripting -> Load script -> pick this file.
--   2. Tools -> Scripting -> View console, to see the log output below.
--   3. Load rom/seaglass v3.0.gba, get into a wild battle, and throw a
--      Poke Ball until you get an actual catch. (A low-HP/weak wild
--      Pokemon with a high catch rate, e.g. a low-level Zigzagoon, makes
--      this fast and reliable — you don't need to actually complete the
--      catch cleanly on the first ball, just get one "Gotcha!" to fire.)
--   4. Watch the console: note which candidate(s) fire, and in what order,
--      right as "Gotcha! [X] was caught!" appears on screen. For contrast,
--      also note which candidate(s) fire on an ordinary battle message
--      (e.g. a Pokemon fainting) so the catch-specific one can be told
--      apart from shared/sibling cases.
--   5. Report back the hit log (or paste it into docs/ROUTINE_MAP.md) so
--      the real catch-success handler can be marked CONFIRMED and Phase 1's
--      hook site locked in.
--
-- API used here (verified against mGBA 0.10.2's src/core/scripting.c):
--   emu:setBreakpoint(callback, address, [segment]) -> breakpoint id
--   emu:readRegister(name)  -- e.g. "r0", "pc"
--   console:log(str)
-- If any call errors out, mGBA's in-app scripting docs (Tools -> Scripting
-- -> the API browser in the console dock) are the source of truth for the
-- installed version's exact signatures.

local candidates = {
    { name = "FUN_0811ff44", addr = 0x0811ff44 },
    { name = "FUN_08120304", addr = 0x08120304 },
    { name = "FUN_08120534", addr = 0x08120534 },
    { name = "FUN_081208d4", addr = 0x081208d4 },
    { name = "FUN_08120cd0", addr = 0x08120cd0 },
    { name = "FUN_08120db8", addr = 0x08120db8 },
}

local hitCounts = {}

for _, c in ipairs(candidates) do
    hitCounts[c.name] = 0
    emu:setBreakpoint(function()
        hitCounts[c.name] = hitCounts[c.name] + 1
        local pc = emu:readRegister("pc")
        local r0 = emu:readRegister("r0")
        local r1 = emu:readRegister("r1")
        local r2 = emu:readRegister("r2")
        console:log(string.format(
            "[catch-trace] %-14s hit #%-3d pc=0x%08X r0=0x%08X r1=0x%08X r2=0x%08X",
            c.name, hitCounts[c.name], pc, r0, r1, r2))
    end, c.addr)
end

console:log("[catch-trace] armed breakpoints on all 6 catch-string-choice candidates.")
console:log("[catch-trace] battle a wild Pokemon, throw a Poke Ball, and watch for 'Gotcha!'.")
