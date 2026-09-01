#!/bin/bash
# Negative test for tools/character_mode/verify_docs.py.
#
# A checker is only evidence on the runs where it executes, and only if it can
# actually fail. This repo's sibling shipped a verify_docs.py that could not
# PASS for weeks (its parser fell out of step with ROSTERS.md's shape and it
# reported 246 content failures), and the vacuous-harness work found layers that
# could not FAIL. Both stayed invisible because nobody ran them. So: tamper the
# docs on purpose and require a non-zero exit for each.
#
# ROSTERS.md is restored by a trap, so an interrupted run cannot leave the
# working tree dirty. verify_docs.py writes nothing, so no tampered data can
# reach a generator.
set -u
cd "$(dirname "$0")/../.." || exit 1
V=tools/character_mode/verify_docs.py
[ -f "$V" ] || { echo "SKIP: no verify_docs.py"; exit 0; }
BAK=$(mktemp); cp ROSTERS.md "$BAK"
trap 'cp "$BAK" ROSTERS.md; rm -f "$BAK"' EXIT

fail=0; pass=0
run() { # <label> <want-exit>
    python3 "$V" >/dev/null 2>&1
    local got=$?
    if [ "$got" = "$2" ]; then printf '  ok    %-46s exit=%s\n' "$1" "$got"; pass=$((pass+1))
    else printf '  FAIL  %-46s got %s want %s\n' "$1" "$got" "$2"; fail=1; fi
}

echo "verify_docs negative test"
run "control: untampered docs pass" 0

# 1. a roster loses a Pokemon the ROM still allows
python3 - <<'PY'
import re
out, killed = [], False
for l in open("ROSTERS.md", encoding="utf-8"):
    if not killed and re.match(r"^\| [A-Z][^|]*\| ", l) and "Pokémon |" not in l:
        killed = True; continue
    out.append(l)
assert killed, "found no data row to delete"
open("ROSTERS.md", "w", encoding="utf-8").writelines(out)
PY
run "a deleted roster row fails" 1
cp "$BAK" ROSTERS.md

# 2. a roster gains a Pokemon the ROM does not allow
python3 - <<'PY'
import re
s = open("ROSTERS.md", encoding="utf-8").read()
m = re.search(r"^\|---\|---\|$", s, re.M)
s = s[:m.end()] + "\n| Mewtwo | bogus, not in this bitmap |" + s[m.end():]
open("ROSTERS.md", "w", encoding="utf-8").write(s)
PY
run "a bogus roster row fails" 1
cp "$BAK" ROSTERS.md

# 3. the advertised character count drifts from what the ROM offers.
# ⚠️ The count line is phrased differently per repo ("**114 characters.**" vs
# "**123 selectable characters.**"), so bump whatever number this file actually
# advertises, and ASSERT THE TAMPER LANDED. A negative-test MISS in this
# workspace has more often been a tamper that hit nothing than a real gap in the
# checker; a tamper that changes no bytes makes a good checker look broken.
if python3 - <<'PYTAMPER'
import re, sys
s = open("ROSTERS.md", encoding="utf-8").read()
s2, n = re.subn(r"\*\*(\d+) ((?:selectable )?characters)", r"**999 \2", s, count=1)
if n != 1:
    sys.exit("TAMPER FAILED: no '**N characters' line in ROSTERS.md to bump")
open("ROSTERS.md", "w", encoding="utf-8").write(s2)
PYTAMPER
then run "a drifted character count fails" 1
else echo "  FAIL  could not tamper the character count"; fail=1
fi
cp "$BAK" ROSTERS.md

# 4. the parse guard: a heading with no rows under it
python3 - <<'PY'
import re
out, cur, dropped = [], None, 0
for l in open("ROSTERS.md", encoding="utf-8"):
    m = re.match(r"^### (.+?) — ", l)
    if m: cur = m.group(1)
    if cur and re.match(r"^\| ", l) and "Pokémon |" not in l and "---" not in l:
        dropped += 1; continue
    out.append(l)
    if dropped: cur = None      # empty only the first character
assert dropped
open("ROSTERS.md", "w", encoding="utf-8").writelines(out)
PY
run "an emptied roster fails as a PARSE error" 1
cp "$BAK" ROSTERS.md

run "restored: docs pass again" 0
[ $fail -eq 0 ] && echo "verify_docs negative test: $pass/$pass PASS" \
                || echo "verify_docs negative test: FAILURES"
exit $fail
