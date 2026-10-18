"""Live350 Spotify display-only bridge. No playback commands or touch/GPIO writes."""
import argparse,concurrent.futures,json,time
from player_ui import render
from spotify_player import metadata,artwork,FrameTransport
from spotify_bridge import Channel,ROOT
from nuvi350_display import encode

def run(seconds):
    channel=Channel(ROOT/'analysis/nuvi350/usb/nuvi350-usb-host');pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        info=channel.rpc('info');transport=FrameTransport(channel)
        started=time.monotonic();next_meta=0;meta_job=None;art_job=None;art_url=None;art=None;revision=0;sent_revision=-1;encoded_revision=-1;desired=None
        track=dict(title='Open Spotify',artist='On your Mac',state='paused')
        with (ROOT/'evidence/nuvi350/spotify-display.jsonl').open('a') as log:
            def record(kind,**fields):
                row=dict(time=time.time(),kind=kind,**fields);log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
            record('started',profile=info,scope='Display only; controls not enabled',seconds=seconds)
            try:
                while time.monotonic()-started<seconds:
                    now=time.monotonic()
                    if meta_job is None and now>=next_meta:meta_job=pool.submit(metadata)
                    if meta_job is not None and meta_job.done():
                        track=meta_job.result();meta_job=None;next_meta=now+1;revision+=1
                        url=track.get('artwork','')
                        if url!=art_url:
                            art_url=url;art=None
                            if art_job is not None:art_job.cancel()
                            art_job=pool.submit(artwork,url)
                    if art_job is not None and art_job.done():
                        try:art=art_job.result();revision+=1
                        except Exception as error:record('artwork_unavailable',reason=str(error))
                        art_job=None
                    if revision!=encoded_revision:
                        desired=encode(render(track,art),info['width'],info['height'],'ccw');encoded_revision=revision
                    pending=transport.pending(desired)
                    for index,block in pending[:256]:transport.send(index,block)
                    if len(pending)<=256 and sent_revision!=revision:
                        record('frame',title=track.get('title'),artist=track.get('artist'),state=track.get('state'),artwork=art is not None,touch_enabled=False)
                        sent_revision=revision
                    time.sleep(.005 if pending else .025)
                record('stopped',reason='duration reached')
            except KeyboardInterrupt:record('stopped',reason='interrupted')
    finally:channel.close();pool.shutdown(wait=False,cancel_futures=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=1800);a=p.parse_args()
    if not 1<=a.seconds<=3600:p.error('seconds must be1..3600')
    run(a.seconds)
if __name__=='__main__':main()
