/* Character Mode mugshot renderer for Pokemon Emerald Seaglass v3.0.
 *
 * 152 character front pics are injected at CM_SPRITE_PTRS_ADDR (an additive
 * blob + pointer table that touches no engine table), but until now nothing
 * read them. These two entry points are called from the confirm script via
 * `callnative` (script command 0x23 — already proven in this ROM: the injector
 * retargets 112 inline callnative give pointers), bracketing the "Character
 * Mode is now active!" message:
 *
 *     delay 2
 *     callnative CM_ShowCharacterMugshot
 *     loadword <msg>; callstd 4      <- blocks until the player presses A
 *     callnative CM_HideCharacterMugshot
 *     ...give the starter, goto the received-mon tail
 *
 * Ported from RadicalRed-Character-Mode/src/character_sprite.c (which proved
 * the technique) and Unbound. Those two are FireRed-family hacks whose low-ROM
 * vanilla region is untouched, so CFRU's BPRE.ld addresses held byte-exact and
 * cost nothing. Lazarus is a full pokeemerald-expansion rebuild: no symbol
 * file, nothing at a stock address, so EVERY address below was mined out of
 * this binary and confirmed by disassembly. Provenance for all of them:
 * docs/ROUTINE_MAP.md, "OAM sprite API"; rederivable with
 * tools/find_sprite_api.py. They are NOT Lazarus's values -- same engine, same
 * author, different build: every single address differs.
 *
 * Separate compile unit from character_mode.c on purpose, and placed in the
 * sprite blobs' own free run rather than the main injection block. That block
 * is the tight one: the 2026-07-25 rebase left only ~126 B of headroom below
 * SCRIPT_ADDR, and SCRIPT_ADDR itself cannot move (naming_open.ss embeds a
 * paused script context pointing at it). Linking here disturbs no existing
 * layout at all.
 *
 * Failure is silent and safe: an out-of-range id, a character with no staged
 * art, or a full OBJ palette all leave the message looking exactly as it did.
 */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed short s16;

#define VAR_CM_CHAR    0x40E4
#define NUM_CHARACTERS 193

/* Supplied by the injector (-DSPRITE_PTRS_ADDR=<CM_SPRITE_PTRS_ADDR>):
 * NUM_CHARACTERS x {u32 gfx, u32 pal} absolute ROM pointers in character-index
 * order, {0,0} where no art is staged. */
#ifndef SPRITE_PTRS_ADDR
#error "compile with -DSPRITE_PTRS_ADDR=0x08xxxxxx"
#endif

#define CM_TILE_TAG    0xC0DE
#define CM_PALETTE_TAG 0xC0DF
#define MUGSHOT_GFX_SIZE 2048   /* 64x64 4bpp, DECOMPRESSED */

/* Sprite position is its CENTRE (CreateSprite applies the centre-to-corner
 * vector itself): upper right, clear of the message box at the bottom. */
#define MUGSHOT_X 192
#define MUGSHOT_Y 48

/* --- engine, all confirmed by disassembly in THIS ROM --- */
#define GetVarPointer ((u16 *(*)(u16)) 0x0810D0C1)

#define LoadCompressedSpriteSheet   ((u16 (*)(const void *)) 0x080F5B5D)
#define LoadCompressedSpritePalette ((u8  (*)(const void *)) 0x080F5C15)
#define CreateSprite  ((u8 (*)(const void *, s16, s16, u8)) 0x08003A39)
#define FreeSpriteTilesByTag   ((void (*)(u16)) 0x08005529)
#define FreeSpritePaletteByTag ((void (*)(u16)) 0x080057FD)

#define gSprites            ((u8 *) 0x02039810)
#define SPRITE_COUNT        64
#define SPRITE_STRIDE       0x44
#define SPRITE_OFF_TEMPLATE 0x14
#define SPRITE_OFF_INUSE    0x3E   /* bit 0 */

#define gDummySpriteAnimTable       ((const void *) 0x08A500CC)
#define gDummySpriteAffineAnimTable ((const void *) 0x08A500D0)
#define SpriteCallbackDummy         ((void (*)(void *)) 0x0800414D)

#define MAX_SPRITES_RETURN 64      /* CreateSprite's "no free slot" return */
#define PALETTE_ALLOC_FAIL 0xFF

struct CompressedSpriteSheet {
    const void *data;
    u16 size;                      /* decompressed */
    u16 tag;
};

struct CompressedSpritePalette {
    const void *data;
    u16 tag;
};

struct SpriteTemplate {
    u16 tileTag;
    u16 paletteTag;
    const void *oam;
    const void *anims;
    const void *images;            /* only read when tileTag == TAG_NONE */
    const void *affineAnims;
    void (*callback)(void *);
};

/* attr0 = 0 (square, 4bpp, normal), attr1 = 0xC000 (size 3 -> 64x64),
 * attr2 = 0 (priority 0; CreateSprite fills tileNum/paletteNum from the tags) */
static const u32 sMugshotOam[2] = { 0xC0000000, 0x00000000 };

static const struct SpriteTemplate sMugshotTemplate = {
    CM_TILE_TAG,
    CM_PALETTE_TAG,
    sMugshotOam,
    gDummySpriteAnimTable,
    0,
    gDummySpriteAffineAnimTable,
    SpriteCallbackDummy,
};

void CM_HideCharacterMugshot(void);

void CM_ShowCharacterMugshot(void)
{
    struct CompressedSpriteSheet sheet;
    struct CompressedSpritePalette pal;
    const u32 *entry;
    u16 id = *GetVarPointer(VAR_CM_CHAR);

    if (id < 1 || id > NUM_CHARACTERS)
        return;

    /* ids are 1-based in the var, 0-based in the table */
    entry = (const u32 *) SPRITE_PTRS_ADDR + (u32) (id - 1) * 2;
    if (entry[0] == 0 || entry[1] == 0)
        return;                    /* no front pic staged for this character */

    /* Never leave a previous mugshot's tags allocated. */
    CM_HideCharacterMugshot();

    pal.data = (const void *) entry[1];
    pal.tag = CM_PALETTE_TAG;
    if (LoadCompressedSpritePalette(&pal) == PALETTE_ALLOC_FAIL)
        return;                    /* all 16 OBJ palette slots in use */

    sheet.data = (const void *) entry[0];
    sheet.size = MUGSHOT_GFX_SIZE;
    sheet.tag = CM_TILE_TAG;
    LoadCompressedSpriteSheet(&sheet);

    if (CreateSprite(&sMugshotTemplate, MUGSHOT_X, MUGSHOT_Y, 0) == MAX_SPRITES_RETURN) {
        FreeSpriteTilesByTag(CM_TILE_TAG);
        FreeSpritePaletteByTag(CM_PALETTE_TAG);
    }
}

void CM_HideCharacterMugshot(void)
{
    u8 *s = gSprites;
    u32 i;

    /* Identify our own sprite by template pointer: needs no save-block var and
     * no scratch RAM, and stays correct if it was never created.
     *
     * Clearing inUse rather than calling DestroySprite is deliberate, not a
     * shortcut around a missing symbol. DestroySprite on a tag-allocated
     * sprite only resets the struct (it frees tiles ONLY for sprites that do
     * not use a sheet), and both AnimateSprites and AddSpritesToOamBuffer skip
     * !inUse slots, so the sprite is gone from OAM on the next frame either
     * way. CreateSpriteAt memsets the whole 0x44 struct when the slot is
     * reused -- confirmed in its own code at 0x08003B4A (`movs r2,#68`) -- so
     * nothing stale can survive. The tag allocations are what actually need
     * releasing, and those are freed explicitly below. */
    for (i = 0; i < SPRITE_COUNT; i++, s += SPRITE_STRIDE) {
        if (!(s[SPRITE_OFF_INUSE] & 1))
            continue;
        if (*(const void **) (s + SPRITE_OFF_TEMPLATE) == (const void *) &sMugshotTemplate)
            s[SPRITE_OFF_INUSE] &= ~1;
    }

    FreeSpriteTilesByTag(CM_TILE_TAG);
    FreeSpritePaletteByTag(CM_PALETTE_TAG);
}
