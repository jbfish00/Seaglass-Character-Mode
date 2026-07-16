-- Seaglass Character Mode: fully-autonomous, headless catch-mechanic trace.
--
-- Unlike trace_catch_mechanic.lua (written for a human running the real GUI
-- and playing interactively), this script is meant for mgba-headless (built
-- from source in tools/mgba_src/ — see CLAUDE.md's Toolchain section for
-- why: the packaged mgba-qt 0.10.2 doesn't have --script) loaded with a
-- savestate that's already sitting at "wild battle in progress, bag open,
-- cursor on POKE BALL". From that point on, everything is scripted: no
-- GUI, no human, no display.
--
-- HOW TO RUN (from the Seaglass-Character-Mode repo root):
--   ./tools/mgba_src/build/mgba-headless \
--     --script tools/mgba_scripts/headless_catch_trace.lua \
--     -t /path/to/savestate.ss1 \
--     "rom/seaglass v3.0.gba" 2>&1 | grep "catch-trace"
--
-- The savestate path is supplied via mgba-headless's own -t/--savestate
-- flag, not by this script. Grep for "catch-trace" to cut out mGBA's very
-- verbose default BIOS/DMA/serial-IO logging.
--
-- WHAT IT DOES: arms breakpoints on the 6 catch-string-choice candidates
-- from docs/ROUTINE_MAP.md's "Catch mechanic" section (FUN_0811ff44,
-- FUN_08120304/534/8d4/cd0/db8), then presses A every ~20 frames from frame
-- 30 through frame ~800 (real Bash time: a few seconds, since mgba-headless
-- runs unthrottled) to: select POKE BALL, confirm the throw, and click
-- through whatever dialogue follows (shake animations don't need input;
-- "Gotcha!"/nickname-prompt/PC-transfer text does). Logs every breakpoint
-- hit with its frame number, function name, and r0-r2, then a completion
-- line — the process still needs an external `timeout` (see wrapper) since
-- there's no clean self-terminate call confirmed in this build.
--
-- API verified empirically against this exact build (not just read from
-- source): emu:setBreakpoint/emu:addKey/emu:clearKey/emu:getKeys all
-- confirmed working via a standalone test before this script was written.

local candidates = {
    { name = "FUN_0811ff44", addr = 0x0811ff44 },
    { name = "FUN_08120304", addr = 0x08120304 },
    { name = "FUN_08120534", addr = 0x08120534 },
    { name = "FUN_081208d4", addr = 0x081208d4 },
    { name = "FUN_08120cd0", addr = 0x08120cd0 },
    { name = "FUN_08120db8", addr = 0x08120db8 },
}

local GBA_KEY_A = 0
local hitCounts = {}
local frameCount = 0

for _, c in ipairs(candidates) do
    hitCounts[c.name] = 0
    emu:setBreakpoint(function()
        hitCounts[c.name] = hitCounts[c.name] + 1
        local pc = emu:readRegister("pc")
        local r0 = emu:readRegister("r0")
        local r1 = emu:readRegister("r1")
        local r2 = emu:readRegister("r2")
        console:log(string.format(
            "catch-trace HIT frame=%-5d %-14s #%-3d pc=0x%08X r0=0x%08X r1=0x%08X r2=0x%08X",
            frameCount, c.name, hitCounts[c.name], pc, r0, r1, r2))
    end, c.addr)
end

console:log("catch-trace ARMED: 6 breakpoints set, starting scripted A-press sequence")

local aHeld = false
callbacks:add("frame", function()
    frameCount = frameCount + 1

    -- toggle A on/off every 20 frames from frame 30 to frame 800: selects
    -- POKE BALL, confirms the throw, and clicks through all following
    -- dialogue regardless of exact animation-length timing.
    if frameCount >= 30 and frameCount <= 800 and (frameCount % 20) == 0 then
        if aHeld then
            emu:clearKey(GBA_KEY_A)
            aHeld = false
        else
            emu:addKey(GBA_KEY_A)
            aHeld = true
        end
    end

    if frameCount == 810 then
        console:log("catch-trace DONE: frame 810 reached, sequence complete")
        for _, c in ipairs(candidates) do
            console:log(string.format("catch-trace SUMMARY %-14s total_hits=%d", c.name, hitCounts[c.name]))
        end
    end
end)
