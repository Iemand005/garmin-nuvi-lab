/* Offline candidate for nuvi 350-family HWID 0476 / software 6.20 ONLY.
 * Not deployment-approved merely by building it. No stock loader code used.
 * Reads LCD/DMA registers; NEVER writes peripheral registers or flash.
 * Draws a persistent64x64 monochrome checkerboard in one validated framebuffer.
 * Both success and rejection PARK: physical reset is required afterward.
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
    cmp r12, #2
    bne park
    /* Enabled TFT / palette-and-data path; no timing or orientation writes. */
    ldr r0, =0xfffec000
    ldr r1, [r0]
    and r2, r1, #0x81
    cmp r2, #0x81
    bne park
    tst r1, #0x00300000
    bne park
    /* Both exact dimension profiles are present in this350 firmware.
     * Resident TIMING1/TIMING2 values: 0x3106253f/0x120008ef or
     * 0x051438ef/0x0605093f. Select matching RAM stride, never reprogram LCD.
     */
    ldr r2, [r0, #4]
    ldr r3, =0x3ff
    and r2, r2, r3
    ldr r1, [r0, #8]
    and r1, r1, r3
    ldr r3, =319
    cmp r2, r3
    beq landscape
    cmp r2, #239
    bne park
    cmp r1, r3
    bne park
    mov r8, #480
    ldr r9, =0xf0d0
    b profile_ready
landscape:
    cmp r1, #239
    bne park
    mov r8, #640
    ldr r9, =0xdd20
profile_ready:

    /* Snapshot programmed DMA B1 start/end using halfword accesses. */
    ldr r7, =0xfffee3c0
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    ldr r0, =0x11fda7e0
    cmp r4, r0
    beq known_buffer
    ldr r0, =0x11fb4fc0
    cmp r4, r0
    bne park
known_buffer:
    sub r5, r5, r4
    ldr r0, =0x2581e
    cmp r5, r0
    bne park
    ldrh r0, [r4]
    and r0, r0, #0x7000
    cmp r0, #0x4000
    bne park
    /* Reject a source change while snapshotting. */
    ldrh r0, [r7, #8]
    ldrh r2, [r7, #10]
    orr r0, r0, r2, lsl #16
    cmp r0, r4
    bne park

    /* Centered64x64 board. White/black survives either RGB pixel layout.
     * Keep the pattern visible until reset; do not return to overwritten stock code.
     */
    add r4, r4, r9
    ldr r2, =0xffff
    mov r6, #0
marker_row:
    mov r5, #0
marker_pixel:
    mov r0, r6, lsr #4
    eor r0, r0, r5, lsr #4
    tst r0, #1
    moveq r0, #0
    movne r0, r2
    strh r0, [r4], #2
    add r5, r5, #1
    cmp r5, #64
    bne marker_pixel
    sub r0, r8, #128
    add r4, r4, r0
    add r6, r6, #1
    cmp r6, #64
    bne marker_row
    b park

park:
    b park
    .ltorg
    .balign 4
hwid:
    .hword 476
version:
    .hword 620
footer:
    .hword 0xa55a
    .balign 4
scratch:
    .space 4
probe_end:
