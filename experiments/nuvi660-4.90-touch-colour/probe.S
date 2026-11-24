/* nuvi 660 (HWID 596, SW 4.90) - touch colour fill experiment.
 * LOCAL EXPERIMENT. Uses firmware touch_get to read X/Y/pressed and fills
 * the whole screen with a position-derived RGB565 colour while touched.
 * Remove SD before recovery reset.
 */
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.balign 4
.global probe_start
.equ STAGE,     0x10040000
.equ DMA_BASE,  0xFFFEE3C0
.equ DMA_LEN,   0x3FC1E
.equ BUF0,      0x11FC03E0
.equ BUF1,      0x11FC03E0
.equ PIXHDR,    32
.equ PIXELS,    130560
.equ TOUCH_VALS, 0x1004126c

probe_start:
    b entry
    .word STAGE + (footer - probe_start)
    .word STAGE + (hwid - probe_start)
    .word STAGE + (version - probe_start)

entry:
    cmp r12, #2
    bne park

    ldr r7, =DMA_BASE
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    ldr r0, =BUF0
    cmp r4, r0
    beq known
    ldr r0, =BUF1
    cmp r4, r0
    bne park
known:
    sub r5, r5, r4
    ldr r0, =DMA_LEN
    cmp r5, r0
    bne park
    ldrh r0, [r7, #8]
    ldrh r2, [r7, #10]
    orr r0, r0, r2, lsl #16
    cmp r0, r4
    bne park

main_loop:
    /* sample touch into TOUCH_VALS (x@+0, y@+2, pressed@+4) */
    ldr r0, =TOUCH_VALS
    ldr r3, =0x100e8f59
    blx r3

    ldr r0, =TOUCH_VALS
    ldrh r5, [r0]
    ldrh r6, [r0, #2]
    ldrb r7, [r0, #4]

    cmp r7, #0
    beq fill_black

    /* RGB565: R = x>>5, G = y>>4, B = (x+y)>>6 */
    lsr r0, r5, #5
    and r0, r0, #0x1F
    lsl r0, r0, #11
    lsr r1, r6, #4
    and r1, r1, #0x3F
    lsl r1, r1, #5
    orr r0, r0, r1
    add r1, r5, r6
    lsr r1, r1, #6
    and r1, r1, #0x1F
    orr r0, r0, r1
    b do_fill

fill_black:
    mov r0, #0

do_fill:
    /* recompute framebuffer base so touch_get cannot corrupt r9 */
    ldr r3, =DMA_BASE
    ldrh r1, [r3, #8]
    ldrh r2, [r3, #10]
    orr r1, r1, r2, lsl #16
    add r9, r1, #PIXHDR
    bl fill_screen
    b main_loop

fill_screen:
    mov r1, r9
    ldr r2, =PIXELS
fs_loop:
    strh r0, [r1], #2
    subs r2, r2, #1
    bne fs_loop
    bx lr

park:
    b park

    .ltorg
    .balign 4
hwid:    .hword 596
version: .hword 490
footer:  .hword 0xA55A
