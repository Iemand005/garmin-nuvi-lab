/* Offline candidate for nuvi 200 HWID 0660 / software 5.00 ONLY.
 * Not deployment-approved merely by building it. No stock loader code used.
 * Reads LCD/DMA registers; NEVER writes peripheral registers or flash.
 * Saves, inverts, and restores a 32x32 rectangle in one validated framebuffer.
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
    cmp r12, #12
    bne park
    /* Exact enabled TFT / palette-and-data path; no timing changes. */
    ldr r0, =0xfffec000
    ldr r1, [r0]
    and r2, r1, #0x81
    cmp r2, #0x81
    bne park
    tst r1, #0x00300000
    bne park
    ldr r2, [r0, #4]
    ldr r3, =0x3ff
    and r2, r2, r3
    ldr r3, =319
    cmp r2, r3
    bne park
    ldr r2, [r0, #8]
    ldr r3, =0x3ff
    and r2, r2, r3
    cmp r2, #239
    bne park

    /* Snapshot programmed DMA B1 start/end using halfword accesses. */
    ldr r7, =0xfffee3c0
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    ldr r0, =0x11f69f80
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

    /* Header=32 bytes, stride=640; x=144,y=104, width=height=32. */
    ldr r0, =0x10540
    add r9, r4, r0
    mov r4, r9
    ldr r8, =STAGE + (scratch - probe_start)
    mov r6, #32
save_row:
    mov r5, #32
save_pixel:
    ldrh r0, [r4], #2
    strh r0, [r8], #2
    subs r5, r5, #1
    bne save_pixel
    add r4, r4, #576
    subs r6, r6, #1
    bne save_row

    mov r4, r9
    ldr r8, =STAGE + (scratch - probe_start)
    mov r6, #32
    ldr r2, =0xffff
invert_row:
    mov r5, #32
invert_pixel:
    ldrh r0, [r8], #2
    eor r0, r0, r2
    strh r0, [r4], #2
    subs r5, r5, #1
    bne invert_pixel
    add r4, r4, #576
    subs r6, r6, #1
    bne invert_row

    /* Finite CPU delay, wall time uncalibrated. Watchdog may reset early. */
    mov r12, #0x01000000
delay:
    subs r12, r12, #1
    bne delay

    mov r4, r9
    ldr r8, =STAGE + (scratch - probe_start)
    mov r6, #32
restore_row:
    mov r5, #32
restore_pixel:
    ldrh r0, [r8], #2
    strh r0, [r4], #2
    subs r5, r5, #1
    bne restore_pixel
    add r4, r4, #576
    subs r6, r6, #1
    bne restore_row

park:
    b park
    .ltorg
    .balign 4
hwid:
    .hword 660
version:
    .hword 500
footer:
    .hword 0xa55a
    .balign 4
scratch:
    .space 2048
probe_end:
