/* Character Mode shims for Pokemon Emerald Seaglass v3.0 (by Nemo622).
 *
 * Six entry points. The first five live in the big free block (ROM
 * 0x08ED2164+) and are reached only through full 32-bit pointers (BG-event
 * ptr, specials-free script pointers, 49 callnative operands) — except the
 * two acquisition BLs, which go through the 8-byte trampoline at 0x08470200.
 * The sixth (CM_WildMonSpeciesGated) lives in the SAME far blob but is
 * reached via a SEPARATE small trampoline (src/wild_trampoline.c, placed
 * right after the acquisition trampoline at 0x08470208) because its hook
 * site is ~7.6 MiB away — out of Thumb BL range from here, so the far
 * trampoline does a manual long-call (no BLX on this CPU). See
 * tools/inject_character_mode.py + docs/ROUTINE_MAP.md; every fixed address is
 * CONFIRMED for this exact ROM (rom.sha1).
 *
 *  1. CM_OpenCodeEntry(ctx) — callnative from our repointed cheat-clipboard
 *     script. Opens the expansion CODE naming screen (template 5) writing to
 *     gStringVar2, with the return-to-field callback 0x08179AFD so the paused
 *     script resumes after the player types a code. Seaglass's own GIFT CODE
 *     flow is the Easy-Chat questionnaire (no free text), so unlike Lazarus
 *     there is no matcher special to hook — we drive the (compiled but unused)
 *     CODE naming screen ourselves.
 *
 *  2. CM_MatchCode(ctx) — callnative right after the `waitstate`. Case-folds
 *     the entered code (gStringVar2) against the 170 character codes + 3 debug
 *     codes; on match sets VAR_CM_CHAR + FLAG_CHARACTER_MODE + VAR_CM_STARTER
 *     (the script gives that species) and gSpecialVar_Result = 1 (matched) /
 *     2 (debug-off) so the script branches to the confirmation. No match ->
 *     Result 0 and VAR_CM_STARTER cleared (stale-marker guard).
 *
 *  3. CM_GiveMonToPlayerGated(mon) — acquisition gate (ROWE/RR semantics):
 *     Character Mode on + off-roster non-egg -> PC instead of party.
 *     BL-retargeted callers: wild-catch 0x080A6A46 and the small script-give
 *     fn's internal call 0x081F18DE. Egg-hatch 0x08188514 stays original.
 *
 *  4. CM_NativeGiveGated(ctx) — Seaglass's real script gifts do NOT go through
 *     GiveMonToPlayer; they use a custom callnative give (0x081F2175, 49
 *     inline script sites, all retargeted here). The native inserts into the
 *     party itself, so this wrapper post-checks: party grew + new last slot is
 *     off-roster non-egg -> copy to PC and drop from party. Soft-lock guard:
 *     never removes the only party mon.
 *
 *  5. CM_TradeCheck(ctx) — in-game trade gate (task #4; sIngameTrades located
 *     separately). Writes 1 (allow) / 0 (refuse) to gSpecialVar_Result.
 *
 *  6. CM_WildMonSpeciesGated(species, level) — wild-encounter override (task
 *     #5). Hooked at the SINGLE call site inside the wild-encounter
 *     species/level roll that invokes CreateMonWithIVs-simple (0x081A7504),
 *     found live via mgba-headless breakpoint tracing (docs/ROUTINE_MAP.md):
 *     ROM file offset 0x22BF36 (BL operand, currently -> 0x081A7504),
 *     r0=gEnemyParty, r1=rolled species, r2=rolled level at that exact PC.
 *     This single choke point is shared by every wild-roll table type --
 *     grass/cave land encounters, surfing, rock smash, and all 3 fishing rod
 *     tiers all fall through TryGenerateWildMon/GenerateFishingWildMon (the
 *     donor's shared species+level roll routines) into this one
 *     CreateMonWithIVs call, exactly mirroring the acquisition gate's single
 *     GiveMonToPlayer choke point. Static/scripted gift encounters never
 *     reach this call (they use the separate give-native path already
 *     gated by CM_NativeGiveGated), so they're untouched by construction.
 *     On a 10% roll (CM on only — inert with Character Mode off, per
 *     gateActive()), overrides the rolled species with a random member of
 *     the active character's wild pool (tools/character_mode/emit_wildpool.py
 *     -> wildpool.bin — non-legendary roster bases only, expanded through
 *     the donor evolution graph with a canon "first appears at this level"
 *     estimate per family member), picking the stage whose level best fits
 *     the roll (nearest-at-or-below, else nearest overall). The rolled level
 *     itself is left untouched — only the species may change.
 *
 * MON_DATA_SPECIES=18 / IS_EGG=52 confirmed for this ROM (docs/ROUTINE_MAP.md).
 */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

/* 0 script refs (audited: no setflag/clearflag/checkflag operand anywhere in
   the ROM) AND outside every engine sweep range. The original pick, 0x945, was
   inside DAILY_FLAGS (0x920-0x95F), which ClearDailyFlags() memsets on every
   RTC day rollover -- Character Mode silently switched itself off at midnight
   while VAR_CM_CHAR stayed set. Any replacement must stay clear of the temp
   block (0x000-0x01F, ClearTempFieldEventData) and the daily block. */
#define FLAG_CHARACTER_MODE 0x2B0
#define VAR_CM_CHAR         0x40E4   /* only 2 copyvar-SOURCE refs, none write it */
#define VAR_CM_STARTER      0x40E5   /* adjacent free slot; doubles as give/confirm marker */
#define CM_STARTER_OFF_MARKER 0xFFFF

/* NUM_CHARACTERS and TOBIAS_CHAR_ID are passed in by the injector, derived from
   characters_manifest.json -- never hardcoded here. Both were, and both went
   stale when Volo was inserted on 2026-07-25: TOBIAS_CHAR_ID stayed 182, which
   is now VOLO, so Volo drew Tobias's 1%% legendary-inclusive rate and Tobias's
   Latios fired at 10%%. A stale NUM_CHARACTERS is the worse half of the pair --
   too high and gateActive() TRUSTS an out-of-range index instead of rejecting
   it. */
#ifndef NUM_CHARACTERS
#error "compile with -DNUM_CHARACTERS= (derive it from characters_manifest.json)"
#endif
#ifndef TOBIAS_CHAR_ID
#error "compile with -DTOBIAS_CHAR_ID= (derive it from characters_manifest.json; 0 if absent)"
#endif
#define NUM_SPECIES    1489          /* max ROM species id 1488 + 1 */
#define BITMAP_STRIDE  187
#define CODE_LEN       11
#define MON_SIZE       100

#define MON_DATA_SPECIES 18
#define MON_DATA_IS_EGG  52

/* Naming-screen template ids (expansion enum). */
#define NAMING_SCREEN_CODE 5

/* Confirmed engine functions (Thumb entry: |1). docs/ROUTINE_MAP.md. */
#define FlagSet         ((u8   (*)(u16))                 0x0810D255)
#define FlagClear       ((u8   (*)(u16))                 0x0810D305)
#define FlagGet         ((u8   (*)(u16))                 0x0810D35D)
#define GetVarPointer   ((u16 *(*)(u16))                 0x0810D0C1)
#define GetMonData      ((u32  (*)(void *, int, void *)) 0x081A94AD)
#define GiveMonToPlayer ((u8   (*)(void *))              0x081AA5AD)
#define CopyMonToPC     ((u8   (*)(void *))              0x081AA621)
#define DoNamingScreen  ((void (*)(u8, u8 *, u16, u16, u32, void (*)(void))) 0x08174415)
#define OrigNativeGive  ((void (*)(void *))              0x081F2175)

/* InBattlePyramid() -- gMapHeader(0x0200B04C).mapLayoutId(+0x12) == 361 || 378.
   Disassembled in THIS ROM at 0x0808B034; the body is exactly
       r0 = (layoutId == 361) | (layoutId == 378)
   i.e. LAYOUT_..._BATTLE_PYRAMID_FLOOR and ..._TOP. Byte-for-byte the same
   predicate Lazarus has at 0x0808C264, same two layout ids. Needed by the wild
   override -- see the ⚠️ block in CM_WildMonSpeciesGated. verify_artifacts.py
   pins the signature so this address cannot silently become another predicate. */
#define InBattlePyramid ((u8   (*)(void))                 0x0808B035)

/* Return-to-field callback that ALSO continues the paused (waitstate) script.
 * 0x08179C85 sets gFieldCallback = the continue-script field callback then
 * returns to field -- the exact path ShowEasyChatScreen uses so the original
 * clipboard script resumes. (0x08179AFD returns to field WITHOUT continuing
 * the script -> the script stalls at waitstate and CM_MatchCode never runs.) */
#define CONTINUE_SCRIPT_CB 0x08179C85

/* Confirmed globals. */
#define gPlayerPartyCount (*(volatile u8 *) 0x02019C1D)
#define gPlayerParty      ((u8 *)           0x02019C20)
#define gStringVar2       ((u8 *)           0x0203AF24)
#define RETURN_TO_FIELD_CB ((void (*)(void)) CONTINUE_SCRIPT_CB)

/* gSpecialVar_Result via the special-var table (0x800D). */
#define VAR_RESULT 0x800D

/* Injection-time data placement. */
#ifndef CODES_ADDR
#error "compile with -DCODES_ADDR= -DSTARTERS_ADDR= -DBITMAPS_ADDR= -DDBG_GIVE2_SPECIES="
#endif
#define sCodes    ((const u8 *)  CODES_ADDR)    /* 170 x 11, charmap, 0xFF pad */
#define sStarters ((const u16 *) STARTERS_ADDR) /* 170 x u16 ROM species id    */
#define sBitmaps  ((const u8 *)  BITMAPS_ADDR)  /* 170 x 187 allowed-species   */

#ifndef WILDPOOL_ADDR
#error "compile with -DWILDPOOL_ADDR="
#endif
/* Entries per character. Authoritative value is emit_wildpool.py's POOL_STRIDE,
   published as `pool_stride` in wildpool_manifest.json and passed in by the
   injector. It was hardcoded 104 here and shipped that way after the data moved
   to 176 on 2026-07-23, so every character but #1 indexed 416 B per character
   into a 704 B stride -- a misaligned slice of somebody else's pool, and every
   pool truncated at 104 entries. Nothing caught it: verify_artifacts checked
   the .bin, never the constant the compiler baked in. */
#ifndef WILDPOOL_STRIDE
#error "compile with -DWILDPOOL_STRIDE= (read pool_stride from wildpool_manifest.json)"
#endif
typedef struct { u16 species; u8 minLevel; u8 _pad; } WildPoolEntry;
#define sWildPool ((const WildPoolEntry *) WILDPOOL_ADDR)

/* --- 1%% legendary wild encounters (game_plans/legendary_encounters.md) ---
 * Data from tools/character_mode/emit_legendaries.py. Three arrays, laid out
 * back to back; LEGENDARY_COUNT comes in as -D so the layout cannot drift from
 * the emitter (the WILDPOOL_STRIDE bug shipped for exactly that reason).
 *
 * ⚠️ "Caught" is tracked with one dedicated FLAG per legendary, not with the
 * Pokedex caught bitmap the spec prefers. The dex accessor is not located in
 * this ROM -- four probe strategies failed, all recorded in
 * game_plans/seaglass.md 5b -- and this is the fallback that plan sanctions. It
 * costs 20 bits of save state instead of zero. If the dex is ever found, only
 * caught() below changes.
 *
 * ⚠️ The flags are NOT consecutive: there is no run of 20 free flags anywhere in
 * this ROM (longest is 8), so the flag id is looked up from the table rather
 * than computed as BASE + index. Do not "simplify" that.
 */
#ifndef LEGENDARY_ADDR
#error "compile with -DLEGENDARY_ADDR= -DLEGENDARY_COUNT="
#endif
#ifndef LEGENDARY_COUNT
#error "compile with -DLEGENDARY_COUNT= (from legendaries_manifest.json)"
#endif
#define sLegendaryIds   ((const u16 *) (LEGENDARY_ADDR))
#define sLegendaryFlags ((const u16 *) (LEGENDARY_ADDR + LEGENDARY_COUNT * 2))
#define sCharLegendary  ((const u32 *) (LEGENDARY_ADDR + LEGENDARY_COUNT * 4))

/* Has this legendary already been caught? The single point that would change if
   the Pokedex bitmap is ever located. */
static int caught(int i)
{
    return FlagGet(sLegendaryFlags[i]) != 0;
}

/* Record a catch. Called from the acquisition gate, which every catch and every
   script gift already passes through -- so "offered until caught" needs no new
   hook site. Marks regardless of whether the mon went to the party or the PC:
   it is caught either way. */
static void markCaught(u32 species)
{
    int i;
    for (i = 0; i < LEGENDARY_COUNT; i++) {
        if (sLegendaryIds[i] == species) {
            FlagSet(sLegendaryFlags[i]);
            return;
        }
    }
}

/* Build fingerprint -- the values this translation unit ACTUALLY compiled with,
   parked in the shim blob so a verifier can read them back out of the BUILT ROM
   rather than re-reading the source text or the emitted .bin. That gap is
   exactly what let the two constants above ship wrong. Lives in a .text.*
   section, not .rodata, so it is spliced inside the shim blob at a predictable
   offset instead of wherever ld's default script would page-align a new
   segment. The magic is what verify_artifacts scans for. */
#define CM_FINGERPRINT_MAGIC 0x4D435346u   /* 'FSCM' little-endian */
__attribute__((used, section(".text.cm_fingerprint")))
const u32 CM_BuildFingerprint[5] = {
    CM_FINGERPRINT_MAGIC,
    NUM_CHARACTERS,
    WILDPOOL_STRIDE,
    TOBIAS_CHAR_ID,
    BITMAP_STRIDE,
};

/* --- helpers --- */

/* Charmap case fold: A-Z = 0xBB-0xD4, a-z = 0xD5-0xEE (ROWE charmap). */
static u8 fold(u8 c)
{
    if (c >= 0xD5 && c <= 0xEE)
        return c - 0x1A;
    return c;
}

static int codeEq(const u8 *entered, const u8 *code)
{
    int j;
    for (j = 0; j < CODE_LEN; j++) {
        u8 a = fold(entered[j]);
        u8 b = fold(code[j]);
        if (a != b)
            return 0;
        if (a == 0xFF)
            return 1;
    }
    return 1;
}

static int onRoster(u16 charId, u32 species)
{
    const u8 *bm = sBitmaps + (charId - 1) * BITMAP_STRIDE;
    if (species == 0 || species >= NUM_SPECIES)
        return 1; /* out-of-model species: never block */
    return (bm[species >> 3] >> (species & 7)) & 1;
}

static int gateActive(void)
{
    u16 id;
    if (!FlagGet(FLAG_CHARACTER_MODE))
        return 0;
    id = *GetVarPointer(VAR_CM_CHAR);
    return id >= 1 && id <= NUM_CHARACTERS;
}

/* --- 1. open the CODE naming screen --- */
void CM_OpenCodeEntry(void *ctx)
{
    (void) ctx;
    /* clear the dest so a shorter code can't inherit stale tail bytes */
    {
        int j;
        for (j = 0; j < CODE_LEN; j++)
            gStringVar2[j] = 0xFF;
    }
    DoNamingScreen(NAMING_SCREEN_CODE, gStringVar2, 0, 0, 0, RETURN_TO_FIELD_CB);
}

/* --- 2. match the entered code --- */
/* Debug codes (charmap-encoded "CMDBGOFF", "CMDBGGIVE1", "CMDBGGIVE2"). */
static const u8 sDbgOff[CODE_LEN]   = {0xBD,0xC7,0xBE,0xBC,0xC1,0xC9,0xC0,0xC0,0xFF,0xFF,0xFF};
static const u8 sDbgGive1[CODE_LEN] = {0xBD,0xC7,0xBE,0xBC,0xC1,0xC1,0xC3,0xD0,0xBF,0xA2,0xFF};
static const u8 sDbgGive2[CODE_LEN] = {0xBD,0xC7,0xBE,0xBC,0xC1,0xC1,0xC3,0xD0,0xBF,0xA3,0xFF};

void CM_MatchCode(void *ctx)
{
    u16 i;
    u16 *result = GetVarPointer(VAR_RESULT);
    (void) ctx;

    if (codeEq(gStringVar2, sDbgOff)) {
        FlagClear(FLAG_CHARACTER_MODE);
        *GetVarPointer(VAR_CM_CHAR) = 0;
        *GetVarPointer(VAR_CM_STARTER) = CM_STARTER_OFF_MARKER;
        *result = 2;                 /* script: "Character Mode off" msg */
        return;
    }
    if (codeEq(gStringVar2, sDbgGive1)) {
        u16 id = *GetVarPointer(VAR_CM_CHAR);
        *GetVarPointer(VAR_CM_STARTER) =
            sStarters[(id >= 1 && id <= NUM_CHARACTERS) ? id - 1 : 0];
        *result = 1;
        return;
    }
    if (codeEq(gStringVar2, sDbgGive2)) {
        *GetVarPointer(VAR_CM_STARTER) = DBG_GIVE2_SPECIES;
        *result = 1;
        return;
    }

    for (i = 0; i < NUM_CHARACTERS; i++) {
        if (codeEq(gStringVar2, sCodes + i * CODE_LEN)) {
            *GetVarPointer(VAR_CM_CHAR) = i + 1;
            FlagSet(FLAG_CHARACTER_MODE);
            *GetVarPointer(VAR_CM_STARTER) = sStarters[i];
            *result = 1;             /* script: confirm + give starter */
            return;
        }
    }
    /* no match: clear marker so a stale species can't be re-given */
    *GetVarPointer(VAR_CM_STARTER) = 0;
    *result = 0;                     /* script: "invalid code" msg */
}

/* --- 2c. wild-encounter marker (../../game_plans/rowe_parity.md §3) ---
 *
 * The wild intro names the active character when the Pokemon that appeared is
 * on that character's roster:
 *
 *     Wild GIBLE appeared,
 *     destined for CYNTHIA!
 *
 * WHY. The 10%% override hands out a family ROOT, and a family root is
 * indistinguishable from something the map's own table could have produced.
 * ROWE measured the consequence -- the median selectable character matches
 * ~2%% of the game's own wild slots, so the override is doing nearly all the
 * work of building a team, invisibly -- and Platinum proved the failure mode
 * is real: a playthrough reported as "no on-roster encounters" turned out to
 * have no bug at all. Naming the character was the fix there too. Rates are
 * NOT touched; this is a message and nothing else.
 *
 * HOW. BufferStringBattle picks one of several intro strings into r0 and falls
 * into a single BattleStringExpandPlaceholders(src, dst) call at 0x08086EAA.
 * That one BL is retargeted here; every other battle string passes straight
 * through untouched, because we substitute only when `src` is exactly the
 * wild-intro pointer.
 *
 * ⚠️ DELIBERATE DEVIATION FROM ROWE, and it is a real one. ROWE marks only
 * when the OVERRIDE fired, which it can do because it is a decomp with a byte
 * of RAM to remember that in. This ROM has none -- its legendary feature
 * already had to spend 20 save flags for want of writable RAM -- so the test
 * here is "is the wild mon on the roster", which needs no state at all and is
 * true whether the override or the map's own table produced it. That answers
 * the question the player actually has ("is this one mine to keep?"), and it
 * cannot claim something false. It does mean a natural on-roster encounter is
 * marked too, which ROWE's would not be.
 *
 * The mon's own name still comes from the engine: the strings keep the
 * {FD}{06} B_OPPONENT_MON1_NAME placeholder copied verbatim out of the
 * original, so the expander sees exactly what it always saw.
 *
 * Double battles are left alone on purpose -- two opponents, only one of which
 * could be the roster mon, so a marker would name half a battle. Same call
 * ROWE made. */
#ifndef MARKER_ADDR
#error "compile with -DMARKER_ADDR= (marker_strings.bin injection address)"
#endif
#define MARKER_STRIDE 64
/* "Wild {FD}{06} appeared!{FB}" -- the plain single-wild intro, the only one we
   substitute. Its address is asserted by the injector before the BL is moved. */
#define TEXT_WILD_APPEARED ((const u8 *) 0x084C646C)
#define OrigExpandString ((void (*)(const u8 *, u8 *)) 0x080876DD)
/* gEnemyParty = gPlayerParty + 6 * MON_SIZE, i.e. 0x02019E78 --
   the same address tools/mgba_scripts/harness.lua records as verified. */
#define gEnemyParty (gPlayerParty + 6 * MON_SIZE)

void CM_BattleStringGated(const u8 *src, u8 *dst)
{
    if (src == TEXT_WILD_APPEARED && gateActive()) {
        u16 charId = *GetVarPointer(VAR_CM_CHAR);
        u32 species = GetMonData(gEnemyParty, MON_DATA_SPECIES, 0);

        if (species != 0 && onRoster(charId, species))
            src = (const u8 *) (MARKER_ADDR
                                + (u32) (charId - 1) * MARKER_STRIDE);
    }
    OrigExpandString(src, dst);
}

/* --- 3. acquisition gate --- */
u8 CM_GiveMonToPlayerGated(void *mon)
{
    if (gateActive() && gPlayerPartyCount != 0
     && !GetMonData(mon, MON_DATA_IS_EGG, 0)) {
        u32 species = GetMonData(mon, MON_DATA_SPECIES, 0);
        /* "Offered until caught": retire this legendary from the 1%% roll.
           Done BEFORE the roster branch so it lands whether the mon joins the
           party or is routed to the PC -- it is caught either way. */
        markCaught(species);
        if (!onRoster(*GetVarPointer(VAR_CM_CHAR), species))
            return CopyMonToPC(mon);
    }
    return GiveMonToPlayer(mon);
}

/* --- 4. script-gift (callnative) gate --- */
void CM_NativeGiveGated(void *ctx)
{
    u8 before = gPlayerPartyCount;
    u8 after;

    OrigNativeGive(ctx);

    if (!gateActive())
        return;
    after = gPlayerPartyCount;
    if (after > before && after >= 2) {
        u8 *mon = gPlayerParty + (after - 1) * MON_SIZE;
        if (!GetMonData(mon, MON_DATA_IS_EGG, 0)) {
            u32 species = GetMonData(mon, MON_DATA_SPECIES, 0);
            markCaught(species);           /* script gifts retire it too */
            if (!onRoster(*GetVarPointer(VAR_CM_CHAR), species)
             && CopyMonToPC(mon) == 1) {   /* boxes full -> stays in party */
                int j;
                for (j = 0; j < MON_SIZE; j++)
                    mon[j] = 0;
                gPlayerPartyCount = after - 1;
                *GetVarPointer(VAR_RESULT) = 1; /* "transferred to the PC" tail */
            }
        }
    }
}

/* --- 5. trade gate (sIngameTrades filled in by the injector via -DTRADE_*) --- */
#ifdef TRADE_TABLE_ADDR
#define VAR_0x8004 0x8004
void CM_TradeCheck(void *ctx)
{
    u16 allowed = 1;
    (void) ctx;
    if (gateActive()) {
        u16 idx = *GetVarPointer(VAR_0x8004);
        if (idx < TRADE_COUNT) {
            const u8 *e = (const u8 *) TRADE_TABLE_ADDR + idx * TRADE_STRIDE;
            u16 species = (u16) (e[TRADE_RECV_OFF] | (e[TRADE_RECV_OFF + 1] << 8));
            allowed = onRoster(*GetVarPointer(VAR_CM_CHAR), species) ? 1 : 0;
        }
    }
    *GetVarPointer(VAR_RESULT) = allowed;
}
#endif

/* --- 6. wild encounter species override (task #5) --- */

/* Not the game's own Random() (its address wasn't worth chasing down for a
 * cosmetic 10% roll, and every RE minute here went into finding the actual
 * hook site instead) -- and deliberately NOT a `static` counter either:
 * this shim is linked directly into the ROM image (-Ttext at a ROM
 * address), so a mutable file-scope variable would be a global sitting in
 * *read-only* cartridge space. On real hardware writes to ROM are simply
 * ignored (the value would never actually advance); relying on it would be
 * an emulator-only illusion of persistence. Instead this seeds from the
 * live VCOUNT scanline + button-state hardware registers (both genuinely
 * writable-by-hardware, read-only for us, no RAM budget needed) mixed with
 * the roll's own species+level -- different encounters land on different
 * table slots/levels and fire at slightly different real-time instants, so
 * consecutive rolls still land on different seeds despite there being no
 * carried state. One seed feeds two independent-enough decisions (the 10%
 * gate, then the tie-break pick) via a second constant-multiplier mix step. */
static u32 wildSeed(u16 species, u8 level)
{
    u16 vcount = *(volatile u16 *) 0x04000006;   /* REG_VCOUNT: current scanline */
    u16 keys   = *(volatile u16 *) 0x04000130;   /* REG_KEYINPUT: active-low pad state */
    return (u32) species * 2654435761u + (u32) level * 40503u
         + (u32) vcount * 6151u + (u32) keys;
}

u16 CM_WildMonSpeciesGated(u16 species, u8 level)
{
    u16 charId;
    const WildPoolEntry *e;
    const WildPoolEntry *best;
    const WildPoolEntry *fallback;
    u32 tieCount, pick, seed;
    int i;

    if (!gateActive())
        return species;                    /* CM off: fully inert */

    /* ⚠️ NEVER override inside the Battle Pyramid. Its encounter tables do not
     * store species at all -- they store INDICES. GenerateBattlePyramidWildMon
     * (0x0808AD8C) does
     *     id = GetMonData(&gEnemyParty[0], MON_DATA_SPECIES) - 1;
     *     ... wildMons[id] ...
     * on a 12-byte stride (sizeof(struct PyramidWildMon)) into an 8-entry round
     * table, so a real roster species makes `id` several hundred: it reads
     * kilobytes past the table and writes a garbage species, which then indexes
     * the base-stats and front-anim tables.
     *
     * ⚠️ THIS REPO WAS RECORDED AS CLEAR OF THIS BUG AND WAS NOT. The verdict
     * (docs/ROUTINE_MAP.md:389, ../game_plans/rowe_parity.md §2) rested on "no
     * facility caller is retargeted" -- true, and irrelevant, because the
     * pyramid does not use a facility caller. It reuses the ORDINARY land path,
     * one level above our hook:
     *     0x0822C544  the pyramid branch
     *       -> TryGenerateWildMon  0x0822BFB8
     *          -> CreateWildMon    0x0822BEF0   (contains our retargeted BL
     *                                            0x0822BF36)
     *       -> GenerateBattlePyramidWildMon 0x0808AD8C
     * Measured 2026-08-20 by searching for the (species-1)*12 instruction
     * sequence, which occurs exactly twice in this ROM (0x0808ADD6,
     * 0x0808AEFA) and nowhere else -- so the pyramid is the only table here
     * with index semantics, but it IS reachable. Lazarus had the identical
     * defect and the identical wrong verdict. */
    if (InBattlePyramid())
        return species;
    charId = *GetVarPointer(VAR_CM_CHAR);
    seed = wildSeed(species, level);

    /* --- 1%% legendary roll, BEFORE the ordinary 10%% override ---
     *
     * ⚠️ INDEPENDENCE. This must NOT reuse `seed % 100` the way the override
     * below does. Seaglass has no writable RAM and deliberately avoids the game
     * RNG, so both decisions come from one wildSeed(); testing `seed % 100 < 1`
     * here and `seed % 100 >= 10` below would make the legendary hit a strict
     * SUBSET of the override hit rather than an independent event -- every
     * legendary encounter would also have been a roster override, and the two
     * rates would be silently entangled. The extra mix step below decorrelates
     * them, the same trick the tie-break at the end of this function uses.
     * Constants are distinct from the tie-break's so the two draws do not track
     * each other either.
     *
     * ⚠️ THE DATA CHECK PRECEDES EVERYTHING. Reading the mask first costs
     * nothing for the 117 of 193 characters with no legendary. (The usual
     * reason for this rule -- not consuming a Random() and shifting the game's
     * encounter stream -- does not bite here, because wildSeed() reads hardware
     * registers rather than the engine RNG. Ordering it this way anyway keeps
     * the rule true in every game.) */
    {
        u32 mask = sCharLegendary[charId - 1];
        if (mask) {
            u32 lseed = seed * 2246822519u + 374761393u;
            if (lseed % 100 < 1) {
                u32 avail = 0;
                int n = 0;
                for (i = 0; i < LEGENDARY_COUNT; i++) {
                    if (((mask >> i) & 1) && !caught(i)) {
                        avail |= 1u << i;
                        n++;
                    }
                }
                if (n) {                   /* all caught -> fall through, no reroll */
                    u32 pick2;
                    lseed = lseed * 1664525u + 1013904223u;
                    pick2 = lseed % (u32) n;
                    for (i = 0; i < LEGENDARY_COUNT; i++) {
                        if ((avail >> i) & 1) {
                            if (pick2 == 0)
                                return sLegendaryIds[i];
                            pick2--;
                        }
                    }
                }
            }
        }
    }

    /* Tobias (user spec 2026-07-23): 1%% per roll; everyone else 10%%. His
     * pool is his (legendary) signature Latios via the starter_count slice. */
    if (seed % 100 >= ((charId == TOBIAS_CHAR_ID) ? 1 : 10))
        return species;                    /* miss: leave the normal roll alone */
    e = sWildPool + (charId - 1) * WILDPOOL_STRIDE;

    /* best = the entry whose minLevel is the closest to (and not above) the
     * rolled level -- "pick the stage whose canon level range best fits the
     * rolled level, low level -> early stage, high level -> evolved stage".
     * fallback = the single lowest-minLevel entry in the whole pool, used
     * only if EVERY entry's minLevel is above the roll (nearest-stage
     * fallback for a roster whose pool starts higher than this level). */
    best = 0;
    fallback = 0;
    for (i = 0; i < WILDPOOL_STRIDE; i++) {
        if (e[i].species == 0)
            break;                          /* terminator: end of this char's pool */
        if (!fallback || e[i].minLevel < fallback->minLevel)
            fallback = &e[i];
        if (e[i].minLevel <= level && (!best || e[i].minLevel > best->minLevel))
            best = &e[i];
    }
    if (!best)
        best = fallback;
    if (!best)
        return species;                    /* empty pool (shouldn't happen): never override */

    /* Several members can share the same minLevel (branched evolutions, or
     * several unrelated roster families that happen to line up) -- pick
     * uniformly among the tied entries rather than always the first. */
    tieCount = 0;
    for (i = 0; i < WILDPOOL_STRIDE && e[i].species != 0; i++) {
        if (e[i].minLevel == best->minLevel)
            tieCount++;
    }
    seed = seed * 1103515245u + 12345u;    /* second mix step: an independent-enough draw */
    pick = seed % tieCount;
    for (i = 0; i < WILDPOOL_STRIDE && e[i].species != 0; i++) {
        if (e[i].minLevel == best->minLevel) {
            if (pick == 0)
                return e[i].species;
            pick--;
        }
    }
    return best->species;                  /* unreachable */
}
