/* Local handoff probe for nüvi 52LM HWID 1613 / software 3.30 ONLY.
 * No flash, filesystem, MMIO, or display writes. If the resident SD loader
 * accepts this payload, the device will park in an infinite loop until reset.
 * Both success and rejection require a normal reset afterward.
 */
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.balign 4
.global probe_start
.equ STAGE, 0x10040000
probe_start:
    b entry
    .word STAGE + (footer - probe_start)
    .word STAGE + (hwid - probe_start)
    .word STAGE + (version - probe_start)

entry:
    b entry
    .ltorg
    .balign 4
hwid:
    .hword 1613
version:
    .hword 330
footer:
    .hword 0xa55a
    .balign 4
probe_end:
