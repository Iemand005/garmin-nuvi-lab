"""USB3 checks completion-before-enable, setup priority and status-stage direction."""
import json,struct
from audit_usb2_probe import USB2
from audit_usb_probe import USB,protocol_checks
from audit_touch_probe import main,ROOT,BASE,BUFFERS

class USB3(USB2):
    def read(self,address,size):
        if address==0xfffb4008:
            value=super().read(address,size)
            if getattr(self,'inject_setup_after_read',False) and not self.setup:
                self.inject_setup_after_read=False
                self.setup=list(struct.unpack('<4H',struct.pack('<BBHHH',0x80,6,0x100,0,8)))
                self.regs[0x30]|=4
            return value
        if address==0xfffb4010:
            assert size==2
            return self.regs.get(0x10,8)
        return super().read(address,size)

    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if address==state+68:
            assert size==2 and value<=18
            self.put(address,value,size)
            return
        if address==0xfffb400c:
            if value==4:assert self.regs.get(0x30,0)&3==0, 'Enable before completion acknowledgment'
            if value==0x80:
                assert size==2 and self.selection==0x30
                self.usb_writes.append((12,value,size))
                return
        super().write(address,value,size)

    def decorate_frame(self,expected):
        USB.decorate_frame(self,expected)
        state=BASE+self.symbols['scratch']
        values=[(60,62,self.regs.get(0x20,0))]
        values += [(60,y,self.read(state+offset,2)) for y,offset in zip((78,94,110,126),(34,36,38,40))]
        values += [(164,62,self.read(state+68,2)),(164,120,self.read(state+64,2))]
        table=self.payload[self.symbols['register_glyphs']:self.symbols['register_glyphs']+4096]
        for x,y,value in values:
            for digit,ch in enumerate(f'{value:04X}'):
                tile=table[int(ch,16)*256:(int(ch,16)+1)*256]
                for row in range(16):
                    for col in range(8):
                        xx,yy=x+digit*8+col,y+row
                        if self.visible and ((yy==self.y and abs(xx-self.x)<=6) or (xx==self.x and abs(yy-self.y)<=6)):continue
                        offset=yy*640+xx*2
                        expected[offset:offset+2]=tile[row*16+col*2:row*16+col*2+2]
        assert self.otg_writes==[0x50000]

def completion_checks(data,meta,model_type=USB3):
    model=model_type(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
    model.call('usb_init')
    state=BASE+meta['symbols']['scratch']
    result=[]
    for name,bm,source,ack,expect_out in (
        ('IN data ACK arms OUT status',0x80,1,8,True),
        ('OUT request IN status ends',0x40,1,8,False),
        ('IN data without ACK does not advance',0x80,1,0,False),
        ('IN STALL clears halt without advancing',0x80,1,0x20,False),
        ('OUT status ends without rearming',0x80,2,8,False)):
        model.put(state+34,bm,2)
        model.regs[0x30]=source
        model.regs[0x10]=ack
        model.usb_writes=[]
        model.call('usb_poll')
        enabled=False
        selected=0
        for off,value,size in model.usb_writes:
            if off==4:selected=value
            if off==12 and value==4 and selected==0x20:enabled=True
        assert enabled==expect_out,name
        assert model.regs[0x30]&3==0
        result.append(name)
    model.regs[0x10]=8
    model.setup=list(struct.unpack('<4H',struct.pack('<BBHHH',0x80,6,0x100,0,18)))
    model.regs[0x30]=7
    model.packets=[]
    model.usb_writes=[]
    model.call('usb_poll')
    dev=data[meta['symbols']['usb_device']:meta['symbols']['usb_device']+18]
    assert model.packets==[dev]
    assert model.usb_writes[0]==(0x30,3,2)
    result.append('new SETUP supersedes simultaneous stale completions')
    model.setup=list(struct.unpack('<4H',struct.pack('<BBHHH',0x80,6,0x100,0,18)))
    model.regs[0x30]=4
    model.inject_setup_after_read=True
    model.packets=[]
    model.call('usb_poll')
    assert not model.packets and model.setup, 'Answered stale SETUP'
    model.call('usb_poll')
    assert model.packets==[dev[:8]] and not model.setup
    result.append('SETUP arriving during FIFO read defers stale reply and services latest request')
    return result

if __name__=='__main__':
    main('usb3',USB3)
    out=ROOT/'analysis/usb3-probe'
    meta=json.loads((out/'build.json').read_text())
    data=(out/'usb3-candidate.bin').read_bytes()
    report=json.loads((out/'audit.json').read_text())
    report['usb_protocol']=protocol_checks(data,meta,USB3)
    report['completion_checks']=completion_checks(data,meta)
    for offset,value in ((4,0),(8,0)):
        model=USB3(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
        model.otg[offset]=value
        model.call('usb_init')
        assert not model.usb_writes and not model.otg_writes
    report['usb_protocol']['otg_guards_rejected']=2
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('USB3 protocol and7completion checks passed.')
