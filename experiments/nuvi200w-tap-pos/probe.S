/* nüvi 200W (HWID 737, SW 4.00) - tap position to color, debounced.
 * LOCAL EXPERIMENT - 200W TOUCH UNVERIFIED. Reuses nüvi 200 OMAP ADC/GPIO
 * touch sampling sequence; position mapping is raw ADC heuristic.
 * Debounces press/release to avoid noisy false edges. Remove SD before reset.
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
.equ PRESS_LO, 0x60
.equ PRESS_HI, 0x340
.equ DEBOUNCE, 4

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

    /* ADC/touch GPIO inherited-state guards */
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

    add r9, r4, #PIXHDR
    ldr r6, =palette
    mov r8, #7                  /* initial: white */
    mov r11, #0                 /* stable pressed state */
    bl draw_color

main_loop:
    bl sample_touch_debounced   /* r0=0/1/2, r4/r5 last adc on success */
    cmp r0, #2
    beq touch_fail
    cmp r0, #1
    bne not_pressed
    cmp r11, #1
    beq hold_wait               /* already handled this press */
    /* new stable press: map position to color */
    mov r11, #1
    mov r0, r4, lsr #8          /* 0..3 */
    cmp r0, #3
    movhi r0, #3
    mov r1, r5, lsr #9          /* 0..1 */
    cmp r1, #1
    movhi r1, #1
    add r8, r0, r1, lsl #2
    and r8, r8, #7
    bl draw_color
hold_wait:
    /* wait until released (debounced) before accepting next press */
    bl sample_touch_debounced
    cmp r0, #2
    beq touch_fail
    cmp r0, #1
    beq hold_wait
    mov r11, #0
    b main_loop
not_pressed:
    mov r11, #0
    b main_loop

touch_fail:
    /* show small red indicator, then resume */
    ldr r0, =0xf800
    ldr r3, =12088
    add r4, r9, r3
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
    ldr r12, =0x00800000
fail_delay:
    subs r12, r12, #1
    bne fail_delay
    b main_loop

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

/* Debounced sample: require DEBOUNCE same-state reads. r0=0/1/2. */
sample_touch_debounced:
    stmfd sp!, {r6-r8, lr}
    mov r7, #DEBOUNCE           /* remaining needed */
    mov r8, #0xFF               /* last state unknown */
deb_loop:
    bl sample_touch_raw
    cmp r0, #2
    beq deb_fail
    cmp r0, r8
    moveq r7, r7
    beq deb_same
    mov r8, r0
    mov r7, #DEBOUNCE
deb_same:
    subs r7, r7, #1
    bne deb_loop
    mov r0, r8
    ldmfd sp!, {r6-r8, pc}
deb_fail:
    mov r0, #2
    ldmfd sp!, {r6-r8, pc}

/* Raw sample. r0=0 released,1 pressed,2 timeout. r4/r5 adc values. */
sample_touch_raw:
    mov r10, lr
    bl select_0
    ldr r0, =0x8000
    bl sample_adc
    cmn r0, #1
    beq raw_fail
    mov r4, r0
    bl select_1
    ldr r0, =0x9000
    bl sample_adc
    cmn r0, #1
    beq raw_fail
    mov r5, r0
    bl select_0
    /* pressed if either adc in [PRESS_LO, PRESS_HI) */
    cmp r4, #PRESS_LO
    blo check_y
    ldr r2, =PRESS_HI
    cmp r4, r2
    blo is_pressed
check_y:
    cmp r5, #PRESS_LO
    blo not_pressed_sample
    ldr r2, =PRESS_HI
    cmp r5, r2
    blo is_pressed
not_pressed_sample:
    mov r0, #0
    bx r10
is_pressed:
    mov r0, #1
    bx r10
raw_fail:
    mov r0, #2
    bx r10

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
