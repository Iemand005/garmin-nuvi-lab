/* nüvi 660 (HWID 596, SW 4.90) - SAFE debug HUD.
 * LOCAL EXPERIMENT. No GPIO writes, no ADC writes, no unknown MMIO reads.
 * Only reads DMA/LCD regs and renders debug text to framebuffer.
 * Remove SD before recovery reset.
 */
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.balign 4
.global probe_start
.equ STAGE,    0x10040000
.equ DMA_BASE, 0xFFFEE3C0
.equ DMA_LEN,  0x3FC1E
.equ BUF0,     0x11FC03E0
.equ BUF1,     0x11FC03E0
.equ PIXHDR,   32
.equ WIDTH,    480
.equ HEIGHT,   272
.equ STRIDE,   960
.equ PIXELS,   130560
.equ BG,       0x1082
.equ FG,       0xFFFF
.equ FG2,      0x07E0
.equ FG3,      0xFFE0

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
    mov r8, #0

main_loop:
    add r8, r8, #1
    mov r2, #2
    mov r3, #2
    ldr r1, =FG2
    ldr r0, =str_title
    bl draw_string
    mov r2, #170
    mov r3, #2
    ldr r1, =FG
    ldr r0, =str_frame
    bl draw_string
    mov r0, r8
    mov r2, #212
    mov r3, #2
    ldr r1, =FG3
    bl draw_hex16

    /* DMA */
    mov r2, #2
    mov r3, #12
    ldr r1, =FG2
    ldr r0, =str_dma
    bl draw_string
    ldr r7, =DMA_BASE
    ldrh r0, [r7, #8]
    ldrh r1, [r7, #10]
    orr r0, r0, r1, lsl #16
    mov r2, #38
    mov r3, #12
    ldr r1, =FG3
    bl draw_hex32
    ldrh r0, [r7, #12]
    ldrh r1, [r7, #14]
    orr r0, r0, r1, lsl #16
    mov r2, #136
    mov r3, #12
    ldr r1, =FG3
    bl draw_hex32
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    sub r0, r5, r4
    mov r2, #234
    mov r3, #12
    ldr r1, =FG3
    bl draw_hex32

    /* LCD */
    mov r2, #2
    mov r3, #22
    ldr r1, =FG2
    ldr r0, =str_lcd
    bl draw_string
    ldr r0, =0xfffec000
    ldr r0, [r0]
    mov r2, #38
    mov r3, #22
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffec004
    ldr r0, [r0]
    mov r2, #136
    mov r3, #22
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffec008
    ldr r0, [r0]
    mov r2, #234
    mov r3, #22
    ldr r1, =FG3
    bl draw_hex32

    /* ADC regs read-only */
    mov r2, #2
    mov r3, #32
    ldr r1, =FG2
    ldr r0, =str_adc
    bl draw_string
    ldr r0, =0xfffe6014
    ldrh r0, [r0]
    mov r2, #38
    mov r3, #32
    ldr r1, =FG3
    bl draw_hex16
    ldr r0, =0xfffe6018
    ldrh r0, [r0]
    mov r2, #86
    mov r3, #32
    ldr r1, =FG3
    bl draw_hex16
    ldr r0, =0xfffe6034
    ldrh r0, [r0]
    mov r2, #134
    mov r3, #32
    ldr r1, =FG3
    bl draw_hex16
    ldr r0, =0xfffec708
    ldr r0, [r0]
    mov r2, #182
    mov r3, #32
    ldr r1, =FG3
    bl draw_hex32

    /* GPIO DATAIN candidates (read-only) */
    mov r2, #2
    mov r3, #42
    ldr r1, =FG2
    ldr r0, =str_gpa
    bl draw_string
    ldr r0, =0xfffbc430
    ldr r0, [r0]
    mov r2, #38
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbcc30
    ldr r0, [r0]
    mov r2, #136
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbdc30
    ldr r0, [r0]
    mov r2, #234
    mov r3, #42
    ldr r1, =FG3
    bl draw_hex32

    mov r2, #2
    mov r3, #52
    ldr r1, =FG2
    ldr r0, =str_gpb
    bl draw_string
    ldr r0, =0xfffbe430
    ldr r0, [r0]
    mov r2, #38
    mov r3, #52
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbec30
    ldr r0, [r0]
    mov r2, #136
    mov r3, #52
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbe42c
    ldr r0, [r0]
    mov r2, #234
    mov r3, #52
    ldr r1, =FG3
    bl draw_hex32

    mov r2, #2
    mov r3, #62
    ldr r1, =FG2
    ldr r0, =str_gpc
    bl draw_string
    ldr r0, =0xfffbec2c
    ldr r0, [r0]
    mov r2, #38
    mov r3, #62
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbc42c
    ldr r0, [r0]
    mov r2, #136
    mov r3, #62
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbcc2c
    ldr r0, [r0]
    mov r2, #234
    mov r3, #62
    ldr r1, =FG3
    bl draw_hex32

    /* Touch: guarded TSC2046 read via McSPI0 (660 4.90 app seq) */
    mov r2, #2
    mov r3, #72
    ldr r1, =FG2
    ldr r0, =str_tch
    bl draw_string
    bl sample_touch_raw
    mov r6, r0
    mov r0, r4
    mov r2, #38
    mov r3, #72
    ldr r1, =FG3
    bl draw_hex16
    mov r0, r5
    mov r2, #86
    mov r3, #72
    ldr r1, =FG3
    bl draw_hex16
    mov r0, r6
    mov r2, #134
    mov r3, #72
    ldr r1, =FG3
    bl draw_hex16

    /* more read-only regs: MPUIO/GPIO direction/data candidates */
    mov r2, #2
    mov r3, #86
    ldr r1, =FG2
    ldr r0, =str_dir
    bl draw_string
    ldr r0, =0xfffbe434
    ldr r0, [r0]
    mov r2, #38
    mov r3, #86
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbec34
    ldr r0, [r0]
    mov r2, #136
    mov r3, #86
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffbc434
    ldr r0, [r0]
    mov r2, #234
    mov r3, #86
    ldr r1, =FG3
    bl draw_hex32

    mov r2, #2
    mov r3, #96
    ldr r1, =FG2
    ldr r0, =str_mpu
    bl draw_string
    ldr r0, =0xfffb5008
    ldr r0, [r0]
    mov r2, #38
    mov r3, #96
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffb5004
    ldr r0, [r0]
    mov r2, #136
    mov r3, #96
    ldr r1, =FG3
    bl draw_hex32
    ldr r0, =0xfffb5014
    ldr r0, [r0]
    mov r2, #234
    mov r3, #96
    ldr r1, =FG3
    bl draw_hex32

    /* help */
    mov r2, #2
    mov r3, #110
    ldr r1, =FG
    ldr r0, =str_note
    bl draw_string

    ldr r12, =0x00100000
delay:
    subs r12, r12, #1
    bne delay
    b main_loop

do_exit:
    ldr r0, =BG
    bl fill_screen
    ldr r0, =str_exit
    ldr r1, =FG2
    mov r2, #2
    mov r3, #120
    bl draw_string
    ldr r0, =str_exit2
    ldr r1, =FG
    mov r2, #2
    mov r3, #132
    bl draw_string
park_idle:
    ldr r12, =0x40000
pi_d:
    subs r12, r12, #1
    bne pi_d
    b park_idle

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
    stmfd sp!, {r4-r11,lr}
    /* Only attempt when PENIRQ-like bit19 is low on BE434 */
    ldr r0, =0xfffbe434
    ldr r0, [r0]
    tst r0, #0x80000
    movne r4, #0
    movne r5, #0
    movne r0, #0
    ldmfdne sp!, {r4-r11,pc}

    ldr r8, =0xfffb0c00
    ldr r0, [r8, #0x14]
    tst r0, #1
    beq tr_fail

    /* Save CH0CONF/CH0CTRL */
    ldr r9, [r8, #0x2c]
    ldr r10, [r8, #0x28]

    /* X: cmd 0xD0 (12bit, ADC on, ref on) */
    mov r0, #0xD0
    bl spi_cmd8
    cmp r0, #0
    blt tr_fail_restore
    mov r0, #0
    bl spi_read16
    cmp r0, #0
    blt tr_fail_restore
    mov r4, r0

    /* Y: cmd 0x90 */
    mov r0, #0x90
    bl spi_cmd8
    cmp r0, #0
    blt tr_fail_restore
    mov r0, #0
    bl spi_read16
    cmp r0, #0
    blt tr_fail_restore
    mov r5, r0

    /* PD: cmd 0x00 */
    mov r0, #0x00
    bl spi_cmd8

    /* Restore */
    str r10, [r8, #0x28]
    str r9, [r8, #0x2c]
    mov r0, #1
    ldmfd sp!, {r4-r11,pc}

tr_fail_restore:
    str r10, [r8, #0x28]
    str r9, [r8, #0x2c]
tr_fail:
    mov r4, #0xFFFF
    mov r5, #0xFFFF
    mov r0, #2
    ldmfd sp!, {r4-r11,pc}

spi_cmd8:
    stmfd sp!, {r4-r7,lr}
    mov r4, r0
    ldr r6, =0xfffb0c00
    /* CH0CONF: 8-bit, D0, CLKD small, force single, POL=0 PHA=0 from app-ish */
    ldr r0, [r6, #0x2c]
    bic r0, r0, #0x1F         /* WL */
    orr r0, r0, #0x07         /* 8-bit */
    bic r0, r0, #(1<<20)      /* TURBO off */
    orr r0, r0, #(1<<16)      /* FORCE */
    str r0, [r6, #0x2c]
    mov r0, #1
    str r0, [r6, #0x28]       /* CH0CTRL enable */
    ldr r2, =300000
spi_cmd_txs:
    ldr r1, [r6, #0x30]
    tst r1, #2
    bne spi_cmd_txs_ok
    subs r2, r2, #1
    bne spi_cmd_txs
    b spi_err
spi_cmd_txs_ok:
    str r4, [r6, #0x38]
    ldr r2, =300000
spi_cmd_rxs:
    ldr r1, [r6, #0x30]
    tst r1, #1
    bne spi_cmd_rxs_ok
    subs r2, r2, #1
    bne spi_cmd_rxs
    b spi_err
spi_cmd_rxs_ok:
    ldr r0, [r6, #0x3c]
    mov r0, #0
    str r0, [r6, #0x28]
    ldmfd sp!, {r4-r7,pc}

spi_read16:
    stmfd sp!, {r4-r7,lr}
    ldr r6, =0xfffb0c00
    ldr r0, [r6, #0x2c]
    bic r0, r0, #0x1F
    orr r0, r0, #0x0F         /* 16-bit */
    orr r0, r0, #(1<<16)
    str r0, [r6, #0x2c]
    mov r0, #1
    str r0, [r6, #0x28]
    ldr r2, =300000
spi_rd_txs:
    ldr r1, [r6, #0x30]
    tst r1, #2
    bne spi_rd_txs_ok
    subs r2, r2, #1
    bne spi_rd_txs
    b spi_err
spi_rd_txs_ok:
    mov r0, #0
    str r0, [r6, #0x38]
    ldr r2, =300000
spi_rd_rxs:
    ldr r1, [r6, #0x30]
    tst r1, #1
    bne spi_rd_rxs_ok
    subs r2, r2, #1
    bne spi_rd_rxs
    b spi_err
spi_rd_rxs_ok:
    ldr r0, [r6, #0x3c]
    mov r1, #0
    str r1, [r6, #0x28]
    mov r0, r0, lsr #3
    ldr r1, =0x0FFF
    and r0, r0, r1
    ldmfd sp!, {r4-r7,pc}

spi_err:
    mov r0, #0
    str r0, [r6, #0x28]
    mvn r0, #0
    ldmfd sp!, {r4-r7,pc}


park:
    b park

    .ltorg
    .balign 4
hwid:    .hword 596
version: .hword 490
footer:  .hword 0xA55A
    .balign 4
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

str_title:  .asciz "660 490"
str_frame:  .asciz "FR:"
str_dma:    .asciz "DMA"
str_lcd:    .asciz "LCD"
str_adc:    .asciz "ADC"
str_gpa:    .asciz "GPA"
str_gpb:    .asciz "GPB"
str_gpc:    .asciz "GPC"
str_tch:    .asciz "TCH"
str_tx:     .asciz "X"
str_ty:     .asciz "Y"
str_tp:     .asciz "P"
str_dir:    .asciz "DIR"
str_mpu:    .asciz "MPU"
str_note:   .asciz "TOGGLE PWR SW: WATCH GPIO/MPU BITS"
str_exit:   .asciz "500 REACHED. IDLE LOW-CPU. HOLD PWR SW."
str_exit2:  .asciz "NO OS RETURN/POWEROFF PATH VERIFIED."
    .balign 4
