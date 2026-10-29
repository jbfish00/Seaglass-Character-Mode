-- Live layer (QoL A3 instant HP bar, 2026-10-28; tools/inject_character_mode.py instant_hp).
-- From battle_menu2.ss (Torchic vs a wild Zigzagoon; A advances the intro, the menu is up by ~950): the lead's Attack and Sp. Atk are set to 999 and the
-- foe's speed to 1, so Scratch KOs the full-HP foe first and its bar drains end to end. Every MoveBattleBar(HEALTH_BAR)
-- call (entry 0x0807CAD0, r2 == 0) is counted by frame, with the bar updates they belong to (an update starts while
-- gBattleSpritesDataPtr (0x0200085C)->battleBars[b].currValue holds -32768).
--   WANT_INSTANT=1 -> at most 4 frames an update (the shipped ROM)
--   WANT_INSTANT=0 -> more than 4 (B_FAST_HP_DRAIN: maxHP/24 a frame; build/seaglass_cm_nohp.gba, the control)
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local GBATTLEMONS = 0x02000360        -- gBattleMons, stride 0x60: attack +2, speed +6, sp. atk +8, hp +0x2A
local WANT = tonumber(os.getenv("WANT_INSTANT") or "1")
local frames, updates, last, hpBefore = 0, 0, -1, nil
H.breakpoint("MoveBattleBar", 0x0807CAD0, function()
    if emu:readRegister("r2") & 0xFF ~= 0 then return end
    if H.frame() ~= last then frames = frames + 1; last = H.frame() end
    local bars = emu:read32(emu:read32(0x0200085C) + 12)
    if emu:read32(bars + (emu:readRegister("r0") & 0xFF) * 20 + 16) == 0xFFFF8000 then updates = updates + 1 end
end)
H.onFrame(function(f)
    if f == 5 or f == 900 then                                  -- after the intro too, in case it re-reads stats
        emu:write16(GBATTLEMONS + 0x02, 999); emu:write16(GBATTLEMONS + 0x08, 999)
        emu:write16(GBATTLEMONS + 0x60 + 0x06, 1)
        hpBefore = hpBefore or emu:read16(GBATTLEMONS + 0x60 + 0x2A)
    end
    if f == 100 or f == 350 or f == 600 then H.press(K.A, 12, 30) end   -- the intro text (cm_catch_test.lua's timing)
    if f == 950 or f == 1100 then H.press(K.A, 12, 30) end     -- FIGHT, then move 1 (Scratch)
    if f > 1300 and f < 2600 and f % 40 == 0 then H.press(K.B, 6) end
    if os.getenv("SHOTS") and (f == 940 or f == 1090 or f == 1300 or f == 2000 or f == 2700) then emu:screenshot(os.getenv("SHOTS") .. f .. ".png") end
    if f == 2800 then
        H.log(("HP bar: %d frames of MoveBattleBar calls over %d updates; foe hp %d -> %d"):format(
            frames, updates, hpBefore, emu:read16(GBATTLEMONS + 0x60 + 0x2A)))
        H.assertTrue("the foe's bar drained (it started above 0 and the bar moved)", hpBefore > 0 and updates > 0)
        if WANT == 1 then
            H.assertTrue("instant HP bar: at most 4 frames per update", frames <= 4 * updates)
        else
            H.assertTrue("animated HP bar: more than 4 frames per update", frames > 4 * updates)
        end
        H.finish()
    end
end)
