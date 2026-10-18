/* Raw touch candidate: exact stock logical-channel 0/1 drive and ADC sequence.
 * Inherited clocks/directions only, bounded polls. No flash/filesystem access.
 * Added peripheral stores are restricted by the offline audit.
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

    /* Inherited ADC configuration must already be initialized. */
    ldr r0, =0xfffe6000
    ldrh r1, [r0, #0x14]
    tst r1, #1
    beq park
    /* Existing stock touchscreen drive pins must already be outputs. */
    ldr r0, =0xfffbb400
    ldr r1, [r0, #0x34]
    tst r1, #0x0e
    bne park
    ldr r0, =0xfffbe400
    ldr r1, [r0, #0x34]
    ldr r2, =0x8010
    tst r1, r2
    bne park

    /* Guarded source frame has 32-byte prefix; preserve that prefix. */
    add r4, r4, #32
    ldr r8, =STAGE + (screen - probe_start)
    ldr r6, =76800
copy_screen:
    ldrh r0, [r8], #2
    strh r0, [r4], #2
    subs r6, r6, #1
    bne copy_screen
    /* r4 is end of pixel data; recover the validated prefix base. */
    ldr r0, =153632
    sub r4, r4, r0

    /* r4 is the previously validated framebuffer prefix. */
    add r9, r4, #32
    mov r7, #0
    ldr r8, =STAGE + (scratch - probe_start)
    mov r0, #1
    strh r0, [r8, #10]
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
    mov lr, pc
    b restore_cursor
    b cursor_update
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

/* Local scratch halfwords: good, bad, visible, x, y. */
restore_cursor:
    ldr r8, =STAGE + (scratch - probe_start)
    ldrh r0, [r8, #4]
    cmp r0, #0
    beq cursor_restored
    ldrh r1, [r8, #6]
    ldrh r2, [r8, #8]
    sub r1, r1, #6
    sub r2, r2, #6
    add r3, r2, r2, lsl #2
    mov r3, r3, lsl #7
    add r3, r3, r1, lsl #1
    add r4, r9, r3
    ldr r0, =STAGE + (screen - probe_start)
    add r0, r0, r3
    mov r6, #13
restore_row:
    mov r5, #13
restore_pixel:
    ldrh r1, [r0], #2
    strh r1, [r4], #2
    subs r5, r5, #1
    bne restore_pixel
    add r0, r0, #612
    add r0, r0, #2
    add r4, r4, #612
    add r4, r4, #2
    subs r6, r6, #1
    bne restore_row
cursor_restored:
    bx lr

cursor_update:
    ldr r8, =STAGE + (scratch - probe_start)
    cmp r10, #50
    bls cursor_invalid
    cmp r11, #50
    bls cursor_invalid
    mov r0, #0
    strh r0, [r8, #2]
    ldrh r0, [r8]
    cmp r0, #2
    addlo r0, r0, #1
    strh r0, [r8]
    cmp r0, #2
    blo cursor_pending
    /* x=(113*ADC1 >>8)-59; y=307-(94*ADC0 >>8).
     * Shift/add approximation of provisional video fit; clamp marker bounds.
     */
    add r0, r11, r11, lsl #4
    add r0, r0, r11, lsl #5
    add r0, r0, r11, lsl #6
    mov r0, r0, lsr #8
    cmp r0, #65
    movlo r0, #6
    subhs r0, r0, #59
    ldr r1, =313
    cmp r0, r1
    movhi r0, r1
    strh r0, [r8, #6]
    mov r0, r10, lsl #6
    add r0, r0, r10, lsl #5
    sub r0, r0, r10, lsl #1
    mov r0, r0, lsr #8
    ldr r1, =307
    ldr r2, =301
    cmp r0, r2
    movhi r0, #6
    subls r0, r1, r0
    cmp r0, #233
    movhi r0, #233
    strh r0, [r8, #8]
    mov r0, #1
    strh r0, [r8, #4]
    b button_track
cursor_invalid:
    mov r0, #0
    strh r0, [r8]
    ldrh r0, [r8, #2]
    cmp r0, #4
    addlo r0, r0, #1
    strh r0, [r8, #2]
    cmp r0, #4
    blo cursor_pending
    mov r0, #0
    strh r0, [r8, #4]
    b button_release
cursor_pending:
    ldr r10, =0xfd20
    b cursor_draw
cursor_active:
    ldr r10, =0x16d6
cursor_draw:
    mov lr, pc
    b draw_counter
    mov lr, pc
    b draw_swatch
    ldr r8, =STAGE + (scratch - probe_start)
    ldrh r0, [r8, #4]
    cmp r0, #0
    beq contact_status
    ldrh r1, [r8, #6]
    ldrh r2, [r8, #8]
    sub r1, r1, #6
    sub r2, r2, #6
    add r3, r2, r2, lsl #2
    mov r3, r3, lsl #7
    add r3, r3, r1, lsl #1
    add r4, r9, r3
    ldr r0, =0xffff
    mov r6, #0
cross_row:
    mov r5, #0
cross_pixel:
    cmp r6, #6
    strheq r0, [r4]
    cmp r5, #6
    strheq r0, [r4]
    add r4, r4, #2
    add r5, r5, #1
    cmp r5, #13
    bne cross_pixel
    add r4, r4, #612
    add r4, r4, #2
    add r6, r6, #1
    cmp r6, #13
    bne cross_row
contact_status:
    ldr r0, =31240
    add r4, r9, r0
    mov r6, #8
status_row:
    mov r5, #36
status_pixel:
    strh r10, [r4], #2
    subs r5, r5, #1
    bne status_pixel
    add r4, r4, #568
    subs r6, r6, #1
    bne status_row
    b heartbeat

button_track:
    /* Inclusive hit rectangles, matching rendered button boundaries. */
    mov r2, #0
    ldrh r0, [r8, #8]
    cmp r0, #144
    blo hit_done
    cmp r0, #192
    bhi hit_done
    ldrh r0, [r8, #6]
    cmp r0, #18
    blo hit_done
    cmp r0, #105
    movls r2, #1
    bls hit_done
    cmp r0, #116
    blo hit_done
    cmp r0, #203
    movls r2, #2
    bls hit_done
    cmp r0, #214
    blo hit_done
    ldr r1, =301
    cmp r0, r1
    movls r2, #3
hit_done:
    strh r2, [r8, #18]
    ldrh r0, [r8, #10]
    cmp r0, #0
    beq cursor_active
    /* Capture only the first accepted contact; sliding in cannot arm a tap. */
    strh r2, [r8, #12]
    mov r0, #0
    strh r0, [r8, #10]
    b cursor_active

button_release:
    ldrh r0, [r8, #10]
    cmp r0, #0
    bne button_idle
    mov r0, #1
    strh r0, [r8, #10]
    ldrh r0, [r8, #12]
    ldrh r1, [r8, #18]
    cmp r0, r1
    bne button_idle
    cmp r0, #1
    beq count_tap
    cmp r0, #2
    beq clear_taps
    cmp r0, #3
    bne button_idle
    ldrh r0, [r8, #16]
    eor r0, r0, #1
    strh r0, [r8, #16]
    b button_idle
count_tap:
    ldrh r0, [r8, #14]
    ldr r1, =999
    cmp r0, r1
    addlo r0, r0, #1
    strh r0, [r8, #14]
    b button_idle
clear_taps:
    mov r0, #0
    strh r0, [r8, #14]
button_idle:
    ldr r10, =0x2945
    b cursor_draw

draw_counter:
    ldr r0, =STAGE + (scratch - probe_start)
    ldrh r2, [r0, #14]
    mov r11, #0
hundreds:
    cmp r2, #100
    blo tens_start
    sub r2, r2, #100
    add r11, r11, #256
    b hundreds
tens_start:
    cmp r2, #10
    blo digits_ready
    sub r2, r2, #10
    add r11, r11, #16
    b tens_start
digits_ready:
    add r11, r11, r2
    ldr r0, =51472
    add r4, r9, r0
    mov r8, #3
decimal_digit:
    mov r3, r11, lsr #8
    and r3, r3, #15
    ldr r0, =STAGE + (decimal_glyphs - probe_start)
    add r0, r0, r3, lsl #10
    mov r6, #32
decimal_row:
    mov r5, #16
decimal_pixel:
    ldrh r1, [r0], #2
    strh r1, [r4], #2
    subs r5, r5, #1
    bne decimal_pixel
    add r4, r4, #608
    subs r6, r6, #1
    bne decimal_row
    ldr r3, =20448
    sub r4, r4, r3
    mov r11, r11, lsl #4
    subs r8, r8, #1
    bne decimal_digit
    bx lr

draw_swatch:
    ldr r0, =STAGE + (scratch - probe_start)
    ldrh r0, [r0, #16]
    cmp r0, #0
    ldr r0, =0x16d6
    ldrne r0, =0xf97b
    ldr r1, =45320
    add r4, r9, r1
    mov r6, #12
swatch_row:
    mov r5, #36
swatch_pixel:
    strh r0, [r4], #2
    subs r5, r5, #1
    bne swatch_pixel
    add r4, r4, #568
    subs r6, r6, #1
    bne swatch_row
    bx lr

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
    .balign 4
decimal_glyphs:
    .incbin "experiments/buttons/decimal.rgb565"
screen:
    .incbin "experiments/buttons/screen.rgb565"
probe_end:
