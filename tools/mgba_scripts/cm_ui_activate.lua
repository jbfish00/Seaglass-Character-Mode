-- Real-UI activation e2e: from naming_open.ss (CODE naming screen open, cursor
-- at 'A'), type a character code via explicitly-scheduled 40-frame-spaced cursor
-- moves (calibrated: closer taps get eaten as key-repeat), commit (START -> A),
-- A-mash the confirm/give dialogue, then assert Character Mode activated + the
-- starter given.
--
-- Config via env (defaults = Red): CM_CODE (e.g. "RED"), CM_EXPECT_CHAR (1).
-- CM_EXPECT=reject flips the assertions: the code must NOT activate anything
-- (flag stays 0, char stays 0, party unchanged) — for invalid-code input.
-- CM_EXPECT=off + CM_PRESET_CHAR=n: preset CM active (flag + char n) via RAM,
-- then the typed code (CMDBGOFF) must deactivate it (flag/char cleared, party
-- unchanged, starterVar = 0xFFFF off-marker).
-- UPPER page grid (col 6 = space, col 7 = punctuation):
--   row0 ABCDEF . | row1 GHIJKL , | row2 MNOPQRS | row3 TUVWXYZ
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local FLAG_CM, VAR_CHAR, VAR_STARTER = 0x945, 0x40E4, 0x40E5

local code = os.getenv("CM_CODE") or "RED"
local expectChar = tonumber(os.getenv("CM_EXPECT_CHAR") or "1")
local expectMode = os.getenv("CM_EXPECT") or "on"   -- on | reject | off
local presetChar = tonumber(os.getenv("CM_PRESET_CHAR") or "0")

local ROWS = { "ABCDEF .", "GHIJKL ,", "MNOPQRS ", "TUVWXYZ " }
local function findKey(ch)
    for r, row in ipairs(ROWS) do
        local c = row:find(ch, 1, true)
        if c then return r - 1, c - 1 end
    end
    error("char not on UPPER page: " .. ch)
end

-- flat list of key taps
local plan = {}
local cr, cc = 0, 0
for i = 1, #code do
    local r, c = findKey(code:sub(i, i))
    while cr < r do plan[#plan+1] = K.DOWN;  cr = cr + 1 end
    while cr > r do plan[#plan+1] = K.UP;    cr = cr - 1 end
    while cc < c do plan[#plan+1] = K.RIGHT; cc = cc + 1 end
    while cc > c do plan[#plan+1] = K.LEFT;  cc = cc - 1 end
    plan[#plan+1] = K.A
end
plan[#plan+1] = K.START
plan[#plan+1] = K.A

local STEP, START0 = 40, 40
local function at(f, key) H.onFrame(function(g) if g == f then H.press(key, 8) end end) end
for i = 1, #plan do
    at(START0 + (i - 1) * STEP, plan[i])
end
local commitFrame = START0 + (#plan - 1) * STEP   -- last step (commit A)

local before = {}
H.onFrame(function(f)
    if f == 8 then
        if presetChar > 0 then
            H.setFlag(FLAG_CM)
            H.setVar(VAR_CHAR, presetChar)
        end
        before.party = emu:read8(H.gPlayerPartyCount)
        before.flag = H.getFlag(FLAG_CM)
        H.log(("before: party=%d flag=%d char=%d"):format(
            before.party, before.flag, H.getVar(VAR_CHAR)))
    end
    if f == commitFrame - 20 then emu:screenshot("tools/savestates/ui_typed.png") end
end)
-- Dismiss the confirm/result dialogue AFTER commit. Keep this window SHORT:
-- the player is still standing at the clipboard, so a long A-mash re-triggers
-- the BG event, reopens the code entry, and can commit a stray invalid code
-- (which overwrites VAR_CM_STARTER and muddies the asserts). ~9 presses is
-- plenty for one msgbox; too few to drive prompt->naming->commit again.
H.mash(K.A, commitFrame + 80, commitFrame + 500, 45)
H.onFrame(function(f)
    if f == commitFrame + 900 then
        local party = emu:read8(H.gPlayerPartyCount)
        local flag = H.getFlag(FLAG_CM)
        local char = H.getVar(VAR_CHAR)
        local starter = H.getVar(VAR_STARTER)
        emu:screenshot("tools/savestates/ui_activate_end.png")
        H.log(("observed: flag=%d char=%d party %d->%d starterVar=%d"):format(
               flag, char, before.party, party, starter))
        if expectMode == "reject" then
            H.assertEq("flag stays clear", flag, 0)
            H.assertEq("char stays 0", char, 0)
            H.assertEq("party unchanged", party, before.party)
            H.assertEq("starter var cleared", starter, 0)
        elseif expectMode == "off" then
            H.assertEq("CM flag cleared", flag, 0)
            H.assertEq("char cleared", char, 0)
            H.assertEq("party unchanged", party, before.party)
            H.assertEq("starter var = off marker", starter, 0xFFFF)
        else
            H.assertEq("CM flag set", flag, 1)
            H.assertEq("character id", char, expectChar)
            H.assertEq("starter added to party", party, before.party + 1)
            H.assertEq("starter var cleared", starter, 0)
        end
        H.finish()
    end
end)
