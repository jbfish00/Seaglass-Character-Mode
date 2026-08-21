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
local FLAG_CM, VAR_CHAR, VAR_STARTER = 0x2B0, 0x40E4, 0x40E5

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


-- ---- character mugshot (Phase 3 render surface) ----
-- The confirm script brackets its "Character Mode is now active!" message with
-- callnative show/hide, so the mugshot must be on screen while that box is up.
-- The template is located by scanning the renderer blob for its tag pair rather
-- than hardcoding an address the build could move.
-- ⚠️ ...except the BLOB BASE was itself hardcoded, which is the same bug one
-- level up. On 2026-07-29 the renderer was rebased 0x08F42000 -> 0x08F60000 to
-- make room for four more portraits, and this layer failed with "template not
-- located in the renderer blob" while Character Mode itself was working
-- perfectly -- the flag, character and starter all asserted green in the same
-- run. run_tests.sh now exports CM_MUGSHOT_ADDR straight from the injector.
local MUG_BASE = tonumber(os.getenv("CM_MUGSHOT_ADDR") or "") or 0x08F60000
local MUG_SPAN = 0x300
local GSPRITES, SPRITE_COUNT, SPRITE_STRIDE = 0x02039810, 64, 0x44
local OFF_TEMPLATE, OFF_INUSE = 0x14, 0x3E

local MUG_TEMPLATE
for a = MUG_BASE, MUG_BASE + MUG_SPAN, 4 do
    if emu:read16(a) == 0xC0DE and emu:read16(a + 2) == 0xC0DF then MUG_TEMPLATE = a break end
end

local function countMugshot()
    if not MUG_TEMPLATE then return -1 end
    local n = 0
    for i = 0, SPRITE_COUNT - 1 do
        local s = GSPRITES + i * SPRITE_STRIDE
        if (emu:read8(s + OFF_INUSE) & 1) ~= 0
           and emu:read32(s + OFF_TEMPLATE) == MUG_TEMPLATE then n = n + 1 end
    end
    return n
end

local mugSeen, mugSampled, mugShot = 0, false, false

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
-- Sample across the whole post-commit window: the sprite is created while the
-- screen is still redrawing out of the naming screen, so a shot at the first
-- frame it exists shows a bare overworld and reads as a failure. Shoot +40.
H.onFrame(function(f)
    if f >= commitFrame + 20 and f <= commitFrame + 880 then
        local n = countMugshot()
        mugSampled = true
        if n > mugSeen then mugSeen = n end
        if n > 0 and not mugShot then
            mugShot = f
            H.log("mugshot present at frame " .. (f - commitFrame) .. " past commit")
        end
        if mugShot and f == mugShot + 40 then
            emu:screenshot("tools/savestates/ui_mugshot.png")
        end
    end
end)
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
            -- Report the sampling separately from the result: a window that
            -- never ran would otherwise read as "0 sprites" and pass as if the
            -- mugshot had simply been torn down already.
            H.assertTrue("mugshot template located in the renderer blob",
                         MUG_TEMPLATE ~= nil)
            H.assertTrue("confirm message was sampled", mugSampled)
            H.assertEq("mugshot drawn during the confirm message", mugSeen, 1)
            H.assertEq("mugshot torn down afterwards", countMugshot(), 0)
        end
        H.finish()
    end
end)
