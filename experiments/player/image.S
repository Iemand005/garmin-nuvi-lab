/* One 64-byte RGB565 block in the validated 153600-byte framebuffer.
 * EP0 OUT follows TI SPRU761A + Linux omap_udc.c ep0_irq/read_fifo.
 * No pointers supplied by host. index0..2399 -> exactly32 pixels.
 */
player_chunk:
    cmp r1, #0
    bne usb_stall
    ldr r0, =2400
    cmp r2, r0
    bhs usb_stall
    cmp r3, #64
    bne usb_stall
    strh r2, [r8, #92]
    mov r0, #1
    strh r0, [r8, #90]
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
    bx lr
player_receive:
    mov r0, #0x20
    strh r0, [r6, #4]
    ldrh r0, [r6, #0x10]
    tst r0, #8
    beq player_bad_packet
    /* Full EP0 packet: Linux uses FIFO_FULL instead of RXFSTAT here. */
    tst r0, #1
    bne player_full_packet
    ldrh r0, [r6, #0x14]
    cmp r0, #64
    bne player_bad_packet
player_full_packet:
    ldrh r0, [r8, #92]
    ldr r1, =2400
    cmp r0, r1
    bhs player_bad_packet
    add r2, r9, r0, lsl #6
    mov r3, #32
player_pixels:
    ldrh r1, [r6, #8]
    strh r1, [r2], #2
    subs r3, r3, #1
    bne player_pixels
    mov r0, #0
    strh r0, [r8, #90]
    strh r0, [r6, #4]
    /* Complete the OUT transfer with an IN zero-length status packet. */
    mov r3, #0
    b usb_ack
player_bad_packet:
    mov r0, #0
    strh r0, [r8, #90]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
    b usb_stall
