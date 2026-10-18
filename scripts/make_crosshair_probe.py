"""Prepare local crosshair diagnostic with unchanged stock ADC protocol."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/crosshair'
out.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(320,240),'#101b2b')
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Menlo.ttc'
small=ImageFont.truetype(font,10)
body=ImageFont.truetype(font,12)
d.text((18,12),'TOUCH / CROSSHAIR',font=body,fill='white')
d.text((18,34),'DRAG SLOWLY, THEN LIFT',font=small,fill='#b9cadb')
d.text((18,49),'CONTACT: GRAY / AMBER / GREEN',font=small,fill='white')
d.text((32,70),'RAW HEX / PROVISIONAL XY',font=small,fill='#b9cadb')
for label,y in [('ADC 0',88),('ADC 1',136)]:d.text((32,y),label,font=body,fill='white')
for y in (112,160):d.rectangle((31,y-1,288,y+12),outline='#b9cadb')
d.text((18,190),'WHITE CROSS = ESTIMATED TOUCH',font=small,fill='white')
d.text((18,208),'REMOVE CARD BEFORE RESET',font=small,fill='#b9cadb')
im.save(out/'preview.png')
(out/'screen.rgb565').write_bytes(b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.getdata()))
s=(ROOT/'experiments/calibration/probe.S').read_text()
s=s.replace('experiments/calibration/screen.rgb565','experiments/crosshair/screen.rgb565')
s=s.replace('render_input:\n','render_input:\n    mov lr, pc\n    b restore_cursor\n')
s=s.replace('    b heartbeat\ndraw_hex:', '    b cursor_update\ndraw_hex:')
s=s.replace('\npark:\n','\n'+(out/'cursor.S').read_text()+'\npark:\n')
(out/'probe.S').write_text(s)
print('Prepared local crosshair candidate assets.')
