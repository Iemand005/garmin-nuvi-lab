"""Correct EP0 completion order; preserve old payloads and add request tracing."""
from pathlib import Path
import struct
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/usb3'
out.mkdir(parents=True,exist_ok=True)
im=Image.open(ROOT/'experiments/usb2/preview.png').convert('RGB')
d=ImageDraw.Draw(im)
font='/System/Library/Fonts/Menlo.ttc'
d.rectangle((18,12,250,56),fill='#101b2b')
d.text((18,12),'NUVI / USB3',font=ImageFont.truetype(font,20),fill='#13d9b0')
d.text((18,43),'CONTROL TRANSFER / LAST REQUEST',font=ImageFont.truetype(font,10),fill='#b9cadb')
d.rectangle((18,60,124,141),fill='#101b2b')
for y,label in zip((62,78,94,110,126),('DEV','CMD','VAL','IDX','LEN')):
    d.text((18,y),label,font=ImageFont.truetype(font,10),fill='#b9cadb')
d.text((136,62),'TX',font=ImageFont.truetype(font,10),fill='#b9cadb')
d.text((136,120),'REQ',font=ImageFont.truetype(font,10),fill='#b9cadb')
im.save(out/'preview.png')
(out/'screen.rgb565').write_bytes(b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.getdata()))
s=(ROOT/'experiments/usb2/probe.S').read_text().replace('experiments/usb2/screen.rgb565','experiments/usb3/screen.rgb565')
start=s.index('usb_no_ds:\n')
end=s.index('usb_no_rx:\n',start)
s=s[:start]+'''usb_no_ds:
    /* TI SPRU761A Table35: clear completion flags BEFORE FIFO enable.
     * Snapshot both flags, clear them once; never clear a newly arriving event.
     */
    and r0, r5, #3
    strh r0, [r6, #0x30]
    /* A fresh SETUP supersedes old TX/RX stages (Linux ep0_irq). */
    tst r5, #4
    bne usb_no_rx
    tst r5, #1
    beq usb_no_tx
    mov r0, #0x30
    strh r0, [r6, #4]
    ldrh r4, [r6, #0x10]
    tst r4, #0x20
    movne r0, #0x80
    strhne r0, [r6, #12]
    mov r0, #0x10
    strh r0, [r6, #4]
    tst r4, #8
    beq usb_no_tx
    /* IN data completion arms OUT status; OUT-request IN status is finished. */
    ldrh r0, [r8, #34]
    tst r0, #0x80
    beq usb_no_tx
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #4
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
usb_no_tx:
    tst r5, #2
    beq usb_no_rx
    /* All supported OUT requests have zero data bytes. RX is IN status:
     * consume/clear it without rearming EP0 outside a control transfer.
     */
    mov r0, #0x20
    strh r0, [r6, #4]
    mov r0, #2
    strh r0, [r6, #12]
    mov r0, #0
    strh r0, [r6, #4]
'''+s[end:]
# Do not answer a stale packet if another SETUP arrived while it was read.
s=s.replace('    /* Exact bmRequestType/request pairs;', '''    ldrh r4, [r6, #0x30]
    tst r4, #4
    bne usb_return
    /* Exact bmRequestType/request pairs;''')
s=s.replace('    movhi r1, r3\n    mov r2, #0x30','    movhi r1, r3\n    strh r1, [r8, #68]\n    mov r2, #0x30')
start=s.index('    b draw_usb_status\n')+len('    b draw_usb_status\n')
end=s.index('    ldr r8, =STAGE + (scratch - probe_start)\n',start)
render=[]
fields=[(60,62,0xfffb4000,0x20),(60,78,None,34),(60,94,None,36),
        (60,110,None,38),(60,126,None,40),(164,62,None,68),(164,120,None,64)]
for x,y,base,offset in fields:
    address=hex(base) if base else 'STAGE + (scratch - probe_start)'
    render += [f'    ldr r0, ={address}',f'    ldrh r11, [r0, #{offset}]',
               '    mov r11, r11, lsl #16',f'    ldr r0, ={y*640+x*2}',
               '    add r4, r9, r0','    mov lr, pc','    b draw_register']
s=s[:start]+'\n'.join(render)+'\n'+s[end:]
(out/'probe.S').write_text(s)
print('Prepared USB3 EP0 completion fix and last-request readouts locally.')
