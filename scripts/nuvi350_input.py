"""Calibrated350 sampled touch controls. No native release queue is available on350."""
import json,math
from spotify_player import button_at
from nuvi350_touch_xy import fit,mapped

def load_calibration(path,profile):
    if path.stat().st_size>16384:raise ValueError('Calibration file too large')
    cal=json.loads(path.read_text())
    if any(cal['profile'].get(k)!=profile.get(k) for k in ('model','hwid','software','width','height')):raise ValueError('Calibration belongs to a different device/profile')
    checked=fit(cal['points'])
    for key in ('x','y'):
        if len(cal[key])!=3 or any(not math.isfinite(v) for v in cal[key]) or any(abs(a-b)>1e-8 for a,b in zip(cal[key],checked[key])):raise ValueError('Calibration coefficients do not match measured targets')
    return checked

class TouchControls:
    """Idle-before-start, two-good press, two-up release, sticky drag cancellation."""
    def __init__(self,cal):
        self.cal=cal;self.armed=False;self.up=0;self.good=0;self.held=False;self.capture=0;self.candidate=0;self.cancelled=False;self.inconsistent=0;self.pulse=0;self.until=0
    def update(self,row,now):
        flags=row['flags']
        if flags&12:raise RuntimeError(f"Touch controller stopped: flags={flags}, transfer={row.get('failed_transfer')}")
        if flags==17:
            self.inconsistent+=1;self.up=0
            if self.inconsistent>=12:raise RuntimeError('Touch contact state is inconsistent; playback control stopped')
            return 0
        self.inconsistent=0
        if flags==3:
            if not 0<=row['a']<=255 or not 0<=row['b']<=255:raise ValueError('Invalid raw coordinates')
            self.up=0
            if not self.armed:return 0
            x,y=mapped(self.cal,row['a'],row['b']);hit=button_at(x,y)
            if not self.held:
                if self.good==0:self.candidate=hit
                elif hit!=self.candidate:self.cancelled=True
                self.good+=1
                if self.good>=2:self.held=True;self.capture=self.candidate
            elif hit!=self.capture:self.cancelled=True
            return 0
        if flags==0:
            self.up+=1
            if self.up<2:return 0
            action=self.capture if self.armed and self.held and not self.cancelled else 0
            self.armed=True;self.good=0;self.held=False;self.capture=0;self.candidate=0;self.cancelled=False
            if action:self.pulse=action;self.until=now+.14
            return action
        # Invalid sample is never a release; cancel an in-flight gesture.
        self.up=0;self.cancelled=True;return 0
    def active(self,now):
        if self.held:return self.capture if not self.cancelled else 0
        return self.pulse if now<self.until else 0
