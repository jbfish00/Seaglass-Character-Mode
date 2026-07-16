; Toolchain validation patch — NOT part of Character Mode itself.
; Writes a harmless marker string into the trailing 0xFF free-space block
; (docs/FREE_SPACE.md: 0x00ED2164-EOF), which nothing in the ROM references,
; to prove the armips -> flips -> boot-test pipeline works end to end before
; any real hook is attempted.
.gba
.open "rom/seaglass v3.0.gba", "build/test_roundtrip.gba", 0x08000000
.org 0x08ED2164
.ascii "SEAGLASS_CM_TOOLCHAIN_ROUNDTRIP_TEST_OK"
.close
