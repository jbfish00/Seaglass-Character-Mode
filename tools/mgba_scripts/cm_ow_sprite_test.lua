-- Live test: the player's overworld sprite follows the character (2026-10-03).
--
-- From naming_open.ss (the CODE screen open at the clipboard), type CM_CODE the
-- way cm_ui_activate.lua does, let the shipped activation script run (its
-- callnative now sweeps, then refreshes the player's sprite), and then read the
-- player straight out of OBJ VRAM and palette RAM against the expected art
-- (tools/tests/ow_sprite_env.py writes it from the SOURCE sheet or the base
-- ROM, never from the build).
--
--   CM_EXPECT=on   right after the script: VRAM shows one of the character's
--                  frames and the palette is theirs. Then walking and running
--                  in all four directions: every sample is that direction's
--                  frame, and each direction draws a step frame of its own
--                  while walking and while running.
--   CM_EXPECT=off  the code is refused (ZZZ): the player is not the character.
--
-- Env: CM_CODE, CM_EXPECT, CM_OW_EXPECT, CM_OW_FRAME_BYTES, CM_EXPECT_CHECKS,
--      CM_SHOTS (screenshot prefix), CM_OW_NATIVE_IMAGES (Brendan/May: their
--      images table, asserted instead of VRAM bytes).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local FLAG_CM, VAR_CHAR = 0x2B0, 0x40E4
local code = os.getenv("CM_CODE") or "MISTY"
local expectMode = os.getenv("CM_EXPECT") or "on"
local FB = tonumber(os.getenv("CM_OW_FRAME_BYTES") or "256")
local SHOTS = os.getenv("CM_SHOTS") or "/tmp/sg_ow"
local NATIVE_IMAGES = tonumber(os.getenv("CM_OW_NATIVE_IMAGES") or "")   -- set for Brendan/May
local NATIVE_CHECK_AT

local fh = assert(io.open(os.getenv("CM_OW_EXPECT"), "rb"))
local blob = fh:read("a"); fh:close()
local FRAMES, PAL = {}, {}
for i = 0, 17 do FRAMES[i] = blob:sub(i * FB + 1, (i + 1) * FB) end
for k = 0, 15 do PAL[k] = string.unpack("<I2", blob, 18 * FB + 2 * k + 1) end

-- pokeemerald's player layout: walk stands 0-2, walk steps 3-8, run stands 9-11,
-- run steps 12-17 (south, north, west; east is west flipped).
local SETS = { walk = { DOWN = { 0, 3, 4 }, UP = { 1, 5, 6 }, LEFT = { 2, 7, 8 }, RIGHT = { 2, 7, 8 } },
               run = { DOWN = { 9, 12, 13 }, UP = { 10, 14, 15 }, LEFT = { 11, 16, 17 }, RIGHT = { 11, 16, 17 } } }
local STAND = { DOWN = 0, UP = 1, LEFT = 2, RIGHT = 2 }

local gSprites, SPRITE_SIZE = 0x02039810, 0x44
-- The player's object by its isPlayer bit (flags word bit 16), its sprite id at
-- +0x23 (ObjectEventSetGraphics reads it there). gPlayerAvatar's own index
-- named the follower once, so it isn't trusted.
local function playerSprite()
    for i = 0, 15 do
        local o = 0x0200564C + i * 0x24
        if (emu:read32(o) & 0x10001) == 0x10001 then return gSprites + emu:read8(o + 0x23) * SPRITE_SIZE end
    end
    return gSprites
end
local function vramFrames()
    local b = playerSprite()
    local at = 0x06010000 + (emu:read16(b + 4) & 0x3FF) * 32
    local t = {}
    for k = 0, FB - 1, 4 do t[#t + 1] = string.pack("<I4", emu:read32(at + k)) end
    local cur, hit = table.concat(t), {}
    for i = 0, 17 do if FRAMES[i] == cur then hit[#hit + 1] = i end end
    return #hit > 0 and hit or nil
end
local function paletteOk()
    local pal = (emu:read16(playerSprite() + 4) >> 12) & 15
    for k = 1, 15 do
        if emu:read16(0x05000200 + pal * 32 + 2 * k) ~= PAL[k] then return false end
    end
    return true
end
local function contains(t, v) for _, x in ipairs(t) do if x == v then return true end end return false end
local function overlaps(a, b) for _, x in ipairs(a) do if contains(b, x) then return true end end return false end
-- Gait from the sprite's own anim number: the player table's run anims are
-- 20-23 (0x085D0F98, decoded 2026-10-03). gPlayerAvatar's flag byte reads as
-- noise in this fork, so it isn't used.
local function dashing()
    local a = emu:read8(playerSprite() + 0x2A)
    return a >= 20 and a <= 23
end

-- ---- type the code (cm_ui_activate.lua's grid and timing) ----
local ROWS = { "ABCDEF .", "GHIJKL ,", "MNOPQRS ", "TUVWXYZ " }
local function findKey(ch)
    for r, row in ipairs(ROWS) do
        local c = row:find(ch, 1, true)
        if c then return r - 1, c - 1 end
    end
    error("char not on UPPER page: " .. ch)
end
local plan, cr, cc = {}, 0, 0
for i = 1, #code do
    local r, c = findKey(code:sub(i, i))
    while cr < r do plan[#plan + 1] = K.DOWN; cr = cr + 1 end
    while cr > r do plan[#plan + 1] = K.UP; cr = cr - 1 end
    while cc < c do plan[#plan + 1] = K.RIGHT; cc = cc + 1 end
    while cc > c do plan[#plan + 1] = K.LEFT; cc = cc - 1 end
    plan[#plan + 1] = K.A
end
plan[#plan + 1] = K.START
plan[#plan + 1] = K.A
local STEP, START0 = 40, 40
for i = 1, #plan do
    local f0, key = START0 + (i - 1) * STEP, plan[i]
    H.onFrame(function(g) if g == f0 then H.press(key, 8) end end)
end
local commitFrame = START0 + (#plan - 1) * STEP
H.mash(K.A, commitFrame + 80, commitFrame + 500, 45)

-- ---- after the script: the look, then out of the mart, then walk/run ----
-- Emerald forbids running in the Oldale Mart, so the route first leaves it:
-- right to the door column (x 3), then down until the map changes (to Oldale
-- 0.10, arriving at (14,6) with open ground south and east). Measured
-- 2026-10-03 from mart_inside.ss. Running is B + direction here.
local function pos()
    local sb = emu:read32(0x030051B8)
    return emu:read16(sb), emu:read16(sb + 2), emu:read8(sb + 4) * 256 + emu:read8(sb + 5)
end
local steps = {
    { dir = "DOWN", b = true, hold = 40 }, { dir = "RIGHT", b = true, hold = 24 },
    { dir = "UP", b = true, hold = 16 }, { dir = "LEFT", b = true, hold = 16 },
    { dir = "DOWN", b = false, hold = 32 }, { dir = "RIGHT", b = false, hold = 32 },
    { dir = "UP", b = false, hold = 32 }, { dir = "LEFT", b = false, hold = 32 },
}
local exitPlan, exitMap = { "RIGHT", "RIGHT", "RIGHT" }, nil
for _ = 1, 10 do exitPlan[#exitPlan + 1] = "DOWN" end
local CHECK_AT, GAP, TURN = commitFrame + 900, 24, 3
local got, bad, si, t0 = {}, {}, 1, nil

H.onFrame(function(f)
    if f == CHECK_AT then
        local hit = vramFrames()
        emu:screenshot(SHOTS .. "_stand.png")
        H.log(("after the script: flag=%d char=%d frame=%s"):format(H.getFlag(FLAG_CM),
              H.getVar(VAR_CHAR), hit and table.concat(hit, "+") or "none"))
        if expectMode == "off" then
            H.assertEq("mode stays off", H.getFlag(FLAG_CM), 0)
            H.assertTrue("the player is not drawn with the character's art", hit == nil)
            H.assertTrue("the palette is not the character's", not paletteOk())
            H.finish()
        end
        H.assertEq("mode on", H.getFlag(FLAG_CM), 1)
        if NATIVE_IMAGES then
            -- Seaglass's own player sprites (Brendan, May) are adjusted after
            -- the copy, so their VRAM never equals the ROM frames byte for
            -- byte. Assert the sprite runs on that native images table instead,
            -- before and after a map change (the mart door).
            H.assertEq("right after activation the sprite uses the native images table",
                       emu:read32(playerSprite() + 12), NATIVE_IMAGES)
        else
            H.assertTrue("right after activation VRAM holds one of the character's frames", hit ~= nil)
            H.assertTrue("and the palette is the character's", paletteOk())
        end
        exitMap = select(3, pos())
        t0 = f + 1
    elseif t0 and exitPlan and #exitPlan > 0 then
        local dt = f - t0
        if dt == 0 then emu:addKey(K[exitPlan[1]])
        elseif dt == 16 then emu:clearKey(K[exitPlan[1]])
        elseif dt == 28 then
            table.remove(exitPlan, 1)
            if select(3, pos()) ~= exitMap then
                exitPlan = nil
                local x, y, m = pos()
                H.log(("left the mart: map %d.%d at (%d,%d)"):format(m // 256, m % 256, x, y))
                if NATIVE_IMAGES then
                    NATIVE_CHECK_AT = f + 40
                end
                t0 = f + 60
                return
            end
            t0 = f + 1
            if #exitPlan == 0 then H.assertTrue("left the mart", false); H.finish() end
        end
    elseif NATIVE_CHECK_AT and f == NATIVE_CHECK_AT then
        H.assertEq("after the map change it still does",
                   emu:read32(playerSprite() + 12), NATIVE_IMAGES)
        H.finish()
    elseif t0 and not exitPlan and not NATIVE_IMAGES and si <= #steps and f >= t0 then
        local s, dt = steps[si], f - t0
        if dt == 0 then
            emu:addKey(K[s.dir]); if s.b then emu:addKey(K.B) end
        elseif dt <= s.hold then
            if dt > TURN then
                local hit = vramFrames()
                local gait = dashing() and "run" or "walk"
                local ok = hit and (overlaps(hit, SETS.walk[s.dir]) or overlaps(hit, SETS.run[s.dir])
                                    or contains(hit, STAND[s.dir]))
                if not ok then bad[#bad + 1] = ("%s/%s:%s"):format(s.dir, gait, hit and table.concat(hit, "+") or "x") end
                if hit then
                    for _, v in ipairs(hit) do
                        local set = SETS[gait][s.dir]
                        if contains(set, v) and v ~= set[1] and v ~= STAND[s.dir] then
                            got[s.dir] = got[s.dir] or {}; got[s.dir][gait] = true
                        end
                    end
                end
            end
            if dt == s.hold // 2 then emu:screenshot(("%s_%d_%s%s.png"):format(SHOTS, si, s.dir, s.b and "_B" or "")) end
        elseif dt == s.hold + 1 then
            emu:clearKey(K[s.dir]); emu:clearKey(K.B)
        elseif dt >= s.hold + GAP then
            si, t0 = si + 1, f + 1
            if si > #steps then
                H.assertTrue("every sample shows its own direction's frame (stray: "
                             .. (#bad == 0 and "none" or table.concat(bad, " ")) .. ")", #bad == 0)
                for _, d in ipairs({ "DOWN", "UP", "LEFT", "RIGHT" }) do
                    for _, g in ipairs({ "walk", "run" }) do
                        H.assertTrue(("%s %s: a step frame was drawn"):format(g, d), got[d] and got[d][g])
                    end
                end
                H.finish()
            end
        end
    end
end)
