"""Build local native dashboard. Button actions are RAM-only on qualified release."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/buttons'
out.mkdir(parents=True,exist_ok=True)
font='/System/Library/Fonts/Menlo.ttc'
small=ImageFont.truetype(font,10)
body=ImageFont.truetype(font,12)
title=ImageFont.truetype(font,20)
im=Image.new('RGB',(320,240),'#101b2b')
d=ImageDraw.Draw(im)
d.text((18,12),'NUVI / DESK',font=title,fill='#13d9b0')
d.text((18,43),'TOUCH. HOLD. RELEASE.',font=small,fill='#b9cadb')
d.text((18,70),'TAPS',font=body,fill='white')
d.text((18,92),'ONE PER',font=small,fill='#b9cadb')
d.text((18,106),'RELEASE',font=small,fill='#b9cadb')
d.text((253,91),'COLOR',font=small,fill='#b9cadb')
for x,label in [(18,'TAP +1'),(116,'RESET'),(214,'COLOR')]:
    d.rounded_rectangle((x,144,x+87,192),radius=6,fill='#1d3045',outline='#13d9b0')
    bbox=d.textbbox((0,0),label,font=body)
    d.text((x+(88-bbox[2])/2,160),label,font=body,fill='white')
d.text((18,207),'SLIDE OUT TO CANCEL',font=small,fill='white')
d.text((18,223),'REMOVE CARD BEFORE RESET',font=small,fill='#b9cadb')
im.save(out/'preview.png')
def pixels(image):
    return b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in image.getdata())
(out/'screen.rgb565').write_bytes(pixels(im))
table=bytearray()
for ch in '0123456789':
    tile=Image.new('RGB',(16,32),'#101b2b')
    ImageDraw.Draw(tile).text((0,0),ch,font=ImageFont.truetype(font,24),fill='#13d9b0')
    table.extend(pixels(tile))
(out/'decimal.rgb565').write_bytes(table)
s=(ROOT/'experiments/crosshair/probe.S').read_text()
s=s.replace('experiments/crosshair/screen.rgb565','experiments/buttons/screen.rgb565')
# State starts unpressed and armed; all other scratch bytes are zero in payload.
s=s.replace('input_loop:\n', '    ldr r8, =STAGE + (scratch - probe_start)\n    mov r0, #1\n    strh r0, [r8, #10]\ninput_loop:\n',1)
begin=s.index('render_input:\n')
end=s.index('heartbeat:\n',begin)
s=s[:begin]+'''render_input:
    mov lr, pc
    b restore_cursor
    b cursor_update
'''+s[end:]
s=s.replace('    b cursor_active\ncursor_invalid:', '    b button_track\ncursor_invalid:')
start=s.index('cursor_invalid:')
end=s.index('cursor_pending:',start)
part=s[start:end].replace('cmp r0, #2','cmp r0, #4')
part=part.replace('    ldr r10, =0x2945\n    b cursor_draw','    b button_release')
s=s[:start]+part+s[end:]
s=s.replace('cursor_draw:\n','''cursor_draw:
    mov lr, pc
    b draw_counter
    mov lr, pc
    b draw_swatch
    ldr r8, =STAGE + (scratch - probe_start)
''')
s=s.replace('\npark:\n','\n'+(out/'ui.S').read_text()+'\npark:\n')
s=s.replace('hex_glyphs:\n    .incbin "experiments/calibration/hex.rgb565"','decimal_glyphs:\n    .incbin "experiments/buttons/decimal.rgb565"')
(out/'probe.S').write_text(s)
print('Prepared native buttons dashboard source/assets.')
