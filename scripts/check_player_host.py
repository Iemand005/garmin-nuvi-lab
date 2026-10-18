"""Offline renderer, active-state and RPC checks; no real Spotify/device actions."""
import tempfile,json,time
from pathlib import Path
import spotify_player as p
from PIL import Image
track=dict(title='Long title with Beyoncé and symbols — ♫',artist='KAYTRANADA',album='BUBBA',duration=186.68,position=24,state='playing',artwork='')
art=Image.new('RGB',(96,96),'#bd3e22')
pressed_frame=p.rgb565(p.render(track,art,active=2));pressed_probe=(155*320+145)*2
im=p.render(track,art);frame=p.rgb565(im)
assert im.size==(320,240) and len(frame)==153600
assert len(p.changed_chunks(frame,None))==2400 and p.changed_chunks(frame,frame)==[]
changed=bytearray(frame);changed[-2:]=b'\x34\x12'
assert p.changed_chunks(bytes(changed),frame)==[(2399,bytes(changed[-64:]))]
for button,(left,top,right,bottom) in enumerate(p.BUTTON_REGIONS,1):
    pressed=p.render(track,art,active=button)
    changed_pixels=[(i%320,i//320) for i,(a,b) in enumerate(zip(im.getdata(),pressed.getdata())) if a!=b]
    assert changed_pixels and all(left-3<=x<=right+3 and top-3<=y<=bottom+3 for x,y in changed_pixels)
for url in ('http://i.scdn.co/image/x','https://example.com/x','https://user@i.scdn.co/image/x'):
    try:p.artwork(url)
    except ValueError:pass
    else:raise AssertionError('Invalid artwork URL accepted')
# Native release events own actions; status is visual feedback only.
t=p.PressState()
def sample(x,y,contact):return t.update(dict(x=x,y=y,contact=contact))
sample(62,168,1);assert t.active(0)==1
for _ in range(10):sample(62,168,1);assert t.active(0)==1
sample(160,168,1);assert t.active(0)==0
sample(62,168,1);assert t.active(0)==1
sample(62,168,0);assert t.active(0)==0
sample(80,100,1);sample(160,168,1);assert t.active(0)==0
sample(160,168,0);t.pulse(2,1);assert t.active(1.1)==2 and t.active(1.2)==0
assert p.button_at(18,144)==1 and p.button_at(105,192)==1
assert p.button_at(106,168)==0 and p.button_at(80,100)==0
class Fake:
    def __init__(self,*args):self.queue=[(1,3)];self.mem=bytearray(153600);self.chunks=0;self.closed=False;self.pressed_seen=False;self.stage=0;self.release_at=0;globals()['channel']=self
    def rpc(self,line):
        parts=line.split()
        if parts[0]=='status':
            if self.chunks>=10 and self.stage==0:self.stage=1;self.release_at=time.monotonic()+.15
            if self.stage==1 and time.monotonic()>=self.release_at:
                self.stage=2;self.queue.append((2,2))
            return dict(value=0,x=160,y=168,contact=int(self.stage==1),color=0,configured=1)
        if parts[0]=='event':
            seq,button=self.queue[0] if self.queue else (0,0)
            return dict(seq=seq,button=button,dropped=0)
        if parts[0]=='ack':assert int(parts[1])==self.queue[0][0];self.queue.pop(0)
        elif parts[0]=='chunk':
            index=int(parts[1]);data=bytes.fromhex(parts[2]);assert 0<=index<2400 and len(data)==64
            self.mem[index*64:index*64+64]=data;self.chunks+=1
            if self.mem[pressed_probe:pressed_probe+2]==pressed_frame[pressed_probe:pressed_probe+2]:self.pressed_seen=True
        return dict(ok=True)
    def close(self):self.closed=True
# Interrupted/failed transfers must not mark unsent blocks as delivered.
f=Fake();transport=p.FrameTransport(f);transport.send(0,frame[:64])
assert len(transport.pending(frame))==2399
saved=f.rpc
f.rpc=lambda _:(_ for _ in ()).throw(RuntimeError('synthetic failure'))
try:transport.send(1,frame[64:128])
except RuntimeError:pass
else:raise AssertionError('Failure not propagated')
assert transport.blocks[1] is None
f.rpc=saved
p.Channel=Fake;p.metadata=lambda:track;p.artwork=lambda _:art
actions=[];p.action=actions.append
with tempfile.TemporaryDirectory() as tmp:
    p.ROOT=Path(tmp);(p.ROOT/'evidence').mkdir();p.run(.8)
    records=[json.loads(x) for x in (p.ROOT/'evidence/spotify-player.jsonl').read_text().splitlines()]
assert actions==[2] and channel.closed and channel.pressed_seen
assert channel.mem==frame
assert any(r['kind']=='interaction' and r['active']==2 for r in records)
assert any(r['kind']=='interaction' and r['active']==0 for r in records)
report=dict(framebuffer_roundtrip=True,full_frame_chunks=2400,unchanged_frame_chunks=0,last_block_diff=True,startup_discard=True,live_event_once=True,native_queue_actions_restored=True,artwork_url_validation=True,pressed_regions_isolated=True,capture_drag_cancel=True,release_feedback=True,partial_frame_tracking=True,failed_transfer_not_committed=True,actual_device_io=False,actual_spotify_actions=0)
Path('evidence/player-host-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
