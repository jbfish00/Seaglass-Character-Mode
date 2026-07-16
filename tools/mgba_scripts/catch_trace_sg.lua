-- Seaglass catch trace (Lazarus method). From battle_menu2.ss ("Wild X
-- appeared!" stage): give 20 Poke Balls + weaken the wild mon to 1 HP (reliable
-- catch), advance to the command menu, BAG -> POKe BALLS pocket -> throw a ball.
-- Write-change watchpoints on gPlayerPartyCount + party slot1 catch the
-- GiveMonToPlayer write path. RUN WITH MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local DIR = "tools/savestates/"
local K = H.KEY
local POCKETS = 0x0200B0B8
local ENEMY = 0x02019E78
local PARTYCOUNT = 0x02019C1D

-- setup at f=30: balls + weaken enemy
H.onFrame(function(f)
    if f ~= 30 then return end
    local desc = POCKETS + 8
    local slots = emu:read32(desc)
    local key = emu:read16(emu:read32(H.gSaveBlock2Ptr) + 0xB0)
    emu:write16(slots, 1); emu:write16(slots + 2, 20 ~ key)
    emu:write16(ENEMY + 0x56, 1)          -- wild mon HP = 1
    H.log(string.format("setup: balls in, enemy HP now %d, partyCount %d",
        emu:read16(ENEMY + 0x56), emu:read8(PARTYCOUNT)))
end)

-- arm watchpoints late (they single-step). type 5 = WRITE_CHANGE.
local armed = false
local hits = 0
local function armWP()
    for _, spec in ipairs({{"partyCount", PARTYCOUNT}, {"slot1", 0x02019C20 + 100}}) do
        local id = emu:setWatchpoint(function()
            hits = hits + 1
            if hits <= 60 then
                H.log(string.format("WP %-10s pc=0x%08X lr=0x%08X r0=0x%08X r1=0x%08X r2=0x%08X",
                    spec[1], emu:readRegister("pc"), emu:readRegister("lr"),
                    emu:readRegister("r0"), emu:readRegister("r1"), emu:readRegister("r2")))
            end
        end, spec[2], 5)
        H.log(spec[1] .. " wp id=" .. tostring(id))
    end
end

H.onFrame(function(f)
    if f==100 or f==350 or f==600 then H.press(K.A, 12, 30) end   -- advance intro
    if f==950  then H.press(K.RIGHT, 12, 30) end                  -- FIGHT -> BAG
    if f==1100 then H.press(K.A, 12, 30) end                      -- open bag
    if f==1300 then emu:screenshot(DIR.."cts_bag.png"); H.press(K.RIGHT, 12, 30) end  -- ITEMS -> BALLS
    if f==1500 then emu:screenshot(DIR.."cts_balls.png") end
    if f==1520 and not armed then armed=true; armWP() end
    if f==1560 then H.press(K.A, 12, 40) end                      -- select Poke Ball
    if f==1720 then H.press(K.A, 12, 40) end                      -- confirm throw
    if f>1900 and f<4200 and f%80==0 then H.press(K.A, 8, 30) end -- advance catch text
    if f==4400 then
        emu:screenshot(DIR.."cts_end.png")
        H.log(string.format("END partyCount=%d slot1pid=0x%08X wpHits=%d",
            emu:read8(PARTYCOUNT), emu:read32(0x02019C20+100), hits))
        emu:saveStateFile(DIR.."after_catch.ss")
        H.finish()
    end
end)
