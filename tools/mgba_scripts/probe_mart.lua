-- Probe: from mart_inside.ss, report player pos/map, party count, and shoot a
-- screenshot so we can see where the cheat clipboard is relative to the player.
local H = dofile("tools/mgba_scripts/harness.lua")
H.onFrame(function(f)
    if f == 30 then
        local sb1 = emu:read32(H.gSaveBlock1Ptr)
        local x = emu:read16(sb1 + H.SB1_POS_X)
        local y = emu:read16(sb1 + H.SB1_POS_Y)
        local grp = emu:read8(sb1 + H.SB1_MAPGRP)
        local num = emu:read8(sb1 + H.SB1_MAPNUM)
        local party = emu:read8(H.gPlayerPartyCount)
        H.log(string.format("pos=(%d,%d) map=%d.%d party=%d", x, y, grp, num, party))
        emu:screenshot("tools/savestates/mart_probe.png")
        H.log("shot mart_probe.png")
    end
end)
