"""Replay contact qualification without USB/device/playback I/O."""
import contextlib,io,json,tempfile
from pathlib import Path
from unittest.mock import patch
import nuvi350_touch_xy as app
IDLE=dict(flags=0,a=0,b=0,valid=False,failed_transfer=0)
VALID=dict(flags=3,a=100,b=150,valid=True,failed_transfer=0)
INCONSISTENT=dict(flags=17,a=100,b=150,valid=False,failed_transfer=0)
class Clock:
    def __init__(self):self.now=0
    def monotonic(self):return self.now
    def time(self):return self.now
    def sleep(self,_):pass
class Transport:
    def __init__(self,_):pass
    def pending(self,_):return []
def replay(sequence):
    clock=Clock()
    class Channel:
        def __init__(self,*_):self.index=0
        def rpc(self,cmd):
            if cmd=='info':return dict(width=240,height=320)
            assert cmd=='raw'
            row=sequence[self.index];self.index+=1;clock.now+=1;return row
        def close(self):pass
    with tempfile.TemporaryDirectory() as root:
        root=Path(root);(root/'evidence/nuvi350').mkdir(parents=True)
        with patch.multiple(app,ROOT=root,Channel=Channel,time=clock,FrameTransport=Transport,screen=lambda *a,**k:None,encode=lambda *a:b''),contextlib.redirect_stdout(io.StringIO()):
            error=None
            try:app.run(len(sequence))
            except RuntimeError as e:error=str(e)
        rows=[json.loads(x) for x in (root/'evidence/nuvi350/touch-xy.jsonl').read_text().splitlines()]
        return rows,error
prefix=[IDLE]*2+[VALID]*5+[INCONSISTENT]*2
rows,error=replay(prefix)
assert not error and not any(r['kind']=='target' for r in rows),'Inconsistent samples advanced calibration'
rows,error=replay(prefix+[IDLE]*2)
targets=[r for r in rows if r['kind']=='target']
assert not error and len(targets)==1 and targets[0]['time']==11 and targets[0]['a']==100 and targets[0]['b']==150
rows,error=replay([IDLE]*2+[VALID]*5+[INCONSISTENT]*12)
assert 'inconsistent' in error and not any(r['kind']=='target' for r in rows)
rows,error=replay([VALID]*5+[IDLE]*2)
assert not error and not any(r['kind']=='target' for r in rows),'Startup-held touch captured'
print('Contact capture replay checks passed: no false release, qualified lift, inconsistent stop, startup hold')
