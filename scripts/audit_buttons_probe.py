"""Interpret native button dashboard, checking events, rendering and store bounds."""
import json
from audit_touch_probe import Touch, main, ROOT, BASE, BUFFERS, SEQ0, SEQ1

def point(x,y):
    a=min(range(51,1024),key=lambda a:abs(max(6,min(233,307-94*a//256))-y))
    b=min(range(51,1024),key=lambda b:abs(max(6,min(313,113*b//256-59))-x))
    return (a,b)

IDLE=(0,17)
A=point(60,168)
B=point(160,168)
C=point(258,168)
OUT=point(160,120)

class Buttons(Touch):
    step_budget=5000000

    def __init__(self,*args,seed=0,**kwargs):
        super().__init__(*args,**kwargs)
        self.values=([IDLE]*4+[A]*6+[IDLE]*4+
                     [A]*2+[IDLE]*3+[A]*3+[IDLE]*4+
                     [C]*2+[IDLE]*4+[B]*2+[IDLE]*4+
                     [A]*2+[B]*2+[IDLE]*4+
                     [OUT]*2+[A]*2+[IDLE]*4+
                     [A]+[IDLE]*4+[A]*2+[IDLE]*4+
                     [C]*2+[IDLE]*4+[(51,51)]*2+[(1023,1023)]*2+[IDLE]*4)
        self.good=self.bad=self.visible=self.x=self.y=0
        self.armed=1
        self.capture=self.last_hit=self.toggle=0
        self.count=seed
        self.put(BASE+self.symbols['scratch']+14,seed,2)
        self.events=[]

    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if state<=address and address+size<=state+20:
            assert size==2 and address%2==0
            self.put(address,value,size)
            return
        super().write(address,value,size)

    def verify_frame(self):
        a,b=self.values[self.round]
        if min(a,b)>50:
            self.bad=0
            self.good=min(2,self.good+1)
            color=0xfd20
            if self.good==2:
                self.x=max(6,min(313,113*b//256-59))
                self.y=max(6,min(233,307-94*a//256))
                self.visible=1
                self.last_hit=0
                if 144<=self.y<=192:
                    for button,(left,right) in enumerate(((18,105),(116,203),(214,301)),1):
                        if left<=self.x<=right:self.last_hit=button
                if self.armed:
                    self.capture=self.last_hit
                    self.armed=0
                color=0x16d6
        else:
            self.good=0
            self.bad=min(4,self.bad+1)
            color=0xfd20
            if self.bad==4:
                self.visible=0
                color=0x2945
                if not self.armed:
                    self.armed=1
                    if self.capture and self.capture==self.last_hit:
                        self.events.append((self.round,self.capture))
                        if self.capture==1:self.count=min(999,self.count+1)
                        elif self.capture==2:self.count=0
                        else:self.toggle^=1
        state=BASE+self.symbols['scratch']
        actual=[self.read(state+2*i,2) for i in range(10)]
        assert actual==[self.good,self.bad,self.visible,self.x,self.y,self.armed,self.capture,self.count,self.toggle,self.last_hit], (self.round,actual)
        expected=bytearray(self.expected)
        def paint(x,y,width,height,color):
            for row in range(y,y+height):
                offset=row*640+x*2
                expected[offset:offset+width*2]=color.to_bytes(2,'little')*width
        table=self.payload[self.symbols['decimal_glyphs']:self.symbols['decimal_glyphs']+10240]
        for index,ch in enumerate(f'{self.count:03d}'):
            tile=table[int(ch)*1024:(int(ch)+1)*1024]
            for row in range(32):
                offset=(80+row)*640+(136+index*16)*2
                expected[offset:offset+32]=tile[row*32:row*32+32]
        paint(260,70,36,12,0xf97b if self.toggle else 0x16d6)
        if self.visible:
            paint(self.x-6,self.y,13,1,0xffff)
            paint(self.x,self.y-6,1,13,0xffff)
        paint(260,48,36,8,color)
        paint(284,18,12,12,0x16d6 if self.round%2==0 else 0x2945)
        self.decorate_frame(expected)
        actual=bytes(self.mem[self.selected+32+i] for i in range(153600))
        assert actual==expected, f'Frame mismatch at sample{self.round}'
        sequence=SEQ0+[(0xfffe6020,0x8000)]+SEQ1+[(0xfffe6020,0x9000)]+SEQ0
        assert self.peripheral==[(a,v,2 if a==0xfffe6020 else 4) for a,v in sequence]*(self.round+1)
        self.verify_other()
        if self.round==len(self.values)-1:
            assert [button for _,button in self.events]==[1,1,3,2,1,3], self.events
            assert self.count==1 and self.toggle==0

    def decorate_frame(self,expected):
        pass

if __name__=='__main__':
    main('buttons',Buttons)
    out=ROOT/'analysis/buttons-probe'
    meta=json.loads((out/'build.json').read_text())
    data=(out/'buttons-candidate.bin').read_bytes()
    extras=[]
    for seed in (127,456,789,998):
        model=Buttons(data,meta['symbols'],BUFFERS[0],changes=[],mode=12,seed=seed)
        result=model.run()
        extras.append({'initial_count':seed,**result})
    report=json.loads((out/'audit.json').read_text())
    report['decimal_and_saturation_scenarios']=extras
    report['sample_pairs_per_buffer']=len(model.values)
    report['button_events_expected']=[1,1,3,2,1,3]
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Additional decimal/saturation scenarios passed:',len(extras))
