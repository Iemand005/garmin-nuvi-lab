/* nuvi 660 (HWID 596, SW 4.90) - USB EP0 diagnostic.
 * LOCAL EXPERIMENT. Displays SETUP/descriptor/send/stall counters.
 * Remove SD before recovery reset.
 */
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.balign 4
.global probe_start
.equ STAGE,     0x10040000
.equ DMA_BASE,  0xFFFEE3C0
.equ DMA_LEN,   0x3FC1E
.equ BUF0,      0x11FC03E0
.equ BUF1,      0x11FC03E0
.equ PIXHDR,    32
.equ PIXELS,    130560
.equ WIDTH,     480
.equ HEIGHT,    272
.equ STRIDE,    960
.equ BG,        0x1082
.equ FG,        0xFFFF
.equ FG2,       0x07E0
.equ FG3,       0xFFE0

probe_start:
    b entry
    .word STAGE + (footer - probe_start)
    .word STAGE + (hwid - probe_start)
    .word STAGE + (version - probe_start)

entry:
    cmp r12, #2
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
    ldr r0, =BG
    bl fill_screen
    bl usb_init

main_loop:
    bl usb_poll
    ldr r10, =STAGE + (scratch - probe_start)
    ldr r11, =0xfffb4000

    mov r2, #2
    mov r3, #2
    ldr r1, =FG2
    ldr r0, =str_title
    bl draw_string

    mov r2, #2
    mov r3, #14
    ldr r1, =FG
    ldr r0, =str_setup
    bl draw_string
    ldrh r0, [r10, #80]
    mov r2, #56
    mov r3, #14
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #120
    mov r3, #14
    ldr r1, =FG
    ldr r0, =str_req
    bl draw_string
    ldrh r0, [r10, #82]
    mov r2, #174
    mov r3, #14
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #238
    mov r3, #14
    ldr r1, =FG
    ldr r0, =str_val
    bl draw_string
    ldrh r0, [r10, #84]
    mov r2, #292
    mov r3, #14
    ldr r1, =FG3
    bl draw_hex16

    mov r2, #2
    mov r3, #28
    ldr r1, =FG
    ldr r0, =str_len
    bl draw_string
    ldrh r0, [r10, #88]
    mov r2, #56
    mov r3, #28
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #120
    mov r3, #28
    ldr r1, =FG
    ldr r0, =str_idx
    bl draw_string
    ldrh r0, [r10, #86]
    mov r2, #174
    mov r3, #28
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #238
    mov r3, #28
    ldr r1, =FG
    ldr r0, =str_desc
    bl draw_string
    ldrh r0, [r10, #90]
    mov r2, #292
    mov r3, #28
    ldr r1, =FG3
    bl draw_hex16

    mov r2, #2
    mov r3, #42
    ldr r1, =FG
    ldr r0, =str_send
    bl draw_string
    ldrh r0, [r10, #92]
    mov r2, #56
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #120
    mov r3, #42
    ldr r1, =FG
    ldr r0, =str_stall
    bl draw_string
    ldrh r0, [r10, #94]
    mov r2, #174
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #238
    mov r3, #42
    ldr r1, =FG
    ldr r0, =str_flag
    bl draw_string
    ldrh r0, [r10, #62]
    mov r2, #292
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex16

    mov r2, #2
    mov r3, #56
    ldr r1, =FG
    ldr r0, =str_irq
    bl draw_string
    ldrh r0, [r11, #0x30]
    mov r2, #56
    mov r3, #56
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #120
    mov r3, #56
    ldr r1, =FG
    ldr r0, =str_ctl
    bl draw_string
    ldrh r0, [r11, #0x18]
    mov r2, #174
    mov r3, #56
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #238
    mov r3, #56
    ldr r1, =FG
    ldr r0, =str_ep0
    bl draw_string
    ldrh r0, [r11, #0x80]
    mov r2, #292
    mov r3, #56
    ldr r1, =FG3
    bl draw_hex16

    ldr r12, =0x00100000
delay_loop:
    subs r12, r12, #1
    bne delay_loop
    b main_loop

fill_screen:
    mov r1, r9
    ldr r2, =PIXELS
fs_loop:
    strh r0, [r1], #2
    subs r2, r2, #1
    bne fs_loop
    bx lr

draw_string:
    stmfd sp!, {r4-r9, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
ds_loop:
    ldrb r0, [r4], #1
    cmp r0, #0
    beq ds_done
    mov r1, r5
    mov r2, r6
    mov r3, r7
    bl draw_char
    add r6, r6, #6
    ldr r0, =474
    cmp r6, r0
    blt ds_loop
ds_done:
    ldmfd sp!, {r4-r9, pc}

draw_char:
    stmfd sp!, {r4-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    and r4, r4, #127
    ldr r8, =font
    add r8, r8, r4, lsl #2
    add r8, r8, r4
    mov r10, #0
dc_col:
    ldrb r11, [r8, r10]
    mov r12, #0
dc_row:
    add r2, r6, r10
    mov r1, #6
    sub r3, r1, r12
    add r3, r7, r3  /* flip glyph vertically only */
    mov r0, #1
    tst r11, r0, lsl r12
    moveq r0, #0x0000
    movne r0, r5
    bl put_pixel
    add r12, r12, #1
    cmp r12, #7
    blt dc_row
    add r10, r10, #1
    cmp r10, #5
    blt dc_col
    ldmfd sp!, {r4-r11, pc}

put_pixel:
    ldr r1, =WIDTH
    cmp r2, r1
    bhs pp_ret
    ldr r1, =HEIGHT
    cmp r3, r1
    bhs pp_ret
    /* no screen flip */
    ldr r1, =STRIDE
    mul r1, r3, r1
    add r1, r1, r2, lsl #1
    add r1, r9, r1
    strh r0, [r1]
pp_ret:
    bx lr

draw_hex32:
    stmfd sp!, {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #28
dh32_loop:
    mov r0, r4, lsr r8
    and r0, r0, #15
    cmp r0, #10
    addlo r0, r0, #48
    addhs r0, r0, #55
    mov r1, r5
    mov r2, r6
    mov r3, r7
    bl draw_char
    add r6, r6, #6
    subs r8, r8, #4
    bhs dh32_loop
    ldmfd sp!, {r4-r8, pc}


draw_hex16:
    stmfd sp!, {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #12
dh16_loop:
    mov r0, r4, lsr r8
    and r0, r0, #15
    cmp r0, #10
    addlo r0, r0, #48
    addhs r0, r0, #55
    mov r1, r5
    mov r2, r6
    mov r3, r7
    bl draw_char
    add r6, r6, #6
    subs r8, r8, #4
    bhs dh16_loop
    ldmfd sp!, {r4-r8, pc}
sample_touch_raw:
    stmfd sp!, {r7,r8,lr}
    mov r4, #0
    mov r5, #0
    ldr r0, =0xfffe6000
    ldrh r1, [r0, #0x14]
    tst r1, #1
    beq tr_fail
    bl select_0
    ldr r0, =0x8000
    bl sample_adc
    cmn r0, #1
    beq tr_fail
    mov r4, r0
    bl select_1
    ldr r0, =0x9000
    bl sample_adc
    cmn r0, #1
    beq tr_fail
    mov r5, r0
    bl select_0
    ldr r2, =0x340
    cmp r4, #0x60
    blo tr_chk_y
    cmp r4, r2
    blo tr_press
tr_chk_y:
    cmp r5, #0x60
    blo tr_rel
    cmp r5, r2
    blo tr_press
tr_rel:
    mov r0, #0
    ldmfd sp!, {r7,r8,pc}
tr_press:
    mov r0, #1
    ldmfd sp!, {r7,r8,pc}
tr_fail:
    ldr r0, =0xffff
    mov r4, r0
    mov r5, r0
    mov r0, #2
    ldmfd sp!, {r7,r8,pc}

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
    /* EP1 bulk IN at FIFO 72, EP1 bulk OUT at FIFO 136, 64-byte packets. */
    ldr r0, =0xb009
    strh r0, [r6, #0xc4]
    ldr r0, =0xb011
    strh r0, [r6, #0x84]
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
    ldrh r5, [r8, #80]
    add r5, r5, #1
    strh r5, [r8, #80]
    strh r0, [r8, #82]
    strh r1, [r8, #84]
    strh r2, [r8, #86]
    strh r3, [r8, #88]
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
    ldr r4, =0x6bc0
    cmp r0, r4
    bne usb_vendor_next
    cmp r2, #4
    bne usb_vendor_20
    ldr r0, =STAGE + (ms_compat_id - probe_start)
    mov r1, #40
    b usb_send
usb_vendor_20:
    cmp r2, #7
    bne usb_stall
    ldr r0, =STAGE + (usb_msos20 - probe_start)
    mov r1, #30
    b usb_send
usb_vendor_next:
    ldr r4, =0x0102
    cmp r0, r4
    beq usb_ack
    ldr r4, =0x0302
    cmp r0, r4
    beq usb_ack
    ldr r4, =0x0082
    cmp r0, r4
    beq usb_get_status_ep
    ldr r4, =0x5140
    cmp r0, r4
    beq usb_set_value
    ldr r4, =0x52c0
    cmp r0, r4
    beq usb_get_touch
    b usb_stall

usb_descriptor:
    ldrh r5, [r8, #90]
    add r5, r5, #1
    strh r5, [r8, #90]
    cmp r1, #0x00f
    bne usb_desc_device
    cmp r2, #0
    bne usb_stall
    ldr r0, =STAGE + (usb_bos - probe_start)
    mov r1, #33
    b usb_send
usb_desc_device:
    cmp r1, #0x100
    bne usb_desc_config
    cmp r2, #0
    bne usb_stall
    ldr r0, =STAGE + (usb_device - probe_start)
    mov r1, #18
    b usb_send
usb_desc_config:
    cmp r1, #0x200
    bne usb_desc_os_string
    cmp r2, #0
    bne usb_stall
    ldr r0, =STAGE + (usb_configuration - probe_start)
    mov r1, #32
    b usb_send
usb_desc_os_string:
    ldr r4, =0x03ee
    cmp r1, r4
    bne usb_stall
    ldr r0, =STAGE + (ms_os_string - probe_start)
    mov r1, #18
    b usb_send
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
    b usb_status_reply
usb_get_status_ep:
    cmp r1, #0
    bne usb_stall
usb_status_reply:
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
    ldrh r5, [r8, #92]
    add r5, r5, #1
    strh r5, [r8, #92]
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
    ldrh r5, [r8, #94]
    add r5, r5, #1
    strh r5, [r8, #94]
    mov r0, #0x20
    strh r0, [r6, #0x1c]
usb_return:
    bx lr

    .balign 4
hwid:    .hword 596
version: .hword 490
footer:  .hword 0xA55A
    .balign 4
scratch:
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0

    .balign 4
usb_device:
    .byte 18,1,0x00,2,0,0,0,64,0x09,0x12,0xfc,0xff,1,0,0,0,0,1
usb_configuration:
    .byte 9,2,32,0,1,1,0,0x80,250
    .byte 9,4,0,0,2,0xff,0,0,0
    .byte 7,5,0x81,2,64,0,0
    .byte 7,5,0x01,2,64,0,0
usb_bos:
    .byte 5,0x0f,33,0,1
    .byte 28,0x10,5,0
    .byte 0xdf,0x60,0xdd,0xd8,0x89,0x45,0xc7,0x4c
    .byte 0x9c,0xd2,0x65,0x9d,0x9e,0x64,0x8a,0x9f
    .byte 0,0,3,6
    .byte 30,0
    .byte 0x6b,0
usb_msos20:
    .byte 10,0,0,0,0,0,3,6,30,0
    .byte 20,0,3,0
    .ascii "WINUSB"
    .byte 0,0,0,0,0,0,0,0,0,0
ms_os_string:
    .byte 18,3
    .byte 0x4d,0,0x53,0,0x46,0,0x54,0,0x31,0,0x30,0,0x30,0
    .byte 0x6b,0
ms_compat_id:
    .byte 0x28,0,0,0
    .byte 0,1
    .byte 4,0
    .byte 1
    .byte 0,0,0,0,0,0,0
    .byte 0
    .byte 1
    .ascii "WINUSB"
    .byte 0,0
    .byte 0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0
    .balign 4

    .ltorg
    .balign 4
hwid:    .hword 596
version: .hword 490
footer:  .hword 0xA55A
    .balign 4
scratch:
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0

usb_device:
    .byte 18,1,0x00,2,0,0,0,64,0x09,0x12,0xfc,0xff,1,0,0,0,0,1
usb_configuration:
    .byte 9,2,32,0,1,1,0,0x80,250
    .byte 9,4,0,0,2,0xff,0,0,0
    .byte 7,5,0x81,2,64,0,0
    .byte 7,5,0x01,2,64,0,0
usb_bos:
    .byte 5,0x0f,33,0,1
    .byte 28,0x10,5,0
    .byte 0xdf,0x60,0xdd,0xd8,0x89,0x45,0xc7,0x4c
    .byte 0x9c,0xd2,0x65,0x9d,0x9e,0x64,0x8a,0x9f
    .byte 0,0,3,6
    .byte 30,0
    .byte 0x6b,0
usb_msos20:
    .byte 10,0,0,0,0,0,3,6,30,0
    .byte 20,0,3,0
    .ascii "WINUSB"
    .byte 0,0,0,0,0,0,0,0,0,0
ms_os_string:
    .byte 18,3
    .byte 0x4d,0,0x53,0,0x46,0,0x54,0,0x31,0,0x30,0,0x30,0
    .byte 0x6b,0
ms_compat_id:
    .byte 0x28,0,0,0
    .byte 0,1
    .byte 4,0
    .byte 1
    .byte 0,0,0,0,0,0,0
    .byte 0
    .byte 1
    .ascii "WINUSB"
    .byte 0,0
    .byte 0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0
    .balign 4
    .ltorg

font:
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,125,0,0,0,0,0,0,0,20
    .byte 127,20,127,20,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,28,34,65,0,0,65,34
    .byte 28,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,8,8,8,8,8,0,3,3,0,0,2,4,8,16,32
    .byte 62,69,73,81,62,0,33,127,1,0,33,67,69,73,49,66
    .byte 65,81,105,70,12,20,36,127,4,114,81,81,81,78,30,41
    .byte 73,73,6,64,71,72,80,96,54,73,73,73,54,48,73,73
    .byte 74,60,0,54,54,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,20,20,20,20,20,0,0,0,0,0,32,64,69,72,48
    .byte 0,0,0,0,0,63,68,68,68,63,127,73,73,73,54,62
    .byte 65,65,65,34,127,65,65,34,28,127,73,73,73,65,127,72
    .byte 72,72,64,62,65,73,73,46,127,8,8,8,127,0,65,127
    .byte 65,0,2,1,65,126,64,127,8,20,34,65,127,1,1,1
    .byte 1,127,32,24,32,127,127,16,8,4,127,62,65,65,65,62
    .byte 127,72,72,72,48,62,65,69,66,61,127,72,76,74,49,50
    .byte 73,73,73,38,64,64,127,64,64,126,1,1,1,126,124,2
    .byte 1,2,124,126,1,6,1,126,99,20,8,20,99,112,8,7
    .byte 8,112,67,69,73,81,97,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1
    .byte 0,0,0,0,0,63,68,68,68,63,127,73,73,73,54,62
    .byte 65,65,65,34,127,65,65,34,28,127,73,73,73,65,127,72
    .byte 72,72,64,62,65,73,73,46,127,8,8,8,127,0,65,127
    .byte 65,0,2,1,65,126,64,127,8,20,34,65,127,1,1,1
    .byte 1,127,32,24,32,127,127,16,8,4,127,62,65,65,65,62
    .byte 127,72,72,72,48,62,65,69,66,61,127,72,76,74,49,50
    .byte 73,73,73,38,64,64,127,64,64,126,1,1,1,126,124,2
    .byte 1,2,124,126,1,6,1,126,99,20,8,20,99,112,8,7
    .byte 8,112,67,69,73,81,97,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0


str_title:  .asciz "USB EP0 DIAG"
str_setup:  .asciz "SET"
str_req:    .asciz "REQ"
str_val:    .asciz "VAL"
str_len:    .asciz "LEN"
str_idx:    .asciz "IDX"
str_desc:   .asciz "DSC"
str_send:   .asciz "SND"
str_stall:  .asciz "STL"
str_flag:   .asciz "FLG"
str_irq:    .asciz "IRQ"
str_ctl:    .asciz "CTL"
str_ep0:    .asciz "EP0"
    .balign 4
