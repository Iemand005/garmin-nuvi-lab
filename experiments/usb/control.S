/* Poll-only EP0. Halfword UDC access, no clocks/mux/PHY/flash operations.
 * r7/r9/r10/r11/r12 preserved. r0..r6/r8 clobbered. No nested calls/stack.
 * Local USB state at scratch+32: configured, setup(8), response(16), errors.
 */
usb_init:
    ldr r6, =0xfffb4000
    /* Entry must have stock EP0=64bytes at FIFO offset8 and disconnected. */
    ldrh r0, [r6, #0x80]
    ldr r1, =0x3001
    cmp r0, r1
    bne usb_disabled
    ldrh r0, [r6, #0x18]
    cmp r0, #0
    bne usb_disabled
    mov r0, #0
    strh r0, [r6, #0x28]
    strh r0, [r6, #0x2c]
    strh r0, [r6, #0x40]
    strh r0, [r6, #0x44]
    /* Disable nonzero endpoints while configuration is unlocked. */
    add r1, r6, #0x84
    mov r2, #15
usb_disable_ep:
    strh r0, [r1]
    strh r0, [r1, #0x40]
    add r1, r1, #4
    subs r2, r2, #1
    bne usb_disable_ep
    ldr r0, =0x7bf
    strh r0, [r6, #0x30]
    mov r0, #4
    strh r0, [r6, #0x1c]
    ldr r0, =0x101
    strh r0, [r6, #0x18]
    ldr r1, =STAGE + (scratch - probe_start)
    mov r0, #1
    strh r0, [r1, #62]
    bx lr
usb_disabled:
    bx lr

usb_poll:
    ldr r8, =STAGE + (scratch - probe_start)
    ldrh r0, [r8, #62]
    cmp r0, #1
    bne usb_return
    ldr r6, =0xfffb4000
    /* Service completed stages first, then take the most recent SETUP. */
    ldrh r5, [r6, #0x30]
    tst r5, #8
    beq usb_no_ds
    ldrh r0, [r6, #0x20]
    tst r0, #0x20
    movne r0, #0
    strhne r0, [r8, #32]
    mov r0, #8
    strh r0, [r6, #0x30]
usb_no_ds:
    tst r5, #1
    beq usb_no_tx
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
    mov r0, #1
    strh r0, [r6, #0x30]
usb_no_tx:
    tst r5, #2
    beq usb_no_rx
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #0x30]
usb_no_rx:
    ldrh r5, [r6, #0x30]
    tst r5, #4
    beq usb_return
    mov r0, #0x40
    strh r0, [r6, #4]
    /* Reading eight bytes drains SETUP; no write-to-clear for this bit. */
    ldrh r0, [r6, #8]
    strh r0, [r8, #34]
    ldrh r1, [r6, #8]
    strh r1, [r8, #36]
    ldrh r2, [r6, #8]
    strh r2, [r8, #38]
    ldrh r3, [r6, #8]
    strh r3, [r8, #40]
    mov r4, #0
    strh r4, [r6, #4]
    /* Exact bmRequestType/request pairs; unrecognized requests STALL. */
    ldr r4, =0x0680
    cmp r0, r4
    beq usb_descriptor
    ldr r4, =0x0900
    cmp r0, r4
    beq usb_set_config
    ldr r4, =0x0880
    cmp r0, r4
    beq usb_get_config
    ldr r4, =0x0080
    cmp r0, r4
    beq usb_get_status
    ldr r4, =0x0081
    cmp r0, r4
    beq usb_get_status
    ldr r4, =0x0a81
    cmp r0, r4
    beq usb_get_interface
    ldr r4, =0x0b01
    cmp r0, r4
    beq usb_set_interface
    ldr r4, =0x5140
    cmp r0, r4
    beq usb_set_value
    ldr r4, =0x52c0
    cmp r0, r4
    beq usb_get_touch
    b usb_stall

usb_descriptor:
    cmp r2, #0
    bne usb_stall
    cmp r1, #0x100
    ldreq r0, =STAGE + (usb_device - probe_start)
    moveq r1, #18
    beq usb_send
    cmp r1, #0x200
    ldreq r0, =STAGE + (usb_configuration - probe_start)
    moveq r1, #18
    beq usb_send
    b usb_stall
usb_set_config:
    cmp r2, #0
    bne usb_stall
    cmp r3, #0
    bne usb_stall
    cmp r1, #1
    bhi usb_stall
    strh r1, [r8, #32]
    cmp r1, #0
    mov r0, #4
    movne r0, #8
    strh r0, [r6, #0x1c]
    b usb_ack
usb_get_config:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    ldrh r1, [r8, #32]
    strh r1, [r8, #42]
    add r0, r8, #42
    mov r1, #1
    b usb_send
usb_get_status:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    mov r1, #0
    strh r1, [r8, #42]
    add r0, r8, #42
    mov r1, #2
    b usb_send
usb_get_interface:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    mov r1, #0
    strh r1, [r8, #42]
    add r0, r8, #42
    mov r1, #1
    b usb_send
usb_set_interface:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    cmp r3, #0
    bne usb_stall
    b usb_ack
usb_set_value:
    cmp r2, #0
    bne usb_stall
    cmp r3, #0
    bne usb_stall
    ldr r0, =999
    cmp r1, r0
    bhi usb_stall
    strh r1, [r8, #14]
    b usb_ack
usb_get_touch:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    ldr r0, =0x4c47
    strh r0, [r8, #42]
    mov r0, #1
    strh r0, [r8, #44]
    ldrh r0, [r8, #14]
    strh r0, [r8, #46]
    ldrh r0, [r8, #6]
    strh r0, [r8, #48]
    ldrh r0, [r8, #8]
    strh r0, [r8, #50]
    ldrh r0, [r8, #4]
    strh r0, [r8, #52]
    ldrh r0, [r8, #16]
    strh r0, [r8, #54]
    ldrh r0, [r8, #32]
    strh r0, [r8, #56]
    add r0, r8, #42
    mov r1, #16
    b usb_send
usb_ack:
    mov r1, #0
usb_send:
    /* <=18bytes, single packet. Read descriptor/state halfwords, FIFO writes16. */
    cmp r1, r3
    movhi r1, r3
    mov r2, #0x30
    strh r2, [r6, #4]
    mov r2, #2
    strh r2, [r6, #12]
    cmp r1, #0
    beq usb_queue
usb_fifo:
    ldrh r2, [r0], #2
    /* Odd-length replies may write an extra byte; avoided by bounded even send.
     * One-byte config/interface reply uses byte FIFO access below.
     */
    cmp r1, #1
    beq usb_last_byte
    strh r2, [r6, #8]
    subs r1, r1, #2
    bne usb_fifo
    b usb_queue
usb_last_byte:
    strb r2, [r6, #8]
usb_queue:
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0x10
    strh r0, [r6, #4]
    bx lr
usb_stall:
    mov r0, #0x20
    strh r0, [r6, #0x1c]
usb_return:
    bx lr

draw_usb_status:
    ldr r1, =STAGE + (scratch - probe_start)
    ldr r0, =0xf800
    ldrh r2, [r1, #62]
    cmp r2, #1
    bne usb_status_draw
    ldr r0, =0xfd20
    ldrh r2, [r1, #32]
    cmp r2, #1
    ldreq r0, =0x16d6
usb_status_draw:
    ldr r1, =72200
    add r4, r9, r1
    mov r6, #8
usb_status_row:
    mov r5, #36
usb_status_pixel:
    strh r0, [r4], #2
    subs r5, r5, #1
    bne usb_status_pixel
    add r4, r4, #568
    subs r6, r6, #1
    bne usb_status_row
    bx lr
