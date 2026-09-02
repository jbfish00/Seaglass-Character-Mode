#!/usr/bin/env python3
"""Emit per-character WILD-ENCOUNTER MARKER strings -- marker_strings.bin.

WHY THIS EXISTS (../../game_plans/rowe_parity.md §3). Character Mode's 10%
roster override hands the player a family ROOT, and an override that produces
a family root is INDISTINGUISHABLE from an ordinary encounter the map's own
table could have produced. ROWE measured the consequence: the median selectable
character matches ~2% of the game's own wild slots, so the override is doing
nearly all the work of building a team -- invisibly. Platinum then proved the
failure mode is real rather than theoretical: its first playthrough was reported
as "no on-roster encounters" when there was no bug at all, and naming the
character in the wild intro was the fix.

WHAT THE ENGINE NEEDS. The wild intro is picked in BufferStringBattle, which
loads one of several string pointers into r0 and falls into a single
    BattleStringExpandPlaceholders(src, dst)
call. We retarget that one call and swap `src` for one of these strings.

⚠️ WHY THE STRINGS ARE STATIC, ONE PER CHARACTER, RATHER THAN BUILT AT RUNTIME.
The obvious design is to build "…destined for <NAME>!" in a scratch buffer at
display time -- and this ROM has no RAM of its own to build it in. Seaglass's
legendary feature already had to spend 20 save flags for want of writable RAM.
Emitting one finished string per character costs ~9 KB of otherwise-dead ROM,
needs no buffer, no allocation and no lifetime reasoning, and cannot be
corrupted by anything the engine does to its own text buffers.

The mon's own name still comes from the engine: {FD}{06} is the
B_OPPONENT_MON1_NAME placeholder, copied verbatim out of the original string so
the expander sees exactly what it always saw.

Output: marker_strings.bin, NUM_CHARACTERS x STRIDE bytes, 0xFF-padded.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

def _resolve_charmap():
    """Path to this repo's vendored game-text charmap (tools/charmap.txt).

    This was a hardcoded absolute path into the unrelated "Pokemon Rowe
    Alteration" working tree, which made this repo unbuildable and
    unverifiable from a fresh clone. The charmap is now vendored here
    (byte-identical, md5 b31d142ca98103d64d707f9894fa42e3). Resolution is
    anchored to this file's own location, never the cwd.

    Override with the CM_CHARMAP environment variable.
    """
    import os
    from pathlib import Path
    override = os.environ.get("CM_CHARMAP")
    if override:
        p = Path(override)
        if not p.is_file():
            raise SystemExit("CM_CHARMAP=%s is not a file" % override)
        return p
    # Walk up to the REPO ROOT only. An unbounded walk would keep climbing past
    # the repo into ~ and could silently pick up an unrelated tools/charmap.txt
    # -- reading the wrong charmap presents as "this game encodes text
    # differently", not as a missing file. Bound it at the .git directory.
    for parent in Path(__file__).resolve().parents:
        cand = parent / "tools" / "charmap.txt"
        if cand.is_file():
            return cand
        if (parent / ".git").exists():
            break
    raise SystemExit(
        "charmap.txt not found. Expected it vendored at <repo>/tools/charmap.txt; "
        "set CM_CHARMAP to override.")

CHARMAP = str(_resolve_charmap())

# Copied byte-for-byte out of this ROM at 0x084C646C:
#   "Wild " {FD}{06} " appeared!" {FB} {FF}
PLACEHOLDER = bytes([0xFD, 0x06])   # B_OPPONENT_MON1_NAME
PARAGRAPH = 0xFB                    # the original's trailing control byte
NEWLINE = 0xFE
TERM = 0xFF

STRIDE = 64          # generous; the longest name here is well inside it


def load_charmap():
    """Byte-for-byte the injector's loader. Deliberately not a second
    implementation: the codes it produces have to agree with the ones the
    selection codes and character names were encoded with, and a charmap that
    disagreed by one entry would show as garbled text mid-battle, not as an
    error here."""
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    with open(CHARMAP, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if m and m.group(1) not in table:
                table[m.group(1)] = int(m.group(2), 16)
    return table


def enc(s, cm):
    out = bytearray()
    for ch in s:
        if ch not in cm:
            raise SystemExit(f"emit_marker_strings: {ch!r} not in charmap ({s!r})")
        out.append(cm[ch])
    return bytes(out)


def main():
    cm = load_charmap()
    with open(os.path.join(HERE, "characters_manifest.json")) as f:
        chars = json.load(f)["characters"]

    blob = bytearray()
    longest = 0
    for rec in chars:
        name = rec["character"]
        # Strip the " (anime)" disambiguator: it is a roster-data key, not
        # something to say to the player mid-battle.
        shown = name.replace(" (anime)", "")
        s = bytearray()
        s += enc("Wild ", cm)
        s += PLACEHOLDER
        s += enc(" appeared,", cm)
        s.append(NEWLINE)
        s += enc("destined for ", cm)
        s += enc(shown.upper(), cm)
        s += enc("!", cm)
        s.append(PARAGRAPH)
        s.append(TERM)
        if len(s) > STRIDE:
            raise SystemExit(
                "emit_marker_strings: %r needs %d bytes, STRIDE is %d -- raise "
                "STRIDE rather than silently truncating a character's marker"
                % (shown, len(s), STRIDE))
        longest = max(longest, len(s))
        blob += s + b"\xFF" * (STRIDE - len(s))

    out = os.path.join(HERE, "marker_strings.bin")
    with open(out, "wb") as f:
        f.write(blob)
    with open(os.path.join(HERE, "marker_strings_manifest.json"), "w") as f:
        json.dump({"count": len(chars), "stride": STRIDE,
                   "longest_used": longest, "bytes": len(blob)}, f, indent=1)
    print("marker_strings.bin: %d characters x %d = %d B (longest %d)"
          % (len(chars), STRIDE, len(blob), longest))


if __name__ == "__main__":
    main()
