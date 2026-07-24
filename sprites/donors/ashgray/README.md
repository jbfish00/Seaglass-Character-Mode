# Ash Gray donor sprites

Ripped from **Pokemon Ash Gray v4.5.3** (FireRed hack by metapod23), built
locally: BPS patch (RetroAchievements RAPatches mirror) applied with flips to
a **byte-matching pret/pokefirered build** (SHA1 `41cb23d8...` vanilla US 1.0)
— no ROM was downloaded. Ripper: `tools/rip_frlg_sprites.py` (vanilla table
addresses from the pokefirered .map); blob extractor:
`tools/extract_ashgray_blobs.py`.

- `*_front.lz` / `*_frontpal.lz` — verbatim LZ77 streams (64x64 4bpp gfx /
  32 B BGR555 palette), byte-copyable into any FRLG/Emerald-family ROM.
- `preview/` — decoded PNGs of the 19 staged front pics.
- `ow_preview/` — identified overworld sprites (Ash walk/bike/fishing sets,
  Jessie, James candidates, Misty, Gary candidate, Nurse Joy, Pikachu
  follower) + Ash's 5-frame back-pic sheet.
- (full 148/6/152 rip lives in RadicalRed-Character-Mode/sprites/donors/ashgray/rip/)
  sheets, 152 OW sprites (this full dump lives only in this repo; siblings
  carry the curated set).
- `manifest.json` — per-blob sizes + provenance.

Credit metapod23 in any distribution that ships this art (see CREDITS.md).
