"""350 raw touch calibration/crosshair experiment. No Spotify actions or storage writes."""
import argparse,json,math,statistics,time
from PIL import Image,ImageDraw
from player_ui import font
from spotify_bridge import Channel,ROOT
from spotify_player import FrameTransport
from nuvi350_display import encode
TARGETS=((30,30),(290,30),(290,210),(30,210),(160,120))

def fit(points):
    if len(points)!=5:raise ValueError('Need five calibration targets')
    raw=[(float(p['a']),float(p['b']),1.) for p in points]
    if min(max(p[k] for p in points)-min(p[k] for p in points) for k in ('a','b'))<40:raise ValueError('Touch samples did not span both axes')
    def solve(axis):
        matrix=[[sum(r[i]*r[j] for r in raw) for j in range(3)]+[sum(r[i]*p[axis] for r,p in zip(raw,points))] for i in range(3)]
        for col in range(3):
            pivot=max(range(col,3),key=lambda row:abs(matrix[row][col]));matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
            scale=matrix[col][col]
            if abs(scale)<1e-8:raise ValueError('Degenerate touch calibration')
            matrix[col]=[v/scale for v in matrix[col]]
            for row in range(3):
                if row!=col:
                    factor=matrix[row][col];matrix[row]=[a-factor*b for a,b in zip(matrix[row],matrix[col])]
        return [matrix[i][3] for i in range(3)]
    x,y=solve('x'),solve('y');errors=[]
    for r,p in zip(raw,points):errors.append(math.hypot(sum(a*b for a,b in zip(x,r))-p['x'],sum(a*b for a,b in zip(y,r))-p['y']))
    if max(errors)>12:raise ValueError('Calibration mismatch; targets need another pass')
    return dict(x=x,y=y,max_error_pixels=max(errors),points=points)

def mapped(cal,a,b):return tuple(sum(c*v for c,v in zip(cal[k],(a,b,1))) for k in ('x','y'))

def screen(index,down=False,cross=None,message=None):
    im=Image.new('RGB',(960,720),'#071b2b');d=ImageDraw.Draw(im)
    def text(y,s,size=14):
        f=font(size);bbox=d.textbbox((0,0),s,font=f);d.text(((960-(bbox[2]-bbox[0]))/2,y*3),s,font=f,fill='white')
    if index<5:
        text(84,'Touch and hold the green target',16);text(112,'Then lift your finger',13);text(144,f'{index+1} of 5',12)
        x,y=TARGETS[index];r=13
        d.ellipse(((x-r)*3,(y-r)*3,(x+r)*3,(y+r)*3),fill='#57ff9a' if down else '#1ed760')
        d.ellipse(((x-3)*3,(y-3)*3,(x+3)*3,(y+3)*3),fill='white')
    else:
        text(15,'Touch calibration complete',16);text(42,'Drag to move the crosshair',12)
        if cross:
            x,y=cross;x=max(0,min(319,x));y=max(0,min(239,y))
            d.line(((x-8)*3,y*3,(x+8)*3,y*3),fill='white',width=3)
            d.line((x*3,(y-8)*3,x*3,(y+8)*3),fill='white',width=3)
    if message:text(185,message,11)
    return im.resize((320,240),Image.Resampling.LANCZOS)

def run(seconds):
    channel=Channel(ROOT/'analysis/nuvi350/usb/nuvi350-touchxy-host')
    try:
        profile=channel.rpc('info');transport=FrameTransport(channel);points=[];samples=[];cal=None;armed=False;released=0;inconsistent=0;desired=None;last_key=None
        log=(ROOT/'evidence/nuvi350/touch-xy.jsonl').open('a');start=time.monotonic()
        def record(kind,**data):
            row=dict(time=time.time(),kind=kind,**data);line=json.dumps(row);log.write(line+'\n');log.flush();print(line,flush=True)
        record('started',profile=profile,actions_enabled=False)
        try:
            while time.monotonic()-start<seconds:
                r=channel.rpc('raw');record('raw',**r)
                if r['flags']&12:raise RuntimeError(f"Touch sampling stopped: flags={r['flags']} transfer={r['failed_transfer']}")
                if r['flags']==17:
                    inconsistent+=1
                    if inconsistent>=12:raise RuntimeError('Touch contact stayed inconsistent; calibration stopped')
                else:inconsistent=0
                cross=None
                if cal:
                    if r['valid']:cross=mapped(cal,r['a'],r['b'])
                elif r['valid'] and armed:
                    samples.append((r['a'],r['b']));samples=samples[-40:];released=0
                elif r['flags']==0:
                    released+=1
                    if released>=2:
                        if armed and len(samples)>=5:
                            a=statistics.median(p[0] for p in samples);b=statistics.median(p[1] for p in samples);x,y=TARGETS[len(points)]
                            point=dict(a=a,b=b,x=x,y=y);points.append(point);record('target',index=len(points),**point)
                            if len(points)==5:
                                cal=fit(points)
                                (ROOT/'evidence/nuvi350/touch-calibration.json').write_text(json.dumps(dict(profile=profile,**cal),indent=2)+'\n')
                                record('calibrated',**cal)
                        samples=[];armed=True
                else:released=0
                index=len(points);key=(index,bool(samples),tuple(round(v/2)*2 for v in cross) if cross else None)
                if key!=last_key:
                    desired=encode(screen(index,bool(samples),cross),profile['width'],profile['height'],'ccw');last_key=key
                # Finish each small frame change before acquiring the next sample.
                for i,block in transport.pending(desired):transport.send(i,block)
                time.sleep(.035)
            record('stopped',reason='duration reached')
        except KeyboardInterrupt:record('stopped',reason='interrupted')
        except Exception as e:record('stopped',reason=str(e));raise
        finally:log.close()
    finally:channel.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=600);a=p.parse_args()
    if not 1<=a.seconds<=1800:p.error('seconds must be1..1800')
    run(a.seconds)
