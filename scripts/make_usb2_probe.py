"""Add verified stock OTG session step and live register readouts; local only."""
from pathlib import Path
import struct
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/usb2'
out.mkdir(parents=True,exist_ok=True)
im=Image.open(ROOT/'experiments/usb/preview.png').convert('RGB')
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Menlo.ttc'
d.rectangle((18,12,250,56),fill='#101b2b')
d.text((18,12),'NUVI / USB2',font=ImageFont.truetype(font,20),fill='#13d9b0')
d.text((18,43),'USB SESSION / LIVE REGISTERS',font=ImageFont.truetype(font,10),fill='#b9cadb')
d.rectangle((18,60,124,141),fill='#101b2b')
for y,label in zip((62,78,94,110,126),('CFG','DEV','IRQ','REQ','OTG')):
    d.text((18,y),label,font=ImageFont.truetype(font,10),fill='#b9cadb')
im.save(out/'preview.png')
(out/'screen.rgb565').write_bytes(b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.getdata()))
s=(ROOT/'experiments/usb/probe.S').read_text()
s=s.replace('experiments/usb/screen.rgb565','experiments/usb2/screen.rgb565')
needle='    mov r0, #0\n    strh r0, [r6, #0x28]'
assert s.count(needle)==1
s=s.replace(needle,'''    /* Stock 0x100ec658 configures USB0 transceiver mode3 and OTG_EN.
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
'''+needle)
needle='    ldrh r5, [r6, #0x30]\n    tst r5, #8'
assert s.count(needle)==1
s=s.replace(needle,'''    ldrh r5, [r6, #0x30]
    ldrh r0, [r8, #66]
    orr r0, r0, r5
    strh r0, [r8, #66]
    tst r5, #8''')
s=s.replace('    strh r3, [r8, #40]\n','''    strh r3, [r8, #40]
    ldrh r4, [r8, #64]
    add r4, r4, #1
    strh r4, [r8, #64]
''')
render=[]
for y,(base,offset,word) in zip((62,78,94,110,126),
    ((0xfffb4000,0x18,False),(0xfffb4000,0x20,False),
     ('STAGE + (scratch - probe_start)',66,False),
     ('STAGE + (scratch - probe_start)',64,False),(0xfffb0400,12,True))):
    address=hex(base) if isinstance(base,int) else base
    render += [f'    ldr r0, ={address}',
               f'    {"ldr" if word else "ldrh"} r11, [r0, #{offset}]']
    if not word:render += ['    mov r11, r11, lsl #16']
    render += [f'    ldr r0, ={y*640+60*2}','    add r4, r9, r0',
               '    mov lr, pc','    b draw_register']
s=s.replace('    b draw_usb_status\n','    b draw_usb_status\n'+'\n'.join(render)+'\n')
draw='''draw_register:
    mov r8, #4
register_digit:
    mov r3, r11, lsr #28
    ldr r0, =STAGE + (register_glyphs - probe_start)
    add r0, r0, r3, lsl #8
    mov r6, #16
register_row:
    mov r5, #8
register_pixel:
    ldrh r1, [r0], #2
    strh r1, [r4], #2
    subs r5, r5, #1
    bne register_pixel
    add r4, r4, #624
    subs r6, r6, #1
    bne register_row
    ldr r3, =10224
    sub r4, r4, r3
    mov r11, r11, lsl #4
    subs r8, r8, #1
    bne register_digit
    bx lr
'''
s=s.replace('\npark:\n','\n'+draw+'\npark:\n')
s=s.replace('\ndecimal_glyphs:\n','\nregister_glyphs:\n    .incbin "experiments/calibration/hex.rgb565"\ndecimal_glyphs:\n')
(out/'probe.S').write_text(s)
print('Prepared USB2 session-valid and live readout candidate locally.')
