-- Layer 2 boot smoke: prove the patched ROM actually boots and initialises,
-- rather than merely proving the emulator survived 200 frames.
--
-- ⚠️ 2026-08-20: until today this script asserted NOTHING. It ran to frame
-- 200, took a screenshot, logged "booted ok" and called H.finish() -- which
-- emitted RESULT: PASS on an empty tally, and run_tests.sh counted it as one
-- of the 19 green layers. It was the vacuous layer predicted by
-- ../game_plans/rowe_parity.md §1, found the moment the harness guard landed.
-- It could not have asserted the save blocks even if it had tried: the trio
-- only goes live at frame 240 (harness.lua's anchor notes) and this stopped at
-- 200.
--
-- What a boot smoke can honestly claim: the ROM reached the point of
-- allocating its save blocks. That is a real liveness signal -- a ROM that
-- crashes in the injected code, or wedges on a bad pointer, never gets here.
local H = dofile("tools/mgba_scripts/harness.lua")

local DEADLINE = 400   -- the trio is populated by frame 240
local done = false

local function inEwram(p) return p >= 0x02000000 and p < 0x02040000 end

H.onFrame(function(f)
    if done or f < DEADLINE then return end
    done = true
    local b1 = H.rd32(H.gSaveBlock1Ptr)
    local b2 = H.rd32(H.gSaveBlock2Ptr)
    local b3 = H.rd32(H.gPokemonStoragePtr)
    H.log(string.format("SB1=%s SB2=%s Storage=%s at frame %d",
                        H.hex(b1), H.hex(b2), H.hex(b3), f))
    H.assertTrue("SaveBlock1 pointer is live EWRAM", inEwram(b1))
    H.assertTrue("SaveBlock2 pointer is live EWRAM", inEwram(b2))
    H.assertTrue("PokemonStorage pointer is live EWRAM", inEwram(b3))
    -- Distinctness is the control: three reads of one stuck value, or of a
    -- constant left over in IWRAM, would satisfy the range checks above.
    H.assertTrue("the three pointers are distinct",
                 b1 ~= b2 and b2 ~= b3 and b1 ~= b3)
    emu:screenshot("tools/savestates/boot.png")
    H.finish()
end)
