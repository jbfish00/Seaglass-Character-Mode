/* Character Mode shims for Pokemon Emerald Seaglass v3.0 (by Nemo622).
 *
 * Five entry points, all placed in the big free block (ROM 0x08ED2164+) and
 * reached only through full 32-bit pointers (BG-event ptr, specials-free
 * script pointers, 49 callnative operands) — except the two acquisition BLs,
 * which go through the 8-byte trampoline at 0x08470200. See
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
