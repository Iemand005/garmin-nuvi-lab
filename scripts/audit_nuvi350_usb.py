"""Bounded offline350 USB/display-only ARM audit. No device I/O."""
import hashlib,json,struct
from audit_usb3_probe import USB3,completion_checks
from audit_usb_probe import protocol_checks
from audit_player_probe import image_checks
from audit_rectangle_probe import ROOT,BASE
from emulate_loader_handoff import Handoff
class USB350(USB3):
    buffers=(0x11fb4fc0,0x11fda7e0)
    def __init__(self,*args,width=320,height=240,changing=False,**kwargs):
        super().__init__(*args,**kwargs);self.rx=[];self.rx_count=64;self.width=width;self.height=height;self.changing=changing;self.low_reads=0
        self.put(0xfffec004,width-1,4);self.put(0xfffec008,height-1,4)
        for start in self.buffers:
            for i in range(2,32):self.put(start+i,0xa5,1)
    def read(self,address,size):
        if address==0xfffb4008 and self.selection==0x20:
            assert size==2 and self.rx;return self.rx.pop(0)
        if address==0xfffb4014:
            assert size==2 and self.selection==0x20;return self.rx_count
        if address==0xfffee3c8 and self.changing:
            self.low_reads+=1
            if self.low_reads==2:return super().read(address,size)^0x20
        return super().read(address,size)
    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if address in (state+90,state+92):assert size==2;self.put(address,value,size);return
        super().write(address,value,size)
    def verify_other(self):
        other=next(b for b in self.buffers if b!=self.selected)
        assert bytes(self.mem[other+32+i] for i in range(153600))==self.before[other]
        for b in self.buffers:assert self.read(b,2)==0x4000
    def boot(self,display=True,usb=True):
        for steps in range(65000):
            if self.pc in (BASE+self.symbols['park'],BASE+self.symbols['input_loop']):break
            self.step()
        else:raise AssertionError('Entry bound exceeded')
        assert (self.pc==BASE+self.symbols['input_loop'])==display
        assert not self.peripheral,'USB test unexpectedly touched ADC/GPIO'
        assert self.pixel_writes==(4096 if display else 0)
        state=BASE+self.symbols['scratch'];assert self.read(state+62,2)==int(usb)
        if not usb:assert not self.usb_writes and not self.otg_writes
        for start in self.buffers:
            expected=bytearray(self.before[start])
            if display and start==self.selected:
                x,y=(self.width-64)//2,(self.height-64)//2
                for row in range(64):
                    for col in range(64):
                        off=(y+row)*self.width*2+(x+col)*2
                        expected[off:off+2]=(65535 if ((row//32+col//32)%2) else 0).to_bytes(2,'little')
            assert bytes(self.mem[start+i] for i in range(32,153632))==expected
            assert self.read(start,2) in (0x4000,0x3000)
            assert bytes(self.mem[start+i] for i in range(2,32))==b'\xa5'*30
        return dict(steps=steps,marker_visible=display,usb_initialized=usb,no_touch_io=True,pixel_writes=self.pixel_writes)

def main(experiment='nuvi350-usb',model_type=USB350,extra_checks=None):
    USB350=model_type
    out=ROOT/f'analysis/{experiment}-probe';meta=json.loads((out/'build.json').read_text());data=(out/f'{experiment}-candidate.bin').read_bytes();assert hashlib.sha256(data).hexdigest()==meta['sha256']
    cases=[];infos=[]
    for width,height in ((320,240),(240,320)):
        for buffer in USB350.buffers:
            m=USB350(data,meta['symbols'],buffer,changes=[],mode=2,width=width,height=height)
            cases.append(dict(case=f'{width}x{height}:{buffer:x}',**m.boot()))
            expected=struct.pack('<8H',0x3530,1,476,620,width,height,buffer&65535,buffer>>16)
            for length in (0,1,15,16,65535):assert m.request(0xc0,0x58,0,0,length)[0]==[expected[:length]]
            for value,index in ((1,0),(0,1)):
                p,cmd=m.request(0xc0,0x58,value,index,16);assert not p and cmd==0x20
            infos.append(dict(width=width,height=height,buffer=hex(buffer),clipped_lengths=5,bad_inputs_rejected=2))
    for name,width,height,mode,changes,changing in (
        ('wrong_mode',320,240,12,[],False),('lcd_off',320,240,2,[(0xfffec000,0x80,4)],False),
        ('data_only',320,240,2,[(0xfffec000,0x200081,4)],False),('wrong_width',319,240,2,[],False),('wrong_height',320,239,2,[],False),
        ('mixed_profiles',320,320,2,[],False),('wrong_dma',320,240,2,[(0xfffee3cc,0,2)],False),
        ('wrong_format',320,240,2,[(USB350.buffers[0],0x3000,2)],False),('changing_buffer',320,240,2,[],True),
        ('unknown_buffer',320,240,2,[],False)):
        selected=0x11000000 if name=='unknown_buffer' else USB350.buffers[0]
        m=USB350(data,meta['symbols'],selected,changes=[],mode=mode,width=width,height=height,changing=changing)
        for a,v,n in changes:m.put(a,v,n)
        cases.append(dict(case=name,**m.boot(False,False)))
    for name,field,value in (('EP0_layout',0x80,0),('SYSCON1',0x18,1),('OTG_mode',4,0),('OTG_enable',8,0)):
        m=USB350(data,meta['symbols'],USB350.buffers[0],changes=[],mode=2)
        if name.startswith('OTG'):m.otg[field]=value
        else:m.regs[field]=value
        cases.append(dict(case=name,**m.boot(True,False)))
    legacy=protocol_checks(data,meta,USB350)
    completions=completion_checks(data,meta,USB350)
    images=image_checks(data,meta,USB350,USB350.buffers)
    boot=(ROOT/'analysis/nuvi350/gcd/resident-boot-candidate.bin').read_bytes()
    m=Handoff(boot,0x10800000,data,mode=2,copy_entry=0x170,fallbacks=(0x1d8,0x1e8),veneer=0x17f2c);handoff=m.run(max_steps=len(data)*5+1000)
    assert handoff['entry_mode_r12']==2 and handoff['copied_bytes']==len(data)
    report=dict(payload_sha256=meta['sha256'],bytes=len(data),cases=cases,info_checks=infos,usb_protocol=legacy,completion_checks=completions,image_checks=images,handoff=handoff,device_io=False,scope='Synthetic ARM and register/FIFO model; no physical USB/cache/clock/timing emulation, hardware preamble skipped.')
    if extra_checks is not None:report['snapshot_checks']=extra_checks(data,meta,model_type)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print('350 USB/display audit passed:',meta['sha256'])
if __name__=='__main__':main()
