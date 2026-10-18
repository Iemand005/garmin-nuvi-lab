"""Generate the local RGB565 screen and derive code from the proven probe.

No mounted volume is accessed. The original rectangle payload is preserved.
"""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/dashboard'
OUT.mkdir(parents=True, exist_ok=True)
image = Image.new('RGB', (320, 240), '#101b2b')
d = ImageDraw.Draw(image)
font_path = '/System/Library/Fonts/Menlo.ttc'
title = ImageFont.truetype(font_path, 23)
body = ImageFont.truetype(font_path, 12)
small = ImageFont.truetype(font_path, 10)
accent = '#13d9b0'
d.rectangle((0, 0, 319, 239), outline=accent)
d.text((18, 16), 'NUVI / LAB', font=title, fill=accent)
d.text((18, 50), 'CUSTOM CODE. ORIGINAL LCD.', font=body, fill='white')
d.line((18, 77, 301, 77), fill='#3b5066')
d.text((18, 88), 'CPU HEARTBEAT', font=small, fill='#b9cadb')
d.rectangle((144, 104, 175, 135), fill=accent)
d.text((18, 153), '320 x 240 / RGB565', font=body, fill='white')
for i, color in enumerate(('#ffffff','#ffff00','#00ffff','#00ff00','#ff00ff','#ff0000','#0000ff')):
    d.rectangle((18 + i*40, 181, 57 + i*40, 197), fill=color)
d.text((18, 216), 'SD PROGRAM / RESET TO EXIT', font=small, fill='#b9cadb')
image.save(OUT / 'preview.png')
pixels = b''.join(struct.pack('<H', ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
                  for r, g, b in image.getdata())
assert len(pixels) == 153600
(OUT / 'screen.rgb565').write_bytes(pixels)

source = (ROOT / 'experiments/rectangle/probe.S').read_text()
source = source.replace('/* Offline candidate', '/* Dashboard candidate derived from physically observed rectangle probe.\n * Full-frame RGB565 copy and repeated central inversion.\n * Offline candidate', 1)
marker = '    /* Header=32 bytes, stride=640; x=144,y=104, width=height=32. */'
assert source.count(marker) == 1
copy = '''    /* Guarded source frame has 32-byte prefix; preserve that prefix. */
    add r4, r4, #32
    ldr r8, =STAGE + (screen - probe_start)
    ldr r6, =76800
copy_screen:
    ldrh r0, [r8], #2
    strh r0, [r4], #2
    subs r6, r6, #1
    bne copy_screen
    /* r4 is end of pixel data; recover the validated prefix base. */
    ldr r0, =153632
    sub r4, r4, r0

'''
source = source.replace(marker, copy + marker)
source = source.replace('    mov r4, r9\n    ldr r8, =STAGE + (scratch - probe_start)\n    mov r6, #32\n    ldr r2, =0xffff',
                        'animate:\n    mov r4, r9\n    ldr r8, =STAGE + (scratch - probe_start)\n    mov r6, #32\n    ldr r2, =0xffff')
source = source.replace('park:\n    b park', '''    mov r12, #0x01000000
delay_off:
    subs r12, r12, #1
    bne delay_off
    b animate

park:
    b park''')
source = source.replace('probe_end:', '''    .balign 4
screen:
    .incbin "experiments/dashboard/screen.rgb565"
probe_end:''')
(OUT / 'probe.S').write_text(source)
print('Generated preview, 153600 RGB565 bytes, and dashboard probe.S locally.')
