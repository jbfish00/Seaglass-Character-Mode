-- Live layer: START > "Extras" (QoL round 2 item 3, 2026-11-11): EXP RATE / HEAL PARTY / PC, every save.
-- From route101.ss (on Route 101, with a party). The lead is set to 1 HP + poison, then START, UP
-- (the cursor wraps to the bottom row), A opens the Extras choice; KEYS ("D" down, "U" up, "B" cancel, "A" choose).
--   KEYS=DA  -> Heal party: the lead is at full HP with no status   (WANT_HEAL=1)
--   KEYS=DDA -> PC: the storage special (gSpecials[0x3F]) ran once  (WANT_PC=1)
--   KEYS=B   -> nothing
--   NO_MON_FLAG=1 KEYS=DA WANT_RATE=1: FLAG_SYS_POKEMON_GET cleared first -> the row opens the rate chooser at once
--     (D, A = x1.5: var 0x407C = 1), nothing is healed
-- Also: the normal menu ends with action 16, and START works again afterwards (the script released the player).
-- CLOSE: the key pressed after the action (A closes the heal message, B leaves the PC menu).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ACTIONS, COUNT = 0x0201D334, 0x0201D330      -- sCurrentStartMenuActions, sNumStartMenuActions
local PSS = tonumber(os.getenv("CM_PSS") or "0x081BB3E0") & ~1      -- gSpecials[0x3F]
local KEYS = os.getenv("KEYS") or "DA"
local WANT_HEAL, WANT_PC = tonumber(os.getenv("WANT_HEAL") or "1"), tonumber(os.getenv("WANT_PC") or "0")
local SHOT = os.getenv("CM_SHOT")
local P = H.gPlayerParty
local lastAction, pcHits = -1, 0
H.breakpoint("pss_special", PSS, function() pcHits = pcHits + 1 end)

H.onFrame(function(f)
    if f == 5 then
        H.setVar(0x407C, 0)
        if os.getenv("NO_MON_FLAG") == "1" then H.clearFlag(0x860) end
        emu:write16(P + 0x56, 1); emu:write32(P + 0x50, 8)
        H.assertTrue("lead hurt for the test (1 HP of more)", emu:read16(P + 0x56) == 1 and emu:read16(P + 0x58) > 1)
    end
    if f == 20 then H.press(K.START, 6) end
    if f == 70 then
        lastAction = emu:read8(ACTIONS + emu:read8(COUNT) - 1)
        H.press(K.UP, 6)
    end
    if f == 100 then H.press(K.A, 6) end
    if f == 190 and SHOT then emu:screenshot(SHOT) end
    for i = 1, #KEYS do
        if f == 200 + 30 * i then
            local c = KEYS:sub(i, i)
            H.press(c == "D" and K.DOWN or c == "U" and K.UP or c == "B" and K.B or K.A, 6)
        end
    end
    if f == 500 and SHOT then emu:screenshot((SHOT:gsub("%.png$", "_after.png"))) end
    if f == 520 then H.press(WANT_HEAL == 1 and K.A or K.B, 6) end
    if f == 580 then H.press(K.B, 6) end
    if f == 695 then emu:write8(COUNT, 0) end          -- so only a rebuilt menu passes the last check
    if f == 700 then H.press(K.START, 6) end
    if f == 760 then
        local healed = emu:read16(P + 0x56) == emu:read16(P + 0x58) and emu:read32(P + 0x50) == 0
        H.log(("last START action %d, lead hp %d/%d status %d, PC special hits %d, menu rows %d"):format(lastAction,
            emu:read16(P + 0x56), emu:read16(P + 0x58), emu:read32(P + 0x50), pcHits, emu:read8(COUNT)))
        H.assertEq("the normal START menu ends with the Extras row (action 16)", lastAction, 16)
        H.assertEq("lead healed (full HP, no status) after " .. KEYS, healed and 1 or 0, WANT_HEAL)
        H.assertEq("PC storage special ran", pcHits, WANT_PC)
        H.assertEq("EXP rate var 0x407C", H.getVar(0x407C), tonumber(os.getenv("WANT_RATE") or "0"))
        H.assertTrue("START opens again afterwards (player released, menu rebuilt)",
            emu:read8(COUNT) > 0 and emu:read8(ACTIONS + emu:read8(COUNT) - 1) == 16)
        H.finish()
    end
end)
