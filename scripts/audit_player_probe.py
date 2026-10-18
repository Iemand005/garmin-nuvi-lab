"""Audit native pixel transport, clean UI and preserved touch/USB protocol."""
import json,struct
from audit_music_probe import Music
from audit_usb_probe import protocol_checks
from audit_usb3_probe import completion_checks
from audit_touch_probe import main,ROOT,BASE,BUFFERS,SEQ0,SEQ1

class Player(Music):
    fault_marker=False
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.rx=[];self.rx_count=64
        pos=self.symbols['delay_ticks']
        self.delay_words=tuple(struct.unpack_from('<2I',self.payload,pos))
        assert self.delay_words[0]==0xe25cc001
        # Second instruction must be BEQ input_loop, independent of code offset.
        w=self.delay_words[1];offset=(w&0xffffff)*4
        if offset&(1<<25):offset-=1<<26
        assert w>>24==0x0a and pos+4+8+offset==self.symbols['input_loop']
    def read(self,address,size):
        if address==0xfffb4008 and self.selection==0x20:
            assert size==2 and self.rx
            return self.rx.pop(0)
        if address==0xfffb4014:
            assert size==2 and self.selection==0x20
            return self.rx_count
        return super().read(address,size)
    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if address in (state+90,state+92):
            assert size==2;self.put(address,value,size);return
        super().write(address,value,size)
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
        assert bytes(self.mem[self.selected+32+i] for i in range(153600))==self.expected, self.round
        sequence=SEQ0+[(0xfffe6020,0x8000)]+SEQ1+[(0xfffe6020,0x9000)]+SEQ0
        assert self.peripheral==[(a,v,2 if a==0xfffe6020 else 4) for a,v in sequence]*(self.round+1)
        self.verify_other()
        if self.round==len(self.values)-1:assert self.music_events==[1,1,3,2,1,3]


def image_checks(data,meta,model_type=Player,buffers=BUFFERS):
    result=[]
    for selected in buffers:
        m=model_type(data,meta['symbols'],selected,changes=[],mode=12)
        m.r[9]=selected+32;m.call('usb_init')
        for i in range(2,32):m.put(selected+i,0xa5,1)
        state=BASE+meta['symbols']['scratch']
        def req(index,value=0,length=64):return m.request(0x40,0x57,value,index,length)
        # All valid blocks, first and last pixels: exact framebuffer bounds.
        before={a:v for a,v in m.mem.items() if selected<=a<selected+153632}
        for block in range(2400):
            packets,cmd=req(block)
            assert not packets and cmd!=0x20 and m.read(state+90,2)==1
            words=[(block*32+i)&65535 for i in range(32)]
            m.rx=words.copy();m.rx_count=64;m.regs[0x10]=9;m.regs[0x30]=2;m.packets=[]
            m.call('usb_poll')
            assert not m.rx and m.packets==[b''] and m.read(state+90,2)==0
            assert [m.read(selected+32+block*64+i*2,2) for i in range(32)]==words
        assert all(m.read(selected+i,1)==before[selected+i] for i in range(32))
        m.verify_other()
        for index,value,length in ((2400,0,64),(65535,0,64),(0,1,64),(0,0,0),(0,0,63),(0,0,65)):
            packets,cmd=req(index,value,length);assert not packets and cmd==0x20
        # Short/malformed data must leave framebuffer unchanged and STALL.
        for ack,count in ((8,62),(0,64),(8,0)):
            req(0);m.rx_count=count;m.regs[0x10]=ack;m.regs[0x30]=2
            old=bytes(m.mem[selected+32+i] for i in range(153600))
            m.call('usb_poll');assert m.regs[0x1c]==0x20 and m.read(state+90,2)==0
            assert bytes(m.mem[selected+32+i] for i in range(153600))==old
        # Non-full FIFO uses RX byte count and accepts only exactly64bytes.
        req(2399);m.rx=list(range(32));m.rx_count=64;m.regs[0x10]=8;m.regs[0x30]=2;m.call('usb_poll')
        assert not m.rx
        # New SETUP cancels pending data before processing a descriptor.
        req(0);m.request(0x80,6,0x100,0,18);assert m.read(state+90,2)==0
        # Bus reset cancels pending data.
        req(0);m.regs[0x30]=8;m.regs[0x20]=0x20;m.call('usb_poll');assert m.read(state+90,2)==0
        # Forged pending block cannot escape bounds.
        req(0);m.put(state+92,2400,2);m.regs[0x10]=9;m.regs[0x30]=2
        old=bytes(m.mem[selected+32+i] for i in range(153600));m.call('usb_poll')
        assert m.regs[0x1c]==0x20 and bytes(m.mem[selected+32+i] for i in range(153600))==old
        result.append({'buffer':hex(selected),'blocks_verified':2400,'malformed_requests_rejected':6,'bad_packets_rejected':3,'setup_reset_cancel':True,'invalid_pending_index_rejected':True})
    return result

if __name__=='__main__':
    main('player',Player)
    out=ROOT/'analysis/player-probe';meta=json.loads((out/'build.json').read_text());data=(out/'player-candidate.bin').read_bytes()
    report=json.loads((out/'audit.json').read_text())
    report['usb_protocol']=protocol_checks(data,meta,Player)
    report['completion_checks']=completion_checks(data,meta,Player)
    report['image_checks']=image_checks(data,meta)
    for offset,value in ((4,0),(8,0)):
        m=Player(data,meta['symbols'],BUFFERS[0],changes=[],mode=12);m.otg[offset]=value;m.call('usb_init')
        assert not m.usb_writes and not m.otg_writes
    report['usb_protocol']['otg_guards_rejected']=2
    # Capability v2 plus preserved FIFO semantics; no image host can target v1.
    m=Player(data,meta['symbols'],BUFFERS[0],changes=[],mode=12);m.call('usb_init')
    assert m.request(0xc0,0x56,0,0,8)[0]==[struct.pack('<4H',0x4d55,2,48,8)]
    report['capability_version']=2
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Player pixel bounds, malformed packets, touch and USB checks passed.')
