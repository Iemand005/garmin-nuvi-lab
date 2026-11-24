/* nuvi 660 (HWID 596, SW 4.90) - USB colour control.
 * LOCAL EXPERIMENT. Takes over the stock-initialized UDC at 0xfffb4000
 * and exposes vendor request 0x51 (OUT, wValue=RGB565, wIndex=0, wLength=0)
 * to set the full-screen fill colour. Remove SD before recovery reset.
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
.equ COLOR_OFF, 14
.equ LAST_OFF,  16

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
    bl usb_init
    ldr r8, =STAGE + (scratch - probe_start)
    ldrh r1, [r8, #62]
    cmp r1, #1
    moveq r0, #0x001F
    movne r0, #0xF800
    strh r0, [r8, #COLOR_OFF]
    ldr r0, =0xFFFF
    strh r0, [r8, #LAST_OFF]
    b main_loop

main_loop:
    bl usb_poll
    ldr r8, =STAGE + (scratch - probe_start)
    ldrh r0, [r8, #COLOR_OFF]
    ldrh r1, [r8, #LAST_OFF]
    cmp r0, r1
    beq main_delay
    strh r0, [r8, #LAST_OFF]
    bl fill_screen
main_delay:
    ldr r12, =0x4000
delay:
    subs r12, r12, #1
    bne delay
    b main_loop

fill_screen:
    mov r1, r9
    ldr r2, =PIXELS
fs_loop:
    strh r0, [r1], #2
    subs r2, r2, #1
    bne fs_loop
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
    .byte 18,1,0x00,2,0,0,0,64,0x1e,9,0xfc,0xff,1,0,0,0,0,1
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
