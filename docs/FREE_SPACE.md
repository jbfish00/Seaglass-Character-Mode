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
