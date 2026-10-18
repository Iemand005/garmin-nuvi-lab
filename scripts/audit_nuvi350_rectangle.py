"""Offline350 screen probe audit; never executes on or writes to the device."""
from pathlib import Path
import hashlib,json,struct
from audit_rectangle_probe import Model,BASE,ROOT
from emulate_loader_handoff import Handoff
class Display350(Model):
    buffers=(0x11fb4fc0,0x11fda7e0)
    def __init__(self,*args,changing=False,**kwargs):
        super().__init__(*args,**kwargs);self.changing=changing;self.low_reads=0
        for start in self.buffers:
            for i in range(2,32):self.put(start+i,0xa5,1)
    def read(self,address,size):
        if address==0xfffee3c8 and self.changing:
            self.low_reads+=1
            if self.low_reads==2:return super().read(address,size)^0x20
        return super().read(address,size)
out=ROOT/'analysis/nuvi350-rectangle-probe';meta=json.loads((out/'build.json').read_text());data=(out/'nuvi350-rectangle-candidate.bin').read_bytes()
assert hashlib.sha256(data).hexdigest()==meta['sha256']
cases=[('buffer_1',Display350.buffers[0],[],2,True),('buffer_2',Display350.buffers[1],[],2,True),
       ('wrong_mode',Display350.buffers[0],[],12,False),('lcd_disabled',Display350.buffers[0],[(0xfffec000,0x80,4)],2,False),
       ('wrong_width',Display350.buffers[0],[(0xfffec004,479,4)],2,False),('wrong_height',Display350.buffers[0],[(0xfffec008,271,4)],2,False),
       ('data_only',Display350.buffers[0],[(0xfffec000,0x200081,4)],2,False),('unknown_buffer',0x11000000,[],2,False),
       ('wrong_dma_length',Display350.buffers[0],[(0xfffee3cc,0,2)],2,False),('wrong_prefix_format',Display350.buffers[0],[(Display350.buffers[0],0x3000,2)],2,False),
       ('changing_buffer',Display350.buffers[0],[],2,False)]
report=[]
for name,selected,changes,mode,success in cases:
    m=Display350(data,meta['symbols'],selected,changes,mode,changing=name=='changing_buffer');prefixes={start:bytes(m.mem[start+i] for i in range(32)) for start in m.buffers}
    result=m.run();assert result['inversion_observed']==success
    assert all(bytes(m.mem[start+i] for i in range(32))==prefixes[start] for start in m.buffers)
    if not success:assert result['halfword_writes']==0
    report.append(dict(case=name,**result))
boot=(ROOT/'analysis/nuvi350/gcd/resident-boot-candidate.bin').read_bytes()
loader=Handoff(boot,0x10800000,data,mode=2,copy_entry=0x170,fallbacks=(0x1d8,0x1e8),veneer=0x17f2c)
handoff=loader.run(max_steps=len(data)*5+1000)
assert handoff['outcome']=='staged_entry_reached' and handoff['entry_mode_r12']==2 and handoff['copied_bytes']==len(data)
assert bytes(loader.memory[BASE+i] for i in range(len(data)))==data
fallback=[]
for name,source,payload,length in (('bad_footer',0x10800000,data[:meta['symbols']['footer']]+b'\0\0'+data[meta['symbols']['footer']+2:],None),('zero_length',0x10800000,data,0),('source_below_stage',BASE-0x100,data,None),('source_over_limit',0x12000000,data,None)):
    model=Handoff(boot,source,payload,length,mode=2,copy_entry=0x170,fallbacks=(0x1d8,0x1e8),veneer=0x17f2c)
    r=model.run(max_steps=len(data)*5+1000);assert r['outcome']=='normal_startup_fallback';fallback.append(dict(case=name,**r))
result=dict(payload_sha256=meta['sha256'],bytes=len(data),cases=report,handoff=handoff,handoff_rejections=fallback,device_io=False,scope='Synthetic ARM model. Copy-stage preamble hardware initialization skipped, staged entry never executed by handoff model. No hardware/cache/timing emulation.')
(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
