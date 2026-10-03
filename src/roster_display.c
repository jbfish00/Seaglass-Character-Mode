/* Character Mode in-game roster display for Pokemon Emerald Seaglass v3.0.
 *
 * ../../game_plans/roster_display.md is the runbook. A read-only list of the
 * ACTIVE character's roster, one row per family ROOT, name + bordered icon.
 *
 * The list itself is the engine's own dynamic multichoice: a script calls
 * CM_RosterPushRows, then `dynmultistack ... callbacks=2`. This file supplies
 * the rows and callback set 2, which the injector writes into slot [2] of the
 * RELOCATED sDynamicListMenuEventCollections (DYN_EVENT_TABLE_ADDR). NONE is
 * 0xFF in this ROM, so 2 is a real set (verify_artifacts [20]).
 *
 * Set 2 is modelled on the ROM's own set 1 (MultichoiceDynamicEventShowItem,
 * 0x081EFC01 / 0x081EFC7D / 0x081EFD25), decoded instruction by instruction:
 * the same auxiliary framed window beside the list, the same scratchpad slots
 * for state, and a MON icon where set 1 draws an item icon. Every address
 * below was read out of set 1's own calls or the icon trace
 * (docs/ROUTINE_MAP.md, "Mon icons" and "Dynamic multichoice").
 *
 * ⭐ NO WRITABLE STATICS: this code runs from ROM. State lives in the engine's
 * sDynamicMenuEventScratchPad (100 x u16, AllocZeroed before OnInit and freed
 * after OnDestroy for ANY callback set; its pointer is at 0x0201D230), exactly
 * as set 1 keeps its window and sprite ids there.
 *
 * ⭐ Rows carry the SPECIES as their id (the stack form keeps the pushed id;
 * the script-pointer form would overwrite it with the row index), so
 * OnSelectionChanged's selectedItem is the species directly -- which is also
 * what moveCursorFunc passes: the item's ID, not its index.
 */

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed short s16;
typedef signed int s32;

#define VAR_CM_CHAR   0x40E4
#define VAR_RESULT    0x800D

#ifndef NUM_CHARACTERS
#error "compile with -DNUM_CHARACTERS=<from characters_manifest.json>"
#endif
#ifndef ROSTER_ROOTS_ADDR
#error "compile with -DROSTER_ROOTS_ADDR=0x08xxxxxx"
#endif
#ifndef ROSTER_ROOTS_OFF
#error "compile with -DROSTER_ROOTS_OFF=<roots_offset_bytes from the manifest>"
#endif
#if !defined(ROSTER_NAMES_ADDR) || !defined(ROSTER_NAME_STRIDE)
#error "compile with -DROSTER_NAMES_ADDR=0x08xxxxxx -DROSTER_NAME_STRIDE=<n>"
#endif

/* gSpeciesInfo 0x088F0780; the name is at +44 (rom_species_table.json's
 * "table base" 0x8F07AC is this field, not the struct). */
#define SPECIES_NAME(s) ((const u8 *) (0x088F07AC + (u32) (s) * 208))
#define NAME_ALLOC 16            /* longest name is 11 chars + 0xFF */
#define EOS 0xFF

/* --- engine: script vars, heap, dynamic multichoice --- */
#define GetVarPointer ((u16 *(*)(u16)) 0x0810D0C1)
#define Alloc         ((void *(*)(u32, u32)) 0x080033D9)   /* (size, 0), as ScrCmd_dynmultipush calls it */
/* struct ListMenuItem {name, id} passed by value: name in r0, id in r1 */
#define MultichoiceDynamic_PushElement ((void (*)(const u8 *, s32)) 0x081EFE85)
#define sDynamicMenuEventScratchPad (*(u16 **) 0x0201D230)

/* --- engine: windows (from set 1's OnInit / OnDestroy) --- */
#define gWindows ((const u8 *) 0x0203B9C0)   /* 12 B each: WindowTemplate + tileData */
#define AddWindow                    ((u16 (*)(const void *)) 0x08008BDD)
#define RemoveWindow                 ((void (*)(u8)) 0x08008DB5)
#define SetStandardWindowBorderStyle ((void (*)(u8, u8)) 0x08166BC9)
#define ClearStdWindowAndFrame       ((void (*)(u8, u8)) 0x08166801)
#define FillWindowPixelBuffer        ((void (*)(u8, u8)) 0x0800939D)
#define CopyWindowToVram             ((void (*)(u8, u8)) 0x08008EAD)
/* (windowId, fontId, str, x, y, speed, callback). Located 2026-10-02 from the
 * PC multichoice's "LOG OFF" print (BL at 0x081F0A9E, string literal pool
 * 0x081F0AE0); its body reads the gFonts pointer at stride 12. 381 callers. */
#define AddTextPrinterParameterized \
    ((u16 (*)(u8, u8, const u8 *, u8, u8, u8, void *)) 0x08006415)
#define FONT_NORMAL 1
#define COPYWIN_FULL 3
#define PIXEL_FILL_1 0x11

/* --- engine: mon icons (live-traced from the party menu) --- */
#define CreateMonIcon ((u8 (*)(u16, void *, s16, s16, u8, u32)) 0x081B5CE5)
#define SpriteCB_MonIcon ((void *) 0x081B61BD)
#define FreeAndDestroyMonIconSprite ((void (*)(void *)) 0x081B5FE9)
#define LoadMonIconPalette ((void (*)(u16)) 0x081B6079)
#define FreeMonIconPalette ((void (*)(u16)) 0x081B618D)
#define gSprites ((u8 *) 0x02039810)
#define SPRITE_STRIDE 0x44
#define MAX_SPRITES 64               /* "no sprite": CreateSprite's full return, set 1's sentinel */

/* Scratchpad slots. [0]/[1] are the same meaning set 1 gives them. */
#define PAD_AUX_WINDOW 0
#define PAD_SPRITE     1
#define PAD_SPECIES    2             /* the species whose icon palette we hold */
#define PAD_HEADER     3             /* the "<name>'s roster" header window */

/* The icon box: 4x4 tiles, two tiles right of the list, like set 1's. The
 * sprite is centred in it, raised 4 px because icon art is bottom-weighted in
 * its 32x32 frame (ROWE measured this off the rendered screen). */
#define AUX_GAP   2
#define AUX_SIZE  4
#define AUX_PAL   15
#define ICON_RAISE 4

/* The header: two lines, "<name>'s roster" then sText_Hint (user ruling
 * 2026-10-02: the list is family roots only while every stage is allowed, so
 * say so). Rows 1-4, frame 0-5; the script opens the list at top 6, i.e. rows
 * 7-18 with frame 6-19, so the two fill the 20-row screen exactly. */
#define HEADER_LEFT   1
#define HEADER_TOP    1
#define HEADER_WIDTH  18
#define HEADER_HEIGHT 4

/* "'s roster" and "Evolutions count too." in the game charmap */
static const u8 sText_Suffix[] = { 0xB4, 0xE7, 0x00, 0xE6, 0xE3, 0xE7, 0xE8, 0xD9, 0xE6, EOS };
static const u8 sText_Hint[] = { 0xBF, 0xEA, 0xE3, 0xE0, 0xE9, 0xE8, 0xDD, 0xE3, 0xE2, 0xE7, 0x00,
                                 0xD7, 0xE3, 0xE9, 0xE2, 0xE8, 0x00, 0xE8, 0xE3, 0xE3, 0xAD, EOS };

struct WindowTemplate {
    u8 bg, tilemapLeft, tilemapTop, width, height, paletteNum;
    u16 baseBlock;
};

struct DynamicListMenuEventArgs {
    const void *list;
    u16 selectedItem;
    u8 windowId;
};

static const struct WindowTemplate *ListWindow(const struct DynamicListMenuEventArgs *a)
{
    return (const struct WindowTemplate *) (gWindows + a->windowId * 12);
}

/* callnative: push one row per family root of the active character, name +
 * species id. VAR_RESULT = the number of rows, so the script can skip the
 * menu entirely on 0 (dynmultistack on an empty stack would draw nothing). */
void CM_RosterPushRows(void)
{
    u16 *result = GetVarPointer(VAR_RESULT);
    u16 id = *GetVarPointer(VAR_CM_CHAR);
    const u16 *entry, *roots;
    u32 i, n;

    *result = 0;
    if (id < 1 || id > NUM_CHARACTERS)
        return;
    entry = (const u16 *) ROSTER_ROOTS_ADDR + (u32) (id - 1) * 2;
    roots = (const u16 *) (ROSTER_ROOTS_ADDR + ROSTER_ROOTS_OFF) + entry[0];
    n = entry[1];

    for (i = 0; i < n; i++) {
        /* Heap-allocated: the engine Free()s every row name when the list
         * closes (FreeListMenuItems), so a ROM pointer here would be freed. */
        u8 *buf = Alloc(NAME_ALLOC, 0);
        const u8 *src = SPECIES_NAME(roots[i]);
        u32 k;
        if (buf == 0)
            break;
        for (k = 0; k < NAME_ALLOC - 1 && src[k] != EOS; k++)
            buf[k] = src[k];
        buf[k] = EOS;
        MultichoiceDynamic_PushElement(buf, roots[i]);
        (*result)++;
    }
}

static void DestroyIcon(u16 *pad)
{
    if (pad[PAD_SPRITE] != MAX_SPRITES) {
        FreeAndDestroyMonIconSprite(gSprites + pad[PAD_SPRITE] * SPRITE_STRIDE);
        FreeMonIconPalette(pad[PAD_SPECIES]);
        pad[PAD_SPRITE] = MAX_SPRITES;
    }
}

/* VAR_CM_CHAR is 1-based and was range-checked by CM_RosterPushRows, which
 * runs first and leaves no rows (so no menu) for an out-of-range id. */
static void DrawHeader(u8 win)
{
    u16 id = *GetVarPointer(VAR_CM_CHAR);
    const u8 *name = (const u8 *) ROSTER_NAMES_ADDR + (u32) (id - 1) * ROSTER_NAME_STRIDE;
    u8 buf[ROSTER_NAME_STRIDE + sizeof(sText_Suffix)];
    u32 n = 0, k;

    if (id >= 1 && id <= NUM_CHARACTERS)
        while (n < ROSTER_NAME_STRIDE - 1 && name[n] != EOS) {
            buf[n] = name[n];
            n++;
        }
    for (k = 0; k < sizeof(sText_Suffix); k++)
        buf[n + k] = sText_Suffix[k];
    AddTextPrinterParameterized(win, FONT_NORMAL, buf, 0, 1, 0, 0);
    AddTextPrinterParameterized(win, FONT_NORMAL, sText_Hint, 0, 16, 0, 0);
}

void CM_RosterMenu_OnInit(struct DynamicListMenuEventArgs *a)
{
    const struct WindowTemplate *w = ListWindow(a);
    struct WindowTemplate aux;
    u16 *pad = sDynamicMenuEventScratchPad;
    u8 win;

    aux.bg = 0;
    aux.tilemapLeft = w->tilemapLeft + w->width + AUX_GAP;
    aux.tilemapTop = w->tilemapTop;
    aux.width = AUX_SIZE;
    aux.height = AUX_SIZE;
    aux.paletteNum = AUX_PAL;
    aux.baseBlock = w->baseBlock + w->width * w->height;
    win = AddWindow(&aux);
    SetStandardWindowBorderStyle(win, 0);
    FillWindowPixelBuffer(win, PIXEL_FILL_1);
    CopyWindowToVram(win, COPYWIN_FULL);

    pad[PAD_AUX_WINDOW] = win;
    pad[PAD_SPRITE] = MAX_SPRITES;

    /* The header window's tiles follow the icon box's. */
    aux.tilemapLeft = HEADER_LEFT;
    aux.tilemapTop = HEADER_TOP;
    aux.baseBlock += AUX_SIZE * AUX_SIZE;
    aux.width = HEADER_WIDTH;
    aux.height = HEADER_HEIGHT;
    win = AddWindow(&aux);
    SetStandardWindowBorderStyle(win, 0);
    FillWindowPixelBuffer(win, PIXEL_FILL_1);
    DrawHeader(win);
    CopyWindowToVram(win, COPYWIN_FULL);
    pad[PAD_HEADER] = win;
}

void CM_RosterMenu_OnSelectionChanged(struct DynamicListMenuEventArgs *a)
{
    const struct WindowTemplate *w = ListWindow(a);
    u16 *pad = sDynamicMenuEventScratchPad;
    u16 species = a->selectedItem;
    s16 x = (w->tilemapLeft + w->width + AUX_GAP) * 8 + AUX_SIZE * 4;
    s16 y = w->tilemapTop * 8 + AUX_SIZE * 4 - ICON_RAISE;
    u8 id;

    DestroyIcon(pad);
    LoadMonIconPalette(species);
    id = CreateMonIcon(species, SpriteCB_MonIcon, x, y, 0, 0);
    if (id >= MAX_SPRITES) {
        FreeMonIconPalette(species);
        return;
    }
    /* Above the window layer, as set 1 does for its item icon: clear
     * oam.priority (attr2 bits 10-11 = bits 2-3 of byte 5). */
    gSprites[id * SPRITE_STRIDE + 5] &= ~0x0C;
    pad[PAD_SPRITE] = id;
    pad[PAD_SPECIES] = species;
}

void CM_RosterMenu_OnDestroy(struct DynamicListMenuEventArgs *a)
{
    u16 *pad = sDynamicMenuEventScratchPad;
    (void) a;
    DestroyIcon(pad);
    ClearStdWindowAndFrame(pad[PAD_AUX_WINDOW], 1);
    RemoveWindow(pad[PAD_AUX_WINDOW]);
    ClearStdWindowAndFrame(pad[PAD_HEADER], 1);
    RemoveWindow(pad[PAD_HEADER]);
}
