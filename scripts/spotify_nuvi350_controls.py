"""Live Spotify remote on350 using physically calibrated raw touch and original LCD."""
import argparse,concurrent.futures,json,time
from player_ui import render
from spotify_player import metadata,artwork,FrameTransport
from spotify_bridge import Channel,ROOT,action
from nuvi350_display import encode
from nuvi350_input import load_calibration,TouchControls

def priority_blocks(width,height):
    if (width,height)==(240,320):return {((x*240+y)//32) for x in range(18,303) for y in range(140,198)}
    return {((y*320+x)//32) for x in range(18,303) for y in range(140,198)}

def run(seconds):
    channel=Channel(ROOT/'analysis/nuvi350/usb/nuvi350-touchxy-host');pool=concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        profile=channel.rpc('info');cal=load_calibration(ROOT/'evidence/nuvi350/touch-calibration.json',profile)
        touch=TouchControls(cal);transport=FrameTransport(channel);priority=priority_blocks(profile['width'],profile['height'])
        started=time.monotonic();next_meta=0;next_input=0;meta_job=None;art_job=None;art_url=None;future_url=None;art=None;revision=0;cached=None;desired=None;completed=None;actions=[];last_active=0
        track=dict(title='Open Spotify',artist='On your Mac',state='paused')
        with (ROOT/'evidence/nuvi350/spotify-controls.jsonl').open('a') as log:
            def record(kind,**fields):
                row=dict(time=time.time(),kind=kind,**fields);line=json.dumps(row);log.write(line+'\n');log.flush();print(line,flush=True)
            def pump():
                nonlocal next_input,last_active
                now=time.monotonic()
                if now<next_input:return
                result=touch.update(channel.rpc('raw'),now)
                if result:actions.append(result);record('qualified_release',button=result)
                active=touch.active(now)
                if active!=last_active:record('interaction',active=active,held=touch.held);last_active=active
                next_input=time.monotonic()+.025
            record('started',profile=profile,seconds=seconds,fit_error_pixels=cal['max_error_pixels'],controls_enabled=True,input='Host-sampled; two-good press/two-up release; hold no-repeat; drag cancels; idle required at start')
            try:
                while time.monotonic()-started<seconds:
                    pump();now=time.monotonic()
                    if meta_job is None and now>=next_meta:meta_job=pool.submit(metadata)
                    if meta_job is not None and meta_job.done():
                        track=meta_job.result();meta_job=None;next_meta=now+1;revision+=1
                        url=track.get('artwork','')
                        if url!=art_url:
                            art_url=url;art=None
                            if art_job is not None:art_job.cancel()
                            art_job=pool.submit(artwork,url);future_url=url
                    if art_job is not None and art_job.done():
                        try:
                            result=art_job.result()
                            if future_url==art_url:art=result;revision+=1
                        except Exception as e:record('artwork_unavailable',reason=str(e))
                        art_job=None
                    active=touch.active(time.monotonic());key=(revision,active)
                    if key!=cached:
                        desired=encode(render(track,art,active=active),profile['width'],profile['height'],'ccw');cached=key
                    pending=transport.pending(desired);pending.sort(key=lambda item:0 if item[0] in priority else 1)
                    for n,(index,block) in enumerate(pending[:128]):
                        transport.send(index,block)
                        if n%8==7:
                            pump()
                            if touch.active(time.monotonic())!=active:break
                    if not transport.pending(desired) and completed!=key:
                        record('frame',title=track.get('title'),artist=track.get('artist'),state=track.get('state'),artwork=art is not None,active=active);completed=key
                    while actions:
                        button=actions.pop(0)
                        # One attempt per qualified release. Never retry ambiguous Apple Event failure.
                        record('playback_attempt',button=button);action(button);record('playback_sent',button=button);next_meta=0
                    time.sleep(.005 if pending else .012)
                record('stopped',reason='duration reached')
            except KeyboardInterrupt:record('stopped',reason='interrupted')
            except Exception as e:record('stopped',reason=str(e));raise
    finally:channel.close();pool.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=1800);a=p.parse_args()
    if not 1<=a.seconds<=3600:p.error('seconds must be1..3600')
    run(a.seconds)
