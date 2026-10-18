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
    b cursor_active
cursor_invalid:
    mov r0, #0
    strh r0, [r8]
    ldrh r0, [r8, #2]
    cmp r0, #2
    addlo r0, r0, #1
    strh r0, [r8, #2]
    cmp r0, #2
    blo cursor_pending
    mov r0, #0
    strh r0, [r8, #4]
    ldr r10, =0x2945
    b cursor_draw
cursor_pending:
    ldr r10, =0xfd20
    b cursor_draw
cursor_active:
    ldr r10, =0x16d6
cursor_draw:
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
