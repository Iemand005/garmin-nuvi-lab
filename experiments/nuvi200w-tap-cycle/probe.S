/* nüvi 200W (HWID 737, SW 4.00) - tap-to-cycle color RAM payload.
 * LOCAL EXPERIMENT - 200W TOUCH IS UNVERIFIED. Reuses nüvi 200 OMAP ADC/GPIO
 * touch sampling sequence; may not detect taps on 200W hardware.
 * Loaded by stock SD loader to 0x10040000, mode r12==12.
 * Reads DMA MMIO and ADC/GPIO/timer regs; writes GPIO/ADC control regs as in
 * stock touch sequence and RGB565 pixels to active framebuffer. No flash writes.
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
.equ NCOLORS,  8
.equ PRESS_THR, 0x380       /* heuristic: < thr means pressed (unverified) */

probe_start:
    b entry
    .word STAGE + (footer - probe_start)
    .word STAGE + (hwid - probe_start)
    .word STAGE + (version - probe_start)

entry:
    cmp r12, #12
    bne park

    /* DMA/framebuffer guards */
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

    /* Inherited ADC/touch GPIO guards (from nüvi 200 touch probe). */
    ldr r0, =0xfffe6000
    ldrh r1, [r0, #0x14]
    tst r1, #1
    beq park
    ldr r0, =0xfffbb400
    ldr r1, [r0, #0x34]
    tst r1, #0x0e
    bne park
    ldr r0, =0xfffbe400
    ldr r1, [r0, #0x34]
    ldr r2, =0x8010
    tst r1, r2
    bne park

    add r9, r4, #PIXHDR        /* r9 = pixel base */
    ldr r6, =palette
    mov r8, #0                  /* color index */
    mov r11, #0                 /* last pressed state */

    /* draw initial color */
    bl draw_color

main_loop:
    bl sample_touch             /* r0 = 1 pressed, 0 not pressed, 2 failed */
    cmp r0, #2
    beq touch_fail
    cmp r0, #1
    bne not_pressed
    cmp r11, #1
    beq main_loop               /* still held */
    /* new press edge: advance color */
    mov r11, #1
    add r8, r8, #1
    cmp r8, #NCOLORS
    blo do_draw
    mov r8, #0
do_draw:
    bl draw_color
    /* wait for release, bounded */
    ldr r7, =0x00200000
wait_release:
    bl sample_touch
    cmp r0, #2
    beq touch_fail
    cmp r0, #0
    beq released
    subs r7, r7, #1
    bne wait_release
released:
    mov r11, #0
    b main_loop
not_pressed:
    mov r11, #0
    b main_loop

touch_fail:
    /* red indicator in top-right, then keep trying slowly */
    ldr r0, =0xf800
    ldr r4, =12088             /* 18*640 + 296*2 */
    add r4, r9, r4
    sub r4, r4, #PIXHDR        /* indicator was relative to pixel base */
    mov r2, #12
fail_row:
    mov r3, #12
fail_px:
    strh r0, [r4], #2
    subs r3, r3, #1
    bne fail_px
    add r4, r4, #616
    subs r2, r2, #1
    bne fail_row
    ldr r12, =0x01000000
fail_delay:
    subs r12, r12, #1
    bne fail_delay
    b main_loop

/* Draw current color r8 to framebuffer at r9. Clobbers r0-r5,r12. */
draw_color:
    add r0, r6, r8, lsl #1
    ldrh r1, [r0]
    mov r4, r9
    ldr r5, =PIXELS
draw_fill:
    strh r1, [r4], #2
    subs r5, r5, #1
    bne draw_fill
    bx lr

/* Sample touch. Returns r0: 0=released, 1=pressed, 2=failed/timeout.
 * Clobbers r0-r5,r10,r12,lr. Preserves r6,r8,r9,r11.
 */
sample_touch:
    mov r10, lr
    bl select_0
    ldr r0, =0x8000
    bl sample_adc
    cmn r0, #1
    beq sample_failed
    mov r4, r0                  /* adc0 */
    bl select_1
    ldr r0, =0x9000
    bl sample_adc
    cmn r0, #1
    beq sample_failed
    mov r5, r0                  /* adc1 */
    bl select_0
    ldr r2, =PRESS_THR
    cmp r4, r2
    blo is_pressed
    cmp r5, r2
    blo is_pressed
    mov r0, #0
    bx r10
is_pressed:
    mov r0, #1
    bx r10
sample_failed:
    mov r0, #2
    bx r10

/* Exact stock selector 0 stores */
select_0:
    ldr r0, =0xfffbb4f0
    mov r1, #2
    str r1, [r0]
    ldr r0, =0xfffbe4b0
    mov r1, #0x8000
    str r1, [r0]
    mov r1, #0x10
    str r1, [r0]
    ldr r0, =0xfffbb4f0
    mov r1, #4
    str r1, [r0]
    ldr r0, =0xfffbb4b0
    mov r1, #8
    str r1, [r0]
    b settle

/* Exact stock selector 1 stores */
select_1:
    ldr r0, =0xfffbb4b0
    mov r1, #2
    str r1, [r0]
    ldr r0, =0xfffbe4f0
    mov r1, #0x8000
    str r1, [r0]
    mov r1, #0x10
    str r1, [r0]
    ldr r0, =0xfffbb4b0
    mov r1, #4
    str r1, [r0]
    mov r1, #8
    str r1, [r0]
settle:
    ldr r0, =0xfffec700
    ldr r1, [r0, #8]
    ldr r3, =0x2f1
    mov r12, #0x10000
settle_poll:
    ldr r2, [r0, #8]
    sub r2, r1, r2
    cmp r2, r3
    bhs settled
    subs r12, r12, #1
    bne settle_poll
    ldr r0, =0xFFFF
    bx lr
settled:
    bx lr

/* ADC conversion. r0=cmd (0x8000/0x9000). Returns r0=result or 0xFFFF timeout. */
sample_adc:
    ldr r1, =0xfffe6020
    ldrh r2, [r1, #0x14]
    strh r0, [r1]
    ldr r2, =0xfffe6000
    mov r12, #0x10000
adc_poll:
    ldrh r0, [r2, #0x18]
    tst r0, #1
    bne converted
    subs r12, r12, #1
    bne adc_poll
    ldr r0, =0xFFFF
    bx lr
converted:
    ldrh r0, [r1, #0x14]
    ldr r2, =0x3ff
    and r0, r0, r2
    bx lr

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
