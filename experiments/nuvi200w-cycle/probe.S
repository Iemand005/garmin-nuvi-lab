/* nüvi 200W (HWID 737, SW 4.00) - color cycle RAM payload.
 * LOCAL EXPERIMENT. Loaded by stock SD loader to 0x10040000, mode r12==12.
 * Reads DMA MMIO only; writes RGB565 colors to active framebuffer pixels.
 * Loops forever; remove SD before recovery reset.
 */
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.balign 4
.global probe_start
.equ STAGE,    0x10040000
.equ DMA_BASE, 0xFFFEE3C0
.equ DMA_LEN,  0x3FC1E
.equ BUF0,     0x11F807C0
.equ BUF1,     0x11FC03E0
.equ PIXHDR,   32
.equ PIXELS,   130560
.equ DELAY,    0x00400000
.equ NCOLORS,  8

probe_start:
    b entry
    .word STAGE + (footer - probe_start)
    .word STAGE + (hwid - probe_start)
    .word STAGE + (version - probe_start)

entry:
    cmp r12, #12
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

    add r9, r4, #PIXHDR
    ldr r6, =palette
    mov r8, #0
next_color:
    add r0, r6, r8, lsl #1
    ldrh r1, [r0]
    mov r4, r9
    ldr r5, =PIXELS
fill:
    strh r1, [r4], #2
    subs r5, r5, #1
    bne fill
    ldr r12, =DELAY
delay:
    subs r12, r12, #1
    bne delay
    add r8, r8, #1
    cmp r8, #NCOLORS
    blo next_color
    mov r8, #0
    b next_color

park:
    b park

    .ltorg
    .balign 4
hwid:    .hword 737
version: .hword 400
footer:  .hword 0xA55A
    .balign 4
palette:
    .hword 0xF800, 0x07E0, 0x001F, 0xFFE0, 0x07FF, 0xF81F, 0xFFFF, 0x0000
