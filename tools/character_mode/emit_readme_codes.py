#!/usr/bin/env python3
"""Regenerate README.md's "## Character codes" section from the injected data.

The code a player types at the mart clipboard is derived from the character name
by exactly one rule (tools/inject_character_mode.py's `code_for`): strip accents,
drop every non-alphanumeric character, cap at 10, because the CODE naming screen
takes no more. Keeping the tables hand-written meant they went stale the moment
the roster moved -- which is how Radical Red shipped 15 characters with no
documented code at all, and how this README came to list 193 codes when only 153
of them work.

Everything comes from characters_manifest.json, so this section cannot drift from
the patch again.

Hidden characters -- those under the six-fully-evolved playability threshold,
whose code slot the injector poisons -- are OMITTED. Their code is refused at the
naming screen, so listing it would document something that does not work.

⚠️ `code_for` here must mirror the injector's exactly, including NOT stripping a
" (anime)" suffix: the injector encodes the full display name, so Kiawe (anime)
is genuinely typed `Kiaweanime`. A sibling port that stripped it documented four
codes the ROM does not accept.

Run after emit_characters.py --final:
    python3 tools/character_mode/emit_readme_codes.py
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.abspath(os.path.join(HERE, "..", ".."))
README = os.path.join(TARGET, "README.md")

SECTION_START = "## Character codes"
SECTION_END = "## Notes & limitations"

# The README's own headings; kept so regenerating does not restyle the document.
REGION = {1: "Kanto", 2: "Johto", 3: "Hoenn", 4: "Sinnoh", 5: "Unova",
          6: "Kalos", 7: "Alola", 8: "Galar", 9: "Paldea"}


def code_for(display):
    """Mirrors tools/inject_character_mode.py's code_for exactly."""
    n = unicodedata.normalize("NFKD", display)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return "".join(ch for ch in n if ch.isalnum())[:10]


def main():
    with open(os.path.join(HERE, "characters_manifest.json"), encoding="utf-8") as f:
        chars = json.load(f)["characters"]

    # Fail loudly rather than documenting every character as selectable: a
    # manifest without the field predates the threshold entirely.
    if any("hidden" not in rec for rec in chars):
        raise SystemExit("characters_manifest.json predates the playability "
                         "threshold (no 'hidden' field) -- re-run "
                         "derive_drops.py then emit_characters.py --final")
    n_total = len(chars)
    n_hidden = sum(1 for rec in chars if rec["hidden"])
    chars = [rec for rec in chars if not rec["hidden"]]

    by_gen = defaultdict(list)
    for rec in chars:
        by_gen[rec["generation"]].append(rec)
    for g in by_gen:
        by_gen[g].sort(key=lambda r: r["character"])

    out = [SECTION_START, "",
           "Codes are the character's name with spaces and punctuation removed.",
           "Case is ignored. **%d selectable characters** across all nine"
           % len(chars),
           "generations:", ""]
    for gen in sorted(by_gen):
        out += ["### Gen %d — %s" % (gen, REGION.get(gen, "?")), "",
                "| Code | Character |", "|---|---|"]
        for rec in by_gen[gen]:
            out.append("| `%s` | %s |" % (code_for(rec["character"]),
                                          rec["character"]))
        out.append("")
    out += [
        "### Characters that are not offered in Seaglass", "",
        "%d of the %d characters in the table are **not selectable here** and "
        "their codes are refused." % (n_hidden, n_total),
        "Seaglass's dex is a curated subset -- all of Gen 1-3 plus a small set of",
        "later cross-gen evolutions -- so those characters cannot field six fully",
        "evolved Pokemon in this game, and picking them would mean catching almost",
        "nothing for the whole run. They keep their slot internally so existing",
        "saves still load correctly; they simply cannot be chosen.", "",
    ]

    with open(README, encoding="utf-8") as f:
        text = f.read()
    try:
        start, end = text.index(SECTION_START), text.index(SECTION_END)
    except ValueError:
        raise SystemExit("emit_readme_codes: could not find the %r .. %r section "
                         "boundaries in README.md" % (SECTION_START, SECTION_END))
    text = text[:start] + "\n".join(out) + "\n" + text[end:]

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)

    # Any surviving hardcoded total elsewhere in the README is the same drift
    # this script exists to stop, one paragraph away from the part it fixed.
    # Scan only OUTSIDE the regenerated section -- the section legitimately says
    # "40 of the 193 characters in the table", and matching your own output is
    # how a guard becomes noise that gets ignored.
    outside = text[:text.index(SECTION_START)] + text[text.index(SECTION_END):]
    stale = [m.group(0) for m in re.finditer(r"\b%d characters?\b" % n_total, outside)]
    if stale:
        print("  !! README still says %r outside the codes section -- "
              "check it by hand" % stale[0], file=sys.stderr)
    print("rewrote README.md's character-code tables: %d selectable of %d "
          "(%d hidden below the threshold, omitted) across generations %s"
          % (len(chars), n_total, n_hidden,
             ", ".join(str(g) for g in sorted(by_gen))))


if __name__ == "__main__":
    main()
