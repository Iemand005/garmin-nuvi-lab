"""Prepare a local EP0-only USB experiment. Does not install it."""
from pathlib import Path
import struct
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/usb'
out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'experiments/buttons/probe.S').read_text()
im=Image.open(ROOT/'experiments/buttons/preview.png').convert('RGB')
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Menlo.ttc'
d.rectangle((18,12,250,56),fill='#101b2b')
d.text((18,12),'NUVI / USB',font=ImageFont.truetype(font,20),fill='#13d9b0')
d.text((18,43),'USB VALUE / TOUCH RETURN',font=ImageFont.truetype(font,10),fill='#b9cadb')
d.text((236,112),'USB',font=ImageFont.truetype(font,10),fill='#b9cadb')
im.save(out/'preview.png')
(out/'screen.rgb565').write_bytes(b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.getdata()))
s=s.replace('experiments/buttons/screen.rgb565','experiments/usb/screen.rgb565')
s=s.replace('input_loop:\n','    mov lr, pc\n    b usb_init\ninput_loop:\n',1)
s=s.replace('    b draw_swatch\n','    b draw_swatch\n    mov lr, pc\n    b draw_usb_status\n')
# Preserve finite delay with periodic polling; no interrupt or DMA enable.
s=s.replace('input_delay:\n    subs r12, r12, #1', '''input_delay:
    mov lr, pc
    b usb_poll
    subs r12, r12, #1''')
# Poll once per input frame, not each delay iteration (separate loop label).
s=s.replace('    subs r12, r12, #1\n    bne input_delay', 'delay_ticks:\n    subs r12, r12, #1\n    bne delay_ticks')
s=s.replace('\npark:\n','\n'+(out/'control.S').read_text()+'\npark:\n')
s=s.replace('\ndecimal_glyphs:\n','''
usb_device:
    /* Private lab identity, not a mass-storage or firmware-update interface. */
    .byte 18,1,0x10,1,0,0,0,64,0x1e,9,0xfe,0xff,1,0,0,0,0,1
usb_configuration:
    .byte 9,2,18,0,1,1,0,0x80,250
    .byte 9,4,0,0,0,0xff,0,0,0
    .balign 4
decimal_glyphs:
''')
(out/'probe.S').write_text(s)
print('Prepared local EP0 value/touch candidate; no device writes.')
