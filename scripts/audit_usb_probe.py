"""Actual ARM EP0 protocol checks with a synthetic OMAP register/FIFO model.

Does not emulate USB signalling, clocks, enumeration timing or physical hardware.
"""
import hashlib,json,struct
from audit_buttons_probe import Buttons
from audit_touch_probe import main, ROOT, BASE, BUFFERS

class USB(Buttons):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.regs={0x80:0x3001,0x18:0}
        self.selection=0
        self.setup=[]
        self.fifo=bytearray()
        self.packets=[]
        self.usb_writes=[]

    def decorate_frame(self,expected):
        state=BASE+self.symbols['scratch']
        color=0xf800
        if self.read(state+62,2)==1:
            color=0x16d6 if self.read(state+32,2)==1 else 0xfd20
        for y in range(112,120):
            for x in range(260,296):
                # USB status is drawn before the crosshair.
                if self.visible and ((y==self.y and abs(x-self.x)<=6) or (x==self.x and abs(y-self.y)<=6)):
                    continue
                offset=y*640+x*2
                expected[offset:offset+2]=color.to_bytes(2,'little')

    def read(self,address,size):
        if 0xfffb4000<=address<0xfffb4100:
            assert size==2
            offset=address-0xfffb4000
            if offset==8:
                assert self.selection==0x40 and self.setup
                value=self.setup.pop(0)
                if not self.setup:self.regs[0x30]&=~4
                return value
            assert offset in (0x80,0x18,0x30,0x20), hex(offset)
            return self.regs.get(offset,0)
        return super().read(address,size)

    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if state+32<=address and address+size<=state+64:
            assert size==2 and address%2==0
            self.put(address,value,size)
            return
        if 0xfffb4000<=address<0xfffb4100:
            offset=address-0xfffb4000
            assert size==2 or (offset==8 and size==1)
            assert offset in (4,8,12,0x18,0x1c,0x28,0x2c,0x30,0x40,0x44) or (0x84<=offset<=0xbc and offset%4==0) or (0xc4<=offset<=0xfc and offset%4==0), hex(offset)
            self.usb_writes.append((offset,value,size))
            if offset==4:
                assert value in (0,0x10,0x20,0x30,0x40)
                self.selection=value
            elif offset==8:
                assert self.selection==0x30
                self.fifo.extend((value&((1<<(size*8))-1)).to_bytes(size,'little'))
                assert len(self.fifo)<=18
            elif offset==12:
                assert value in (2,4)
                if self.selection==0x30:
                    if value==2:self.fifo.clear()
                    else:self.packets.append(bytes(self.fifo))
                else:assert self.selection==0x20
            elif offset==0x30:self.regs[offset]=self.regs.get(offset,0)&~value
            else:
                if offset==0x18:assert value==0x101
                elif offset==0x1c:assert value in (4,8,0x20)
                else:assert value==0
                self.regs[offset]=value
            return
        super().write(address,value,size)

    def step(self):
        w=super().read(self.pc,4)
        if self.cond(w>>28) and ((w>>26)&3)==1 and w&(1<<22) and not w&(1<<20):
            assert not w&(1<<25) and w&(1<<24) and not w&(1<<21)
            rn,rd=(w>>16)&15,(w>>12)&15
            delta=w&0xfff
            self.write(self.rr(rn)+(delta if w&(1<<23) else -delta),self.rr(rd)&255,1)
            self.pc+=4
            return
        super().step()

    def call(self,label):
        sentinel=BASE+self.symbols['input_loop']
        self.pc=BASE+self.symbols[label]
        self.r[14]=sentinel
        keep={r:self.r[r] for r in (7,9,10,11,12)}
        for steps in range(10000):
            if self.pc==sentinel:
                assert all(self.r[r]==v for r,v in keep.items()), 'USB ABI clobber'
                return steps
            self.step()
        raise AssertionError('USB call did not return within bound')

    def request(self,bm,request,value=0,index=0,length=0):
        self.setup=list(struct.unpack('<4H',struct.pack('<BBHHH',bm,request,value,index,length)))
        self.regs[0x30]=4
        self.regs[0x1c]=0
        self.packets=[]
        self.call('usb_poll')
        assert not self.setup
        return self.packets,self.regs.get(0x1c)

def protocol_checks(data,meta,model_type=USB):
    model=model_type(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
    model.call('usb_init')
    assert model.regs[0x18]==0x101
    assert len([w for w in model.usb_writes if w[0]>=0x84])==30
    cases=[]
    def expect(name,bm,req,value,index,length,expected=None,stall=False):
        packets,cmd=model.request(bm,req,value,index,length)
        if stall:assert not packets and cmd==0x20,name
        else:assert packets==[expected],(name,packets,expected)
        cases.append(name)
    dev=data[meta['symbols']['usb_device']:meta['symbols']['usb_device']+18]
    cfg=data[meta['symbols']['usb_configuration']:meta['symbols']['usb_configuration']+18]
    for length in (0,1,7,8,9,18,64,65535):
        expect('device descriptor length '+str(length),0x80,6,0x100,0,length,dev[:length])
    expect('configuration descriptor',0x80,6,0x200,0,255,cfg)
    expect('set configuration',0,9,1,0,0,b'')
    expect('get configuration',0x80,8,0,0,1,b'\1')
    expect('get status',0x80,0,0,0,2,b'\0\0')
    expect('get interface',0x81,10,0,0,1,b'\0')
    expect('set interface',1,11,0,0,0,b'')
    for value in (0,321,999):
        expect('set displayed value '+str(value),0x40,0x51,value,0,0,b'')
        assert model.read(BASE+meta['symbols']['scratch']+14,2)==value
    state=BASE+meta['symbols']['scratch']
    for offset,value in ((6,123),(8,87),(4,1),(16,1)):model.put(state+offset,value,2)
    touch=struct.pack('<8H',0x4c47,1,999,123,87,1,1,1)
    for length in (0,1,15,16,65535):expect('touch length '+str(length),0xc0,0x52,0,0,length,touch[:length])
    for args in ((0x40,0x51,1000,0,0),(0x40,0x51,1,1,0),(0x40,0x51,1,0,1),
                 (0xc0,0x52,1,0,16),(0,9,2,0,0),(0,9,1,0,1),
                 (0x80,6,0x300,0,18),(0x80,6,0x101,0,18),(0xff,0xff,0xffff,0xffff,0xffff)):
        expect('unsupported '+str(args),*args,stall=True)
    # Completion, device reset and recovery must remain bounded.
    model.regs[0x30]=11
    model.regs[0x20]=0x20
    model.call('usb_poll')
    assert model.read(state+32,2)==0 and model.regs[0x30]==0
    expect('request after reset',0x80,6,0x100,0,18,dev)
    for field,value in ((0x80,0),(0x18,1)):
        rejected=model_type(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
        rejected.regs[field]=value
        rejected.call('usb_init')
        assert not rejected.usb_writes
        rejected.call('usb_poll')
        assert not rejected.usb_writes
    return {'cases':cases,'init_guards_rejected':2,'fifo_max_bytes':18,'abi_preserved':True,'bounded_calls':True}

if __name__=='__main__':
    main('usb',USB)
    out=ROOT/'analysis/usb-probe'
    meta=json.loads((out/'build.json').read_text())
    data=(out/'usb-candidate.bin').read_bytes()
    assert hashlib.sha256(data).hexdigest()==meta['sha256']
    report=json.loads((out/'audit.json').read_text())
    report['usb_protocol']=protocol_checks(data,meta)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('USB protocol checks passed:',len(report['usb_protocol']['cases']))
