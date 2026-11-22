/* nüvi 200W (HWID 737, SW 4.00) - SAFE debug HUD.
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
.equ BUF0,     0x11F807C0
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
    cmp r12, #12
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
    ldr r0, =0x500
    cmp r8, r0
    bhs do_exit
    ldr r0, =BG
    bl fill_screen

    ldr r0, =str_title
    ldr r1, =FG2
    mov r2, #8
    mov r3, #8
    bl draw_string

    ldr r0, =str_safe
    ldr r1, =FG
    mov r2, #8
    mov r3, #24
    bl draw_string

    ldr r0, =str_frame
    ldr r1, =FG
    mov r2, #8
    mov r3, #48
    bl draw_string
    mov r0, r8
    ldr r1, =FG3
    mov r2, #56
    mov r3, #48
    bl draw_hex32

    /* DMA base/start/end/len from live regs */
    ldr r0, =str_dma
    ldr r1, =FG2
    mov r2, #8
    mov r3, #72
    bl draw_string

    ldr r0, =str_dmas
    ldr r1, =FG
    mov r2, #8
    mov r3, #88
    bl draw_string
    ldr r7, =DMA_BASE
    ldrh r0, [r7, #8]
    ldrh r1, [r7, #10]
    orr r0, r0, r1, lsl #16
    ldr r1, =FG3
    mov r2, #80
    mov r3, #88
    bl draw_hex32

    ldr r0, =str_dmae
    ldr r1, =FG
    mov r2, #8
    mov r3, #104
    bl draw_string
    ldr r7, =DMA_BASE
    ldrh r0, [r7, #12]
    ldrh r1, [r7, #14]
    orr r0, r0, r1, lsl #16
    ldr r1, =FG3
    mov r2, #80
    mov r3, #104
    bl draw_hex32

    ldr r0, =str_dmal
    ldr r1, =FG
    mov r2, #8
    mov r3, #120
    bl draw_string
    ldr r7, =DMA_BASE
    ldrh r4, [r7, #8]
    ldrh r0, [r7, #10]
    orr r4, r4, r0, lsl #16
    ldrh r5, [r7, #12]
    ldrh r0, [r7, #14]
    orr r5, r5, r0, lsl #16
    sub r0, r5, r4
    ldr r1, =FG3
    mov r2, #80
    mov r3, #120
    bl draw_hex32

    /* LCD control regs (read-only) */
    ldr r0, =str_lcd
    ldr r1, =FG2
    mov r2, #8
    mov r3, #144
    bl draw_string
    ldr r0, =str_l0
    ldr r1, =FG
    mov r2, #8
    mov r3, #160
    bl draw_string
    ldr r0, =0xfffec000
    ldr r0, [r0]
    ldr r1, =FG3
    mov r2, #80
    mov r3, #160
    bl draw_hex32
    ldr r0, =str_l4
    ldr r1, =FG
    mov r2, #8
    mov r3, #176
    bl draw_string
    ldr r0, =0xfffec004
    ldr r0, [r0]
    ldr r1, =FG3
    mov r2, #80
    mov r3, #176
    bl draw_hex32

        /* Read-only ADC/timer/GPIO candidates - no writes */
    ldr r0, =str_adc
    ldr r1, =FG2
    mov r2, #8
    mov r3, #200
    bl draw_string
    ldr r0, =str_a14
    ldr r1, =FG
    mov r2, #8
    mov r3, #216
    bl draw_string
    ldr r0, =0xfffe6014
    ldrh r0, [r0]
    ldr r1, =FG3
    mov r2, #64
    mov r3, #216
    bl draw_hex16
    ldr r0, =str_a18
    ldr r1, =FG
    mov r2, #128
    mov r3, #216
    bl draw_string
    ldr r0, =0xfffe6018
    ldrh r0, [r0]
    ldr r1, =FG3
    mov r2, #184
    mov r3, #216
    bl draw_hex16
    ldr r0, =str_a34
    ldr r1, =FG
    mov r2, #248
    mov r3, #216
    bl draw_string
    ldr r0, =0xfffe6034
    ldrh r0, [r0]
    ldr r1, =FG3
    mov r2, #304
    mov r3, #216
    bl draw_hex16

    ldr r0, =str_tmr
    ldr r1, =FG
    mov r2, #8
    mov r3, #232
    bl draw_string
    ldr r0, =0xfffec708
    ldr r0, [r0]
    ldr r1, =FG3
    mov r2, #64
    mov r3, #232
    bl draw_hex32

    ldr r0, =str_gpio
    ldr r1, =FG2
    mov r2, #8
    mov r3, #248
    bl draw_string
    ldr r0, =str_ge
    ldr r1, =FG
    mov r2, #8
    mov r3, #264
    bl draw_string
    ldr r0, =0xfffbe42c
    ldr r0, [r0]
    ldr r1, =FG3
    mov r2, #64
    mov r3, #264
    bl draw_hex32
    ldr r0, =str_gc
    ldr r1, =FG
    mov r2, #248
    mov r3, #264
    bl draw_string
    ldr r0, =0xfffbec2c
    ldr r0, [r0]
    ldr r1, =FG3
    mov r2, #304
    mov r3, #264
    bl draw_hex32
ldr r12, =0x00200000
delay:
    subs r12, r12, #1
    bne delay
    b main_loop

do_exit:
    /* Best-effort: clear screen and park. No verified return-to-OS path. */
    ldr r0, =0xF800
    bl fill_screen
    ldr r0, =str_exit
    ldr r1, =FG
    mov r2, #8
    mov r3, #120
    bl draw_string
    b park

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
    mov r0, #1
    tst r11, r0, lsl r12
    beq dc_skip
    add r2, r6, r10
    mov r1, #6
    sub r3, r1, r12
    add r3, r7, r3  /* flip glyph vertically only */
    mov r0, r5
    bl put_pixel
dc_skip:
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
park:
    b park

    .ltorg
    .balign 4
hwid:    .hword 737
version: .hword 400
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

str_title:  .asciz "NUVI 200W DEBUG SAFE"
str_safe:   .asciz "NO GPIO/ADC WRITES. READ-ONLY HUD."
str_frame:  .asciz "FRAME:"
str_dma:    .asciz "DMA REGS (READ ONLY)"
str_dmas:   .asciz "START:"
str_dmae:   .asciz "END:"
str_dmal:   .asciz "LEN:"
str_lcd:    .asciz "LCD REGS (READ ONLY)"
str_l0:     .asciz "FFC000:"
str_l4:     .asciz "FFC004:"
str_adc:    .asciz "ADC/TMR/GPIO READ ONLY"
str_a14:   .asciz "6014:"
str_a18:   .asciz "6018:"
str_a34:   .asciz "6034:"
str_tmr:   .asciz "T708:"
str_gpio:  .asciz "GPIO DIN CANDIDATES"
str_ge:    .asciz "E42C:"
str_gc:    .asciz "EC2C:"
str_exit:   .asciz "COUNTER 500 REACHED. SAFE STOP - RESET"
    .balign 4
