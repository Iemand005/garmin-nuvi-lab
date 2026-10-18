"""Audit both firmware-supported LCD profiles. No device I/O."""
import hashlib,json
from audit_rectangle_probe import Model,ROOT,BASE
from emulate_loader_handoff import Handoff
class Marker(Model):
    buffers=(0x11fb4fc0,0x11fda7e0)
    def __init__(self,*args,width=320,height=240,changing=False,**kwargs):
        super().__init__(*args,**kwargs);self.width=width;self.height=height;self.changing=changing;self.low_reads=0
        self.put(0xfffec004,width-1,4);self.put(0xfffec008,height-1,4)
        for start in self.buffers:
            for i in range(2,32):self.put(start+i,0xa5,1)
        self.prefix={start:bytes(self.mem[start+i] for i in range(32)) for start in self.buffers}
        self.allowed_scratch=set()
        x,y=(width-64)//2,(height-64)//2
        self.allowed_pixels={self.selected+32+(y+row)*width*2+(x+col)*2+i for row in range(64) for col in range(64) for i in range(2)}
    def read(self,address,size):
        if address==0xfffee3c8 and self.changing:
            self.low_reads+=1
            if self.low_reads==2:return super().read(address,size)^0x20
        return super().read(address,size)
    def run(self,success):
        for step in range(55000):
            if self.pc==BASE+self.symbols['park']:break
            self.step()
        else:raise AssertionError('Execution bound')
        expected=bytearray(self.before[self.selected]) if self.selected in self.before else None
        if success:
            x,y=(self.width-64)//2,(self.height-64)//2
            # Explicit parity independent of the native shifts.
            for row in range(64):
                for col in range(64):
                    off=(y+row)*self.width*2+(x+col)*2
                    expected[off:off+2]=(65535 if ((row//16+col//16)%2) else 0).to_bytes(2,'little')
            assert len(self.writes)==4096
        else:assert not self.writes
        for start in self.buffers:
            assert bytes(self.mem[start+i] for i in range(32))==self.prefix[start]
            want=expected if start==self.selected and success else self.before[start]
            assert bytes(self.mem[start+i] for i in range(32,153632))==want
        return dict(steps=step,pixel_writes=len(self.writes),marker_visible=success,prefix_other_pixels_preserved=True,no_mmio_writes=True)
out=ROOT/'analysis/nuvi350-marker-probe';meta=json.loads((out/'build.json').read_text());data=(out/'nuvi350-marker-candidate.bin').read_bytes();assert hashlib.sha256(data).hexdigest()==meta['sha256']
cases=[]
for width,height in ((320,240),(240,320)):
    for buffer in Marker.buffers:cases.append((f'{width}x{height}:{buffer:x}',buffer,width,height,2,[],False,True))
for name,width,height,mode,changes,changing in (
    ('wrong_mode',320,240,12,[],False),('lcd_off',320,240,2,[(0xfffec000,0x80,4)],False),
    ('data_only',320,240,2,[(0xfffec000,0x200081,4)],False),('wrong_width',319,240,2,[],False),('wrong_height',320,239,2,[],False),
    ('mixed_profiles',320,320,2,[],False),('wrong_dma',320,240,2,[(0xfffee3cc,0,2)],False),
    ('wrong_format',320,240,2,[(Marker.buffers[0],0x3000,2)],False),('changing_buffer',320,240,2,[],True)):
    cases.append((name,Marker.buffers[0],width,height,mode,changes,changing,False))
cases.append(('unknown_buffer',0x11000000,320,240,2,[],False,False))
results=[]
for name,buffer,width,height,mode,changes,changing,success in cases:
    m=Marker(data,meta['symbols'],buffer,changes=[],mode=mode,width=width,height=height,changing=changing)
    for a,v,size in changes:m.put(a,v,size)
    # Update baseline after deliberately changed prefix in negative tests.
    m.prefix={start:bytes(m.mem[start+i] for i in range(32)) for start in m.buffers}
    results.append(dict(case=name,**m.run(success)))
boot=(ROOT/'analysis/nuvi350/gcd/resident-boot-candidate.bin').read_bytes()
m=Handoff(boot,0x10800000,data,mode=2,copy_entry=0x170,fallbacks=(0x1d8,0x1e8),veneer=0x17f2c);handoff=m.run(max_steps=len(data)*5+1000)
assert handoff['entry_mode_r12']==2 and handoff['copied_bytes']==len(data)
rejections=[]
for name,source,payload,length in (('bad_footer',0x10800000,data[:meta['symbols']['footer']]+b'\0\0'+data[meta['symbols']['footer']+2:],None),('zero_length',0x10800000,data,0),('source_below_stage',BASE-0x100,data,None),('source_over_limit',0x12000000,data,None)):
    m=Handoff(boot,source,payload,length,mode=2,copy_entry=0x170,fallbacks=(0x1d8,0x1e8),veneer=0x17f2c)
    r=m.run(max_steps=len(data)*5+1000);assert r['outcome']=='normal_startup_fallback';rejections.append(dict(case=name,**r))
report=dict(handoff_rejections=rejections,payload_sha256=meta['sha256'],bytes=len(data),cases=results,handoff=handoff,device_io=False,scope='Synthetic ARM/model copy-stage only; physical LCD variant unconfirmed, no cache/hardware/timing emulation.')
(out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
