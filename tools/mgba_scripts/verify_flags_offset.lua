-- Live verification of Seaglass's TRUE flags base (static disasm 2026-07-16:
-- FlagGet 0x0810D35C reads *0x030051B8 + 0x13C0 + id/8, bit id%8).
-- Method: breakpoint FlagGet entry (record id + our predicted bit) and its
-- regular-path exit `bx lr` (compare actual r0). Any mismatch = wrong base.
--
-- REQUIRES the 2026-07-16 headless-main.c patch:
--   MGBA_HEADLESS_DEBUGGER=1 timeout 180 ./tools/mgba_src/build/mgba-headless \
--     --script tools/mgba_scripts/verify_flags_offset.lua \
--     -t tools/savestates/outside_house.ss "rom/seaglass v3.0.gba" > log 2>&1
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR   = 0x030051B8
local FLAGS_OFF = 0x13C0
local FLAGGET_ENTRY = 0x0810D35C
local FLAGGET_EXIT  = 0x0810D380  -- shared bx lr (id==0 path skipped below)

-- wander a bit so object events / scripts query plenty of flags
H.mash(H.KEY.A, 200, 2800, 90)

local pendingId, pendingWant = nil, nil
local checked, ok, mism = 0, 0, 0

emu:setBreakpoint(function()
    local id = emu:readRegister("r0") % 0x10000
    if id == 0 or id >= 0x4000 then pendingId = nil; return end
    local sb1 = emu:read32(SB1_PTR)
    local byte = emu:read8(sb1 + FLAGS_OFF + math.floor(id / 8))
    pendingId = id
    pendingWant = math.floor(byte / 2 ^ (id % 8)) % 2
end, FLAGGET_ENTRY)

emu:setBreakpoint(function()
    if not pendingId then return end
    local got = emu:readRegister("r0") % 2
    checked = checked + 1
    if got == pendingWant then ok = ok + 1 else
        mism = mism + 1
        if mism <= 10 then
            H.log(string.format("MISMATCH id=0x%03X want=%d got=%d",
                pendingId, pendingWant, got))
        end
    end
    pendingId = nil
end, FLAGGET_EXIT)

local done = false
H.onFrame(function(f)
    if f ~= 3000 or done then return end
    done = true
    H.log(string.format("%d FlagGet calls checked", checked))
    H.assertTrue("checked >= 50 flag reads", checked >= 50)
    H.assertEq("predictions matching FlagGet return", ok, checked)
    H.finish()
end)
