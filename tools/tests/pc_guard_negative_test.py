#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [22] -- the PC second guard
(ROWE's IsRemovingLastAllowedPartyMon, 2026-09-29).

Each case breaks a COPY of the built ROM in one way the guard's patch could be
wrong and requires the matching check to report FAIL BY NAME. A tampered ROM
also fails the BPS round-trip, so a bare non-zero exit would prove nothing.
Checks that must stay SILENT prove the tamper was precise.

  1. control                       -- the real build passes all [22] checks
  2. one deposit site left behind  -- a site still calls the vanilla count,
                                      so one PC path skips the guard
  3. the trampoline aimed elsewhere -- at the party sweep, a REAL shim entry:
                                      the plausible-wrong shape
  4. CanShiftMon's tail reverted   -- the guard's final answer would be read
                                      as a count and the swap rule lost
  5. the dispatch address bent     -- the compiled guard compares its return
                                      address against 0x081C3534 instead of
                                      0x081C3530: CanShiftMon would be treated
                                      as a deposit site and compile fine
  6. control again                 -- proves 2-5 left nothing behind

⚠️ THE ROM IS NEVER MODIFIED IN PLACE.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cm_tally import assert_cases  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")

# Derived from the injector, never restated.
_INJ = open(os.path.join(ROOT, "tools", "inject_character_mode.py"),
            encoding="utf-8").read()


def _inj(name):
    return int(re.search(rf"^{name}\s*=\s*(0x[0-9A-Fa-f]+)", _INJ, re.M).group(1), 16)


TRAMP = _inj("PSS_GUARD_TRAMPOLINE_ADDR") - 0x08000000
TAIL = _inj("PSS_CANSHIFT_TAIL")
COUNT = _inj("PSS_COUNT_ALIVE_EXCEPT")
FIRST_SITE = int(re.search(r"^PSS_GUARD_BL_SITES\s*=\s*\((0x[0-9A-Fa-f]+)",
                           _INJ, re.M).group(1), 16)
CANSHIFT_RET = 0x081C3530


def _syms():
    out = subprocess.run(["arm-none-eabi-nm", os.path.join(ROOT, "build", "cm.elf")],
                         check=True, capture_output=True, text=True).stdout
    return {m.group(2): int(m.group(1), 16)
            for m in re.finditer(r"^([0-9a-f]+) [Tt] (\w+)$", out, re.M)}


def thumb_bl(src, dst):
    off = ((dst - (src + 4)) >> 1) & 0x3FFFFF
    return struct.pack("<HH", 0xF000 | ((off >> 11) & 0x7FF), 0xF800 | (off & 0x7FF))


CHECKS = {
    "sites": "sites call the guard trampoline",
    "tramp": "trampoline is ldr r3,[pc]; bx r3 -> CM_PSSLastMonGuard",
    "tail": "CanShiftMon tail:",
    "lits": "compiled guard carries 0x081C3530",
}


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_pcguard.%d.py" % os.getpid())  # unique per run; gitignored
    open(path, "w", encoding="utf-8").write(src)
    try:
        p = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, cwd=ROOT, env=_child_env())
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return p.returncode, p.stdout + p.stderr


def _hit(out, key, marker):
    return any(line.strip().startswith(marker) and CHECKS[key] in line
               for line in out.splitlines())


# A deliberate LITERAL -- see cm_tally.assert_cases.
EXPECT_CASES = 6


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
    syms = _syms()
    guard_off = (syms["CM_PSSLastMonGuard"] & ~1) - 0x08000000
    fails, passes = [], 0

    with tempfile.TemporaryDirectory() as tmp:

        def case(name, mutate, want_fail, also_pass=()):
            nonlocal passes
            data = bytearray(good)
            if mutate is not None:
                mutate(data)
                if data == good:
                    fails.append(name)
                    print("  [MISS] %s -- TAMPER CHANGED NOTHING" % name)
                    return
            rom = os.path.join(tmp, "tampered.gba")
            open(rom, "wb").write(bytes(data))
            _rc, out = run(rom)
            if want_fail is None:
                ok = all(_hit(out, k, "PASS") for k in CHECKS)
                detail = "every [22] check passes"
            else:
                ok = _hit(out, want_fail, "FAIL")
                detail = "%r reported FAIL" % CHECKS[want_fail]
                for k in also_pass:
                    if not _hit(out, k, "PASS"):
                        ok = False
                        detail += "; but %r did not PASS" % CHECKS[k]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: verify_artifacts [22] PC second guard")
        case("1 control -- the real build", None, None)

        def leave_site(d):
            d[FIRST_SITE:FIRST_SITE + 4] = thumb_bl(0x08000000 + FIRST_SITE, COUNT)
        case("2 one deposit site still calls the vanilla count", leave_site,
             "sites", also_pass=("tramp", "tail", "lits"))

        def aim_elsewhere(d):
            struct.pack_into("<I", d, TRAMP + 4, syms["CM_SweepPartyToPCNative"] | 1)
        case("3 the trampoline aimed at the party sweep", aim_elsewhere,
             "tramp", also_pass=("sites", "tail", "lits"))

        def revert_tail(d):
            d[TAIL:TAIL + 4] = bytes.fromhex("0028f4d1")
        case("4 CanShiftMon's tail reverted", revert_tail, "tail",
             also_pass=("sites", "tramp", "lits"))

        def bend_dispatch(d):
            code = bytes(d[guard_off:guard_off + 0x200])
            k = next((k for k in range(0, len(code) - 3, 4)
                      if struct.unpack_from("<I", code, k)[0] == CANSHIFT_RET), None)
            assert k is not None, "guard literal 0x081C3530 not found -- re-derive"
            struct.pack_into("<I", d, guard_off + k, CANSHIFT_RET + 4)
        case("5 the dispatch address bent to 0x081C3534", bend_dispatch,
             "lits", also_pass=("sites", "tramp", "tail"))

        case("6 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "pc_guard_negative_test")


if __name__ == "__main__":
    sys.exit(main())
