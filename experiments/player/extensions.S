music_text:
    cmp r3, #0
    bne usb_stall
    cmp r2, #48
    bhs usb_stall
    and r0, r1, #255
    cmp r0, #32
    blo usb_stall
    cmp r0, #126
    bhi usb_stall
    mov r0, r1, lsr #8
    cmp r0, #32
    blo usb_stall
    cmp r0, #126
    bhi usb_stall
    add r0, r8, #128
    add r0, r0, r2, lsl #1
    strh r1, [r0]
    b usb_ack
music_info:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    ldr r0, =0x4d55
    strh r0, [r8, #42]
    mov r0, #1
    strh r0, [r8, #44]
    mov r0, #48
    strh r0, [r8, #46]
    mov r0, #8
    strh r0, [r8, #48]
    add r0, r8, #42
    mov r1, #8
    b usb_send
music_event:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    ldr r0, =0x4d45
    strh r0, [r8, #42]
    ldrh r0, [r8, #82]
    ldrh r1, [r8, #80]
    cmp r0, r1
    beq music_empty
    add r0, r0, #1
    and r1, r0, #7
    add r2, r8, #256
    add r2, r2, r1, lsl #2
    ldrh r0, [r2]
    strh r0, [r8, #44]
    ldrh r0, [r2, #2]
    b music_event_reply
music_empty:
    strh r0, [r8, #44]
    mov r0, #0
music_event_reply:
    strh r0, [r8, #46]
    ldrh r0, [r8, #88]
    strh r0, [r8, #48]
    add r0, r8, #42
    mov r1, #8
    b usb_send
music_ack:
    cmp r2, #0
    bne usb_stall
    cmp r3, #0
    bne usb_stall
    ldrh r0, [r8, #82]
    /* Repeated acknowledgment is harmless (host retry after a timeout). */
    cmp r0, r1
    beq usb_ack
    ldrh r2, [r8, #80]
    cmp r0, r2
    beq usb_stall
    add r0, r0, #1
    mov r0, r0, lsl #16
    mov r0, r0, lsr #16
    cmp r0, r1
    bne usb_stall
    strh r1, [r8, #82]
    b usb_ack

draw_music:
    ldr r11, =STAGE + (scratch - probe_start) + 128
    ldr r0, =41024
    add r4, r9, r0
    mov r8, #96
    mov r2, #32
music_character:
    ldrb r3, [r11], #1
    cmp r3, #32
    movlo r3, #32
    cmp r3, #126
    movhi r3, #32
    sub r3, r3, #32
    ldr r0, =STAGE + (music_glyphs - probe_start)
    add r0, r0, r3, lsl #8
    mov r6, #16
music_glyph_row:
    mov r5, #8
music_glyph_pixel:
    ldrh r1, [r0], #2
    strh r1, [r4], #2
    subs r5, r5, #1
    bne music_glyph_pixel
    add r4, r4, #624
    subs r6, r6, #1
    bne music_glyph_row
    ldr r3, =10224
    sub r4, r4, r3
    subs r8, r8, #1
    beq music_drawn
    subs r2, r2, #1
    bne music_character
    mov r2, #32
    add r4, r4, #14848
    b music_character
music_drawn:
    bx lr
