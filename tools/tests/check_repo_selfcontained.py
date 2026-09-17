#!/usr/bin/env python3
"""INVENTORY every reference this repo still makes to the unrelated ROWE tree.

⭐ WHY THIS EXISTS.

Until 2026-09-02 this repo hardcoded the absolute path
"/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt" in its INJECTOR
and in verify_artifacts.py, so it could not be built or verified at all from a
fresh clone -- the ROM build silently depended on an unrelated project's working
tree existing at one particular absolute path on one particular machine.
rowe_parity.md recorded this as affecting only marker-string regeneration, which
understated it by a lot. The charmap is now VENDORED at tools/charmap.txt and
every consumer resolves it from its own location.

⚠️ This is an INVENTORY, not a grep, for the reason lesson #1 gives: a checker
that greps the files which already contain a fix cannot see a NEW file that
lacks one. So it enumerates every surviving reference repo-wide and demands a
stated reason for each. A newly-introduced hardcoded path is then a FAILING
CHECK rather than a silent arrival.

The surviving references are all cross-repo DONOR tools -- scripts whose whole
job is importing data out of ROWE. Those are legitimately absolute. What must
never come back is a reference on the BUILD or VERIFY path.

Run:  python3 tools/tests/check_repo_selfcontained.py   (0 = ok, 1 = changed)
"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from cm_tally import assert_tally          # noqa: E402

NEEDLE = "Pokemon Rowe Alteration"
CHARMAP_MD5 = "b31d142ca98103d64d707f9894fa42e3"

# ⭐ ADDED 2026-09-16. NEEDLE alone was too narrow: it pins the ROWE tree and is
# blind to a dependency on a SIBLING HACK REPO. That hole let Lazarus ship a
# patch tool importing lz77 through ../../Unbound-Character-Mode/tools -- a
# cross-repo import arriving silently past a checker written to prevent exactly
# that. Lesson #1: the checker scanned for ONE path rather than for THE THING
# (a dependency outside this repo). Ported here from Lazarus.
SIBLING_RE = re.compile(r"(?:RadicalRed|Unbound|Prism|Platinum|Lazarus)"
                        r"-Character-Mode")

# How many checks this layer must run. A deliberate LITERAL -- see cm_tally.py.
EXPECT_CHECKS = 7

# Third-party / vendored trees we did not write and do not police.
SKIP_DIRS = {
    "ghidra", "ghidra_11.4.2", "ghidra_prism_proj", "ghidraboy_src", "rgbds",
    "pokecrystal_donor", "cfru_donor", "dpe_unbound_donor",
    "pokeemerald_expansion_donor", "bindiff_venv", "emu_venv", "__pycache__",
    "node_modules", ".git",
}

# path -> why this reference is allowed to survive.
ALLOWED = {'tools/tests/check_repo_selfcontained_negative_test.py': "THIS CHECKER'S OWN NEGATIVE TEST. It must name the forbidden path in order to reintroduce it on purpose in a throwaway tree. Inventoried rather than skipped, so deleting the negative test is itself a failing check.", 'tools/character_mode/sprite_coverage_survey.py': "cross-repo DONOR tool: reads ROWE's sprite_report.txt. Survey only, never on the build or verify path."}


# path -> why this SIBLING-REPO reference is allowed to survive.
# ⭐ NOTE: this repo OWNS the shared mgba-headless build that Lazarus's and
# Radical Red's live suites borrow, so it has no emulator dependency of its own.
ALLOWED_SIBLING = {
    "tools/character_mode/port_sibling_sources.py":
        "cross-repo DONOR tool by design: imports Radical Red's "
        "roster_sources.json. Never on the build or verify path.",
    "tools/character_mode/port_sibling_additions.py":
        "cross-repo DONOR tool by design: imports Radical Red's "
        "roster_additions.json. Never on the build or verify path.",
    "tools/character_mode/sprite_coverage_survey.py":
        "COMMENT only -- names Radical Red's SPRITE_COVERAGE.md as the output "
        "format it mirrors. No path is opened.",
    "tools/character_mode/map_species.py":
        "COMMENT only -- attribution prose about Unbound's version. No path is "
        "opened.",
    "tools/character_mode/emit_characters.py":
        "COMMENT only -- attribution prose ('adapted from Unbound's'). No path "
        "is opened.",
    "tools/tests/check_repo_selfcontained_negative_test.py":
        "THIS CHECKER'S OWN NEGATIVE TEST. It must name a sibling repo in order "
        "to reintroduce the dependency on purpose in a throwaway tree. "
        "Inventoried rather than skipped, so deleting the negative test is "
        "itself a failing check.",
}


def scan():
    """{relpath: [line numbers]} for every file under tools/ naming ROWE."""
    return _scan(lambda ln: NEEDLE in ln)


def scan_siblings():
    """{relpath: [line numbers]} for every file under tools/ naming a SIBLING repo."""
    return _scan(lambda ln: SIBLING_RE.search(ln) is not None)


def _scan(match):
    hits = {}
    base = os.path.join(ROOT, "tools")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith((".py", ".sh", ".lua", ".gdb")):
                continue
            full = os.path.join(dirpath, fn)
            # Skip THIS file. Its docstring and its NEEDLE constant both spell
            # out the path it exists to forbid, so an un-skipped scan reports
            # the checker itself as a violation -- every run, forever.
            if os.path.abspath(full) == os.path.abspath(__file__):
                continue
            rel = os.path.relpath(full, ROOT)
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            found = [i + 1 for i, ln in enumerate(lines) if match(ln)]
            if found:
                hits[rel] = found
    return hits


def resolvers():
    """Files that define _resolve_charmap, and what each resolves to."""
    out = {}
    base = os.path.join(ROOT, "tools")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            src = open(full, encoding="utf-8", errors="replace").read()
            if "def _resolve_charmap" not in src:
                continue
            # Resolve the same way the function does, from THIS file's location.
            cur, got = os.path.dirname(os.path.abspath(full)), None
            while True:
                cand = os.path.join(cur, "tools", "charmap.txt")
                if os.path.isfile(cand):
                    got = cand
                    break
                if os.path.exists(os.path.join(cur, ".git")):
                    break
                nxt = os.path.dirname(cur)
                if nxt == cur:
                    break
                cur = nxt
            out[os.path.relpath(full, ROOT)] = got
    return out


failures = []
ran = 0

hits = scan()

# [1] every surviving ROWE reference is inventoried with a reason
ran += 1
uninventoried = sorted(set(hits) - set(ALLOWED))
if uninventoried:
    failures.append(
        "NEW hardcoded reference(s) to the ROWE tree, with no stated reason:\n" +
        "\n".join("    %s (line %s)" % (p, ",".join(map(str, hits[p])))
                  for p in uninventoried) +
        "\n  If this is a new cross-repo donor tool, add it to ALLOWED with a "
        "reason. If it is on the BUILD or VERIFY path, it must resolve "
        "tools/charmap.txt from its own location instead -- that is the whole "
        "point of this check.")

# [2] every inventoried reference is still present (the other direction)
ran += 1
stale = sorted(set(ALLOWED) - set(hits))
if stale:
    failures.append(
        "inventoried reference(s) no longer present -- delete them from ALLOWED:\n" +
        "\n".join("    %s" % p for p in stale))

# [3] the vendored charmap exists and is the expected file
ran += 1
cm = os.path.join(ROOT, "tools", "charmap.txt")
if not os.path.isfile(cm):
    failures.append("tools/charmap.txt is MISSING. Every text tool in this repo "
                    "resolves it; without it the build cannot run.")
else:
    got = hashlib.md5(open(cm, "rb").read()).hexdigest()
    if got != CHARMAP_MD5:
        failures.append(
            "tools/charmap.txt md5 is %s, expected %s. A DIFFERENT charmap "
            "changes emitted text bytes. Note this repo may also vendor a "
            "donor charmap with a different md5 -- they are not "
            "interchangeable." % (got, CHARMAP_MD5))

# [4] every _resolve_charmap lands on THIS repo's vendored copy
ran += 1
res = resolvers()
bad = {p: v for p, v in res.items()
       if v is None or os.path.abspath(v) != os.path.abspath(cm)}
if bad:
    failures.append(
        "resolver(s) not landing on this repo's tools/charmap.txt:\n" +
        "\n".join("    %s -> %s" % (p, v) for p, v in sorted(bad.items())))

# [5] the inventory is not vacuous. If every consumer were deleted, checks 1-4
#     would all still pass while proving nothing, so assert consumers exist.
ran += 1
if not res:
    failures.append(
        "NO file in this repo resolves the vendored charmap. Checks [1]-[4] "
        "are then vacuously true. Either the text tooling was removed, or this "
        "checker is looking in the wrong place.")

# [6] every reference to a SIBLING hack repo is inventoried with a reason.
ran += 1
sib = scan_siblings()
sib_uninv = sorted(set(sib) - set(ALLOWED_SIBLING))
if sib_uninv:
    failures.append(
        "NEW reference(s) to a SIBLING hack repo, with no stated reason:\n" +
        "\n".join("    %s (line %s)" % (p_, ",".join(map(str, sib[p_])))
                  for p_ in sib_uninv) +
        "\n  A sibling repo is not this repo. If it is a donor tool or a "
        "shared tool binary, add it to ALLOWED_SIBLING with a reason. If it is "
        "a code import, VENDOR the module into this repo's own tools/ and "
        "resolve it from the importing file's location -- a fresh clone of "
        "this repo alone must still build and verify.")

# [7] the other direction: the sibling inventory cannot rot into fiction.
ran += 1
sib_stale = sorted(set(ALLOWED_SIBLING) - set(sib))
if sib_stale:
    failures.append(
        "inventoried sibling reference(s) no longer present -- delete them "
        "from ALLOWED_SIBLING:\n" + "\n".join("    %s" % p_ for p_ in sib_stale))

print("%s -- self-contained check" % os.path.basename(ROOT))
print("  %d file(s) still name the ROWE tree, %d inventoried"
      % (len(hits), len(ALLOWED)))
for p in sorted(ALLOWED):
    mark = "ok " if p in hits else "GONE"
    print("    [%s] %s" % (mark, p))
    print("           %s" % ALLOWED[p])
print("  %d file(s) resolve tools/charmap.txt" % len(res))
print("  %d file(s) name a sibling hack repo, %d inventoried"
      % (len(sib), len(ALLOWED_SIBLING)))
_real = sorted(p_ for p_ in sib if p_ in ALLOWED_SIBLING
               and not ALLOWED_SIBLING[p_].startswith("COMMENT"))
print("    of which %d are REAL dependencies (not comments):" % len(_real))
for p_ in _real:
    print("      %s" % p_)
print()

rc = 0
for f in failures:
    print("  [FAIL] %s" % f)
    rc = 1
if not failures:
    print("  [PASS] no un-inventoried reference to the ROWE tree")
    print("  [PASS] every inventoried reference is still present")
    print("  [PASS] tools/charmap.txt present, md5 %s" % CHARMAP_MD5)
    print("  [PASS] all %d resolver(s) land on this repo's own copy" % len(res))
    print("  [PASS] the inventory is not vacuous -- consumers exist")
    print("  [PASS] no un-inventoried reference to a sibling hack repo")
    print("  [PASS] every inventoried sibling reference is still present")

rc |= assert_tally(ran, EXPECT_CHECKS, "check_repo_selfcontained")
print()
print("ALL PASS" if rc == 0 else "FAILED")
sys.exit(rc)
