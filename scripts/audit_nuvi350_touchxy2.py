"""Model finalPD00/PENIRQ restoration and stock elapsed-time settling requirement."""
import json
from audit_nuvi350_usb import main,BASE,ROOT
from audit_nuvi350_touchxy import TouchXY350,checks as raw_checks,sample

class TouchXY2(TouchXY350):
    final_command=0x98
    def __init__(self,*args,timer_stuck=False,timer_step=16,**kwargs):
        super().__init__(*args,**kwargs)
        self.timer_stuck=timer_stuck;self.timer_step=timer_step;self.timer=0x30;self.timer_reads=0;self.power_command=0
    def read(self,address,size):
        if address==0xfffec708:
            assert size==4
            self.timer_reads+=1
            if not self.timer_stuck:self.timer=(self.timer-self.timer_step)&0xffffffff
            return self.timer
        return super().read(address,size)
    def write(self,address,value,size):
        super().write(address,value,size)
        if address==0xfffb0c2c and self.transfer%3==0:self.power_command=self.tx
        if address==0xfffbe4f0 and self.power_command&1:self.snapshot_values[0xfffbe42c]|=1<<14
    def call(self,label):
        sentinel=BASE+self.symbols['input_loop'];self.pc=BASE+self.symbols[label];self.r[14]=sentinel
        keep={r:self.r[r] for r in (7,9,10,11,12)}
        for steps in range(20000):
            if self.pc==sentinel:
                assert all(self.r[r]==v for r,v in keep.items()),'USB ABI clobber'
                return steps
            self.step()
        raise AssertionError('Touch/USB call bound exceeded')

def checks(data,meta,model_type):
    report=raw_checks(data,meta,model_type);extra=[]
    for name,stuck,step in (('elapsed_wrap',False,16),('slow_timer',False,1),('stuck_timer',True,16)):
        m=model_type(data,meta['symbols'],model_type.buffers[0],changes=[],mode=2,timer_stuck=stuck,timer_step=step);m.boot()
        fields=sample(m)
        if stuck:assert fields[2]==9 and fields[5]==13 and m.timer_reads==1025
        else:
            assert fields[2]==3 and fields[5]==0
            assert m.timer_reads==(5 if step==16 else 64)
            assert m.spi_trace[9][1]==0x98 and not fields[7]&(1<<14)
        extra.append(dict(case=name,flags=fields[2],timer_reads=m.timer_reads,cs_released=not m.cs))
    # Regression reproduces the original bug: same touch held, finalPD01 leavesIRQhigh.
    old=ROOT/'analysis/nuvi350-touchxy-probe';oldmeta=json.loads((old/'build.json').read_text())
    m=model_type((old/'nuvi350-touchxy-candidate.bin').read_bytes(),oldmeta['symbols'],model_type.buffers[0],changes=[],mode=2)
    m.final_command=0x99;m.boot();fields=sample(m);assert fields[2]==17
    extra.append(dict(case='old_pd01_false_release_reproduced',flags=fields[2]))
    report['power_and_settling']=extra
    return report

if __name__=='__main__':main('nuvi350-touchxy2',TouchXY2,checks)
