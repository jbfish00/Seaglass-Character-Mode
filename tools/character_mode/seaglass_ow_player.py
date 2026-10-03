#!/usr/bin/env python3
"""The player's walk/run sprite follows the chosen character (2026-10-03).

Radical Red's behaviour (../game_plans/overworld_sprites.md): with Character
Mode on, the character's own sprite is used walking and running; bike, surf,
fishing, field moves and underwater keep the stock player. No NPC or opponent
sprite changes, and with the mode off nothing changes.

How, all measured on the base ROM and asserted before anything is written:

  * the player's on-foot graphics ids come from sPlayerAvatarGfxIds
    (0x085F24E4, a u8 [state][gender] table: Brendan 0, May 89), which GCC
    inlined into 14 readers. Rather than touch those, the ONE function that
    turns an id into graphics, GetObjectEventGraphicsInfo (0x0811059C, the
    only reader of gObjectEventGraphicsInfoPointers 0x085CE6BC, 39 callers),
    gets an entry trampoline (src/ow_sprite.c): for ids 0 and 89, with the
    mode on and a sprite for the character, it returns that character's
    graphics info; otherwise it replays the 8 overwritten bytes and resumes
    the original. Map objects never use 0 or 89 as real NPCs (the 34 map
    objects with id 0 are all OBJ_KIND_CLONE placeholders; scanned
    2026-10-03), so only the player is affected.
  * an info is the May walk struct (id 89: player anims 0x085D0F98, the
    player's palette slot) with size, oam and subsprites for the sheet's
    frame size (16x32: 0x085D1234 / 0x085D12C0; 32x32: 0x085D123C /
    0x085D1314), its own palette tag (also its reflection tag) and its own
    18-frame image table. The run anims (20-23) use pokeemerald's frame order,
    which is the sheets' order, so no remap.
  * palettes are found by tag in sObjectEventSpritePalettes (0x085D4234, 63
    entries, 0x11FF terminator), read through 12 literals. It is copied, our
    tags 0x1400 + k appended before the terminator, and all 12 repointed.
  * Brendan and May (characters) use Seaglass's own player infos for ids 0 and
    89: full player sprites with run frames. Red and Leaf have only one-frame
    NPC sprites here (ids 230/231), so they keep the stock player.

Everything lives in Character Mode's own free block (OW_REGIONS).
"""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHEETS = ROOT / "sprites" / "ow_player"
CHAR_MANIFEST = ROOT / "tools" / "character_mode" / "characters_manifest.json"

ROM_BASE = 0x08000000
GET_INFO = 0x0811059C                      # GetObjectEventGraphicsInfo
GET_INFO_ORIG = bytes.fromhex("3a4a94460304180c")   # ldr r2,[pc,#232]; mov ip,r2; lsls r3,r0,#16; lsrs r0,r3,#16
GET_INFO_LIT = 0x08110688                  # the ldr's literal (0xFF060000)
INFO_TABLE = 0x085CE6BC                    # gObjectEventGraphicsInfoPointers
SET_GFX_ID = 0x08110268                    # ObjectEventSetGraphicsId(objEvent, u16 id)
SET_GFX_ID_ORIG = bytes.fromhex("30b50c04240c0500")
G_PLAYER_AVATAR = 0x0202588C
G_OBJECT_EVENTS = 0x0200564C
AVATAR_TABLE = 0x085F24E4
PLAYER_GFX = (0, 89)                       # sPlayerAvatarGfxIds[NORMAL][gender]
PLAYER_ANIMS = 0x085D0F98
OAM_SUB = {(16, 32): (0x085D1234, 0x085D12C0), (32, 32): (0x085D123C, 0x085D1314)}
PAL_TABLE = 0x085D4234
PAL_TABLE_ENTRIES = 63
PAL_TABLE_REFS = (0x0810F038, 0x081100F8, 0x08110260, 0x08110528, 0x081108B4,
                  0x0811096C, 0x081109E4, 0x08110A24, 0x08110AD4, 0x08110B98,
                  0x08111698, 0x0811DB14)
PAL_TAG_NONE = 0x11FF
PAL_TAG_BASE = 0x1400
INFO_SIZE = 0x24
NATIVE = {"Brendan": 0, "May": 89}         # characters drawn with Seaglass's own player infos
FLAG_CHARACTER_MODE = 0x2B0
VAR_CM_CHAR = 0x40E4
OW_CODE_ADDR = 0x08FB0000                  # src/ow_sprite.c
OW_CODE_MAX = 0x400
OW_REGIONS = ((0x08FB0400, 0x09000000), (0x08F61000, 0x08FA0000))


def R(a):
    return a - ROM_BASE


def sheets():
    return json.loads((SHEETS / "manifest.json").read_text())["characters"]


def info_ptr(rom, gid):
    return struct.unpack_from("<I", rom, R(INFO_TABLE) + 4 * gid)[0]


def pal_entries(rom):
    return [struct.unpack_from("<IH", rom, R(PAL_TABLE) + 8 * i) for i in range(PAL_TABLE_ENTRIES + 1)]


def check_engine(rom):
    assert rom[R(GET_INFO):R(GET_INFO) + 8] == GET_INFO_ORIG, "GetObjectEventGraphicsInfo moved"
    assert struct.unpack_from("<I", rom, R(GET_INFO_LIT))[0] == 0xFF060000
    assert rom[R(SET_GFX_ID):R(SET_GFX_ID) + 8] == SET_GFX_ID_ORIG, "ObjectEventSetGraphicsId moved"
    refs = [o for o in range(0, len(rom) - 3, 4)
            if struct.unpack_from("<I", rom, o)[0] == INFO_TABLE]
    assert refs == [0x110694], [hex(r) for r in refs]
    assert tuple(rom[R(AVATAR_TABLE):R(AVATAR_TABLE) + 2]) == PLAYER_GFX
    pals = pal_entries(rom)
    assert pals[-1][1] == PAL_TAG_NONE and all(t != PAL_TAG_NONE for _, t in pals[:-1])
    for ref in PAL_TABLE_REFS:
        assert struct.unpack_from("<I", rom, R(ref))[0] == PAL_TABLE, hex(ref)
    refs = sorted(o + ROM_BASE for o in range(0, len(rom) - 3, 4)
                  if struct.unpack_from("<I", rom, o)[0] == PAL_TABLE)
    assert tuple(refs) == PAL_TABLE_REFS, [hex(r) for r in refs]
    may = rom[R(info_ptr(rom, 89)):R(info_ptr(rom, 89)) + INFO_SIZE]
    assert struct.unpack_from("<Hhh", may, 6) == (512, 32, 32)
    assert struct.unpack_from("<III", may, 0x10) == OAM_SUB[(32, 32)] + (PLAYER_ANIMS,)
    for (w, h), (oam, sub) in OAM_SUB.items():
        assert any(struct.unpack_from("<hh", rom, R(info_ptr(rom, g)) + 8) == (w, h)
                   and struct.unpack_from("<II", rom, R(info_ptr(rom, g)) + 0x10) == (oam, sub)
                   for g in range(200)), (w, h)


class Allocator:
    def __init__(self, rom, regions):
        self.pieces = [[R(s), R(e)] for s, e in regions]
        self.rom = rom

    def alloc(self, size, align=4):
        for p in self.pieces:
            s = (p[0] + align - 1) & ~(align - 1)
            if s + size <= p[1]:
                assert all(b == 0xFF for b in self.rom[s:s + size]), f"{s:#x} not free"
                p[0] = s + size
                return s
        raise RuntimeError(f"overworld data: out of space for {size} B")


def build(rom, characters):
    """Plan every write. Returns (writes, word_patches, info_table_addr,
    info_ptrs, sources): writes [(file off, bytes)], word_patches
    [(file off, old, new)], the ROM address of the u32[len(characters)]
    info-pointer table (0 = keep the stock sprite), its contents, and
    {name: "sheet" | "native"}."""
    check_engine(rom)
    have = sheets()
    pals = pal_entries(rom)
    used_tags = {t for _, t in pals}
    may = bytearray(rom[R(info_ptr(rom, 89)):R(info_ptr(rom, 89)) + INFO_SIZE])
    alloc = Allocator(rom, OW_REGIONS)
    writes, patches = [], []

    names = [c["character"] for c in characters]
    sheet_names = [n for c, n in zip(characters, names)
                   if not c.get("hidden") and n not in NATIVE and n in have]
    assert all(PAL_TAG_BASE + k not in used_tags for k in range(len(sheet_names)))

    pal_table = bytearray((len(pals) + len(sheet_names)) * 8)
    for i, (p, tag) in enumerate(pals[:-1]):
        struct.pack_into("<IHH", pal_table, i * 8, p, tag, 0)
    pal_table_off = alloc.alloc(len(pal_table))

    frame_at, infos, sources = {}, {}, {}
    for k, name in enumerate(sheet_names):
        e = have[name]
        w, h = e["width"], e["height"]
        fb = w * h // 2
        gfx = (SHEETS / f"{e['stem']}.4bpp").read_bytes()
        assert len(gfx) == 18 * fb, (name, len(gfx))
        images = bytearray()
        for f in range(18):
            fr = gfx[f * fb:(f + 1) * fb]
            if fr not in frame_at:
                frame_at[fr] = alloc.alloc(fb)
                writes.append((frame_at[fr], fr))
            images += struct.pack("<IHH", ROM_BASE + frame_at[fr], fb, 0)
        pal = (SHEETS / f"{e['stem']}.gbapal").read_bytes()
        assert len(pal) == 32, name
        pal_off = alloc.alloc(32)
        writes.append((pal_off, pal))
        tag = PAL_TAG_BASE + k
        struct.pack_into("<IHH", pal_table, (len(pals) - 1 + k) * 8, ROM_BASE + pal_off, tag, 0)
        images_off = alloc.alloc(len(images))
        writes.append((images_off, bytes(images)))
        info = bytearray(may)
        oam, sub = OAM_SUB[(w, h)]
        struct.pack_into("<HHHhh", info, 2, tag, tag, fb, w, h)
        struct.pack_into("<II", info, 0x10, oam, sub)
        struct.pack_into("<I", info, 0x1C, ROM_BASE + images_off)
        info_off = alloc.alloc(INFO_SIZE)
        writes.append((info_off, bytes(info)))
        infos[name], sources[name] = ROM_BASE + info_off, "sheet"
    struct.pack_into("<IHH", pal_table, (len(pals) - 1 + len(sheet_names)) * 8,
                     pals[-1][0], PAL_TAG_NONE, 0)
    writes.append((pal_table_off, bytes(pal_table)))
    for ref in PAL_TABLE_REFS:
        patches.append((R(ref), PAL_TABLE, ROM_BASE + pal_table_off))

    for c, name in zip(characters, names):
        if name in NATIVE and not c.get("hidden"):
            infos[name], sources[name] = info_ptr(rom, NATIVE[name]), "native"
    ptrs = [0 if c.get("hidden") else infos.get(n, 0) for c, n in zip(characters, names)]
    table = struct.pack(f"<{len(ptrs)}I", *ptrs)
    table_off = alloc.alloc(len(table))
    writes.append((table_off, table))
    return writes, patches, ROM_BASE + table_off, ptrs, sources


if __name__ == "__main__":
    rom = (ROOT / "rom" / "seaglass v3.0.gba").read_bytes()
    chars = json.loads(CHAR_MANIFEST.read_text())["characters"]
    writes, patches, table, ptrs, sources = build(rom, chars)
    print(f"{sum(1 for v in sources.values() if v == 'sheet')} sheets, "
          f"{sum(1 for v in sources.values() if v == 'native')} native; "
          f"{sum(len(b) for _, b in writes):,} B in {len(writes)} writes; table @ {table:#x}")
