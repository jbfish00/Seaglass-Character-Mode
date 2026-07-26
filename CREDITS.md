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
