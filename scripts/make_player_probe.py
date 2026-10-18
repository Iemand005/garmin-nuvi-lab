"""Build clean now-playing native bridge from preserved, proven music code."""
from pathlib import Path
from player_ui import render,rgb565
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'experiments/player';out.mkdir(exist_ok=True)
im=render({'title':'Open Spotify','artist':'Connect your Mac','album':'','state':'paused'})
im.save(out/'preview.png');(out/'screen.rgb565').write_bytes(rgb565(im))
s=(ROOT/'experiments/music/probe.S').read_text().replace('experiments/music/screen.rgb565','experiments/player/screen.rgb565')
# Keep touch acquisition and capture/release logic; remove all debug painting.
s=s.replace('    mov lr, pc\n    b restore_cursor\n    b cursor_update','    b cursor_update')
start=s.index('heartbeat:\n');end=s.index('input_delay:\n',start)
s=s[:start]+'''heartbeat:
    mov r12, #0x100000
    b input_delay
failed:
    b park
'''+s[end:]
s=s.replace('delay_ticks:\n    subs r12, r12, #1\n    bne delay_ticks\n    b input_loop','''delay_ticks:
    subs r12, r12, #1
    beq input_loop
    tst r12, #255
    bne delay_ticks
    b input_delay''')
start=s.index('restore_cursor:\n');end=s.index('cursor_update:\n',start)
s=s[:start]+'restore_cursor:\n    bx lr\n\n'+s[end:]
start=s.index('cursor_draw:\n');end=s.index('button_track:\n',start)
s=s[:start]+'cursor_draw:\n    b heartbeat\n\n'+s[end:]
start=s.index('draw_usb_status:\n');end=s.index('music_text:\n',start)
s=s[:start]+s[end:]
start=s.index('draw_music:\n');end=s.index('park:\n',start)
s=s[:start]+(out/'image.S').read_text()+'\n'+s[end:]
start=s.index('music_glyphs:\n');end=s.index('screen:\n',start)
s=s[:start]+s[end:]
# Distinct capability v2 prevents an image host writing into the legacy demo.
s=s.replace('    mov r0, #1\n    strh r0, [r8, #44]\n    mov r0, #48','    mov r0, #2\n    strh r0, [r8, #44]\n    mov r0, #48')
s=s.replace('    b usb_stall\n\nusb_descriptor:', '''    ldr r4, =0x5740
    cmp r0, r4
    beq player_chunk
    b usb_stall

usb_descriptor:''')
# New SETUP and bus reset cancel any pending OUT data stage.
s=s.replace('    strhne r0, [r8, #32]','    strhne r0, [r8, #32]\n    strhne r0, [r8, #90]')
s=s.replace('    mov r0, #0x40\n    strh r0, [r6, #4]\n    /* Reading', '    mov r0, #0\n    strh r0, [r8, #90]\n    mov r0, #0x40\n    strh r0, [r6, #4]\n    /* Reading')
s=s.replace('    /* All supported OUT requests have zero data bytes.', '    ldrh r0, [r8, #90]\n    cmp r0, #1\n    beq player_receive\n    /* Legacy OUT requests have zero data bytes.')
(out/'probe.S').write_text(s)
print('Prepared clean player UI locally; no device writes.')
