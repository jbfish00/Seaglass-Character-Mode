#!/usr/bin/env python3
"""Live-emulator verification of the wild-encounter species override (task
#5): drives tools/mgba_scripts/cm_wild_test.lua and cm_wild_stage_test.lua
via mgba-headless and checks the RESULT lines they print. Two things a pure
static check (verify_artifacts.py) can't prove: that the override actually
fires at a plausible rate on a real roll, and that when it fires the chosen
species is a real member of the active character's stage-fit pool for the
level in play -- not just "some non-legendary species".

Exit 0 = pass, matching the rest of the tools/tests/ suite.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
MGBA = ROOT / "tools" / "mgba_src" / "build" / "mgba-headless"
ROM = ROOT / "build" / "seaglass_cm.gba"
SAVESTATE = ROOT / "tools" / "savestates" / "at_8_8.ss"
CM = ROOT / "tools" / "character_mode"

CHAR_ID = 1  # Red

_p = _f = 0
def ok(cond, msg):
    global _p, _f
    if cond:
        _p += 1
        print(f"  PASS {msg}")
    else:
        _f += 1
        print(f"  FAIL {msg}")


def run(script, env_extra, timeout=60):
    env = dict(os.environ)
    env["MGBA_HEADLESS_DEBUGGER"] = "1"
    env.update(env_extra)
    r = subprocess.run(
        [str(MGBA), "--script", str(ROOT / "tools" / "mgba_scripts" / script),
         "-t", str(SAVESTATE), str(ROM)],
        env=env, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


RESULT_RE = re.compile(
    r"RESULT pre_species=(\S+) (?:pre_level=(\S+) )?post_species=(\S+) overridden=(\S+)")


def parse_result(log):
    m = None
    for line in log.splitlines():
        m2 = RESULT_RE.search(line)
        if m2:
            m = m2
    if not m:
        return None
    pre, _lvl, post, overridden = m.groups()
    return {
        "pre": None if pre == "nil" else int(pre),
        "post": None if post == "nil" else int(post),
        "overridden": overridden == "true",
    }


def load_pool(char_id):
    manifest = json.loads((CM / "wildpool_manifest.json").read_text())
    return manifest["characters"][char_id - 1]


def load_legendary_names():
    sys.path.insert(0, str(CM))
    from emit_characters import LEGENDARY_BASES
    import map_species as M
    name_to_const, _ = M.load_donor()
    const_to_name = {v: k for k, v in name_to_const.items()}
    return {const_to_name[c] for c in LEGENDARY_BASES if c in const_to_name}


def species_name(sid):
    sp_table = json.loads((CM / "rom_species_table.json").read_text())["species"]
    return sp_table.get(str(sid), "?")


def main():
    if not ROM.exists():
        print("build first: python3 tools/inject_character_mode.py")
        sys.exit(1)

    pool = load_pool(CHAR_ID)
    pool_ids = {e["species_id"]: e["min_level"] for e in pool["pool"]}
    legend_names = load_legendary_names()
    print(f"testing char {CHAR_ID} ({pool['character']}), pool size {len(pool_ids)}")

    # --- 1. stage-fit test: force a high rolled level, retry across a few
    # START_DELAYs until the 10% gate fires, then check the chosen species is
    # a real pool member near the forced level and never a legendary. ---
    forced_level = 45
    stage_hit = None
    for delay in range(1, 40, 3):
        log = run("cm_wild_stage_test.lua",
                   {"CM_CHAR": str(CHAR_ID), "FORCE_LEVEL": str(forced_level),
                    "START_DELAY": str(delay)})
        r = parse_result(log)
        if r and r["overridden"]:
            stage_hit = r
            print(f"  (fired at START_DELAY={delay}: {r})")
            break
    ok(stage_hit is not None, "stage-fit test: override fired within 14 retries")
    if stage_hit:
        post = stage_hit["post"]
        ok(post in pool_ids, f"forced-level override species {post} ({species_name(post)}) is in char's pool")
        ok(species_name(post) not in legend_names,
           f"forced-level override species {post} ({species_name(post)}) is not legendary")
        if post in pool_ids:
            lvl = pool_ids[post]
            # nearest-at-or-below: no pool entry should sit strictly between
            # this stage's level and the forced level.
            better = [sid for sid, l in pool_ids.items() if lvl < l <= forced_level]
            ok(not better, f"no closer-fitting stage exists for level {forced_level} "
                            f"(picked min_level={lvl}, would-be-better={better})")

    # --- 2. rate sample: unforced, natural low-level (2-3) Route 101 rolls,
    # varied START_DELAY for genuine seed variation. Every override observed
    # must be a valid non-legendary pool member; the aggregate rate is a soft
    # (logged, not hard-failed) sanity check against the intended 10%. ---
    n_trials = 20
    hits = 0
    bad_species = []
    for delay in range(0, n_trials * 4, 4):
        log = run("cm_wild_test.lua",
                   {"CM_ON": "1", "CM_CHAR": str(CHAR_ID), "START_DELAY": str(delay)})
        r = parse_result(log)
        if not r:
            continue
        if r["overridden"]:
            hits += 1
            post = r["post"]
            if post not in pool_ids or species_name(post) in legend_names:
                bad_species.append(post)
    rate = hits / n_trials * 100
    print(f"  rate sample: {hits}/{n_trials} overridden ({rate:.1f}%, target ~10%)")
    ok(not bad_species, f"every sampled override is a valid non-legendary pool member (bad: {bad_species})")
    # soft sanity: fail only if wildly outside a generous band (this is a
    # statistical sample of a Bernoulli(0.10, n=20); 0-6 hits is unsurprising).
    ok(0 <= hits <= 8, f"override rate in a plausible band for p=0.10,n={n_trials} ({hits} hits)")

    # --- 3. CM off must never override (deterministic, single trial). ---
    log = run("cm_wild_test.lua", {"CM_ON": "0"})
    r = parse_result(log)
    ok(r is not None and not r["overridden"], "CM off: never overridden (control)")

    print(f"\n{_p} passed, {_f} failed")
    print("RESULT: PASS" if _f == 0 else "RESULT: FAIL")
    sys.exit(1 if _f else 0)


if __name__ == "__main__":
    main()
