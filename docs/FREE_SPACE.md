# Free Space Audit

ROM: `seaglass v3.0.gba` (SHA1 `b9f4d332d30fc88c379f9e037f9eae3b2755ead4`, 16 MiB / 0x1000000 bytes). Scanned via `tools/scan_free_space.py`.

## 0xFF-padded space (primary injection target)

One single contiguous run, occupying the entire tail of the ROM:

| ROM offset | length | notes |
|---|---|---|
| `0x00ED2164` | `0x12DE9C` (1,236,636 bytes / 1.18 MiB) | Runs exactly to `0x01000000` (end of file) — classic trailing free space. |

Total 0xFF-padded free space: **~1.18 MiB**, all in one block. Comparable in size to Unbound's largest single free block (337 KiB) but here it's one contiguous 1.18 MiB region rather than split across three — simpler to reason about for allocation, though everything competes for the same block so budget it deliberately (roster data: `characters.bin`/`rosters.bin`/`names.bin` currently ~1.2 KB names + a few KB rosters once Stage B lands; injected code; sprite assets in Phase 3).

## 0x00-padded space (NOT free space — do not use)

A scan for 0x00 runs ≥1 KiB found 64 runs totaling ~608 KiB scattered throughout the ROM (largest: 71,204 bytes @ `0x00A70C0C`). Unlike the trailing 0xFF block, these are very likely legitimate padding *within* real data structures (compressed graphics, tilemaps, alignment padding between tables) rather than genuinely unused space — GBA carts factory-blank to 0xFF, so 0xFF runs are the reliable "never written" signal, while 0x00 runs are ambiguous and risk corrupting real data if written into. **Do not treat these as injection targets** without per-run verification (e.g. checking what data immediately surrounds each run).

## Conclusion

Free space is not expected to be a bottleneck for Character Mode's data payload (roster/name tables are small — see `tools/character_mode/characters_manifest.json`, currently ~1.2 KB of names alone). The 1.18 MiB trailing 0xFF block at `0x00ED2164` is the primary target for both data injection and any new code routines Phase 1 needs to add.

## Hook trampolines and veneers as built (2026-10-30)

The free tail (`0x08ED2164`+) is out of BL reach of the battle and field code, so every BL-hooked site jumps through a
small veneer near it. ⚠️ The first trampolines sat in a "verified 64-byte 0xFF scavenge run" at `0x08470200` that is a
referenced sprite frame (`SpriteFrameImage {0x08470200, 0x40}` at `0x0895ED54`); a run of 0xFF is not free unless
nothing points at it (rowe_parity.md §13.53). It is now asserted byte-identical to the base.

| address | what lives there | why it is free |
|---|---|---|
| `0x081C3430` +0 / +8 / +16 / +24 | PC second guard, catch + gift gate, encounter marker, wild entry stub (12 B; the wild veneer itself is at `0x08FA8000`) | the standalone IsRemovingLastPartyMon: inlined at all call sites, no BL caller, no pointer (verify [22]) |
| `0x081C3458` | 100% catch veneer | the same function's tail + pool (verify [26]) |
| `0x081C3460` | new-game Exp. Share veneer | the pool's last two words. **The block is now full.** |
| `0x081FF724` | EXP rate veneer (getexp BL `0x0809441E`) | the standalone AddStartMenuAction (16 B + 8 B pool): every caller inlines it; no BL caller, no pointer, no word or short branch into it (verify [31]) |

Patched in place, no veneer: MoveBattleBar `0x0807CB10`, the START menu builder tail `0x081FF7A2` and input handler
`0x0820002A` (EXP rate). Data in the tail is listed by the injector's `*_ADDR` constants (EXP rate block `0x08FA9000`).
