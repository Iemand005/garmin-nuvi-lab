"""Spotify now-playing UI on the original Garmin LCD over bounded USB pixels."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,io,json,time,urllib.request,urllib.parse
from PIL import Image
from player_ui import render,rgb565,BUTTON_REGIONS
from spotify_bridge import Channel,action,ROOT
import subprocess
META='''const s=Application("Spotify");
if (!s.running()) JSON.stringify({state:"closed",title:"Open Spotify",artist:"On your Mac",album:"",duration:0,position:0,artwork:""});
else {let r={state:s.playerState(),position:s.playerPosition(),title:"No track selected",artist:"",album:"",duration:0,artwork:""};
try {const t=s.currentTrack();r.title=t.name();r.artist=t.artist();r.album=t.album();r.duration=t.duration()/1000;r.artwork=t.artworkUrl();}catch(e){} JSON.stringify(r);}'''
def metadata():
    r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',META],capture_output=True,text=True,timeout=5)
    if r.returncode:raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)
def artwork(url):
    if not url:return None
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname!='i.scdn.co' or u.username or u.password:raise ValueError('Unexpected Spotify artwork URL')
    cache=ROOT/'analysis/player/artwork';cache.mkdir(parents=True,exist_ok=True)
    path=cache/(hashlib.sha256(url.encode()).hexdigest()+'.jpg')
    if path.exists():data=path.read_bytes()
    else:
        # Restrict redirect destinations as well as the URL returned by Spotify.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=urllib.request.build_opener(NoRedirect)
        with opener.open(url,timeout=6) as r:data=r.read(6*1024*1024+1)
        if len(data)>6*1024*1024:raise ValueError('Artwork too large')
    with Image.open(io.BytesIO(data)) as im:
        if im.width*im.height>16000000:raise ValueError('Artwork dimensions too large')
        im.load();result=im.convert('RGB')
    if not path.exists():path.write_bytes(data)
    return result

def changed_chunks(frame,old):
    if len(frame)!=153600 or (old is not None and len(old)!=153600):raise ValueError('Wrong frame size')
    return [(i//64,frame[i:i+64]) for i in range(0,len(frame),64) if old is None or frame[i:i+64]!=old[i:i+64]]

def button_at(x,y):
    for button,(left,top,right,bottom) in enumerate(BUTTON_REGIONS,1):
        if left<=x<=right and top<=y<=bottom:return button
    return 0

class PressState:
    """Visual capture follows the native button targets; actions use native events."""
    def __init__(self):
        self.held=False;self.capture=0;self.hit=0;self.pulse_button=0;self.pulse_until=0
    def update(self,status):
        held=bool(status['contact']);hit=button_at(status['x'],status['y']) if held else 0
        if held and not self.held:self.capture=hit
        self.held=held;self.hit=hit
        if not held:self.capture=0
    def pulse(self,button,now):
        self.pulse_button=button;self.pulse_until=now+.14
    def active(self,now):
        if self.held:return self.capture if self.capture==self.hit else 0
        return self.pulse_button if now<self.pulse_until else 0

class FrameTransport:
    """Track each acknowledged block, including interrupted frame updates."""
    def __init__(self,channel):self.channel=channel;self.blocks=[None]*2400
    def pending(self,frame):
        if len(frame)!=153600:raise ValueError('Wrong frame size')
        return [(i,frame[i*64:i*64+64]) for i in range(2400) if self.blocks[i]!=frame[i*64:i*64+64]]
    def send(self,index,data):
        if not 0<=index<2400 or len(data)!=64:raise ValueError('Wrong block')
        self.channel.rpc(f'chunk {index} {data.hex()}')
        self.blocks[index]=data

def run(seconds):
    channel=Channel(ROOT/'analysis/player/player-usb-host')
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
    started=time.monotonic();art=None;art_url=None;future=None;future_url=None
    meta_future=None;next_metadata=0;track_revision=0;art_revision=0
    track=dict(title='Open Spotify',artist='On your Mac',state='paused')
    touch=PressState();transport=FrameTransport(channel);actions=[]
    next_input=0;last_active=0;cached_key=None;desired=None;last_complete=None
    with (ROOT/'evidence/spotify-player.jsonl').open('a') as log:
        def record(kind,**fields):
            item=dict(time=time.time(),kind=kind,**fields);log.write(json.dumps(item)+'\n');log.flush();print(json.dumps(item),flush=True)
        def pump(armed,force=False):
            nonlocal next_input,last_active
            now=time.monotonic()
            if not force and now<next_input:return
            if armed:touch.update(channel.rpc('status'))
            for _ in range(8):
                e=channel.rpc('event')
                if e['dropped']:raise RuntimeError('Button queue overflow; stopping')
                if not e['button']:break
                channel.rpc('ack '+str(e['seq']))
                record('button' if armed else 'discard_before_start',**e)
                if armed:
                    touch.pulse(e['button'],time.monotonic());actions.append(e['button'])
            active=touch.active(time.monotonic())
            if active!=last_active:record('interaction',active=active,held=touch.held);last_active=active
            next_input=time.monotonic()+.03
        try:
            pump(False,True);record('started',seconds=seconds,ui='artwork ambient glass with live pressed states')
            while time.monotonic()-started<seconds:
                pump(True)
                now=time.monotonic()
                if meta_future is None and now>=next_metadata:meta_future=pool.submit(metadata)
                if meta_future is not None and meta_future.done():
                    track=meta_future.result();meta_future=None;next_metadata=now+1;track_revision+=1
                    url=track.get('artwork','')
                    if url!=art_url:
                        art_url=url;art=None;art_revision+=1
                        if future is not None:future.cancel()
                        future=pool.submit(artwork,url);future_url=url
                if future is not None and future.done():
                    try:
                        image=future.result()
                        if future_url==art_url:art=image;art_revision+=1
                    except Exception as e:record('artwork_unavailable',reason=str(e))
                    future=None
                active=touch.active(now);key=(track_revision,art_revision,active)
                if key!=cached_key:
                    desired=rgb565(render(track,art,active=active));cached_key=key
                pending=transport.pending(desired)
                # Button feedback takes priority over cover/progress pixels.
                pending.sort(key=lambda item: 0 if 1400<=item[0]<2000 else 1)
                # Small batches give new touches priority during larger cover updates.
                for n,(index,block) in enumerate(pending[:128]):
                    transport.send(index,block)
                    if n%8==7:
                        pump(True)
                        if touch.active(time.monotonic())!=active:break
                if len(pending)<=128 and not transport.pending(desired) and last_complete!=key:
                    record('frame',title=track.get('title'),state=track.get('state'),artwork=art is not None,active=active,chunks=len(pending))
                    last_complete=key
                # Render the release feedback before issuing a Spotify command.
                while actions:
                    button=actions.pop(0);action(button);next_metadata=0
                time.sleep(.005 if pending else .015)
            record('stopped',reason='duration reached')
        except KeyboardInterrupt:
            record('stopped',reason='bridge replaced or interrupted')
        finally:
            channel.close();pool.shutdown(wait=False,cancel_futures=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',action='store_true');p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--preview',action='store_true')
    a=p.parse_args()
    if a.preview:
        track=metadata();im=render(track,artwork(track.get('artwork','')))
        target=ROOT/'analysis/player/now-playing-preview.png';im.save(target)
        (ROOT/'analysis/player/preview-metadata.json').write_text(json.dumps(track,indent=2)+'\n');print(target)
    elif a.run:
        if not 1<=a.seconds<=3600:p.error('--seconds must be1..3600')
        run(a.seconds)
    else:p.error('Choose --preview or --run')
if __name__=='__main__':main()
