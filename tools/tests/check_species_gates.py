#!/usr/bin/env python3
"""INVENTORY every ChoosePartyMon call site in this ROM, and decode what the
NPCs behind them GIVE.

⭐ WHY THIS EXISTS. `rowe_parity.md` §13.28 measured a class of NPC that wants
a species SHOWN rather than traded, and reported the raw counts 5/5/2/0 across
the four ports as the mission cost of the PC-withdraw fix -- while stating
plainly that NOBODY HAD DECODED WHAT ANY OF THEM GIVE, so the count was an
upper bound and not a loss. §13.37 decoded them. The answer is that the count
matters to nothing: nine of the fourteen gates hand over an item that only
works on the very species the character cannot own, four more give something
a shop sells, and the last two gate on a species that has to be CAUGHT, which
the catch gate already refuses.

⚠️ THE PRIMITIVE, AND WHY IT IS NOT THE DIALOGUE WALK. `check_gift_eggs.py`
finds its sites by decoding forward from a dialogue anchor. That walk is the
right primitive for `giveegg`, and it is the WRONG one here: measured on these
four ROMs it reaches 2 of 11 ChoosePartyMon sites in this game
(20/43, 26/76, 3/19 and 2/11 across the four). The count §13.28 published was
the walk-reachable subset, so it was never a count of the class. This file
scans for the call site itself -- `special <ChoosePartyMon>` immediately
followed by `waitstate`, which every real site has -- and pins the whole set.

⚠️ WHAT THIS DOES AND DOES NOT PROVE. It proves the set of ChoosePartyMon call
sites has not changed and that the decoded gates still compare the recorded
species and still hand over the recorded items. It does NOT claim every site
in SITES has been decoded: the ones that have are in GATES, and the rest are
pinned by address only. A species test that lives in native code (Radical
Red's `special 0x78`, its gender-swap `callasm`, Unbound's Deoxys and Rotom
callasms, Seaglass's `special 0x224`) is in GATES with an EMPTY species tuple
-- it is there because the DIALOGUE was decoded, and no compare scan can see
it.

⚠️ Three false-positive constants worth pinning, all of which decode as a
plausible species right after a ChoosePartyMon:
  255  PARTY_NOTHING_CHOSEN in the Emerald pair (decodes as Torchic)
  412  SPECIES_EGG in the FireRed pair (decodes as Bad Egg)
  a small value in a BP facility is the PRICE IN BP, not a species -- five
  Unbound sites compare 16, 25 or 27, which decode as Pidgey, Pikachu and
  Sandshrew.

Run:  python3 tools/tests/check_species_gates.py   (0 = ok, 1 = changed)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from cm_tally import assert_tally          # noqa: E402

GAME = 'Pokémon Emerald Seaglass v3.0'
ROM = os.path.join(ROOT, 'rom/seaglass v3.0.gba')
ROM_BASE = 0x08000000
CHARMAP = os.path.join(ROOT, "tools/charmap.txt")

# special id of ChoosePartyMon in this engine family, MEASURED against this
# ROM's own scripts -- the two families do not agree.
CHOOSE_SPECIAL = 0xa2
WAITSTATE = 0x27

# (address of the NAME of id 0, stride) for this ROM's own tables. Measured
# per ROM: all four item tables sit at different addresses and the strides are
# 44 / 44 / 80 / 84. NEVER copy one of these from a sibling port.
ITEM_TABLE = (0x0867e77c, 84)
SPECIES_TABLE = (0x088f07ac, 208)
# (id, name) pairs read out of those two tables when this file was written.
# ⚠️ At least one probe is deliberately FAR from the base: a wrong STRIDE is
# invisible at id 1 and shows up only at a high index. That is not
# hypothetical -- an early version of this work carried a sibling's stride for
# Seaglass, read ids 1-4 correctly, and decoded item 51 as mojibake.
# Species id 386 is pinned in the FireRed pair on purpose: it is Volbeat, not
# the national-dex 386, which is the trap `CHARACTER_ROSTER_PLAN.md` records.
ITEM_PROBES = ((1, 'Pokひ Ball'), (51, 'Elixir'))
SPECIES_PROBES = ((386, 'Deoxys'), (1, 'Bulbasaur'))

# Every ChoosePartyMon call site in the ROM. A site being here is not a claim
# that anyone has looked at it; GATES holds the ones that were decoded.
SITES = (
    0x0829cfc7,
    0x082a2e52,
    0x082af845,
    0x082b01c1,
    0x082b8df2,
    0x082c23a8,
    0x082c2439,
    0x082fa9e3,
    0x0830082c,
    0x08301270,
    0x0836642b,
)

# address -> (label, gate species ids, ((give address, item id, qty), ...),
#             verdict, what it actually gives)
#   SPECIES_LOCKED      the reward only works on the species that opens the
#                       gate, so a character who cannot keep that species
#                       loses nothing of value
#   ELSEWHERE           the reward is generic but obtainable another way in
#                       this same ROM (measured, with the other source named)
#   CATCH_ONLY          the reward is generic and has no other source, but
#                       the gate needs a species the catch gate already
#                       refuses. ⚠️ Whether an in-game trade or a computed
#                       gift egg could still deliver that species into the PC
#                       is NOT established here -- so this verdict bounds the
#                       cost, it does not prove it is zero
GATES = {
 0x0829cfc7: (
  'in-game trade (BAGON)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x082a2e52: (
  'Name Rater -- compares SPECIES_EGG (1524)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x082b01c1: (
  'in-game trade (VOLBEAT/PLUSLE)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x082c23a8: (
  'big SEEDOT judge -- Elixir',
  (),
  ((0x082c2408, 51, 1),),
  'UNIQUE',
  'rewards seen in the window between this site and the next call site:'
  ' Elixir x1'),
 0x082c2439: (
  'big LOTAD judge -- Elixir',
  (),
  ((0x082c2499, 51, 1),),
  'UNIQUE',
  'rewards seen in the window between this site and the next call site:'
  ' Elixir x1'),
 0x082fa9e3: (
  'IV judge -- its compares are IV TOTALS (120/150/151)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x0830082c: (
  'the egg kid -- compares SPECIES_EGG (1524)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x08301270: (
  'in-game trade (SKITTY)',
  (),
  (),
  'NOT_A_GATE',
  'no give-item in its window'),
 0x0836642b: (
  'the DEOXYS magic trick (native test, special 0x224)',
  (),
  (),
  'SPECIES_LOCKED',
  'no give-item in its window'),
}

# ---------------------------------------------------------------- non-catch
# ⭐ THE ONLY PART OF THIS CLASS THE PC-WITHDRAW HOOK CAN BE BLAMED FOR.
# Character Mode's catch gate has always refused an off-roster catch, so a gate
# whose species you could only CATCH was already out of reach before the hook
# existed. A gate species that arrives as a GIFT, an EGG or a TRADE lands in the
# party, gets swept into the PC by enforcement -- and before the hook, could be
# withdrawn and shown to the NPC. Measured 2026-09-11; rowe_parity.md §13.42.
#
# (file offset of sInGameTrades, records, species field offset, ((idx, given), ...))
# ⚠️ The 60-byte struct is NOT the same 60 bytes in the two engine families:
# `species` is at +12 in the FireRed pair and +14 in the Emerald pair.
TRADES = (10738480, 4, 14, ((0, 273), (1, 311), (2, 116), (3, 52)))
# (rom address of a givemon, species, level) -- only the sites that matter to a
# gate, each hand-decoded.
GIFTS = ()
# gate site -> ((how its species can arrive without a catch, what it costs), ...)
REACHABLE = {
 0x082c23a8: (
  ('Seedot 273 is trade #0\'s "DOTS"',
   'CLOSED BY ENFORCEMENT -- this engine family REFUSES a trade whose'
    ' incoming mon is off-roster, so the Seedot never arrives for a'
    ' character who cannot keep it'),
 ),
 0x082c2439: (
  ('Seedot 273, the same trade',
   'CLOSED BY ENFORCEMENT -- as above'),
 ),
}

EXPECT_CHECKS = 9

failures = []
checks_run = 0


def check(name, ok, detail=""):
    global checks_run
    checks_run += 1
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                           (" -- " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def charmap():
    import re
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    for line in open(CHARMAP, encoding="utf-8"):
        m = pat.match(line.rstrip("\n"))
        if m:
            table[int(m.group(2), 16)] = m.group(1)
    table[0x00] = " "
    return table


def name_at(b, cm, addr, limit):
    out = []
    for i in range(limit):
        c = b[addr - ROM_BASE + i]
        if c == 0xFF:
            break
        out.append(cm.get(c, "."))
    return "".join(out).strip()


def item_name(b, cm, n):
    base, stride = ITEM_TABLE
    return name_at(b, cm, base + n * stride, min(stride, 14))


def species_name(b, cm, n):
    base, stride = SPECIES_TABLE
    return name_at(b, cm, base + n * stride, min(stride, 12))


def scan_sites(b):
    """Every `special ChoosePartyMon; waitstate` in the ROM."""
    found = []
    pat = bytes((0x25, CHOOSE_SPECIAL, 0x00))
    i = b.find(pat)
    while i >= 0:
        if i + 3 < len(b) and b[i + 3] == WAITSTATE:
            found.append(ROM_BASE + i)
        i = b.find(pat, i + 1)
    return found


def compares(b, addr, span=0x140):
    """Every compare-var-to-value operand in the window after a site."""
    out = []
    o = addr - ROM_BASE
    for i in range(o, min(len(b) - 5, o + span)):
        if b[i] == 0x21:
            var = struct.unpack_from("<H", b, i + 1)[0]
            if var in (0x8000, 0x8004, 0x8005, 0x8006, 0x800D):
                out.append(struct.unpack_from("<H", b, i + 3)[0])
    return out


def main():
    if not os.path.isfile(ROM):
        print("base ROM not found: %s" % os.path.relpath(ROM, ROOT))
        return 1
    with open(ROM, "rb") as f:
        b = f.read()
    cm = charmap()

    found = scan_sites(b)
    print("%s -- %d ChoosePartyMon (special %#04x) call site(s), "
          "%d inventoried, %d decoded\n"
          % (GAME, len(found), CHOOSE_SPECIAL, len(SITES), len(GATES)))

    # A scanner that resolves nothing finds nothing, and an empty result
    # satisfies every set comparison below. Zero is never a pass.
    check("the scan reached at least one call site", bool(found),
          "no site at all -- the special id or the ROM is wrong, not the data")

    new = sorted(set(found) - set(SITES))
    check("every ChoosePartyMon call site in the ROM is inventoried",
          not new,
          ", ".join("%#010x" % a for a in new)
          + " -- a way to hand a Pokemon to an NPC that nobody has looked at")

    gone = sorted(set(SITES) - set(found))
    check("every inventoried call site is still present in the ROM",
          not gone, ", ".join("%#010x" % a for a in gone))

    bad = []
    for addr, (_label, ids, _rew, _v, _why) in sorted(GATES.items()):
        seen = compares(b, addr)
        missing = [i for i in ids if i not in seen]
        if missing:
            bad.append("%#010x wants %s" % (addr, missing))
    check("every decoded gate still compares its recorded species",
          not bad, "; ".join(bad))

    bad = []
    for addr, (_label, _ids, rew, _v, _why) in sorted(GATES.items()):
        for give, item, qty in rew:
            o = give - ROM_BASE
            ok = (b[o:o + 3] == bytes((0x1A, 0x00, 0x80))
                  and struct.unpack_from("<H", b, o + 3)[0] == item
                  and b[o + 5:o + 8] == bytes((0x1A, 0x01, 0x80))
                  and struct.unpack_from("<H", b, o + 8)[0] == qty
                  and b[o + 10:o + 12] == bytes((0x09, 0x00)))
            if not ok:
                bad.append("%#010x is no longer `give item %d x%d`"
                           % (give, item, qty))
    check("every recorded reward still gives that item, at that address",
          not bad, "; ".join(bad))

    # The two name tables are the reason a reward can be READ at all. If one
    # moves, every verdict above describes the wrong item or the wrong
    # species, and every set check above still passes. The probes are
    # deliberately not empty in any port: a check over GATES alone would be
    # vacuous in the game whose only gate is tested in native code and gives
    # no item.
    bad = ["%d reads %r, recorded %r" % (n, item_name(b, cm, n), want)
           for n, want in ITEM_PROBES if item_name(b, cm, n) != want]
    check("the item-name table still reads what this file recorded",
          ITEM_PROBES and not bad, "; ".join(bad) or "no probe is pinned")

    bad = ["%d reads %r, recorded %r" % (n, species_name(b, cm, n), want)
           for n, want in SPECIES_PROBES if species_name(b, cm, n) != want]
    check("the species-name table still reads what this file recorded",
          SPECIES_PROBES and not bad, "; ".join(bad) or "no probe is pinned")

    # The trade table is the one non-catch route that is pure DATA, so it is
    # pinned by content: a moved table or a changed gift makes the reachability
    # claim above describe a ROM this is not running on.
    toff, tn, tsp, tgives = TRADES
    bad = []
    for idx, want in tgives:
        got = struct.unpack_from("<H", b, toff + idx * 60 + tsp)[0]
        if got != want:
            bad.append("trade #%d gives %d (%s), recorded %d (%s)"
                       % (idx, got, species_name(b, cm, got), want,
                          species_name(b, cm, want)))
    check("every in-game trade still gives the species recorded here",
          tgives and not bad, "; ".join(bad) or "no trade is pinned")

    bad = []
    for addr, species, level in GIFTS:
        o = addr - ROM_BASE
        if not (b[o] == 0x79
                and struct.unpack_from("<H", b, o + 1)[0] == species
                and b[o + 3] == level):
            bad.append("%#010x is no longer `givemon %d, %d`"
                       % (addr, species, level))
    check("every gift Pokemon that opens a gate is still that gift",
          not bad, "; ".join(bad))

    if REACHABLE:
        print("\n  🔴 gate(s) whose species can arrive WITHOUT being caught "
              "-- the PC hook's own cost:")
        for site in sorted(REACHABLE):
            print("     %#010x  %s" % (site, GATES[site][0][:64]))
            for how, cost in REACHABLE[site]:
                print("        %s\n          -> %s" % (how, cost))
    else:
        print("\n  ✅ no gate in this game can be opened with a Pokemon the "
              "player did not catch")

    counts = {}
    for _l, _i, _r, verdict, _w in GATES.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    if counts:
        print("\n  verdicts: " + ", ".join("%d %s" % (counts[k], k)
                                           for k in sorted(counts)))
    for addr in sorted(GATES):
        label, ids, rew, verdict, why = GATES[addr]
        print("\n  %#010x  %s" % (addr, verdict))
        print("     %s" % label)
        if ids:
            print("     gate: %s" % ", ".join(
                "%d %s" % (i, species_name(b, cm, i)) for i in ids[:8])
                + (" (+%d more)" % (len(ids) - 8) if len(ids) > 8 else ""))
        else:
            print("     gate: tested in NATIVE code -- no script operand")
        for give, item, qty in rew:
            print("     gives: %#010x item %d x%d  %s"
                  % (give, item, qty, item_name(b, cm, item)))
        print("     %s" % why)

    if assert_tally(checks_run, EXPECT_CHECKS, "check_species_gates"):
        return 1
    print("\n%s" % ("ALL PASS" if not failures
                     else "FAILURES: " + ", ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
