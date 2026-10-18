    /* r4 is the previously validated framebuffer prefix. */
    add r9, r4, #32
    mov r7, #0
input_loop:
    mov lr, pc
    b select_0
    mov r0, #0x8000
    mov lr, pc
    b sample_adc
    mov r10, r0
    mov lr, pc
    b select_1
    mov r0, #0x9000
    mov lr, pc
    b sample_adc
    mov r11, r0
    mov lr, pc
    b select_0
    b render_input

/* Exact five stock stores at main 0x100dc2d8..0x100dc2f0. */
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

/* Exact five stock stores at main 0x100dc316..0x100dc32c. */
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
    /* Stock settling interval: timer decrement >= 0x2f1. */
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
    b failed
settled:
    bx lr

/* Exact conversion command/status/result path at 0x100dcd36..0x100dcd60.
 * r0=0x8000 or0x9000 selects physical ADC0/1 (both board tables agree).
 */
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
    b failed
converted:
    ldrh r0, [r1, #0x14]
    ldr r2, =0x3ff
    and r0, r0, r2
    bx lr

render_input:
    /* Two bars: x32..287, y112..123 and y160..171. */
    ldr r0, =71744
    add r4, r9, r0
    mov r2, r10, lsr #2
    mov r8, #0
bar_begin:
    mov r6, #12
    ldr r0, =0x16d6
    ldr r3, =0x2945
bar_row:
    mov r5, #0
bar_pixel:
    cmp r5, r2
    strhlo r0, [r4], #2
    strhhs r3, [r4], #2
    add r5, r5, #1
    cmp r5, #256
    bne bar_pixel
    add r4, r4, #128
    subs r6, r6, #1
    bne bar_row
    cmp r8, #0
    bne heartbeat
    mov r8, #1
    ldr r0, =102464
    add r4, r9, r0
    mov r2, r11, lsr #2
    b bar_begin
heartbeat:
    eor r7, r7, #1
    ldr r0, =0x16d6
    cmp r7, #0
    ldreq r0, =0x2945
    b indicator
failed:
    /* Stop all further sampling, retain a red failure indicator. */
    ldr r0, =0xf800
indicator:
    ldr r1, =12088
    add r4, r9, r1
    mov r6, #12
indicator_row:
    mov r5, #12
indicator_pixel:
    strh r0, [r4], #2
    subs r5, r5, #1
    bne indicator_pixel
    add r4, r4, #616
    subs r6, r6, #1
    bne indicator_row
    ldr r1, =0xf800
    cmp r0, r1
    beq park
    mov r12, #0x100000
input_delay:
    subs r12, r12, #1
    bne input_delay
    b input_loop
