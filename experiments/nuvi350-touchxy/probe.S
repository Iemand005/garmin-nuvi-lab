/* Bounded raw-coordinate touch candidate for nuvi 350-family HWID 0476 / software 6.20 ONLY.
 * Reuses private EP0; touch transactions reproduce verified350 stock commands.
 * No GPIO directions, muxes, SPI resets, clock configuration or flash writes.
 * Reads LCD/DMA; documented350-stock USB initialization only, no flash/filesystem.
 * Draws a persistent64x64 monochrome checkerboard in one validated framebuffer.
 * USB guard failure leaves marker; LCD guards PARK. Reset required to recover.
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
    cmp r12, #2
    bne park
    /* Enabled TFT / palette-and-data path; no timing or orientation writes. */
    ldr r0, =0xfffec000
    ldr r1, [r0]
    and r2, r1, #0x81
    cmp r2, #0x81
    bne park
    tst r1, #0x00300000
    bne park
    /* Both exact dimension profiles are present in this350 firmware.
     * Resident TIMING1/TIMING2 values: 0x3106253f/0x120008ef or
     * 0x051438ef/0x0605093f. Select matching RAM stride, never reprogram LCD.
     */
    ldr r2, [r0, #4]
    ldr r3, =0x3ff
    and r2, r2, r3
    ldr r1, [r0, #8]
    and r1, r1, r3
    ldr r3, =319
    cmp r2, r3
    beq landscape
    cmp r2, #239
    bne park
    cmp r1, r3
    bne park
    mov r8, #480
    ldr r9, =0xf0d0
    b profile_ready
landscape:
    cmp r1, #239
    bne park
    mov r8, #640
    ldr r9, =0xdd20
profile_ready:

    /* Snapshot programmed DMA B1 start/end using halfword accesses. */
    ldr r7, =0xfffee3c0
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    ldr r0, =0x11fda7e0
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

    mov r10, r4
    /* Centered64x64 board. White/black survives either RGB pixel layout.
     * Keep the pattern visible until reset; do not return to overwritten stock code.
     */
    add r4, r4, r9
    ldr r2, =0xffff
    mov r6, #0
marker_row:
    mov r5, #0
marker_pixel:
    mov r0, r6, lsr #5
    eor r0, r0, r5, lsr #5
    tst r0, #1
    moveq r0, #0
    movne r0, r2
    strh r0, [r4], #2
    add r5, r5, #1
    cmp r5, #64
    bne marker_pixel
    sub r0, r8, #128
    add r4, r4, r0
    add r6, r6, #1
    cmp r6, #64
    bne marker_row
    add r9, r10, #32
    mov lr, pc
    b usb_init
input_loop:
    mov lr, pc
    b usb_poll
    b input_loop

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
    /* Stock 0x100ec658 configures USB0 transceiver mode3 and OTG_EN.
     * Refuse a different inherited mode. Do not alter reset/clock/PHY settings.
     */
    ldr r2, =0xfffb0400
    ldr r0, [r2, #4]
    and r1, r0, #0x70000
    cmp r1, #0x30000
    bne usb_disabled
    ldr r0, [r2, #8]
    tst r0, #0x80000000
    beq usb_disabled
    /* Exact stock read/OR/write at 0x100ec664..66c, also Linux BSESSVLD. */
    ldr r0, [r2, #12]
    orr r0, r0, #0x40000
    str r0, [r2, #12]
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
    ldrh r0, [r8, #66]
    orr r0, r0, r5
    strh r0, [r8, #66]
    tst r5, #8
    beq usb_no_ds
    ldrh r0, [r6, #0x20]
    tst r0, #0x20
    movne r0, #0
    strhne r0, [r8, #32]
    strhne r0, [r8, #90]
    mov r0, #8
    strh r0, [r6, #0x30]
usb_no_ds:
    /* TI SPRU761A Table35: clear completion flags BEFORE FIFO enable.
     * Snapshot both flags, clear them once; never clear a newly arriving event.
     */
    and r0, r5, #3
    strh r0, [r6, #0x30]
    /* A fresh SETUP supersedes old TX/RX stages (Linux ep0_irq). */
    tst r5, #4
    bne usb_no_rx
    tst r5, #1
    beq usb_no_tx
    mov r0, #0x30
    strh r0, [r6, #4]
    ldrh r4, [r6, #0x10]
    tst r4, #0x20
    movne r0, #0x80
    strhne r0, [r6, #12]
    mov r0, #0x10
    strh r0, [r6, #4]
    tst r4, #8
    beq usb_no_tx
    /* IN data completion arms OUT status; OUT-request IN status is finished. */
    ldrh r0, [r8, #34]
    tst r0, #0x80
    beq usb_no_tx
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
usb_no_tx:
    tst r5, #2
    beq usb_no_rx
    ldrh r0, [r8, #90]
    cmp r0, #1
    beq player_receive
    /* Legacy OUT requests have zero data bytes. RX is IN status:
     * consume/clear it without rearming EP0 outside a control transfer.
     */
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
usb_no_rx:
    ldrh r5, [r6, #0x30]
    tst r5, #4
    beq usb_return
    mov r0, #0
    strh r0, [r8, #90]
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
    ldrh r4, [r8, #64]
    add r4, r4, #1
    strh r4, [r8, #64]
    mov r4, #0
    strh r4, [r6, #4]
    ldrh r4, [r6, #0x30]
    tst r4, #4
    bne usb_return
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
    ldr r4, =0x5340
    cmp r0, r4
    beq music_text
    ldr r4, =0x54c0
    cmp r0, r4
    beq music_event
    ldr r4, =0x5540
    cmp r0, r4
    beq music_ack
    ldr r4, =0x56c0
    cmp r0, r4
    beq music_info
    ldr r4, =0x5740
    cmp r0, r4
    beq player_chunk
    ldr r4, =0x58c0
    cmp r0, r4
    beq usb350_info
    ldr r4, =0x59c0
    cmp r0, r4
    beq touch_snapshot
    ldr r4, =0x5ac0
    cmp r0, r4
    beq touch_sample
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
    strh r1, [r8, #68]
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
    mov r0, #2
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

usb350_info:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    ldr r0, =0x3530
    strh r0, [r8, #42]
    mov r0, #1
    strh r0, [r8, #44]
    ldr r0, =476
    strh r0, [r8, #46]
    ldr r0, =620
    strh r0, [r8, #48]
    ldr r0, =0xfffec000
    ldr r2, =0x3ff
    ldr r1, [r0, #4]
    and r1, r1, r2
    add r1, r1, #1
    strh r1, [r8, #50]
    ldr r1, [r0, #8]
    and r1, r1, r2
    add r1, r1, #1
    strh r1, [r8, #52]
    sub r0, r9, #32
    strh r0, [r8, #54]
    mov r0, r0, lsr #16
    strh r0, [r8, #56]
    add r0, r8, #42
    mov r1, #16
    b usb_send

/* Fixed, read-only register snapshots. No arbitrary memory accessor, no SPI RX
 * read (RX read would clear RX_FULL), GPIO/SPI writes, resets or clock changes.
 * GPIO mapping SPRU767A tables8..10; SPI SPRU760C tables3,5,8..11.
 * index0: GPIO DATAIN/DATAOUT/DIRECTION
 * index1: SPI SET1/SET2/CTRL
 * index2: SPI DSR/SSR/REV (status reads have no clear-on-read behavior).
 * Reply: uint16 magic3554,index; uint32[3] little endian.
 */
touch_snapshot:
    cmp r1, #0
    bne usb_stall
    cmp r2, #2
    bhi usb_stall
    ldr r0, =0x3554
    strh r0, [r8, #42]
    strh r2, [r8, #44]
    cmp r2, #0
    beq snapshot_gpio
    cmp r2, #1
    beq snapshot_spi_config
    ldr r0, =0xfffb0c30
    ldr r1, =0xfffb0c14
    ldr r2, =0xfffb0c00
    b snapshot_read
snapshot_gpio:
    ldr r0, =0xfffbe42c
    ldr r1, =0xfffbe430
    ldr r2, =0xfffbe434
    b snapshot_read
snapshot_spi_config:
    ldr r0, =0xfffb0c24
    ldr r1, =0xfffb0c28
    ldr r2, =0xfffb0c2c
snapshot_read:
    ldr r0, [r0]
    strh r0, [r8, #46]
    mov r0, r0, lsr #16
    strh r0, [r8, #48]
    ldr r1, [r1]
    strh r1, [r8, #50]
    mov r1, r1, lsr #16
    strh r1, [r8, #52]
    ldr r2, [r2]
    strh r2, [r8, #54]
    mov r2, r2, lsr #16
    strh r2, [r8, #56]
    add r0, r8, #42
    mov r1, #16
    b usb_send

/* Explicit request only, exactly16bytes. No automatic touch polling/actions.
 * Stock100d104c: D9,D9,99,99, each16-clock TX followed by two8-clock RX;
 * discard first conversion eachaxis. Inherited configuration measured on device.
 * Scratch96/98 hold transaction progress/firstbyte; reply42..57 is disjoint.
 * Flags:1 initialPENIRQlow,2 validXY,4 guardreject,8 SPIabort/timeout,
 * 16 releasedbeforefinish,32 invalidrange. CS always released after assertion.
 */
touch_sample:
    cmp r1, #0
    bne usb_stall
    cmp r2, #0
    bne usb_stall
    cmp r3, #16
    bne usb_stall
    ldr r0, =0x3558
    strh r0, [r8, #42]
    mov r0, #1
    strh r0, [r8, #44]
    mov r0, #0
    strh r0, [r8, #46]
    strh r0, [r8, #48]
    strh r0, [r8, #50]
    strh r0, [r8, #52]
    strh r0, [r8, #54]
    strh r0, [r8, #56]
    ldr r5, =0xfffb0c00
    ldr r0, =0xfffbe434
    ldr r0, [r0]
    tst r0, #0x4000
    beq sample_guard_fail
    tst r0, #2
    bne sample_guard_fail
    ldr r0, =0xfffbe430
    ldr r0, [r0]
    tst r0, #2
    beq sample_guard_fail
    ldr r0, [r5, #0x24]
    cmp r0, #0x0b
    bne sample_guard_fail
    ldr r0, [r5, #0x28]
    cmp r0, #0x8000
    bne sample_guard_fail
    ldr r0, [r5, #0x14]
    cmp r0, #1
    bne sample_guard_fail
    ldr r0, [r5, #0x2c]
    tst r0, #3
    bne sample_guard_fail
    ldr r0, [r5, #0x30]
    cmp r0, #2
    bne sample_guard_fail
    ldr r0, =0xfffbe42c
    ldr r0, [r0]
    strh r0, [r8, #56]
    tst r0, #0x4000
    bne sample_reply
    mov r0, #1
    strh r0, [r8, #46]
    ldr r0, =0xfffbe4b0
    mov r1, #2
    str r1, [r0]
    mov r4, #0
sample_transfer:
    strh r4, [r8, #96]
    ldr r0, [r5, #0x2c]
    tst r0, #3
    bne sample_timeout
    ldr r1, =0xfffffc03
    and r0, r0, r1
    cmp r4, #0
    beq sample_command
    cmp r4, #3
    beq sample_command
    cmp r4, #6
    beq sample_command
    cmp r4, #9
    beq sample_command
    /* Drain previous RX exactly as stock read function, then send dummy clocks. */
    ldr r1, [r5, #0x38]
    mov r1, #0
    str r1, [r5, #0x34]
    orr r0, r0, #0x1d
    mov r2, #1
    b sample_start
sample_command:
    mov r1, #0xd9
    cmp r4, #6
    movhs r1, #0x99
    str r1, [r5, #0x34]
    orr r0, r0, #0x3e
    mov r2, #2
sample_start:
    str r0, [r5, #0x2c]
    mov r3, #1024
sample_poll:
    ldr r0, [r5, #0x30]
    tst r0, r2
    bne sample_complete
    subs r3, r3, #1
    bne sample_poll
    b sample_timeout
sample_complete:
    cmp r2, #1
    bne sample_next
    ldr r0, [r5, #0x38]
    and r0, r0, #255
    cmp r4, #4
    beq sample_firstbyte
    cmp r4, #10
    beq sample_firstbyte
    cmp r4, #5
    beq sample_axis
    cmp r4, #11
    beq sample_axis
    b sample_next
sample_firstbyte:
    strh r0, [r8, #98]
    b sample_next
sample_axis:
    ldrh r1, [r8, #98]
    mov r1, r1, lsl #1
    orr r1, r1, r0, lsr #7
    cmp r4, #5
    strheq r1, [r8, #48]
    strhne r1, [r8, #50]
sample_next:
    add r4, r4, #1
    cmp r4, #12
    bne sample_transfer
    mov r0, #0
    strh r0, [r8, #52]
    b sample_release
sample_timeout:
    ldrh r0, [r8, #96]
    add r0, r0, #1
    strh r0, [r8, #52]
    mov r0, #9
    strh r0, [r8, #46]
sample_release:
    ldr r0, =0xfffbe4f0
    mov r1, #2
    str r1, [r0]
    /* Bounded settling delay before rechecking PENIRQ. No timer dependence. */
    mov r1, #256
sample_settle:
    subs r1, r1, #1
    bne sample_settle
    ldr r0, =0xfffbe42c
    ldr r0, [r0]
    strh r0, [r8, #56]
    ldrh r1, [r8, #46]
    tst r0, #0x4000
    orrne r1, r1, #16
    ldrh r0, [r8, #48]
    cmp r0, #255
    orrhi r1, r1, #32
    ldrh r0, [r8, #50]
    cmp r0, #255
    orrhi r1, r1, #32
    cmp r1, #1
    orreq r1, r1, #2
    strh r1, [r8, #46]
    b sample_reply
sample_guard_fail:
    mov r0, #4
    strh r0, [r8, #46]
sample_reply:
    ldrh r3, [r8, #40]
    ldr r0, [r5, #0x30]
    strh r0, [r8, #54]
    add r0, r8, #42
    mov r1, #16
    b usb_send

park:
    b park
    .ltorg
    .balign 4
hwid:
    .hword 476
version:
    .hword 620
footer:
    .hword 0xa55a
    .balign 4
scratch:
    .space 2048
usb_device:
    /* Private lab identity, not a mass-storage or firmware-update interface. */
    .byte 18,1,0x10,1,0,0,0,64,0x1e,9,0xfe,0xff,1,0,0,0,0,1
usb_configuration:
    .byte 9,2,18,0,1,1,0,0x80,250
    .byte 9,4,0,0,0,0xff,0,0,0
    .balign 4
screen:
probe_end:
