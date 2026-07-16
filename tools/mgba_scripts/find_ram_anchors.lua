-- Seaglass Character Mode — RAM anchor finder (mgba-headless).
--
-- THE BOOTSTRAP STEP for the ROWE-debug-menu port (see docs/TESTING.md).
--
-- ROWE could "Give Pokemon" / "set VAR_CHARACTER_ID" / "toggle catching" from
-- an in-game debug menu because it had C source and could reference the
-- symbols directly. To do the equivalent from outside a closed binary we must
-- first LOCATE the corresponding RAM: gPlayerParty (and its struct stride),
-- the party count, and eventually the flags/vars blocks. Once those are known,
-- harness.lua's wr8/wr16/wr32 give us every state-mutation the debug menu had.
--
-- HOW: run this against a savestate that actually HAS Pokemon in the party
-- (i.e. the "wild battle, bag open" savestate — any save with >=1 party mon
-- works). It scans EWRAM for the unencrypted tail of Gen3 `struct Pokemon`
-- records and reports the base address + stride it infers.
--
--   ./tools/mgba_src/build/mgba-headless \
--     --script tools/mgba_scripts/find_ram_anchors.lua \
--     -t /path/to/savestate.ss1 \
--     "rom/seaglass v3.0.gba" 2>&1 | grep ANCHOR
--
-- WHY A HEURISTIC RATHER THAN VANILLA OFFSETS: Seaglass is a private
-- pokeemerald-expansion fork; its memory map demonstrably does NOT match
-- vanilla Emerald (verified: vanilla's gPlayerParty 0x020244EC, gSaveBlock1Ptr
-- 0x03005D8C etc. have ZERO literal-pool references anywhere in this ROM,
-- while a different IWRAM pointer trio at 0x030051B8/BC/C0 is the most-
-- referenced in the binary). Expansion also changes struct Pokemon's size in
-- some configs, so the STRIDE is discovered from the data rather than assumed
-- to be vanilla's 100 bytes.
--
-- HEURISTIC: in Gen3 the last ~20 bytes of struct Pokemon are plaintext
-- (the encrypted substructures are earlier), laid out as:
--     +0x50 u32 status
--     +0x54 u8  level          <- 1..100
--     +0x55 u8  mail
--     +0x56 u16 hp             <- <= maxHP
--     +0x58 u16 maxHP          <- 1..999
--     +0x5A u16 attack ... (further stats)
-- A real party is >=1 such records back to back at a fixed stride. We look
-- for any address where a plausible (level, hp, maxHP) triple sits, then
-- confirm by checking whether a second plausible record sits at a consistent
-- stride (or accept a lone record and report it as a single-mon candidate).
-- Every candidate is printed with its values so it can be eyeballed against
-- what the savestate actually shows on screen -- nothing here is trusted
-- blindly, and no address is written to.

local EWRAM_START = 0x02000000
local EWRAM_END   = 0x02040000

-- offsets of the plaintext tail within a struct Pokemon
local OFF_LEVEL = 0x54
local OFF_HP    = 0x56
local OFF_MAXHP = 0x58

-- Candidate strides: vanilla Gen3 is 100 (0x64). pokeemerald-expansion
-- variants can be larger. Test a range of plausible 4-byte-aligned sizes.
local STRIDES = { 100, 104, 108, 112, 116, 120, 124, 128 }

-- Pull all of EWRAM in ONE readRange call and parse in pure Lua. Doing this
-- with per-address emu:read8 calls (65k addresses x several reads each)
-- crosses the C/Lua marshalling boundary ~200k times and stalls the emulator
-- so badly the frame callback never returns -- tried it, it hangs. readRange
-- returns the bytes as a plain Lua string, so the whole scan becomes cheap
-- string indexing.
local ewram = nil  -- 1-indexed byte string covering EWRAM_START..EWRAM_END

local function u8(a)
    return string.byte(ewram, a - EWRAM_START + 1) or 0
end
local function u16(a)
    local lo = u8(a)
    local hi = u8(a + 1)
    return lo + hi * 256
end

local function u32(a)
    return u16(a) + u16(a + 2) * 65536
end

-- Tightened after a boot-state trial run: a level/hp/maxHP triple alone is far
-- too loose (52 false-positive "candidates" in uninitialized RAM at the title
-- screen, all with hp=0 and nonsense stats). Two extra constraints make the
-- signal unambiguous:
--   * personality (offset 0) and otId (offset 4) are nonzero for any real mon
--     -- uninitialized/zeroed RAM fails this immediately.
--   * a mon sitting in a party during a battle has hp >= 1 (a fainted mon can
--     be 0, but the savestate we scan is a live wild battle, and requiring
--     hp>=1 on the FIRST record only still allows fainted mons later in the
--     party -- see the run-scan below, which only requires plausibility).
local function plausibleMon(a, requireAlive)
    local level = u8(a + OFF_LEVEL)
    if level < 1 or level > 100 then return nil end
    local hp = u16(a + OFF_HP)
    local maxhp = u16(a + OFF_MAXHP)
    if maxhp < 1 or maxhp > 999 then return nil end
    if hp > maxhp then return nil end
    if requireAlive and hp < 1 then return nil end
    local personality = u32(a)
    local otId = u32(a + 4)
    if personality == 0 or personality == 0xFFFFFFFF then return nil end
    if otId == 0 or otId == 0xFFFFFFFF then return nil end
    return { level = level, hp = hp, maxhp = maxhp, personality = personality }
end

-- Wait before scanning. Two reasons: a loaded savestate's RAM wants a few
-- frames to settle, and the save-block pointer trio is zero at boot and only
-- populated by ~frame 240 (verified) -- scanning too early reports them as
-- 0x00000000 and looks like a failure when it isn't.
local SCAN_FRAME = 300
local frame = 0
local done = false
callbacks:add("frame", function()
    frame = frame + 1
    if done or frame < SCAN_FRAME then return end
    done = true

    console:log("ANCHOR scanning EWRAM for struct Pokemon plaintext tails...")
    ewram = emu:readRange(EWRAM_START, EWRAM_END - EWRAM_START)
    console:log(string.format("ANCHOR read %d bytes of EWRAM", #ewram))

    local singles = {}
    local a = EWRAM_START
    while a < EWRAM_END - 0x80 do
        -- require the FIRST record to be a live mon (hp>=1): party slot 0 in a
        -- live wild battle is always alive, and this is what filters out the
        -- uninitialized-RAM noise.
        local m = plausibleMon(a, true)
        if m then table.insert(singles, { addr = a, mon = m }) end
        a = a + 4
    end
    console:log(string.format("ANCHOR %d single-record candidates", #singles))

    -- Prefer candidates that repeat at a consistent stride: a real party
    -- array has consecutive valid records. Score each (addr, stride) pair by
    -- how many consecutive valid records follow.
    local best = {}
    for _, c in ipairs(singles) do
        for _, stride in ipairs(STRIDES) do
            local n = 1
            while n < 6 and plausibleMon(c.addr + n * stride) do
                n = n + 1
            end
            if n >= 2 then
                table.insert(best, { addr = c.addr, stride = stride, count = n, mon = c.mon })
            end
        end
    end

    table.sort(best, function(x, y)
        if x.count ~= y.count then return x.count > y.count end
        return x.addr < y.addr
    end)

    if #best == 0 then
        console:log("ANCHOR no multi-record runs found.")
        console:log("ANCHOR (a 1-Pokemon party is legitimate -- inspect the")
        console:log("ANCHOR  single-record candidates below by hand instead)")
        for i = 1, math.min(#singles, 25) do
            local c = singles[i]
            console:log(string.format("ANCHOR   single 0x%08X lvl=%d hp=%d/%d",
                c.addr, c.mon.level, c.mon.hp, c.mon.maxhp))
        end
    else
        console:log("ANCHOR multi-record runs (most likely gPlayerParty / gEnemyParty first):")
        for i = 1, math.min(#best, 20) do
            local b = best[i]
            console:log(string.format(
                "ANCHOR   base=0x%08X stride=%d consecutive=%d  first: lvl=%d hp=%d/%d",
                b.addr, b.stride, b.count, b.mon.level, b.mon.hp, b.mon.maxhp))
        end
        console:log("ANCHOR NOTE: gPlayerParty and gEnemyParty look identical to")
        console:log("ANCHOR this scan. Disambiguate by comparing the reported")
        console:log("ANCHOR level/HP against what the savestate shows on screen")
        console:log("ANCHOR (your mon vs the wild mon), then record the winner")
        console:log("ANCHOR in harness.lua's H.gPlayerParty + docs/TESTING.md.")
    end

    -- The save-block pointer trio (confirmed this session): deref and report,
    -- since the flags/vars arrays live inside save block 1 and locating them
    -- is the next step after the party.
    console:log("ANCHOR save-block pointer trio (confirmed runtime-initialized):")
    for _, p in ipairs({ 0x030051B8, 0x030051BC, 0x030051C0 }) do
        console:log(string.format("ANCHOR   [0x%08X] -> 0x%08X", p, emu:read32(p)))
    end
end)
