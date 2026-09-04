# GIFT EGGS — Emerald Seaglass v3.0

**3 `giveegg` sites, all reachable from dialogue, and as of 2026-09-04 all
GATED.** Measured 2026-09-03, closed the next day. Pinned by
`tools/tests/check_gift_eggs.py` (5 checks, negative-tested 7/7); the hook
itself is pinned by five checks in `verify_artifacts.py` (98), negative-tested
6/6 by `tools/tests/egg_hook_negative_test.py`.

✅ **THE HOOK IS IN** (`tools/character_mode/egg_hook.py`). The hatch script's
tail at `0x0832EEF8` is overlaid with a `goto` into an 11-byte replayed tail at `0x08FA0000`
that ends `callnative CM_SweepPartyToPCNative`, **after** the hatch's
waitstate — so the sweep sees the hatched Pokemon, not the egg, and the egg
exemption inside the sweep no longer applies to it. Build `0eb63a8a`.

⚠️⚠️ **THE DONOR SOURCE IS WRONG ABOUT THIS SCRIPT.**
`tools/pokeemerald_expansion_donor/data/scripts/day_care.inc` has
`EventScript_EggHatch` as `lockall; msgbox; special EggHatch; releaseall; end`
— **with no waitstate**. On that shape the sweep would run BEFORE the hatch
scene, see an egg, and be skipped by its own egg exemption: a silent no-op that
would still pass a "the callnative is present" check. The ROM was disassembled
instead of trusted, and it HAS the waitstate. **The donor tree is a guess at
the fork point, not this binary.**

⚠️ **This repo's `docs/ROUTINE_MAP.md:215` exempts the egg-hatch give with the
reason "RR/Lazarus parity".** That is parity with a call **Unbound later
reversed** after determining it was a live hole, and nothing re-examined the
games the justification pointed at. See `game_plans/rowe_parity.md` §13.16.

| site | source | what it gives |
|---|---|---|
| `0x08280EA3` | the hot-spring EGG — *"Will you take this EGG to hatch?"* | species **360** (Wynaut), a fixed inherited Emerald script |
| `0x0828B603` | the **PALDEAN EGG** from the Team Aqua grunt — *"I can't just leave this EGG all vulnerable here. Could you take it?"* | species **1345** |
| `0x082AA568` | the **Alolan Egg vendor** — a SAILOR *"between HOENN and ALOLA"* selling eggs for **PINBALL POINTS**, repeatable | `random 9` → one of **9 species** (958–973) via VAR 0x800D |

## How off-roster is it

Measured against `rosters_expanded.bin` over the **114 offered** characters:

- Wynaut: off-roster for **111 of 114** (on-roster only for Sabrina, Jessie and
  Archer).
- the Paldean Egg's species 1345: off-roster for **all 114**.
- the Alolan vendor's 9 species: **every one is off-roster for all 114**. That
  source is repeatable and cannot produce a keepable Pokemon for anybody.

## How this was measured, and the primitive that does NOT work

`tools/tests/check_gift_eggs.py` is the tool; run it, it is fast and needs
nothing but the base ROM and this repo's own donor tree.

⭐ **The obvious scan is useless, and knowing why is the transferable part.**
`giveegg` is opcode `0x7A` followed by a `u16`. Scanning a ROM for that byte
pattern with a plausible species operand gives, measured on Radical Red,
**3,249 raw candidates**. Filtering on "some aligned ROM word points into the
512 bytes before it, and the script decodes cleanly forward to a terminator"
cuts that to **116** — of which, on inspection, **zero were real**. Script
bytecode is not word-aligned (so an aligned-pointer filter has false negatives
as well as false positives) and one command in isolation is indistinguishable
from data.

✅ **What works is an anchor data cannot cheaply fake**: the byte pair `0F 00`
(`loadword` into destination 0) followed by a ROM pointer whose target decodes
as Gen 3 text. Every dialogue script contains one. Decode linearly from each
anchor, follow `goto`/`call`/`goto_if`/`call_if`, and record every `giveegg`
reached. That is a reachability claim about the script graph, not a byte
pattern. **It was validated on a known positive before it was believed** — the
stock Emerald Lavaridge hot-spring script, which decodes to `giveegg 360`
(Wynaut) in both Emerald ports.

⚠️ **AND THE TEXT SEARCH FOUND WHAT THE OPCODE SCAN CANNOT.** Radical Red's egg
vendor advertises *"a Wonder Egg that just contains a random first form
Pokemon"*; a species that is **computed in native code never appears as a
`giveegg` operand at all**. The inventory is a **floor on the reachable gift
eggs, not a ceiling**. Two independent primitives were used here — decode the
script graph, and read the game's own dialogue — and each found sites the other
did not.

## What this inventory does NOT cover

- **Day Care breeding.** Deliberately out of scope and believed safe: a roster
  stores whole evolution families and only on-roster parents can be kept, so
  offspring are on-roster by construction. Gift eggs are the way in.
- **Eggs whose species is computed in native code** (see above).
- **Whether each script is actually placed on a reachable map.** The scan
  proves the script exists and is entered from dialogue; it does not walk map
  event tables. For the custom content below that is not in doubt (the NPCs
  have their own new dialogue, flags and object removal), but the two stock
  Emerald hot-spring scripts are marked as inherited and their map placement is
  **unverified**.

## How the fix was done

Ported from `Unbound-Character-Mode/tools/character_mode/egg_hook.py`. Unbound's own
summary calls the hole *"the one enforcement hole reachable in ordinary
play"*. Its shape: the overworld step handler calls `ShouldEggHatch` and on a
true result runs a hatch script whose tail is `special <hatch>; waitstate;
release; end`. That tail is overlaid with a `goto` into an injected tail that
replays those commands and then runs the party-sweep special — **after** the
waitstate, so the sweep sees the hatched Pokemon rather than the egg, and the
egg exemption inside the sweep no longer applies to it.

Per-ROM reverse engineering is needed for each port: this ROM's own
`ShouldEggHatch` caller, its hatch script, and free space for the tail. Two
things Unbound checked rather than assumed, and this port must too:

1. **Nothing references the interior of the hatch script**, or the overlay
   lands mid-jump.
2. **Enough displaced bytes are available** for a 5-byte `goto`, with the
   displaced commands replayed rather than shortened.

Both happened together, as the checker requires: the verdicts are GATED **and**
`HATCH_HOOK` is set in `tools/tests/check_gift_eggs.py`. Its fifth check fails
if only one of those two is ever true.

⚠️ **Still not covered, and worth saying plainly:** the sweep boxes an
off-roster hatchling, it does not prevent the egg. That is the deliberate
design — an egg event must never block progress.

⬜ **Not yet done: a live egg-hatch test.** Every assertion here is static plus
the existing live layers; nobody has walked this ROM through a hatch in an
emulator.
