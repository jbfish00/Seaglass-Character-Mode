; Character Mode enforcement injection — Pokemon Emerald Seaglass v3.0.
; Places the compiled shim (build/cm.bin, linked at 0x08ED2164, entry
; CM_GiveMonToPlayerGated = 0x08ED21A6) in the big free block, adds an 8-byte
; trampoline in BL range of the wild-catch caller, and retargets that caller's
; BL from GiveMonToPlayer -> the trampoline -> the gated shim.
;
; Hook site (docs/ROUTINE_MAP.md, live catch-trace-confirmed):
;   0x080A6A46  bl 0x081AA5AC (GiveMonToPlayer)  ->  bl 0x08470200 (trampoline)
; Trampoline scavenge: 0x08470200 (64 bytes of 0xFF padding, BL-reachable).

.gba
.open "rom/seaglass v3.0.gba", "build/seaglass_cm.gba", 0x08000000

; --- shim blob in free space ---
.org 0x08ED2164
.incbin "build/cm.bin"

; --- trampoline (Thumb): jump to the far shim entry ---
.org 0x08470200
.thumb
    ldr r3, [pc, #0]      ; -> word at 0x08470204
    bx  r3
    .word 0x08ED21A7      ; CM_GiveMonToPlayerGated | 1 (Thumb)

; --- retarget the wild-catch caller's BL ---
.org 0x080A6A46
.thumb
    bl 0x08470200

.close
