"""Audit native demo rendering, bounded text, event FIFO and proven USB path."""
import json,struct
from audit_usb3_probe import USB3,completion_checks
from audit_usb_probe import protocol_checks
from audit_touch_probe import main,ROOT,BASE,BUFFERS,SEQ0,SEQ1

class Music(USB3):
    step_budget=15000000
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.music_events=[]

    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if (address in (state+80,state+82,state+88) or
            state+128<=address and address+size<=state+224 or
            state+256<=address and address+size<=state+288):
            assert size==2 and address%2==0
            self.put(address,value,size)
            return
        super().write(address,value,size)

    def step(self):
        w=super().read(self.pc,4)
        if self.cond(w>>28) and ((w>>26)&3)==1 and w&(1<<22) and w&(1<<20):
            assert not w&(1<<25)
            rn,rd=(w>>16)&15,(w>>12)&15
            delta=w&0xfff
            before=self.rr(rn)
            after=before+(delta if w&(1<<23) else -delta)
            address=after if w&(1<<24) else before
            state=BASE+self.symbols['scratch']
            assert state+128<=address<state+224
            self.r[rd]=self.read(address,1)
            if not w&(1<<24) or w&(1<<21):self.r[rn]=after
            self.pc+=4
            return
        super().step()

    def text_frame(self,expected):
        state=BASE+self.symbols['scratch']
        table=self.payload[self.symbols['music_glyphs']:self.symbols['music_glyphs']+24320]
        for index in range(96):
            ch=self.read(state+128+index,1)
            if not 32<=ch<=126:ch=32
            tile=table[(ch-32)*256:(ch-31)*256]
            x,y=32+(index%32)*8,64+(index//32)*24
            for row in range(16):
                offset=(y+row)*640+x*2
                expected[offset:offset+16]=tile[row*16:row*16+16]

    def verify_frame(self):
        a,b=self.values[self.round]
        if min(a,b)>50:
            self.bad=0;self.good=min(2,self.good+1);color=0xfd20
            if self.good==2:
                self.x=max(6,min(313,113*b//256-59))
                self.y=max(6,min(233,307-94*a//256))
                self.visible=1;self.last_hit=0
                if 144<=self.y<=192:
                    for button,(left,right) in enumerate(((18,105),(116,203),(214,301)),1):
                        if left<=self.x<=right:self.last_hit=button
                if self.armed:self.capture=self.last_hit;self.armed=0
                color=0x16d6
        else:
            self.good=0;self.bad=min(4,self.bad+1);color=0xfd20
            if self.bad==4:
                self.visible=0;color=0x2945
                if not self.armed:
                    self.armed=1
                    if self.capture and self.capture==self.last_hit:self.music_events.append(self.capture)
        state=BASE+self.symbols['scratch']
        assert [self.read(state+2*i,2) for i in range(10)]==[self.good,self.bad,self.visible,self.x,self.y,self.armed,self.capture,0,0,self.last_hit]
        assert self.read(state+80,2)==len(self.music_events) and self.read(state+82,2)==0
        for seq,button in enumerate(self.music_events,1):
            entry=state+256+(seq%8)*4
            assert (self.read(entry,2),self.read(entry+2,2))==(seq,button)
        expected=bytearray(self.expected)
        self.text_frame(expected)
        def paint(x,y,w,h,c):
            for row in range(y,y+h):
                offset=row*640+x*2;expected[offset:offset+2*w]=c.to_bytes(2,'little')*w
        initialized=self.read(state+62,2)==1
        configured=self.read(state+32,2)==1
        paint(260,34,36,8,0x16d6 if configured else 0xfd20 if initialized else 0xf800)
        if self.visible:
            paint(self.x-6,self.y,13,1,0xffff);paint(self.x,self.y-6,1,13,0xffff)
        paint(260,48,36,8,color)
        paint(284,18,12,12,0x16d6 if self.round%2==0 else 0x2945)
        assert bytes(self.mem[self.selected+32+i] for i in range(153600))==expected, self.round
        sequence=SEQ0+[(0xfffe6020,0x8000)]+SEQ1+[(0xfffe6020,0x9000)]+SEQ0
        assert self.peripheral==[(a,v,2 if a==0xfffe6020 else 4) for a,v in sequence]*(self.round+1)
        self.verify_other()
        if self.round==len(self.values)-1:assert self.music_events==[1,1,3,2,1,3]

    def release(self,button):
        state=BASE+self.symbols['scratch']
        for offset,value in ((10,0),(12,button),(18,button)):self.put(state+offset,value,2)
        self.r[8]=state
        self.pc=BASE+self.symbols['button_release']
        for _ in range(100):
            if self.pc==BASE+self.symbols['button_idle']:return
            self.step()
        raise AssertionError('Release bound exceeded')

def extension_checks(data,meta):
    model=Music(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
    model.call('usb_init')
    cases=[]
    def request(name,bm,req,value=0,index=0,length=0,expected=None,stall=False):
        packets,cmd=model.request(bm,req,value,index,length)
        assert (not packets and cmd==0x20) if stall else packets==[expected],name
        cases.append(name)
    request('music capability',0xc0,0x56,length=8,expected=struct.pack('<4H',0x4d55,1,48,8))
    for ch in range(32,127):request('text glyph '+str(ch),0x40,0x53,ch|(ch<<8),ch%48,expected=b'')
    request('last text pair',0x40,0x53,0x7e20,47,expected=b'')
    for value,index,length in ((0x2020,48,0),(0x201f,0,0),(0x7f20,0,0),(0x2020,0,1)):
        request('reject text '+str((value,index,length)),0x40,0x53,value,index,length,stall=True)
    for i in range(10):model.release(i%3+1)
    state=BASE+meta['symbols']['scratch']
    assert model.read(state+80,2)==8 and model.read(state+88,2)==2
    request('reject out-of-order ACK',0x40,0x55,2,stall=True)
    for seq in range(1,9):
        reply=struct.pack('<4H',0x4d45,seq,(seq-1)%3+1,2)
        request('event '+str(seq),0xc0,0x54,length=8,expected=reply)
        request('repeat read '+str(seq),0xc0,0x54,length=8,expected=reply)
        request('ack '+str(seq),0x40,0x55,seq,expected=b'')
        request('repeat ack '+str(seq),0x40,0x55,seq,expected=b'')
    request('empty queue',0xc0,0x54,length=8,expected=struct.pack('<4H',0x4d45,8,0,2))
    request('reject future empty ACK',0x40,0x55,9,stall=True)
    model.put(state+80,65534,2);model.put(state+82,65534,2)
    model.release(2);model.release(3)
    for seq,button in ((65535,2),(0,3)):
        request('wrap event '+str(seq),0xc0,0x54,length=8,expected=struct.pack('<4H',0x4d45,seq,button,2))
        request('wrap ack '+str(seq),0x40,0x55,seq,expected=b'')
    # Render all95glyphs, not just typical song text; no device I/O.
    text=bytes(range(32,127))+b' '
    for i,value in enumerate(text):model.put(state+128+i,value,1)
    model.r[9]=model.selected+32
    model.pc=BASE+meta['symbols']['draw_music']
    sentinel=BASE+meta['symbols']['input_loop'];model.r[14]=sentinel
    for _ in range(150000):
        if model.pc==sentinel:break
        model.step()
    else:raise AssertionError('Text renderer bound')
    expected=bytearray(model.expected);model.text_frame(expected)
    for y in (64,88,112):
        for row in range(16):
            offset=(y+row)*640+64
            actual=bytes(model.mem[model.selected+32+offset+i] for i in range(512))
            assert actual==expected[offset:offset+512]
    return {'cases':cases,'queue_capacity':8,'overflow_rejected':2,'sequence_wrap_verified':True,'all_printable_glyphs_verified':95}

if __name__=='__main__':
    main('music',Music)
    out=ROOT/'analysis/music-probe';meta=json.loads((out/'build.json').read_text());data=(out/'music-candidate.bin').read_bytes()
    report=json.loads((out/'audit.json').read_text())
    report['usb_protocol']=protocol_checks(data,meta,Music)
    # Completion tests use only preserved controller paths/labels.
    report['completion_checks']=completion_checks(data,meta)
    report['music_extensions']=extension_checks(data,meta)
    for offset,value in ((4,0),(8,0)):
        m=Music(data,meta['symbols'],BUFFERS[0],changes=[],mode=12);m.otg[offset]=value;m.call('usb_init')
        assert not m.usb_writes and not m.otg_writes
    report['usb_protocol']['otg_guards_rejected']=2
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Music extensions, text bounds, queue/wrap and rendering passed.')
