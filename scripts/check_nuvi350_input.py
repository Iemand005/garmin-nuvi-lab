"""No hardware/playback I/O: replay qualification and calibrated button geometry."""
from nuvi350_input import TouchControls
from player_ui import BUTTON_CENTERS
CAL=dict(x=[1,0,0],y=[0,1,0])
UP=dict(flags=0,a=0,b=0)
def down(x=160,y=169):return dict(flags=3,a=x,b=y)
def replay(rows):
    touch=TouchControls(CAL);actions=[]
    for i,r in enumerate(rows):
        action=touch.update(r,i*.03)
        if action:actions.append(action)
    return actions,touch
# Use actual calibration for the right button (raw8bit cannot represent logical258).
import json
from pathlib import Path
cal=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/nuvi350-calibration.json').read_text())
for button,x in BUTTON_CENTERS:
    candidates=[(a,b) for a in range(256) for b in range(256)]
    from nuvi350_touch_xy import mapped
    a,b=min(candidates,key=lambda p:sum((u-v)**2 for u,v in zip(mapped(cal,*p),(x,169))))
    t=TouchControls(cal);actions=[]
    for i,r in enumerate([UP,UP]+[dict(flags=3,a=a,b=b)]*20+[UP]*10):
        result=t.update(r,i*.03)
        if result:actions.append(result)
    assert actions==[button],(button,actions)
assert replay([UP,UP]+[down()]*20+[UP]*10)[0]==[2]
assert replay([down()]*20+[UP]*5)[0]==[]
assert replay([UP,UP,down(),UP,UP])[0]==[]
assert replay([UP,UP,down(),down(),down(160,120),down(),UP,UP])[0]==[]
assert replay([UP,UP,down(160,120),down(),down(),UP,UP])[0]==[]
assert replay([UP,UP,down(),down(),dict(flags=17),dict(flags=17)])[0]==[]
assert replay([UP,UP,down(),down(),dict(flags=33),UP,UP])[0]==[]
actions,t=replay([UP,UP,down(),down(),UP,UP]);assert actions==[2] and t.active(.15)==2 and t.active(1)==0
for flag in (4,9):
    try:replay([dict(flags=flag)]);raise AssertionError('Controller fault accepted')
    except RuntimeError:pass
print('350 input checks passed: 3 calibrated buttons, hold/no-repeat, idle startup, short tap, drag cancel, slide-in, false release, invalid sample, pulse, faults')
