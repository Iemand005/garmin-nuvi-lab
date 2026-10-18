"""Build local target/readout assets; retain the physically proven ADC sequence."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
out = ROOT/'experiments/calibration'
out.mkdir(parents=True, exist_ok=True)
font = '/System/Library/Fonts/Menlo.ttc'
small = ImageFont.truetype(font, 10)
body = ImageFont.truetype(font, 12)
im = Image.new('RGB', (320,240), '#101b2b')
d = ImageDraw.Draw(im)
d.text((48,12), 'TOUCH / CALIBRATION', font=body, fill='white')
d.text((48,35), 'HOLD 1, 2, 3, 4 THEN LIFT', font=small, fill='#b9cadb')
d.text((32,70), 'RAW HEX / 000..3FF', font=small, fill='#b9cadb')
for label,y in [('ADC 0',88),('ADC 1',136)]:
    d.text((32,y), label, font=body, fill='white')
for y in (112,160):
    d.rectangle((31,y-1,288,y+12), outline='#b9cadb')
d.text((47,190), 'FILM READOUTS WHILE HOLDING', font=small, fill='white')
d.text((47,208), 'REMOVE CARD BEFORE RESET', font=small, fill='#b9cadb')
for n,(x,y) in enumerate(((18,18),(300,18),(18,220),(300,220)),1):
    d.ellipse((x-10,y-10,x+10,y+10), outline='#13d9b0')
    d.line((x-13,y,x+13,y), fill='#13d9b0')
    d.line((x,y-13,x,y+13), fill='#13d9b0')
    d.text((x+13 if x<160 else x-20,y-9), str(n), font=small, fill='white')
im.save(out/'preview.png')
def rgb565(image):
    return b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in image.getdata())
(out/'screen.rgb565').write_bytes(rgb565(im))
glyphs = bytearray()
for ch in '0123456789ABCDEF':
    tile=Image.new('RGB',(8,16),'#101b2b')
    ImageDraw.Draw(tile).text((0,0),ch,font=body,fill='#13d9b0')
    glyphs.extend(rgb565(tile))
(out/'hex.rgb565').write_bytes(glyphs)
s=(ROOT/'experiments/touch/probe.S').read_text()
s=s.replace('experiments/touch/screen.rgb565','experiments/calibration/screen.rgb565')
s=s.replace('    bne heartbeat\n','    bne numeric_values\n')
numeric='''numeric_values:
    /* Fixed-width raw hexadecimal values; no calibration or touch filtering yet. */
    ldr r0, =56740
    add r4, r9, r0
    mov r2, r10
    mov lr, pc
    b draw_hex
    ldr r0, =87460
    add r4, r9, r0
    mov r2, r11
    mov lr, pc
    b draw_hex
    b heartbeat
draw_hex:
    mov r8, #3
hex_digit:
    mov r3, r2, lsr #8
    and r3, r3, #15
    ldr r0, =STAGE + (hex_glyphs - probe_start)
    add r0, r0, r3, lsl #8
    mov r6, #16
hex_row:
    mov r5, #8
hex_pixel:
    ldrh r1, [r0], #2
    strh r1, [r4], #2
    subs r5, r5, #1
    bne hex_pixel
    add r4, r4, #624
    subs r6, r6, #1
    bne hex_row
    /* End at the next character on the original row. */
    ldr r3, =10224
    sub r4, r4, r3
    mov r2, r2, lsl #4
    subs r8, r8, #1
    bne hex_digit
    bx lr
'''
s=s.replace('heartbeat:\n', numeric+'heartbeat:\n')
s=s.replace('\nscreen:\n','\nhex_glyphs:\n    .incbin "experiments/calibration/hex.rgb565"\nscreen:\n')
(out/'probe.S').write_text(s)
print('Prepared local calibration target and exact raw-value readouts.')
