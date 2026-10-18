"""Temporary Garmin<->Spotify experiment. Does not change Garmin storage.

Actions are driven only by qualified Garmin events while --run is active.
Use --metadata for a read-only local Spotify probe.
"""
from pathlib import Path
import argparse,json,select,subprocess,time,unicodedata

ROOT=Path(__file__).resolve().parents[1]
METADATA='''const s=Application("Spotify");
if (!s.running()) JSON.stringify({state:"closed",title:"Open Spotify on the Mac",artist:""});
else { let r={state:s.playerState(),title:"No current track",artist:""};
try {r.title=s.currentTrack().name();r.artist=s.currentTrack().artist();} catch(e) {}
JSON.stringify(r); }'''
ACTIONS={1:'previous track',2:'playpause',3:'next track'}

def metadata():
    r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',METADATA],capture_output=True,text=True,timeout=5)
    if r.returncode:raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)

def action(button):
    if button not in ACTIONS:raise ValueError('Unknown button')
    r=subprocess.run(['/usr/bin/osascript','-e','tell application "Spotify" to '+ACTIONS[button]],capture_output=True,text=True,timeout=5)
    if r.returncode:raise RuntimeError(r.stderr.strip())

def display_text(track):
    def line(s):
        normalized=unicodedata.normalize('NFKD',str(s)).encode('ascii','replace').decode('ascii')
        return ''.join(c if 32<=ord(c)<=126 else ' ' for c in normalized)[:32].ljust(32)
    return (line(track.get('title',''))+line(track.get('artist',''))+line(track.get('state','unknown').upper())).encode('ascii')

class Channel:
    def __init__(self,executable=None):
        self.p=subprocess.Popen([str(executable or ROOT/'analysis/music/music-usb-host'),'serve'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        if self.read().get('ready') is not True:self.close();raise RuntimeError('Music firmware not ready')
    def read(self):
        ready,_,_=select.select([self.p.stdout],[],[],7)
        if not ready:raise TimeoutError('USB host did not reply')
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('USB host stopped')
        value=json.loads(line)
        if 'error' in value:raise RuntimeError(value['error'])
        return value
    def rpc(self,line):
        self.p.stdin.write(line+'\n');self.p.stdin.flush()
        return self.read()
    def close(self):
        if self.p.poll() is None:
            try:self.p.stdin.write('quit\n');self.p.stdin.flush();self.p.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):self.p.terminate();self.p.wait(timeout=3)

def run(seconds,log_path):
    channel=Channel()
    started=time.monotonic();old_text=None;next_metadata=0
    log_path.parent.mkdir(parents=True,exist_ok=True)
    with log_path.open('a') as log:
        def record(kind,**fields):
            item={'time':time.time(),'kind':kind,**fields}
            log.write(json.dumps(item)+'\n');log.flush()
            print(json.dumps(item),flush=True)
        def drain(armed):
            for _ in range(8):
                event=channel.rpc('event')
                if event['dropped']:raise RuntimeError('Button event queue overflow; stopping')
                if not event['button']:return
                # ACK before a non-idempotent music command. Never retry a command
                # on ambiguous Apple Event failure/timeout. A failed action stops.
                channel.rpc('ack '+str(event['seq']))
                record('button' if armed else 'discard_before_start',**event)
                if armed:action(event['button'])
        try:
            drain(False)
            record('started',scope='temporary Spotify experiment')
            while time.monotonic()-started<seconds:
                drain(True)
                now=time.monotonic()
                if now>=next_metadata:
                    current=metadata();text=display_text(current)
                    if text!=old_text:
                        for index in range(48):
                            pair=text[index*2:index*2+2]
                            if old_text is None or pair!=old_text[index*2:index*2+2]:
                                channel.rpc(f'text {index} {int.from_bytes(pair,"little")}')
                                drain(True)
                        old_text=text
                        record('track',**current)
                    next_metadata=time.monotonic()+1
                time.sleep(.08)
            record('stopped',reason='experiment duration reached')
        finally:channel.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    choice=p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--metadata',action='store_true')
    choice.add_argument('--run',action='store_true')
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('--log',type=Path,default=ROOT/'evidence/spotify-bridge.jsonl')
    a=p.parse_args()
    if a.metadata:print(json.dumps(metadata()));return
    if not 1<=a.seconds<=3600:p.error('--seconds must be1..3600')
    run(a.seconds,a.log)

if __name__=='__main__':main()
