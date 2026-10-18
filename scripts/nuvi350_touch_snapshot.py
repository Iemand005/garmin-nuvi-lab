"""Read-only350 GPIO/SPI status logging. No playback, storage or touch-drive writes."""
import argparse,json,time
from spotify_bridge import Channel,ROOT

def run(seconds):
    channel=Channel(ROOT/'analysis/nuvi350/usb/nuvi350-touch-host')
    try:
        profile=channel.rpc('info')
        with (ROOT/'evidence/nuvi350/touch-snapshots.jsonl').open('a') as log:
            def record(row):
                row=dict(time=time.time(),**row);line=json.dumps(row);print(line,flush=True);log.write(line+'\n');log.flush()
            record(dict(kind='started',profile=profile,read_only=True))
            start=time.monotonic();previous=None
            while time.monotonic()-start<seconds:
                row=channel.rpc('snapshot')
                if row!=previous:record(dict(kind='snapshot',**row));previous=row
                time.sleep(.05)
            record(dict(kind='stopped',reason='duration reached'))
    finally:channel.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=60);a=p.parse_args()
    if not 1<=a.seconds<=600:p.error('seconds must be1..600')
    try:run(a.seconds)
    except KeyboardInterrupt:pass
