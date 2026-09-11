# SPECIES GATES — Emerald Seaglass v3.0

**1 decoded gate(s) out of 11 ChoosePartyMon call sites** (2
of them reachable from a dialogue anchor). Measured 2026-09-11; pinned by
`tools/tests/check_species_gates.py` (7 checks, negative-tested).

A *species gate* is an NPC that wants a Pokémon **shown** rather than traded:
it calls `ChoosePartyMon`, tests what you handed it, and gives something back.
It matters to Character Mode because the PC-withdraw fix (`rowe_parity.md`
§13.26c, option 1) sweeps an off-roster Pokémon back into the PC the moment
you leave the storage system, so you can no longer carry one to an NPC.
§13.28 counted these NPCs and said plainly that **nobody had decoded what any
of them give**, leaving the cost an upper bound. This is the decode.

## The verdict

⚠️ **`rowe_parity.md` §13.28 recorded this game as having ZERO species gates.
It has one** — and the verdict that count supported is unchanged, because the
reward is inert without the species.

## The gates

| site | NPC | gate | what it actually gives | verdict |
|---|---|---|---|---|
| `0x0836642B` | the magic trick — *"Please select a DEOXYS."* → *"Congratulations! Your DEOXYS has transformed!"* | Deoxys, tested in **native code** (`special 0x224`), which is why a compare scan scored this site as having no species test | a **form change**, no item | `SPECIES_LOCKED` |

## Why the raw count was never a count

`rowe_parity.md` §13.28 published **5 / 5 / 2 / 0** species gates for Radical
Red / Unbound / Lazarus / Seaglass, found by decoding forward from dialogue
anchors — the same primitive `check_gift_eggs.py` uses, and the right one
there. It is the wrong one here. Measured 2026-09-11, that walk reaches:

| game | ChoosePartyMon call sites in the ROM | reachable from a dialogue anchor |
|---|---|---|
| Radical Red | **43** | 20 |
| Unbound | **76** | 26 |
| Lazarus | **19** | 3 |
| Seaglass | **11** | 2 |

So between 47% and **84%** of the call sites were never seen. The sites the
walk misses are real — Name Rater, move tutors, the *"Hunh? Your BAG is
crammed full."* item NPCs, and in Unbound four more sites of the Deoxys
meteorite and the Rotom appliances, two of the very NPCs §13.28 named. ⭐ **The
better primitive is the call site itself**: `special <ChoosePartyMon>`
immediately followed by `waitstate`, which every real site has and which no
dialogue reachability question can hide. `tools/tests/check_species_gates.py`
pins the whole set that way.

⚠️ **This document does not claim every one of those sites has been decoded.**
The ones that have are in the table above; the rest are pinned by address, so
a new one cannot arrive silently, and a decode of the remainder is open work.

## Three false-positive constants, all of which decode as a species

Each sits immediately after a `ChoosePartyMon` and looks exactly like a
species gate:

- **255** — `PARTY_NOTHING_CHOSEN` in the Emerald pair. Decodes as Torchic.
- **412** — `SPECIES_EGG` in the FireRed pair. Decodes as Bad Egg.
- **a small value inside a BP facility is the PRICE IN BP**, not a species.
  Five Unbound sites compare 16, 25 or 27 right after the choice; those decode
  as Pidgey, Pikachu and Sandshrew, and all five are Battle-Frontier-style
  services whose own dialogue says *"You don't have enough BP"*.

## A species test can be invisible to every compare scan

Four of the gates in this workspace test the species in **native code**, so
the species id never appears as a script operand at all:

| game | NPC | where the test lives |
|---|---|---|
| Radical Red | Heracross size judge | `special 0x78` |
| Radical Red | gender swapper | `callasm 0x09077B59` |
| Unbound | Deoxys meteorite | `callasm 0x088AB3CD` |
| Unbound | Rotom appliances | `callasm 0x088AABB9` / `0x088AACCD` |
| Seaglass | DEOXYS magic trick | `special 0x224` |

They are in the inventory because the **dialogue** was decoded, not because a
scan found them. Any future count of this class is a floor for the same
reason `check_gift_eggs.py` documents for `giveegg`.

## Re-running it

```bash
python3 tools/tests/check_species_gates.py                   # the inventory
python3 tools/tests/check_species_gates_negative_test.py     # break it on purpose
```

The checker reads the **base ROM** and this repo's own vendored
`tools/charmap.txt`; it builds nothing and changes nothing.
