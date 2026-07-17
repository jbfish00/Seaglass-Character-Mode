/* Character Mode enforcement shim for Pokemon Emerald Seaglass v3.0.
 *
 * Adapted from Lazarus-Character-Mode/src/character_mode.c (same author/engine).
 * Every fixed address is CONFIRMED for this exact ROM (rom.sha1) — see
 * docs/ROUTINE_MAP.md ("Catch/give enforcement" section, live catch-trace).
 *
 * Placed in the big free block (ROM 0x08ED2164+) and reached from the wild-catch
 * caller (0x080A6A46) via an 8-byte trampoline (that BL is >4 MB from free
 * space; see tools/inject_character_mode.py / docs). The gate itself is
 * position-independent (all engine calls go through absolute pointers).
 *
 * CM_GiveMonToPlayerGated(mon): ROWE/RR acquisition semantics — when Character
 * Mode is ON and the caught mon is a non-egg species NOT on the active
 * character's roster, route it to the PC instead of the party. Otherwise behave
 * exactly like the original GiveMonToPlayer. Returns the same u8 the caller's
 * `cmp r0,#0` expects (party/PC/cant-give).
 *
 * PoC roster: hardcoded to Torchic's evolution line (Nat-Dex ids 255/256/257 —
 * Gen1-3 species id == National Dex number in this ROM, per docs/SPECIES_CAP.md).
 * Real build swaps onRoster() for a per-character allowed-species bitmap lookup
 * (needs a pipeline bitmap-emit step; rosters.bin currently holds base-species
 * lists, not the expanded bitfield Lazarus's rosters_expanded.bin provides).
 */

typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned int   u32;

/* --- CM state IDs (verified unused in this ROM's scripted bytecode) --- */
#define FLAG_CHARACTER_MODE 0x945   /* 0 script refs */
#define VAR_CM_CHAR         0x40E4  /* 0 script refs */

/* --- Confirmed engine functions (Thumb entry: |1). docs/ROUTINE_MAP.md --- */
#define FlagGet         ((u8   (*)(u16))               0x0810D35D)
#define GetVarPointer   ((u16 *(*)(u16))               0x0810D0C1)
#define GetMonData      ((u32  (*)(void *, int, void *)) 0x081A94AD)
#define GiveMonToPlayer ((u8   (*)(void *))            0x081AA5AD)
#define CopyMonToPC     ((u8   (*)(void *))            0x081AA621)

/* --- Confirmed globals --- */
#define gPlayerPartyCount (*(volatile u8 *) 0x02019C1D)

/* --- MON_DATA field ids (SPECIES=18 used throughout GiveMonToPlayer/CopyMonToPC;
 *     IS_EGG=52 confirmed from the script-gift caller's SetMonData) --- */
#define MON_DATA_SPECIES 18
#define MON_DATA_IS_EGG  52

/* Per-character allowed-species bitmap (tools/character_mode/emit_bitmaps.py:
 * rosters_expanded.bin, 170 x 187 bytes, index-aligned with characters.bin;
 * bit S set => species id S catchable/keepable). Placed in free space by the
 * injector; -DBITMAPS_ADDR passes its address. */
#define NUM_CHARACTERS 170
#define NUM_SPECIES    1489   /* max ROM species id 1488 + 1 */
#define BITMAP_STRIDE  187
#ifndef BITMAPS_ADDR
#error "compile with -DBITMAPS_ADDR=<rosters_expanded.bin address>"
#endif
#define sBitmaps ((const u8 *) BITMAPS_ADDR)

static int gateActive(void)
{
    u16 id;
    if (!FlagGet(FLAG_CHARACTER_MODE))
        return 0;
    id = *GetVarPointer(VAR_CM_CHAR);
    return id >= 1 && id <= NUM_CHARACTERS;
}

static int onRoster(u16 charId, u32 species)
{
    const u8 *bm;
    if (species == 0 || species >= NUM_SPECIES)
        return 1;   /* out-of-model species: never block */
    bm = sBitmaps + (charId - 1) * BITMAP_STRIDE;
    return (bm[species >> 3] >> (species & 7)) & 1;
}

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
