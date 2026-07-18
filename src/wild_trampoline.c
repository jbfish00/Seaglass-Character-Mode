/* CM_WildMonSpecies_Trampoline -- a tiny standalone blob placed in a
 * SEPARATE scavenged free-space slot (0x08470208, immediately after the
 * existing 8-byte catch-gate trampoline at 0x08470200) because it must sit
 * within Thumb BL range (+-4 MiB) of BOTH:
 *   - the retargeted hook site: the BL to CreateMonWithIVs-simple inside the
 *     wild-encounter species/level roll, ROM file offset 0x22BF36
 *     (ROM addr 0x0822BF36) -- CONFIRMED live via mgba-headless breakpoint:
 *     hit once per wild encounter with r0=gEnemyParty, r1=rolled species,
 *     r2=rolled level, lr=0x0822BF3B (the original BL's return address).
 *   - the original target, CreateMonWithIVs-simple @ 0x081A7504 (confirmed
 *     via disasm: masks r1 to u16 species, r2 to u8 level, writes level to
 *     mon+0x54 directly, species via an internal SetMonData(field=18) call).
 * Both are within a few hundred KB of 0x08470208; the main Character Mode
 * shim blob (~0x08ED2200+, where CM_WildMonSpeciesGated actually lives,
 * alongside the roster bitmaps/wildpool data) is ~7.6 MiB away -- OUT of BL
 * range. This CPU (ARM7TDMI / ARMv4T, no BLX) has no absolute-address call
 * instruction, so reaching it needs the classic long-call idiom: manually
 * build a Thumb return address into lr, then `bx` to an absolute address
 * loaded via a PC-relative literal. The final hop to the untouched original
 * CreateMonWithIVs is a plain tail `bx` (not `bl`) so ITS OWN return goes
 * straight back to the real caller, completely skipping this trampoline.
 *
 * ABI: entered via the retargeted BL with r0=mon, r1=species, r2=level,
 * r3=fixedIV (CreateMonWithIVs's own args). Only r1 may end up different;
 * r0/r2/r3 and all stack args (this fn touches sp only via push/pop, net
 * zero) must reach the real CreateMonWithIVs unchanged.
 */
#ifndef GATED_FN_ADDR
#error "compile with -DGATED_FN_ADDR=<CM_WildMonSpeciesGated address>"
#endif
#ifndef ORIG_TARGET_ADDR
#define ORIG_TARGET_ADDR 0x081A7504u  /* CreateMonWithIVs-simple, CONFIRMED */
#endif

__attribute__((naked)) void CM_WildMonSpecies_Trampoline(void)
{
    /* Thumb POP cannot target lr directly (only push can; pop's equivalent
     * high bit is pc). To restore the caller's real return address into the
     * lr register without an extra spare register, the saved-lr stack slot
     * is peeked with a plain ldr (not popped) while sp still points below
     * it, then the remaining two words (fixedIV, scratch r4) are popped
     * normally and sp is manually advanced past the now-consumed lr slot.
     * Stack layout after `push {r0,r2,r3,r4,lr}` (5 words, ascending reg
     * order is how Thumb push/pop always lays consecutive words out):
     *   sp+0  = orig r0 (mon)
     *   sp+4  = orig r2 (level)
     *   sp+8  = orig r3 (fixedIV)
     *   sp+12 = orig r4 (scratch)
     *   sp+16 = orig lr (return-into-CreateWildMon)
     */
    __asm__ volatile(
        "push {r0, r2, r3, r4, lr}\n"
        "mov  r0, r1\n"                 /* r0 = species (CM_WildMonSpeciesGated arg1) */
        "mov  r1, r2\n"                 /* r1 = level   (CM_WildMonSpeciesGated arg2) */
        "adr  r4, 1f\n"                 /* r4 = word-aligned address of the local label */
        "add  r4, #1\n"                 /* set the Thumb bit for a valid return address */
        "mov  lr, r4\n"
        "ldr  r4, =%c[gated]\n"
        "bx   r4\n"                     /* long call: CM_WildMonSpeciesGated(species,level) */
        "1:\n"
        "mov  r1, r0\n"                 /* r1 = returned (possibly overridden) species (final) */
        "pop  {r0, r2}\n"               /* restore mon(r0), level(r2); sp now at fixedIV slot */
        "ldr  r3, [sp, #8]\n"           /* peek the saved-lr slot (fixedIV@0, scratch@4, lr@8) */
        "mov  lr, r3\n"
        "pop  {r3, r4}\n"               /* restore fixedIV(r3), scratch(r4) for real */
        "add  sp, #4\n"                 /* drop the now-consumed saved-lr slot */
        "ldr  r4, =%c[orig]\n"
        "bx   r4\n"                     /* tail jump; lr = return-into-CreateWildMon (correct) */
        :
        : [gated] "i" (GATED_FN_ADDR | 1), [orig] "i" (ORIG_TARGET_ADDR | 1)
    );
}
