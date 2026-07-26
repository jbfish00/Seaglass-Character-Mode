# Credits

## Donor art

- **Pokemon Ash Gray** (FireRed hack) by **metapod23** — anime-character
  trainer sprites (Jessie & James duo, Ritchie, Tracey, Duplica, Todd,
  Giselle, A.J., Otoshi, Samurai, Damian, Gary, Orange Islands leaders
  Cissy/Danny/Rudy, Jessiebelle, anime-style Brock/Misty/Oak/Giovanni) and
  Ash player art (overworld sets + back sprite). Ripped from a locally-built
  copy (BPS patch applied to a source-built clean FireRed). Non-commercial,
  patch-only distribution, with credit — per ROM-hacking community norms.
- Character Pokemon rosters compiled from **Bulbapedia**
  (https://bulbapedia.bulbagarden.net), CC BY-NC-SA.

(When ROWE-tree donor art is eventually shipped here, carry over ROWE's
`CREDITS_CHARACTER_MODE.md` donor list: pret/pokefirered,
sinnoh-remakes/pokeemerald-platinum, PokemonHnS-Development/pokemonHnS,
DiegoWT's Gen5-style resource, StreakOfSprites' Ash sheet.)


## Emerald Rogue — trainer, back and overworld sprites (added 2026-07-25)

Staged in `sprites/donors/rogue/` — 294 sprites covering 160 Character Mode
characters (149 trainer front pics, 133 overworld sheets, 12 battle back pics),
filtered from a 531-file harvest down to characters actually on the roster.

- **Source**: https://github.com/Pokabbie/pokeemerald-rogue, branch `vanilla`,
  commit `79c1df5f8a2ebb423c7a48d29de0cf21ef5783e7`, fetched 2026-07-25.
- **Format**: converted from the repo's PNGs by `tools/png_to_gba.py` into
  `.4bpp` + `.gbapal` and LZ77 (BIOS type 0x10) streams of each. Every blob was
  round-tripped through the decompressor before staging.
- **Licensing**: the repository has **no LICENSE file**. Its in-game credits
  roll is the only attribution trail that exists, and it maps no artist to any
  individual file — so the **whole list travels with any subset of the art**.

**"Additional Sprites" — Emerald Rogue credits roll, reproduced in full:**

AveonTrainer · PurpleZaffre · UlithiumDragon · HighNoonMoon · xDracolich ·
ZacWeavile · Gnomowladny · Beliot419 · Brumirage · Kyledove · Kymotionian ·
cSc-A7X · 2and2makes5 · Pokegirl4ever · Fernandojl · Silver-Skie · Kid1513 ·
TyranitarDark · Getsuei-H · Milomilotic11 · Kyt666 · kdiamo11 · Chocosrawloid ·
SyleDude · Gallanty · Gizamimi-Pichu · princess-phoenix · LunarDusk6 ·
Larryturbo · Kidkatt · Zender1752 · SageDeoxys · Lasee0 · Ezerart · Wolfang62 ·
DarkusShadow · Anarlaurendil · Lasse00 · shaderr31 · CarmaNekko · EduarPokeN ·
TintjeMadelintje101

Plus the Emerald Rogue project itself (Pokabbie) for assembling and converting
the set.


## Team Aqua's Asset Repo, pokemonHnS, pokeemerald-platinum (added 2026-07-25)

Three more donor sets staged alongside `rogue/`, converted by
`tools/png_to_gba.py` and filtered to characters on the Character Mode roster.

### `sprites/donors/taar/` — 251 sprites, 92 characters
- **Source**: https://github.com/TeamAquasHideout/Team-Aquas-Asset-Repo, branch
  `main`, commit `36b619ecd1d2df95212b375c95803af78414f78a`, fetched 2026-07-25.
- **Licence** (repo README, verbatim): *"This is a collection of free to use
  assets that are intended to be used for Generation 3 Pokémon decomp hacking...
  All assets are both free to use and edit by default, but if any assets
  specifically mention not being free to edit, please respect the author's
  wishes... provided they are submitted alongside credit to their original
  creator."*
- **Attribution is per-author and mandatory.** The second path element of every
  upstream file IS the author — `Trainer Back Sprites/yoshord/…` is yoshord's
  work. `harvest_index.json` in the staged directory preserves each file's
  original path, so the author is always recoverable. Named contributors whose
  work is staged here include **yoshord** (Lance back, 64x384 six-frame — his
  README ships the matching `sAnimCmd_Lance_Back[]`), **ShinyDragonHunter**
  (Blue/Gary back, 64x320), **spilledpizza** (Prof. Rowan overworld, Cynthia
  mugshot), **Phantomony** (Archie mugshot), **mudskip** (Phoebe back),
  **Kalarie** (anime front pics), **Ringloom** (HGSS Lyra), **kwenio**, **Lhea**,
  **KyuZee**, **hyo**, **Solo993**.
- Aggregate folders re-credit upstream creators per subfolder — read the
  author's own README before shipping any single sprite.

### `sprites/donors/hns/` — 41 sprites, 30 characters
- **Source**: https://github.com/PokemonHnS-Development/pokemonHnS, branch
  `main`, commit `751823abaf677020bcd72c45fe3e7cb2b8a576e4`.
- HGSS-style 64x64 front pics; covers **Lance, Blue, Misty, Brock**, Red, Karen,
  Clair, Giovanni, Sabrina and the Johto/Kanto leaders and Elite Four.
- **Licence**: no LICENSE file. README, verbatim: *"it's also completely open
  source, and is intended to be a base for a new generation of Johto rom
  hacks"* / *"If you'd like to improve, expand upon, or make your own version of
  HnS, feel free to take advantage of the open source!"*
- **Sprite credit** (flat, no per-file attribution available):
  **Cesare_CBass, AveonTrainer, PurpleZaffre, BatimaTheBat**.

### `sprites/donors/platinum/` — 49 sprites, 36 characters
- **Source**: https://github.com/sinnoh-remakes/pokeemerald-platinum, branch
  `master`, commit `09091ed1d8c07c3353608ac91603ac59ab41fc70`.
- Covers **Cynthia**, **Cyrus**, Dawn, Lucas, Barry, Bertha, Lucian, Volkner,
  Candice, Maylene, Fantina, Roark, Byron, Crasher Wake, Mars/Jupiter/Saturn.
- **⚠️ Weakest attribution of the three.** No LICENSE, no asset licence, and no
  per-sprite attribution at all; the README is the inherited RHH one
  (*"If you use pokeemerald-expansion, please credit RHH (Rom Hacking
  Hideout)."*). It is a fan remake, so some art may be third-party redistributed
  without individual credit. **Prefer the TAAR version of a character where one
  exists with a named author**, and treat this set as the fallback for the
  Sinnoh cast.
