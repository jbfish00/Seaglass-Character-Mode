# Pokemon Emerald Seaglass — Character Mode

An optional add-on patch for **Pokemon Emerald Seaglass v3.0** (by Nemo622)
that adds **Character Mode**: pick one iconic Pokemon character and play
restricted to *their* canonical roster — you can only keep Pokemon from that
character's Bulbapedia-documented team (full evolution families included).
Anything off-roster you catch, are gifted, or trade for is automatically sent
to your PC instead of your party.

This is a fan project distributed **only as a patch**. You must supply your own
legally-obtained Seaglass v3.0 ROM.

## ▶️ How to turn Character Mode on

> **Character Mode is opt-in. Nothing in the game changes until you do this.**

**There are two places you can do it. The bedroom one is available immediately.**

### A. The CHEAT DEVICE in your bedroom ← easiest

1. In your **bedroom** (upstairs in your own house, where you start), walk to
   the **cheat device on the desk** — third object along the top wall, between
   the settings notice and the wall clock.
2. **Stand below it facing UP and press A.** You will be asked
   **"Enter a Character Mode code?"**
   - **No** → the stock cheat device ("turned on the CHEAT DEVICE!"), unchanged.
   - **Yes** → the Character Mode keyboard.
3. **Type your character's code** and confirm.

### B. The clipboard in the Oldale Town Mart

1. Go to the **Oldale Town Mart** (the first Poké Mart in the game) and walk to
   the **clipboard on the left-hand wall** — Nemo622's built-in GIFT CODE
   terminal. ⚠️ **This one clipboard only** — no other mart, shop or Pokémon
   Center has it.
2. **Stand next to it facing LEFT and press A.** You will be asked
   **"Enter a Character Mode code?"**
   - **No** → the game's original gift-code screen (an Easy Chat word picker),
     unchanged. Typing a character name there does nothing.
   - **Yes** → the Character Mode keyboard.
3. **Type your character's code** and confirm.

Both routes run the same code and accept the same codes — use whichever is
closer.

⚠️ **The keyboard is headed "Enter Gift Code:"** — it looks identical to the
game's own gift-code screen. That is the right screen; the heading is reused.

**Your code** is the character's name with spaces and punctuation removed —
`Cynthia`, `LtSurge`, `Red`. Case does not matter.
📋 **Full list: [Character codes](#character-codes)** (114 selectable).

**You will know it worked:** a confirmation message naming your character —
with their portrait beside it — and their signature starter.

**To turn it back off:** enter the code **`CMDBGOFF`** at the same clipboard.

---

## Installing

1. Get a Seaglass v3.0 ROM (the file this patch was built against — see below).
2. Apply **`seaglass_cm.bps`** to it with any BPS patcher
   (e.g. [Floating IPS / Flips](https://www.romhacking.net/utilities/1040/),
   or the online [rom patcher](https://www.marcrobledo.com/RomPatcher.js/)).
3. Play the patched ROM in any GBA emulator.

**Version pin:** the patch applies to the exact Seaglass v3.0 ROM with
SHA-1 `b9f4d332d30fc88c379f9e037f9eae3b2755ead4`. Applying it to any other ROM
will fail or corrupt.

> **Updating from an earlier build of this patch?** Character Mode now records
> "mode is on" in a different save slot, because the old one sat in a block the
> game wipes whenever the in-game day rolls over — which quietly switched the
> mode off at midnight. Your save, party and boxes are untouched, but if you had
> Character Mode active you'll find it reads as off: just re-enter your
> character's code once at the mart clipboard and it stays on for good.

## What happens after you activate

Only your character's roster can enter your party.

### How enforcement works
- **Catching** an off-roster Pokemon: it goes straight to your PC, not your
  party.
- **Gift Pokemon** (story/NPC gifts): off-roster gifts go to the PC — *unless*
  it would be your very first Pokemon (e.g. you activated Character Mode from
  the bedroom device before ever getting a starter). In that one case the
  gift's species is swapped for your character's own signature Pokemon
  instead of being sent away, so you're never left with an empty party. Its
  nickname and starting move(s) may still reflect the original species until
  you rename it or level it up.
- **In-game trades** (DOTS/PLUSES/SEASOR/MEOWOW): if the offered Pokemon isn't
  in your character's roster, the trade is politely declined.
- **PC Box withdrawals**: closing the PC re-runs the same party check that
  runs at activation. If you withdraw an off-roster Pokemon and then exit the
  PC, it gets sent right back to your box on the spot — off-roster Pokemon
  can't be smuggled into your party this way.
- **Eggs** are exempt (they hatch normally). One known, deliberate corner
  case: if your party is down to an off-roster mon plus an unhatched egg,
  the PC-exit sweep can leave you holding *only* the egg — see
  `docs/EGG_ONLY_PARTY.md`. It's fully playable (the egg can battle and flee
  normally); the only real cost is a minor spoiler about the egg's species.
- **Switching characters (including turning Character Mode on for the first
  time) sweeps your current party**: anything you already own that isn't an
  egg and isn't on the *new* character's roster is moved to your PC on the
  spot, the moment you confirm the code. You will never be left with zero
  Pokemon — if everything in your party would otherwise be swept, one
  off-roster mon is left behind rather than emptying your party entirely.

## Seeing your roster in-game

With Character Mode on, use the **CHEAT DEVICE in your bedroom** or the
**clipboard in the Oldale Town Mart** again. Instead of the code question you
get a short menu:

- **View roster**: a list of your character's Pokémon, one row per
  evolution family (the first stage is shown, and the whole family counts).
  The highlighted Pokémon's icon appears in a box beside the list. Scroll with
  Up/Down; A or B closes it.
- **Character code**: the code entry screen, as before.
- **Questionnaire** (clipboard) / **Gift code** (cheat device): the object's
  normal use.

With Character Mode off, both objects work exactly as they always did.

## Character codes

Codes are the character's name with spaces and punctuation removed.
Case is ignored. **114 selectable characters** across all nine
generations:

### Gen 1 — Kanto

| Code | Character |
|---|---|
| `Agatha` | Agatha |
| `Ash` | Ash |
| `Blaine` | Blaine |
| `Blue` | Blue |
| `Brock` | Brock |
| `Bruno` | Bruno |
| `Erika` | Erika |
| `Gary` | Gary |
| `Giovanni` | Giovanni |
| `James` | James |
| `Jessie` | Jessie |
| `Koga` | Koga |
| `Lance` | Lance |
| `Leaf` | Leaf |
| `Lorelei` | Lorelei |
| `LtSurge` | Lt. Surge |
| `Misty` | Misty |
| `Oak` | Oak |
| `Red` | Red |
| `Ritchie` | Ritchie |
| `Sabrina` | Sabrina |

### Gen 2 — Johto

| Code | Character |
|---|---|
| `Archer` | Archer |
| `Ariana` | Ariana |
| `Bugsy` | Bugsy |
| `Chuck` | Chuck |
| `Clair` | Clair |
| `Elm` | Elm |
| `Ethan` | Ethan |
| `Falkner` | Falkner |
| `Janine` | Janine |
| `Jasmine` | Jasmine |
| `Karen` | Karen |
| `Kris` | Kris |
| `Lyra` | Lyra |
| `Morty` | Morty |
| `Pryce` | Pryce |
| `Silver` | Silver |
| `Whitney` | Whitney |
| `Will` | Will |

### Gen 3 — Hoenn

| Code | Character |
|---|---|
| `Anabel` | Anabel |
| `Archie` | Archie |
| `Birch` | Birch |
| `Brandon` | Brandon |
| `Brawly` | Brawly |
| `Brendan` | Brendan |
| `Flannery` | Flannery |
| `Greta` | Greta |
| `Juan` | Juan |
| `Liza` | Liza |
| `Lucy` | Lucy |
| `Maxie` | Maxie |
| `May` | May |
| `Noland` | Noland |
| `Norman` | Norman |
| `Phoebe` | Phoebe |
| `Roxanne` | Roxanne |
| `Sidney` | Sidney |
| `Spenser` | Spenser |
| `Steven` | Steven |
| `Tate` | Tate |
| `Tucker` | Tucker |
| `Wallace` | Wallace |
| `Wally` | Wally |
| `Wattson` | Wattson |
| `Winona` | Winona |

### Gen 4 — Sinnoh

| Code | Character |
|---|---|
| `Aaron` | Aaron |
| `Barry` | Barry |
| `Bertha` | Bertha |
| `Byron` | Byron |
| `Candice` | Candice |
| `CrasherWak` | Crasher Wake |
| `Cynthia` | Cynthia |
| `Cyrus` | Cyrus |
| `Dahlia` | Dahlia |
| `Darach` | Darach |
| `Dawn` | Dawn |
| `Fantina` | Fantina |
| `Flint` | Flint |
| `Gardenia` | Gardenia |
| `Lucas` | Lucas |
| `Lucian` | Lucian |
| `Mars` | Mars |
| `Maylene` | Maylene |
| `Paul` | Paul |
| `Roark` | Roark |
| `Saturn` | Saturn |
| `Tobias` | Tobias |
| `Volkner` | Volkner |
| `Zoey` | Zoey |

### Gen 5 — Unova

| Code | Character |
|---|---|
| `Hilbert` | Hilbert |
| `N` | N |

### Gen 6 — Kalos

| Code | Character |
|---|---|
| `Calem` | Calem |
| `Ramos` | Ramos |
| `Serena` | Serena |
| `Shauna` | Shauna |
| `Sycamore` | Sycamore |
| `Valerie` | Valerie |

### Gen 7 — Alola

| Code | Character |
|---|---|
| `Elio` | Elio |
| `Gladion` | Gladion |
| `Guzma` | Guzma |
| `Hau` | Hau |
| `Kukui` | Kukui |
| `Lanaanime` | Lana (anime) |
| `Lusamine` | Lusamine |
| `Molayne` | Molayne |
| `Selene` | Selene |

### Gen 8 — Galar

| Code | Character |
|---|---|
| `Bede` | Bede |
| `Chloe` | Chloe |
| `Goh` | Goh |
| `Hop` | Hop |
| `Marnie` | Marnie |
| `Milo` | Milo |

### Gen 9 — Paldea

| Code | Character |
|---|---|
| `Penny` | Penny |
| `Rika` | Rika |

### Characters that are not offered in Seaglass

79 of the 193 characters in the table are **not selectable here** and their codes are refused.
Seaglass's dex is a curated subset -- all of Gen 1-3 plus a small set of
later cross-gen evolutions -- so those characters cannot field six fully
evolved Pokemon in this game, and picking them would mean catching almost
nothing for the whole run. They keep their slot internally so existing
saves still load correctly; they simply cannot be chosen.

## Notes & limitations

- **Sprites**: 164 of the 193 characters (96 of the 114 selectable) have a
  64x64 portrait that draws beside the confirmation message when you select
  them — see "How to turn Character Mode on" above. The remaining 29 (no GBA-
  style art exists for them, mostly 3D-era Gen 6–9 characters and a few anime
  cast members) show the confirmation text with no portrait.
- **Overworld sprite** (new 2026-10-03): 100 of the 114 selectable characters
  look like themselves while **walking and running**, from the moment their
  code is accepted (Brendan and May use Seaglass's own player sprites). On a
  bike, surfing, fishing, using a field move or underwater you're the normal
  player, because the sprites have no frames for those. Most sprites have no
  running frames of their own, so running shows their walk cycle at running
  speed. The other 14 (Red, Leaf, Ritchie, Paul, Zoey, Hilbert, Guzma, Lana,
  Goh, Chloe, Sycamore, Tobias, Dahlia, Darach) keep the normal player sprite.
  No NPC's sprite changes, and your battle back sprite is unchanged. The debug
  off code restores the normal sprite at the next map change.
- **Switching characters**: your current party is swept against the new
  character's roster at the moment you activate (see "How enforcement works"
  above) — it is not a one-time grandfather clause. Anything already sitting
  in your PC boxes is left alone either way; only the active party is checked.
- This modifies only free space and a handful of hooks; the base game plays
  identically with Character Mode off.

## Credits

Character Mode feature ported from the Pokemon ROWE implementation. Roster data
from Bulbapedia. Built on Nemo622's Pokemon Emerald Seaglass. Distributed as a
patch only — never as a ROM.
