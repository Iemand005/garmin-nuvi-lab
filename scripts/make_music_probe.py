"""Generate temporary Spotify demo with bounded text RAM and queued button events."""
from pathlib import Path
import struct
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/music'
out.mkdir(parents=True,exist_ok=True)
font='/System/Library/Fonts/Menlo.ttc'
small=ImageFont.truetype(font,10)
body=ImageFont.truetype(font,12)
im=Image.new('RGB',(320,240),'#101b2b')
d=ImageDraw.Draw(im)
d.text((18,12),'SPOTIFY / LAB',font=ImageFont.truetype(font,20),fill='#13d9b0')
d.text((18,43),'TEMPORARY USB EXPERIMENT',font=small,fill='#b9cadb')
d.text((236,34),'USB',font=small,fill='#b9cadb')
for x,label in ((18,'PREV'),(116,'PLAY/PAUSE'),(214,'NEXT')):
    d.rounded_rectangle((x,144,x+87,192),radius=6,fill='#1d3045',outline='#13d9b0')
    chosen=small if len(label)>8 else body
    box=d.textbbox((0,0),label,font=chosen)
    d.text((x+(88-box[2])/2,160),label,font=chosen,fill='white')
d.text((18,207),'SLIDE OUT TO CANCEL',font=small,fill='white')
d.text((18,223),'REMOVE CARD BEFORE RESET',font=small,fill='#b9cadb')
im.save(out/'preview.png')
def pixels(image):
    return b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in image.getdata())
(out/'screen.rgb565').write_bytes(pixels(im))
glyphs=bytearray()
for ch in map(chr,range(32,127)):
    tile=Image.new('RGB',(8,16),'#101b2b')
    ImageDraw.Draw(tile).text((0,0),ch,font=body,fill='#13d9b0')
    glyphs.extend(pixels(tile))
(out/'font.rgb565').write_bytes(glyphs)
s=(ROOT/'experiments/usb3/probe.S').read_text().replace('experiments/usb3/screen.rgb565','experiments/music/screen.rgb565')
s=s.replace('    ldr r1, =72200','    ldr r1, =22280')
start=s.index('cursor_draw:\n')+len('cursor_draw:\n')
end=s.index('    ldr r8, =STAGE + (scratch - probe_start)\n',start)
s=s[:start]+'''    mov lr, pc
    b draw_music
    mov lr, pc
    b draw_usb_status
'''+s[end:]
start=s.index('    cmp r0, #1\n',s.index('button_release:\n'))
end=s.index('button_idle:\n',start)
s=s[:start]+'''    cmp r0, #1
    blo button_idle
    cmp r0, #3
    bhi button_idle
    /* Eight release events; never overwrite an unacknowledged event. */
    ldrh r1, [r8, #80]
    ldrh r2, [r8, #82]
    sub r2, r1, r2
    mov r2, r2, lsl #16
    mov r2, r2, lsr #16
    cmp r2, #8
    bhs music_queue_full
    add r1, r1, #1
    strh r1, [r8, #80]
    and r2, r1, #7
    add r3, r8, #256
    add r3, r3, r2, lsl #2
    strh r1, [r3]
    strh r0, [r3, #2]
    b button_idle
music_queue_full:
    ldrh r0, [r8, #88]
    add r0, r0, #1
    strh r0, [r8, #88]
    b button_idle
'''+s[end:]
needle='    b usb_stall\n\nusb_descriptor:'
assert s.count(needle)==1
s=s.replace(needle,'''    ldr r4, =0x5340
    cmp r0, r4
    beq music_text
    ldr r4, =0x54c0
    cmp r0, r4
    beq music_event
    ldr r4, =0x5540
    cmp r0, r4
    beq music_ack
    ldr r4, =0x56c0
    cmp r0, r4
    beq music_info
    b usb_stall

usb_descriptor:''')
s=s.replace('\npark:\n','\n'+(out/'extensions.S').read_text()+'\npark:\n')
# Seed the bounded96byte text area while preserving zeroed contact/event state.
initial='Waiting for Mac bridge'.ljust(32)+'Spotify experiment'.ljust(32)+'OFFLINE'.ljust(32)
s=s.replace('scratch:\n    .space 2048','scratch:\n    .space 128\n    .byte '+','.join(str(ord(c)) for c in initial)+'\n    .space 1824')
start=s.index('register_glyphs:\n')
end=s.index('screen:\n',start)
s=s[:start]+'music_glyphs:\n    .incbin "experiments/music/font.rgb565"\n'+s[end:]
# Unused legacy counter/readout routines would refer to removed glyph tables.
start=s.index('draw_counter:\n')
end=s.index('usb_init:\n',start)
s=s[:start]+s[end:]
start=s.index('draw_register:\n')
end=s.index('music_text:\n',start)
s=s[:start]+s[end:]
(out/'probe.S').write_text(s)
print('Prepared temporary Spotify demo locally; no device writes.')
