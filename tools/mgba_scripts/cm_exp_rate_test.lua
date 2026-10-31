-- Live layer: EXP rate (QoL, user 2026-10-29; src/character_mode.c "EXP rate").
-- battle_menu2.ss (Torchic vs a wild Zigzagoon, cm_instant_hp_test.lua's timing): Torchic is copied into slot 1 as a
-- bench mon that never battles, the lead's Attack is 999 and the foe's speed 1 so Scratch KOs it, the party-wide
-- Exp. Share flag 0x20 is set and Character Mode is OFF (the rate works in every save), VAR_EXP_RATE (0x407C) = RATE.
-- Asserts the EXP gained by the battler and the bench mon: WANT0 / WANT1, pinned per rate in run_tests.sh
-- (x1 gain * N / 2, N = 2 (x1), 3 (x1.5), 4 (x2), 6 (x3), 1 (x0.5); a nonzero award never becomes 0).
local H = dofile("tools/mgba_scripts/harness.lua")
local M = dofile("tools/mgba_scripts/mon_decrypt.lua")
local K = H.KEY
local FLAG_CM, FLAG_EXP_SHARE, VAR_EXP_RATE = 0x2B0, 0x20, 0x407C
local GBATTLEMONS = 0x02000360
local RATE = tonumber(os.getenv("RATE") or "0")
local WANT0, WANT1 = tonumber(os.getenv("WANT0") or "-1"), tonumber(os.getenv("WANT1") or "-1")
local before0, before1

H.onFrame(function(f)
    if f == 5 then
        H.clearFlag(FLAG_CM)
        H.setFlag(FLAG_EXP_SHARE)
        H.setVar(VAR_EXP_RATE, RATE)
        for k = 0, 99 do emu:write8(H.gPlayerParty + 100 + k, emu:read8(H.gPlayerParty + k)) end
        emu:write8(H.gPlayerPartyCount, 2)
        before0, before1 = M.decode(H.gPlayerParty).exp, M.decode(H.gPlayerParty + 100).exp
    end
    if f == 5 or f == 900 then
        emu:write16(GBATTLEMONS + 0x02, 999); emu:write16(GBATTLEMONS + 0x08, 999)
        emu:write16(GBATTLEMONS + 0x60 + 0x06, 1)
    end
    if f == 100 or f == 350 or f == 600 then H.press(K.A, 12, 30) end
    if f == 950 or f == 1100 then H.press(K.A, 12, 30) end
    if f > 1300 and f < 2600 and f % 40 == 0 then H.press(K.B, 6) end
    if f == 2800 then
        local a, b = M.decode(H.gPlayerParty), M.decode(H.gPlayerParty + 100)
        H.log(("rate %d: battler +%d, bench +%d (want %d / %d)"):format(RATE, a.exp - before0, b.exp - before1, WANT0, WANT1))
        H.assertTrue("Character Mode is off and both mons decrypt", H.getFlag(FLAG_CM) == 0 and a.ok and b.ok)
        H.assertEq("the rate var survived the battle", H.getVar(VAR_EXP_RATE), RATE)
        H.assertEq("battler EXP gained", a.exp - before0, WANT0)
        H.assertEq("bench EXP gained (Exp. Share)", b.exp - before1, WANT1)
        H.finish()
    end
end)
