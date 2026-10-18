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
