-- Why didn't setting TRUE flag 0x74 (SB1+0x13CE bit4) open the gate?
-- Write it at f=90, then watch the byte every 30 frames while walking the
-- gate_test route. Logs: +0x13CE (flag 0x74 byte), +0x13CA (flag 0x52 byte),
-- +0x158C (var 0x4050 low byte) — if +0x13CE reverts, something rewrites the
-- flags block; if it persists yet the gate still blocks, the checkflag path
-- reads elsewhere.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY

local function sb1() return emu:read32(SB1_PTR) end
local function snap(tag)
    local b = sb1()
    H.log(string.format("%s f=%d sb1=0x%08X [+13CE]=0x%02X [+13CA]=0x%02X [+158C]=0x%02X x=%d y=%d map=%d.%d",
        tag, H.frame(), b, emu:read8(b+0x13CE), emu:read8(b+0x13CA),
        emu:read8(b+0x158C), emu:read16(b), emu:read16(b+2),
        emu:read8(b+4), emu:read8(b+5)))
end

local set = false
H.onFrame(function(f)
    if f == 90 and not set then
        set = true
        snap("BEFORE")
        local b = sb1()
        emu:write8(b+0x13CE, emu:read8(b+0x13CE) | 0x10)
        snap("AFTER-WRITE")
        local seq = {
            {K.DOWN,16},{K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.LEFT,16},{K.UP,16},{K.UP,16},{K.UP,16},
        }
        for _, m in ipairs(seq) do H.press(m[1], m[2], 8) end
        -- the flag-0x74 branch is msgbox-only (no warp-back): dismiss the
        -- textbox with A, then keep pushing north
        for _ = 1, 6 do H.press(K.A, 8, 20) end
        for _ = 1, 4 do H.press(K.UP, 16, 8) end
    end
    if set and f > 90 and f % 30 == 0 and f <= 1000 then snap("WATCH") end
    if f == 1050 then
        emu:screenshot("tools/savestates/flag_write_probe.png")
        H.finish()
    end
end)
