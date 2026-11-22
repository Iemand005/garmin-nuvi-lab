/* nüvi 200W (HWID 737, SW 4.00) - debug HUD payload.
 * LOCAL EXPERIMENT. Draws small-font hex debug info on screen.
 * Reads DMA MMIO, ADC/touch regs, and a small read-only GPIO candidate list.
 * No MMIO writes except existing touch/ADC control sequence (bounded).
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
.equ BG,       0x1082       /* dark gray */
.equ FG,       0xFFFF
.equ FG2,      0x07E0       /* green */
.equ FG3,      0xFFE0       /* yellow */
.equ PRESS_LO, 0x60
.equ PRESS_HI, 0x340

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

    /* Inherited ADC config guard */
    ldr r0, =0xfffe6000
    ldrh r1, [r0, #0x14]
    tst r1, #1
    beq park
    /* GPIO output guards for touch pins */
    ldr r0, =0xfffbb400
    ldr r1, [r0, #0x34]
    tst r1, #0x0e
    bne park
    ldr r0, =0xfffbe400
    ldr r1, [r0, #0x34]
    ldr r2, =0x8010
    tst r1, r2
    bne park

    add r9, r4, #PIXHDR         /* r9 pixel base */
    mov r8, #0                  /* frame counter */
    /* initial background */
    mov r0, #BG
    bl fill_screen

main_loop:
    add r8, r8, #1
    /* clear screen each frame for simplicity */
    mov r0, #BG
    bl fill_screen

    /* Header */
    ldr r1, =FG2
    mov r2, #8
    mov r3, #8
    ldr r0, =str_title
    bl draw_string
    ldr r1, =FG
    mov r2, #8
    mov r3, #20
    ldr r0, =str_hw
    bl draw_string

    /* Frame counter */
    mov r2, #320
    mov r3, #8
    ldr r0, =str_frame
    ldr r1, =FG
    bl draw_string
    mov r2, #368
    mov r3, #8
    mov r0, r8
    ldr r1, =FG3
    bl draw_hex32

    /* Touch sampling */
    bl sample_touch_raw         /* r0=state, r4=adc0, r5=adc1 */
    mov r6, r0                  /* save state */
    mov r2, #8
    mov r3, #44
    ldr r0, =str_adc0
    ldr r1, =FG
    bl draw_string
    mov r2, #56
    mov r3, #44
    mov r0, r4
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #120
    mov r3, #44
    ldr r0, =str_adc1
    ldr r1, =FG
    bl draw_string
    mov r2, #168
    mov r3, #44
    mov r0, r5
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #232
    mov r3, #44
    ldr r0, =str_state
    ldr r1, =FG
    bl draw_string
    mov r2, #280
    mov r3, #44
    mov r0, r6
    ldr r1, =FG2
    bl draw_hex16

    /* GPIO read-only candidates */
    mov r2, #8
    mov r3, #72
    ldr r0, =str_gpio
    ldr r1, =FG2
    bl draw_string

    /* row 1 */
    mov r2, #8
    mov r3, #88
    ldr r0, =str_g1
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffbc430
    ldr r0, [r0]
    mov r2, #120
    mov r3, #88
    ldr r1, =FG3
    bl draw_hex32
    mov r2, #248
    mov r3, #88
    ldr r0, =str_g2
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffbcc30
    ldr r0, [r0]
    mov r2, #360
    mov r3, #88
    ldr r1, =FG3
    bl draw_hex32

    /* row 2 */
    mov r2, #8
    mov r3, #104
    ldr r0, =str_g3
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffbdc30
    ldr r0, [r0]
    mov r2, #120
    mov r3, #104
    ldr r1, =FG3
    bl draw_hex32
    mov r2, #248
    mov r3, #104
    ldr r0, =str_g4
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffbec30
    ldr r0, [r0]
    mov r2, #360
    mov r3, #104
    ldr r1, =FG3
    bl draw_hex32

    /* row 3 - ADC regs */
    mov r2, #8
    mov r3, #128
    ldr r0, =str_adcstat
    ldr r1, =FG2
    bl draw_string
    mov r2, #8
    mov r3, #144
    ldr r0, =str_a1
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffe6014
    ldrh r0, [r0]
    mov r2, #120
    mov r3, #144
    ldr r1, =FG3
    bl draw_hex16
    mov r2, #248
    mov r3, #144
    ldr r0, =str_a2
    ldr r1, =FG
    bl draw_string
    ldr r0, =0xfffe6018
    ldrh r0, [r0]
    mov r2, #360
    mov r3, #144
    ldr r1, =FG3
    bl draw_hex16

    /* Footer */
    mov r2, #8
    mov r3, #240
    ldr r0, =str_foot
    ldr r1, =FG
    bl draw_string

    /* delay */
    ldr r12, =0x00100000
ui_delay:
    subs r12, r12, #1
    bne ui_delay
    b main_loop

/* fill_screen: r0=color */
fill_screen:
    mov r1, r9
    ldr r2, =PIXELS
fs_loop:
    strh r0, [r1], #2
    subs r2, r2, #1
    bne fs_loop
    bx lr

/* draw_string: r0=str ptr, r1=color, r2=x, r3=y. clobbers r0-r7,r10,r12 */
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

/* draw_char: r0=ascii, r1=color, r2=x, r3=y */
draw_char:
    stmfd sp!, {r4-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    and r4, r4, #127
    ldr r8, =font
    add r8, r8, r4, lsl #2
    add r8, r8, r4              /* r8 = font + c*5 */
    mov r10, #0                 /* col */
dc_col:
    ldrb r11, [r8, r10]
    mov r12, #0                 /* row */
dc_row:
    mov r0, #1
    tst r11, r0, lsl r12
    beq dc_skip
    add r2, r6, r10
    add r3, r7, r12
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

/* put_pixel: r0=color, r2=x, r3=y */
put_pixel:
    cmp r2, #WIDTH
    bhs pp_ret
    cmp r3, #HEIGHT
    bhs pp_ret
    ldr r1, =STRIDE
    mul r1, r3, r1
    add r1, r1, r2, lsl #1
    add r1, r9, r1
    strh r0, [r1]
pp_ret:
    bx lr

/* draw_hex32: r0=value, r1=color, r2=x, r3=y */
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

/* draw_hex16: r0=value, r1=color, r2=x, r3=y */
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

/* Touch sampling - raw, no debounce, for display */
sample_touch_raw:
    mov r10, lr
    bl select_0
    ldr r0, =0x8000
    bl sample_adc
    cmn r0, #1
    beq raw_fail
    mov r4, r0
    bl select_1
    ldr r0, =0x9000
    bl sample_adc
    cmn r0, #1
    beq raw_fail
    mov r5, r0
    bl select_0
    cmp r4, #PRESS_LO
    blo check_y
    ldr r2, =PRESS_HI
    cmp r4, r2
    blo is_pressed
check_y:
    cmp r5, #PRESS_LO
    blo not_pressed_sample
    ldr r2, =PRESS_HI
    cmp r5, r2
    blo is_pressed
not_pressed_sample:
    mov r0, #0
    bx r10
is_pressed:
    mov r0, #1
    bx r10
raw_fail:
    mov r0, #2
    mov r4, #0
    mov r5, #0
    bx r10

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
    .byte 0,0,0,0,0,0,0,125,0,0,0,0,0,0,0,0
    .byte 20,127,20,127,20,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,28,34,65,0,0,65,34,28,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,3,3
    .byte 2,4,8,16,32,62,69,73,81,62,0,33,127,1,0,33
    .byte 67,69,73,49,66,65,81,105,70,12,20,36,127,4,114
    .byte 81,81,81,78,30,41,73,73,6,64,71,72,80,96,54
    .byte 73,73,73,54,48,73,73,74,60,0,54,54,0,0,0,0
    .byte 0,0,0,20,20,20,20,20,0,0,0,0,0,32,64,69
    .byte 72,48,0,0,0,0,0,63,68,68,68,63,127,73,73,73
    .byte 54,62,65,65,65,34,127,65,65,34,28,127,73,73,73
    .byte 65,127,72,72,72,64,62,65,73,73,46,127,8,8,8
    .byte 127,0,65,127,65,0,2,1,65,126,64,127,8,20,34
    .byte 65,127,1,1,1,1,127,32,24,32,127,127,16,8,4
    .byte 127,62,65,65,65,62,127,72,72,72,48,62,65,69,66
    .byte 61,127,72,76,74,49,50,73,73,73,38,64,64,127,64
    .byte 64,126,1,1,1,126,124,2,1,2,124,126,1,6,1,126
    .byte 99,20,8,20,99,112,8,7,8,112,67,69,73,81,97,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0

str_title:  .asciz "NUVI 200W DEBUG HUD"
str_hw:     .asciz "HW737 SW4.00 RAM PAYLOAD"
str_frame:  .asciz "FRAME:"
str_adc0:   .asciz "ADC0:"
str_adc1:   .asciz "ADC1:"
str_state:  .asciz "TCH:"
str_gpio:   .asciz "GPIO DATAIN (READ ONLY CANDIDATES)"
str_g1:     .asciz "FFFBC430:"
str_g2:     .asciz "FFFBCC30:"
str_g3:     .asciz "FFFBDC30:"
str_g4:     .asciz "FFFBEC30:"
str_adcstat:.asciz "ADC REGS"
str_a1:     .asciz "FFFE6014:"
str_a2:     .asciz "FFFE6018:"
str_foot:   .asciz "TAP TO SEE ADC CHANGE. EJECT SD BEFORE RESET."
    .balign 4
