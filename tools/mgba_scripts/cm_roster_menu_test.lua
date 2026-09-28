-- Live test of the in-game roster display (roster display, 2026-09-27).
--
-- Walks to the Oldale mart clipboard in the SHIPPED build (mart_inside.ss) and
-- interacts. CM state is preset in RAM (flag 0x2B0 + VAR_CM_CHAR), exactly as
-- the trade layer presets it.
--
--   MODE=roster  CM on as CM_CHAR: the pre-entry menu opens; row 0 "View
--                roster" pushes the character's family roots and opens the list
--                with callback set 2. Asserts the EXACT species pushed (from
--                CM_EXPECT_ROOTS, derived from characters_manifest.json by the
--                runner, never from the blob), the first icon, the SECOND row's
--                icon after one DOWN (selectedItem is the species -- the
--                "ID, not index" trap), and that B tears everything down.
--   MODE=code    CM on: row 1 "Character code" reaches the unchanged
--                activation path (CM_OpenCodeEntry runs), and no rows are pushed.
--   MODE=off     CM off: the pre-entry falls through to the original
--                "Enter a Character Mode code?" prompt: no dynmultichoice at
--                all, no rows pushed.
--
-- Symbol addresses come from the built ELFs via the environment (run_tests.sh
-- derives them), so a rebuilt shim cannot leave this test pointing at stale code.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local MODE = os.getenv("MODE") or "roster"
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "10")
local function envaddr(n)
    local v = os.getenv(n)
    if not v then error("missing env " .. n) end
    return tonumber(v)
end
local ON_INIT = envaddr("CM_ROSTER_ONINIT") & ~1
local ON_SEL = envaddr("CM_ROSTER_ONSEL") & ~1
local ON_DESTROY = envaddr("CM_ROSTER_ONDESTROY") & ~1
local OPEN_CODE = envaddr("CM_OPEN_CODE_ENTRY") & ~1
local EXPECT = {}
for s in (os.getenv("CM_EXPECT_ROOTS") or ""):gmatch("%d+") do EXPECT[#EXPECT + 1] = tonumber(s) end

local VAR_RESULT = 0x020055F0
local FLAG_CM, VAR_CM_CHAR = 0x2B0, 0x40E4
local DYNMULTI_HANDLER = 0x081EE0B0           -- ScrCmd_dynmultichoice
local PUSH_ELEMENT = 0x081EFE84               -- MultichoiceDynamic_PushElement
local CURSOR_MOVE = 0x081EFFAC                -- every list cursor move, any set
local gSpeciesInfo, ICON_OFF = 0x088F0780, 120
local gSprites, SPRITE_SIZE = 0x02039810, 68

local pushed, selSeen, dynCalls = {}, {}, 0
local hits = { init = 0, sel = 0, destroy = 0, open = 0, move = 0 }
emu:setBreakpoint(function() pushed[#pushed + 1] = emu:readRegister("r1") end, PUSH_ELEMENT)
emu:setBreakpoint(function() dynCalls = dynCalls + 1 end, DYNMULTI_HANDLER)
emu:setBreakpoint(function() hits.init = hits.init + 1 end, ON_INIT)
emu:setBreakpoint(function()
    hits.sel = hits.sel + 1
    selSeen[#selSeen + 1] = emu:read16(emu:readRegister("r0") + 4)   -- args->selectedItem
end, ON_SEL)
emu:setBreakpoint(function() hits.destroy = hits.destroy + 1 end, ON_DESTROY)
emu:setBreakpoint(function() hits.open = hits.open + 1 end, OPEN_CODE)
emu:setBreakpoint(function() hits.move = hits.move + 1 end, CURSOR_MOVE)

local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end

-- the in-use sprite drawing species s's icon, or nil
local function iconSpriteFor(s)
    local img = emu:read32(gSpeciesInfo + s * 208 + ICON_OFF)
    for i = 0, 63 do
        local b = gSprites + i * SPRITE_SIZE
        if (emu:read8(b + 62) & 1) == 1 and emu:read32(b + 12) == img then return b end
    end
end
local function anyRosterIcon()
    for _, s in ipairs(EXPECT) do if iconSpriteFor(s) then return true end end
    return false
end

local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
local t, firstIcon, secondIcon, secondPrio = {}, nil, nil, nil
local moveBase, selBase = 0, 0
H.onFrame(function(f)
    if f == 5 then
        if MODE == "off" then H.clearFlag(FLAG_CM) else
            H.setFlag(FLAG_CM); H.setVar(VAR_CM_CHAR, CM_CHAR) end
        emu:write16(VAR_RESULT, 0x1234)
    end
    -- ⚠️ The clipboard fires on the route's FIRST A (measured in layer 7a).
    if dynCalls > 0 and t.menu == nil then t.menu = f; phase = "menu_shot"; nextAt = f + 40 end
    if MODE == "off" and t.talked and t.offDone == nil and f > t.talked + 120 then
        t.offDone = f; emu:screenshot("tools/savestates/roster_off_prompt.png"); phase = "done"
    end
    if f < nextAt then return end
    local x, y = pos()
    if phase == "left" then
        stall = (x == lastx) and stall + 1 or 0
        if stall >= 2 then phase, stall, lasty = "up", 0, -1; nextAt = f + 6; return end
        lastx = x; H.press(K.LEFT, 10, 2); nextAt = f + 20
    elseif phase == "up" then
        stall = (y == lasty) and stall + 1 or 0
        if stall >= 2 then phase = "Aup"; nextAt = f + 6; return end
        lasty = y; H.press(K.UP, 10, 2); nextAt = f + 20
    elseif phase == "Aup" then
        H.press(K.A, 6); t.talked = f; phase = "faceL"; nextAt = f + 80
    elseif phase == "faceL" then
        if MODE ~= "off" then H.press(K.LEFT, 8) end
        phase = "talk"; nextAt = f + 30
    elseif phase == "talk" then
        if MODE ~= "off" then H.press(K.A, 6) end
        phase = "wait"; nextAt = f + 1
    elseif phase == "wait" then
        if f > 2500 then phase = "done" end
        nextAt = f + 1
    elseif phase == "menu_shot" then
        emu:screenshot(("tools/savestates/roster_%s_menu.png"):format(MODE))
        moveBase = hits.move
        phase = (MODE == "code") and "to_code" or "pick"; nextAt = f + 1
    elseif phase == "to_code" then
        if hits.move > moveBase then phase = "pick"; nextAt = f + 20
        elseif f - t.menu > 600 then phase = "done"
        else H.press(K.DOWN, 8, 8); nextAt = f + 20 end
    elseif phase == "pick" then
        H.press(K.A, 6)
        phase = (MODE == "code") and "code_wait" or "list_wait"; nextAt = f + 1
        t.picked = f
    elseif phase == "code_wait" then
        if hits.open > 0 then
            t.open = f; phase = "code_shot"; nextAt = f + 60
        elseif f - t.picked > 600 then phase = "done" else nextAt = f + 1 end
    elseif phase == "code_shot" then
        emu:screenshot("tools/savestates/roster_code_naming.png"); phase = "done"
    elseif phase == "list_wait" then
        if hits.init > 0 and hits.sel > 0 then
            t.list = f; phase = "list_shot"; nextAt = f + 40
        elseif f - t.picked > 600 then phase = "done" else nextAt = f + 1 end
    elseif phase == "list_shot" then
        firstIcon = iconSpriteFor(EXPECT[1] or 0) ~= nil
        emu:screenshot(("tools/savestates/roster_list_c%d_row0.png"):format(CM_CHAR))
        selBase = hits.sel
        phase = "down"; nextAt = f + 1
    elseif phase == "down" then
        if hits.sel > selBase then phase = "down_shot"; nextAt = f + 40
        elseif f - t.list > 600 then phase = "close"
        else H.press(K.DOWN, 8, 8); nextAt = f + 20 end
    elseif phase == "down_shot" then
        local b = iconSpriteFor(EXPECT[2] or 0)
        secondIcon = b ~= nil
        secondPrio = b and ((emu:read8(b + 5) >> 2) & 3)
        emu:screenshot(("tools/savestates/roster_list_c%d_row1.png"):format(CM_CHAR))
        phase = "close"; nextAt = f + 1
    elseif phase == "close" then
        if hits.destroy > 0 then t.closed = f; phase = "settle"; nextAt = f + 60
        elseif f - t.list > 1500 then phase = "done"
        else H.press(K.B, 8, 8); nextAt = f + 20 end
    elseif phase == "settle" then
        emu:screenshot(("tools/savestates/roster_closed_c%d.png"):format(CM_CHAR))
        phase = "done"
    end
    if phase == "done" then
        phase = "finished"
        local p = {}
        for _, v in ipairs(pushed) do p[#p + 1] = tostring(v) end
        local s = {}
        for _, v in ipairs(selSeen) do s[#s + 1] = tostring(v) end
        H.log(("mode=%s char=%d dynmultichoice=%d pushed=[%s] sel=[%s] init=%d destroy=%d open=%d")
            :format(MODE, CM_CHAR, dynCalls, table.concat(p, ","), table.concat(s, ","),
                    hits.init, hits.destroy, hits.open))
        if MODE == "roster" then
            H.assertEq("rows pushed == the character's family roots, in order",
                table.concat(p, ","), table.concat(EXPECT, ","))
            H.assertTrue("set 2 OnInit ran once", hits.init == 1)
            H.assertEq("first OnSelectionChanged got the first root's SPECIES", selSeen[1], EXPECT[1])
            H.assertTrue("the first root's icon was drawn from gSpeciesInfo+120", firstIcon == true)
            H.assertEq("after one DOWN, OnSelectionChanged got the SECOND root's species",
                selSeen[#selSeen], EXPECT[2])
            H.assertTrue("the second root's icon replaced it", secondIcon == true)
            H.assertEq("the icon is above the window layer (oam priority)", secondPrio, 0)
            H.assertTrue("B closed the list: set 2 OnDestroy ran", hits.destroy == 1)
            H.assertTrue("no roster icon survives the close", not anyRosterIcon())
            H.assertEq("VAR_RESULT is B (127)", emu:read16(VAR_RESULT), 127)
        elseif MODE == "code" then
            H.assertTrue("the pre-entry menu opened", dynCalls == 1)
            H.assertTrue("row 1 reached CM_OpenCodeEntry", hits.open == 1)
            H.assertTrue("no roster rows were pushed", #pushed == 0)
        else
            H.assertTrue("CM off: the clipboard was used", t.talked ~= nil)
            H.assertTrue("CM off: no dynmultichoice opened", dynCalls == 0)
            H.assertTrue("CM off: no roster rows were pushed", #pushed == 0)
        end
        H.finish()
    end
end)
