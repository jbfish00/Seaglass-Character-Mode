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

#define FLAG_CHARACTER_MODE 0x945    /* 0 script refs (audited) */
#define VAR_CM_CHAR         0x40E4   /* only 2 copyvar-SOURCE refs, none write it */
#define VAR_CM_STARTER      0x40E5   /* adjacent free slot; doubles as give/confirm marker */
#define CM_STARTER_OFF_MARKER 0xFFFF

#define NUM_CHARACTERS 170
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
#define WILDPOOL_STRIDE 104   /* entries/char; tools/character_mode/emit_wildpool.py */
typedef struct { u16 species; u8 minLevel; u8 _pad; } WildPoolEntry;
#define sWildPool ((const WildPoolEntry *) WILDPOOL_ADDR)

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

/* --- 3. acquisition gate --- */
u8 CM_GiveMonToPlayerGated(void *mon)
{
    if (gateActive() && gPlayerPartyCount != 0
     && !GetMonData(mon, MON_DATA_IS_EGG, 0)) {
        u32 species = GetMonData(mon, MON_DATA_SPECIES, 0);
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
    seed = wildSeed(species, level);
    if (seed % 100 >= 10)
        return species;                    /* 90%: leave the normal roll alone */

    charId = *GetVarPointer(VAR_CM_CHAR);
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
