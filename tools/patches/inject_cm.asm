; Character Mode enforcement injection — Pokemon Emerald Seaglass v3.0.
; Places the compiled shim + per-character roster bitmap in the big free block,
; adds an 8-byte trampoline in BL range of the wild-catch caller, and retargets
; that caller's BL from GiveMonToPlayer -> trampoline -> the gated shim.
;
; Hook site (docs/ROUTINE_MAP.md, live catch-trace-confirmed):
;   0x080A6A46  bl 0x081AA5AC (GiveMonToPlayer)  ->  bl 0x08470200 (trampoline)
; CM_ENTRY (shim entry) is generated into build/cm_entry.asm by build_cm.sh.

.gba
.open "rom/seaglass v3.0.gba", "build/seaglass_cm.gba", 0x08000000

.include "build/cm_entry.asm"     ; .definelabel CM_ENTRY, 0x08ED21xx

; --- shim blob in free space ---
.org 0x08ED2164
.incbin "build/cm.bin"

; --- per-character allowed-species bitmap (rosters_expanded.bin) ---
.org 0x08ED2400
.incbin "tools/character_mode/rosters_expanded.bin"

; --- trampoline (Thumb): jump to the far shim entry ---
.org 0x08470200
.thumb
    ldr r3, [pc, #0]      ; -> word at 0x08470204
    bx  r3
    .word CM_ENTRY+1      ; CM_GiveMonToPlayerGated | 1 (Thumb)

; --- retarget the wild-catch caller's BL (primary hook) ---
.org 0x080A6A46
.thumb
    bl 0x08470200

; --- retarget the script-gift caller (ScriptGiveMon) — same trampoline, in
;     BL range (2.6 MB). Gates in-game gift Pokemon. The egg-hatch caller
;     0x08188514 is left original (eggs exempt). ---
.org 0x081F18DE
.thumb
    bl 0x08470200

.close
