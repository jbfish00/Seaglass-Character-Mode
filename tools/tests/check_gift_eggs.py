#!/usr/bin/env python3
"""INVENTORY every scripted gift EGG in this ROM.

⭐ WHY THIS EXISTS. Eggs are deliberately exempt from the catch gate, the gift
routing and the party sweep, so an egg event can never block progress. Nothing
then looks at what the egg HATCHES INTO, so a scripted gift egg of an
off-roster species becomes a permanent off-roster party member. Breeding cannot
reach that: a roster stores whole evolution families and only on-roster parents
can be kept, so offspring are on-roster by construction. **Gift eggs are the
way in**, which makes the set of them the thing worth pinning.

⚠️ THE PRIMITIVE, AND THE ONE THAT DOES NOT WORK. The obvious scan -- "every
0x7A byte followed by a plausible species" -- returns thousands of hits in a
32 MB ROM and cannot be filtered down by species range or by decoding forwards;
measured on Radical Red, it gave 3,249 raw candidates and 116 survivors after
pointer-and-decode filtering, of which ZERO were real. Script bytecode is not
word-aligned and is not distinguishable from data by inspection of one command.

What works is decoding from an anchor that data cannot fake cheaply: the byte
pair `0F 00` (loadword into destination 0) followed by a ROM pointer whose
target decodes as Gen 3 text. Every dialogue script in this engine contains
one. From each anchor we decode linearly and follow goto/call/goto_if/call_if,
and record every `giveegg` reached. That is a REACHABILITY claim about the
script graph, not a byte pattern.

⚠️ WHAT THIS DOES AND DOES NOT PROVE. It proves the set of `giveegg` commands
reachable from dialogue has not changed. It does NOT prove that set is the
complete set of ways an egg can enter the party: an egg whose species is
computed in native code (a `callnative`, or the Day Care) never appears as a
`giveegg` operand at all. Radical Red's egg vendor dialogue advertises a
"Wonder Egg that just contains a random first form Pokemon" -- the pool behind
that wording is not visible to this scan. The inventory is a floor, not a
ceiling, and it is deliberately a floor on the paths that are cheap to see.

Run:  python3 tools/tests/check_gift_eggs.py   (0 = ok, 1 = changed)
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from cm_tally import assert_tally          # noqa: E402

GAME = 'Pokémon Emerald Seaglass v3.0'
ROM = os.path.join(ROOT, 'rom/seaglass v3.0.gba')
ENGINE = 'emerald'
DONOR = os.path.join(ROOT, 'tools/pokeemerald_expansion_donor')

# The repo's own egg-hatch hook, if it has one. Verdicts and this file must
# agree: a site can only be GATED once something actually gates the hatch.
HATCH_HOOK = None

ROM_BASE = 0x08000000
GIVEEGG = 0x7A
# Opcodes after which linear decoding stops (flow leaves this address).
TERMINATORS = frozenset({0x02, 0x03, 0x05, 0x0C, 0x0D})
# giveegg's operand is a var reference, not a species id, at or above this.
VAR_BASE = 0x4000

EXPECT_CHECKS = 5

# file offset -> (operand, verdict, why).
#   GATED    the hatch of this egg is swept by this repo's enforcement
#   EXEMPT   deliberately not gated, with a reason
#   UNGATED  a real hole: the egg hatches into whatever it holds, unchecked
INVENTORY = {
    0x00280ea3: (360, 'UNGATED',
     'the hot-spring EGG ("Will you take this EGG to hatch?"), the '
     'stock Emerald Lavaridge script. Wynaut is off-roster for 111 '
     'of 114 offered characters (on-roster only for Sabrina, Jessie '
     'and Archer). UNGATED.'),
    0x0028b603: (1345, 'UNGATED',
     'the PALDEAN EGG handed over by the Team Aqua grunt ("I can\'t '
     'just leave this EGG all vulnerable here. Could you take it?"). '
     'Species 1345 is off-roster for ALL 114 offered characters. '
     'UNGATED.'),
    0x002aa568: (32781, 'UNGATED',
     'the Alolan Egg vendor -- a SAILOR who sells eggs for PINBALL '
     'POINTS, `random 9` over 9 Alolan species (958-973), '
     'repeatable. Every one of the 9 is off-roster for ALL 114 '
     'offered characters. UNGATED.'),
}

# 🔴 EVERY SITE HERE IS UNGATED. That is the finding, not an oversight in this
# file: this repo has no egg-hatch hook, so each of these hatches into whatever
# it holds and the party keeps it. Unbound closed the identical hole with
# tools/character_mode/egg_hook.py. game_plans/rowe_parity.md §13.16/§13.18.

# ---------------------------------------------------------------- script grammar

_WIDTH = {'byte': 1, 'hword': 2, '2byte': 2, 'short': 2,
          'word': 4, '4byte': 4, 'long': 4}


def _paths(lines, i=0):
    """Every straight-line path through .if/.else/.endif nesting."""
    out = [[]]
    while i < len(lines):
        line = lines[i]
        if re.match(r'\.if', line):
            a, j = _paths(lines, i + 1)
            if j < len(lines) and lines[j].startswith('.else'):
                b, j = _paths(lines, j + 1)
            else:
                b = [[]]
            out = [p + s for p in out for s in a + b]
            i = j + 1
            continue
        if line.startswith('.else') or line.startswith('.endif'):
            return out, i
        out = [p + [line] for p in out]
        i += 1
    return out, i


def _macros(src, symbols):
    """{opcode: (name, size)} from a GAS macro file, symbols resolving names."""
    table = {}
    for name, _args, body in re.findall(
            r'\.macro\s+(\w+)([^\n]*)\n(.*?)^\s*\.endm', src, re.S | re.M):
        lines = [l.split('@')[0].strip() for l in body.split('\n')]
        lines = [l for l in lines if l]
        for path, _ in [(p, 0) for p in _paths(lines)[0]]:
            op, size, bad = None, 0, False
            for line in path:
                m = re.match(r'\.(byte|hword|2byte|short|word|4byte|long)\s+(.*)$',
                             line)
                if not m:
                    bad = True
                    break
                vals = [v.strip() for v in m.group(2).split(',')]
                if op is None:
                    tok = vals[0]
                    if tok in symbols:
                        op = symbols[tok]
                    else:
                        try:
                            op = int(tok, 0)
                        except ValueError:
                            bad = True
                            break
                size += _WIDTH[m.group(1)] * len(vals)
            if not bad and op is not None:
                table.setdefault(op, set()).add((name, size))
    return table


def grammar():
    """(sizes, names) for this repo's engine, read from its own donor tree."""
    symbols = {}
    if ENGINE == 'emerald':
        order = 0
        for line in open(os.path.join(DONOR, 'data/script_cmd_table.inc'),
                         encoding='utf-8'):
            m = re.match(r'script_cmd_table_entry\s+(\S+?),?\s',
                         line.split('@')[0].strip() + ' ')
            if m:
                symbols[m.group(1)] = order
                order += 1
        src = open(os.path.join(DONOR, 'asm/macros/event.inc'),
                   encoding='utf-8').read()
    else:
        src = open(DONOR, encoding='utf-8').read()
    table = _macros(src, symbols)
    sizes = {op: sorted({s for _, s in v}) for op, v in table.items()}
    names = {op: sorted({n for n, _ in v})[0] for op, v in table.items()}
    return sizes, names


def _is_text(b, off, minlen=6):
    """Crude Gen 3 text test: printable-ish run terminated by 0xFF."""
    for i in range(200):
        if off + i >= len(b):
            return False
        c = b[off + i]
        if c == 0xFF:
            return i >= minlen
        if not (c == 0x00 or 0xA1 <= c <= 0xFE or 0x50 <= c <= 0x5A):
            return False
    return False


def sites(b, sizes, names):
    """{file offset: operand} for every giveegg reachable from a msgbox anchor."""
    todo = []
    for i in range(len(b) - 6):
        if b[i] == 0x0F and b[i + 1] == 0x00:
            p = struct.unpack_from('<I', b, i + 2)[0]
            if ROM_BASE <= p < ROM_BASE + len(b) and _is_text(b, p - ROM_BASE):
                todo.append(i)

    seen = bytearray(len(b))
    found = {}
    while todo:
        off = todo.pop()
        for _ in range(400):
            if off >= len(b) or seen[off]:
                break
            seen[off] = 1
            op = b[off]
            name = names.get(op)
            width = sizes.get(op)
            size = width[0] if (width and len(width) == 1) else None
            if op == GIVEEGG and off + 2 < len(b):
                found.setdefault(off, b[off + 1] | (b[off + 2] << 8))
            if size:
                if name in ('goto', 'call'):
                    t = struct.unpack_from('<I', b, off + 1)[0] - ROM_BASE
                    if 0 <= t < len(b):
                        todo.append(t)
                elif name in ('goto_if', 'call_if'):
                    t = struct.unpack_from('<I', b, off + 2)[0] - ROM_BASE
                    if 0 <= t < len(b):
                        todo.append(t)
            if op in TERMINATORS or size is None:
                break
            off += size
    return found


# ---------------------------------------------------------------- checks

failures = []
checks_run = 0


def check(name, ok, detail=""):
    global checks_run
    checks_run += 1
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                           (" -- " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def operand(v):
    return "VAR %#06x" % v if v >= VAR_BASE else "species %d" % v


def main():
    if not os.path.isfile(ROM):
        print("base ROM not found: %s" % os.path.relpath(ROM, ROOT))
        return 1
    with open(ROM, "rb") as f:
        b = f.read()

    sizes, names = grammar()
    found = sites(b, sizes, names)
    print("%s -- %d script opcodes known" % (GAME, len(sizes)))
    print("  %d giveegg site(s) reachable from dialogue, %d inventoried\n"
          % (len(found), len(INVENTORY)))

    # A decoder that resolves nothing finds nothing, and an empty result
    # satisfies every set comparison below. Zero is never a pass.
    check("the scan reached at least one giveegg site",
          bool(found),
          "no site found at all -- the grammar or the anchor test is broken, "
          "not the ROM")

    new = sorted(set(found) - set(INVENTORY))
    check("every giveegg site in the ROM is inventoried",
          not new,
          ", ".join("%#010x" % (ROM_BASE + o) for o in new)
          + " -- a gift egg nobody has looked at hatches into whatever it "
            "holds; identify the script, then add a verdict")

    gone = sorted(set(INVENTORY) - set(found))
    check("every inventoried site is still present in the ROM",
          not gone,
          ", ".join("%#010x" % (ROM_BASE + o) for o in gone))

    moved = sorted(o for o in set(found) & set(INVENTORY)
                   if found[o] != INVENTORY[o][0])
    check("every inventoried site still gives what it is recorded as giving",
          not moved,
          ", ".join("%#010x: %s -> %s" % (ROM_BASE + o, operand(INVENTORY[o][0]),
                                          operand(found[o])) for o in moved))

    # A verdict of GATED is a claim about this repo's code, not about the ROM.
    gated = [o for o in INVENTORY if INVENTORY[o][1] == "GATED"]
    hooked = bool(HATCH_HOOK) and os.path.isfile(os.path.join(ROOT, HATCH_HOOK))
    check("GATED verdicts exist exactly when this repo hooks the egg hatch",
          bool(gated) == hooked,
          ("%d site(s) claim GATED but %s is not present"
           % (len(gated), HATCH_HOOK or "no hatch hook is configured"))
          if gated else
          "the hatch hook %s is present but no site is marked GATED"
          % HATCH_HOOK)

    counts = {}
    for _op, verdict, _why in INVENTORY.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    print("\n  verdicts: " + ", ".join("%d %s" % (counts[k], k)
                                       for k in sorted(counts)))
    ungated = sorted(o for o in INVENTORY if INVENTORY[o][1] == "UNGATED")
    if ungated:
        print("  🔴 UNGATED means the egg hatches into whatever it holds and "
              "nothing checks the roster. See docs/GIFT_EGGS.md:")
        groups = {}
        for o in ungated:
            groups.setdefault(INVENTORY[o][2], []).append(o)
        for why in sorted(groups, key=lambda w: -len(groups[w])):
            offs = groups[why]
            print("     %d site(s): %s" % (len(offs), why))
            print("       " + ", ".join("%#010x %s" % (ROM_BASE + o,
                                                        operand(INVENTORY[o][0]))
                                        for o in offs))

    if assert_tally(checks_run, EXPECT_CHECKS, "check_gift_eggs"):
        return 1
    print("\n%s" % ("ALL PASS" if not failures
                    else "FAILURES: " + ", ".join(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
