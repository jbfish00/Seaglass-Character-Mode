#!/usr/bin/env python3
"""NEGATIVE TEST for check_repo_selfcontained.py -- break it on purpose.

⭐ WHY. rowe_parity.md records, three separate times, that a "MISS" in a negative
test was a BAD TAMPER rather than a real gap: the tamper hit a comment, or hit
the wrong function, or picked a value that fails nothing. So every case here
asserts the tamper LANDED (the file really changed, in the way intended) before
it believes anything about the checker's verdict. A tamper that does not land is
reported as a BROKEN TEST, never as a pass.

It also runs a CONTROL: the untampered tree must PASS. Without that, a checker
that failed unconditionally would score perfectly here and look flawless.

Everything happens in a synthetic throwaway repo under a temp dir. The real tree
is never modified.

Run:  python3 tools/tests/check_repo_selfcontained_negative_test.py
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHECKER = os.path.join(HERE, "check_repo_selfcontained.py")
TALLY = os.path.join(HERE, "cm_tally.py")
REAL_CHARMAP = os.path.join(ROOT, "tools", "charmap.txt")
NEEDLE = "Pokemon Rowe Alteration"

RESOLVER = "\n".join([
    "import os",
    "from pathlib import Path",
    "def _resolve_charmap():",
    '    override = os.environ.get("CM_CHARMAP")',
    "    if override:",
    "        p = Path(override)",
    "        if not p.is_file():",
    '            raise SystemExit("CM_CHARMAP=%s is not a file" % override)',
    "        return p",
    "    for parent in Path(__file__).resolve().parents:",
    '        cand = parent / "tools" / "charmap.txt"',
    "        if cand.is_file():",
    "            return cand",
    '        if (parent / ".git").exists():',
    "            break",
    '    raise SystemExit("charmap.txt not found.")',
    "",
])

BOUND = '        if (parent / ".git").exists():\n            break\n'


def build(tmp):
    """A synthetic repo shaped like this one: a .git marker, a vendored
    charmap, a consumer that resolves it, and one inventoried donor tool."""
    repo = os.path.join(tmp, "fakerepo")
    os.makedirs(os.path.join(repo, ".git"))
    os.makedirs(os.path.join(repo, "tools", "tests"))
    shutil.copy(REAL_CHARMAP, os.path.join(repo, "tools", "charmap.txt"))
    shutil.copy(TALLY, os.path.join(repo, "tools", "tests", "cm_tally.py"))

    with open(os.path.join(repo, "tools", "consumer.py"), "w") as f:
        f.write(RESOLVER)

    with open(os.path.join(repo, "tools", "donor_tool.py"), "w") as f:
        f.write('ROWE = "/home/jbfish00/Documents/%s/x.json"\n' % NEEDLE)

    src = open(CHECKER, encoding="utf-8").read()
    start = src.index("ALLOWED = {")
    end = src.index("\n\n\ndef scan()", start)
    src = (src[:start]
           + 'ALLOWED = {"tools/donor_tool.py": "synthetic donor tool"}'
           + src[end:])
    with open(os.path.join(repo, "tools", "tests",
                           "check_repo_selfcontained.py"), "w") as f:
        f.write(src)
    return repo


def run(repo):
    r = subprocess.run(
        [sys.executable,
         os.path.join(repo, "tools", "tests", "check_repo_selfcontained.py")],
        capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def t_new_hardcode(repo):
    """A load-bearing script regains a hardcoded absolute ROWE path."""
    p = os.path.join(repo, "tools", "consumer.py")
    before = open(p).read()
    with open(p, "a") as f:
        f.write('\nCHARMAP = "/home/jbfish00/Documents/%s/charmap.txt"\n' % NEEDLE)
    after = open(p).read()
    return after != before and NEEDLE in after and NEEDLE not in before


def t_stale_inventory(repo):
    """An inventoried donor reference disappears -- the other direction."""
    p = os.path.join(repo, "tools", "donor_tool.py")
    had = NEEDLE in open(p).read()
    os.remove(p)
    return had and not os.path.exists(p)


def t_wrong_charmap(repo):
    """The vendored charmap is swapped for a different one. This is the trap
    that matters most: Seaglass ships a SECOND charmap with a different md5,
    and substituting it would change emitted text bytes."""
    p = os.path.join(repo, "tools", "charmap.txt")
    before = hashlib.md5(open(p, "rb").read()).hexdigest()
    with open(p, "a") as f:
        f.write("'~' = FE\n")
    return hashlib.md5(open(p, "rb").read()).hexdigest() != before


def t_missing_charmap(repo):
    p = os.path.join(repo, "tools", "charmap.txt")
    existed = os.path.isfile(p)
    os.remove(p)
    return existed and not os.path.exists(p)


def t_resolver_escapes(repo):
    """Remove the repo-root bound so the resolver climbs out of the repo and
    silently reads an unrelated charmap. This is the latent bug the bound was
    added to prevent, and it was measured reachable before the bound existed."""
    p = os.path.join(repo, "tools", "consumer.py")
    before = open(p).read()
    if BOUND not in before:
        return False
    after = before.replace(BOUND, "")
    open(p, "w").write(after)
    outer = os.path.join(os.path.dirname(repo), "tools")
    os.makedirs(outer, exist_ok=True)
    shutil.copy(os.path.join(repo, "tools", "charmap.txt"),
                os.path.join(outer, "charmap.txt"))
    os.remove(os.path.join(repo, "tools", "charmap.txt"))
    return after != before


TAMPERS = [
    ("a new hardcoded ROWE path in a load-bearing script", t_new_hardcode),
    ("an inventoried donor reference that no longer exists", t_stale_inventory),
    ("the vendored charmap replaced with a different one", t_wrong_charmap),
    ("the vendored charmap deleted outright", t_missing_charmap),
    ("the resolver's repo-root bound removed, so it escapes", t_resolver_escapes),
]

print("negative test: check_repo_selfcontained.py")
print("each case asserts the TAMPER LANDED before believing the verdict\n")

results = []

with tempfile.TemporaryDirectory() as tmp:
    rc, out = run(build(tmp))
    ok = rc == 0
    results.append(ok)
    print("  [%s] CONTROL: untampered tree passes (rc=%d)"
          % ("PASS" if ok else "FAIL", rc))
    if not ok:
        print("        " + "\n        ".join(out.strip().splitlines()[-6:]))

for desc, mutate in TAMPERS:
    with tempfile.TemporaryDirectory() as tmp:
        repo = build(tmp)
        landed = mutate(repo)
        if not landed:
            results.append(False)
            print("  [BROKEN] %s -- THE TAMPER DID NOT LAND. That is a broken "
                  "test, not a checker gap." % desc)
            continue
        rc, out = run(repo)
        ok = rc != 0
        results.append(ok)
        print("  [%s] %s -> checker rc=%d"
              % ("PASS" if ok else "MISS", desc, rc))
        if not ok:
            print("        checker did NOT notice. Output:")
            print("        " + "\n        ".join(out.strip().splitlines()[-6:]))

n_ok = sum(1 for r in results if r)
print("\n%d/%d" % (n_ok, len(results)))
print("ALL PASS" if n_ok == len(results) else "FAILED")
sys.exit(0 if n_ok == len(results) else 1)
