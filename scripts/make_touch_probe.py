"""Prepare local raw-touch diagnostic, preserving both prior experiments."""
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/touch'
out.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(320,240),'#101b2b')
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Menlo.ttc'
title=ImageFont.truetype(font,22)
body=ImageFont.truetype(font,12)
small=ImageFont.truetype(font,10)
d.rectangle((0,0,319,239),outline='#13d9b0')
d.text((18,16),'TOUCH / LAB',font=title,fill='#13d9b0')
d.text((18,52),'RAW INPUT / FIRST PASS',font=body,fill='white')
d.line((18,78,301,78),fill='#3b5066')
d.text((32,91),'ADC 0 / X CANDIDATE',font=small,fill='#b9cadb')
d.rectangle((31,111,288,124),outline='#b9cadb')
d.text((32,139),'ADC 1 / Y CANDIDATE',font=small,fill='#b9cadb')
d.rectangle((31,159,288,172),outline='#b9cadb')
d.text((18,190),'PRESS, HOLD, THEN DRAG',font=body,fill='white')
d.text((18,216),'RAW AXES / RESET TO EXIT',font=small,fill='#b9cadb')
im.save(out/'preview.png')
(out/'screen.rgb565').write_bytes(b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.getdata()))
s=(ROOT/'experiments/dashboard/probe.S').read_text()
start=s.index('    /* Header=32 bytes, stride=640;')
end=s.index('park:\n',start)
body=(out/'input-body.S').read_text()
s=s[:start]+body+'\n'+s[end:]
s=s.replace('    /* Guarded source frame has', '''    /* Inherited ADC configuration must already be initialized. */
    ldr r0, =0xfffe6000
    ldrh r1, [r0, #0x14]
    tst r1, #1
    beq park
    /* Existing stock touchscreen drive pins must already be outputs. */
    ldr r0, =0xfffbb400
    ldr r1, [r0, #0x34]
    tst r1, #0x0e
    bne park
    ldr r0, =0xfffbe400
    ldr r1, [r0, #0x34]
    ldr r2, =0x8010
    tst r1, r2
    bne park

    /* Guarded source frame has''')
s=s.replace('experiments/dashboard/screen.rgb565','experiments/touch/screen.rgb565')
s=s[s.index('.syntax unified'):]
s='''/* Raw touch candidate: exact stock logical-channel 0/1 drive and ADC sequence.
 * Inherited clocks/directions only, bounded polls. No flash/filesystem access.
 * Added peripheral stores are restricted by the offline audit.
 */
'''+s
(out/'probe.S').write_text(s)
print('Prepared local touch source and RGB565 preview.')
