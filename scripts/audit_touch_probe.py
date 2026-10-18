"""Interpret raw-touch candidate with bounded ADC/timer models and exact stores.

Hardware/cache/real ADC behavior are not emulated. No device access.
"""
import hashlib
import json
from pathlib import Path
from audit_rectangle_probe import Model, BASE, BUFFERS, MASK
from emulate_loader_handoff import Handoff

ROOT=Path(__file__).resolve().parents[1]
SEQ0=[(0xfffbb4f0,2),(0xfffbe4b0,0x8000),(0xfffbe4b0,0x10),
      (0xfffbb4f0,4),(0xfffbb4b0,8)]
SEQ1=[(0xfffbb4b0,2),(0xfffbe4f0,0x8000),(0xfffbe4f0,0x10),
      (0xfffbb4b0,4),(0xfffbb4b0,8)]

class Touch(Model):
    def __init__(self,*args,fault=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.expected=self.payload[self.symbols['screen']:self.symbols['screen']+153600]
        self.fault=fault
        self.put(0xfffe6014,1,2)
        self.put(0xfffbb434,0,4)
        self.put(0xfffbe434,0,4)
        self.timer=0x12345678
        self.values=[(0,1023),(512,128),(1023,0)]
        self.round=0
        self.command=None
        self.status_reads=0
        self.peripheral=[]
        self.pixel_writes=0
        self.reads=set()

    def read(self,address,size):
        self.reads.add((address,size))
        if address==0xfffec708:
            assert size==4
            if self.fault!='timer':self.timer=(self.timer-100)&MASK
            return self.timer
        if address==0xfffe6018:
            assert size==2 and self.command is not None
            self.status_reads+=1
            return int(self.fault!='adc' and self.status_reads>=3)
        if address==0xfffe6034:
            assert size==2
            if self.command is None:return 0
            if self.status_reads<3:raise ValueError('Result read before readiness')
            return 0xa000|self.values[self.round][int(self.command==0x9000)]
        return super().read(address,size)

    def write(self,address,value,size):
        if self.selected+32<=address and address+size<=self.selected+153632:
            assert size==2 and address%2==0
            self.pixel_writes+=1
            self.put(address,value,size)
        elif address in {a for a,_ in SEQ0+SEQ1}:
            assert size==4 and value in (2,4,8,0x10,0x8000)
            self.peripheral.append((address,value,size))
        elif address==0xfffe6020:
            assert size==2 and value in (0x8000,0x9000)
            self.peripheral.append((address,value,size))
            self.command=value
            self.status_reads=0
        else:
            raise ValueError(f'Forbidden touch store {address:#x} size{size}')

    def step(self):
        w=super().read(self.pc,4)
        if self.cond(w>>28):
            if w&0x0f000000==0x0b000000:
                n=w&0xffffff
                if n&0x800000:n-=1<<24
                self.r[14]=self.pc+4
                self.pc=(self.pc+8+n*4)&MASK
                return
            if w&0x0fffffff==0x012fff1e:
                assert self.r[14]%4==0
                self.pc=self.r[14]
                return
            if (w>>26)&3==1 and not w&(1<<20):
                assert not w&(1<<25) and w&(1<<24) and not w&(1<<21) and not w&(1<<22)
                rn,rd=(w>>16)&15,(w>>12)&15
                delta=w&0xfff
                self.write(self.rr(rn)+(delta if w&(1<<23) else -delta),self.rr(rd),4)
                self.pc+=4
                return
        super().step()

    def verify_frame(self):
        expected=bytearray(self.expected)
        def paint(x,y,width,height,color):
            for row in range(y,y+height):
                for col in range(x,x+width):
                    expected[row*640+col*2:row*640+col*2+2]=color.to_bytes(2,'little')
        for y,value in zip((112,160),self.values[self.round]):
            length=value>>2
            paint(32,y,256,12,0x2945)
            paint(32,y,length,12,0x16d6)
        paint(284,18,12,12,0x16d6 if self.round%2==0 else 0x2945)
        actual=bytes(self.mem[self.selected+32+i] for i in range(153600))
        assert actual==expected, 'Rendered raw values differ'
        sequence=SEQ0+[(0xfffe6020,0x8000)]+SEQ1+[(0xfffe6020,0x9000)]+SEQ0
        assert self.peripheral==[(a,v,2 if a==0xfffe6020 else 4) for a,v in sequence]*(self.round+1)
        self.verify_other()

    def verify_other(self):
        other=next(b for b in BUFFERS if b!=self.selected)
        assert bytes(self.mem[other+32+i] for i in range(153600))==self.before[other]
        for b in BUFFERS:assert super().read(b,2)==0x4000

    def run(self):
        for step in range(getattr(self, 'step_budget', 1100000)):
            if self.pc==BASE+self.symbols['park']:
                if self.fault:
                    assert self.read(self.selected+32+12088,2)==0xf800 if getattr(self,'fault_marker',True) else bytes(self.mem[self.selected+32+i] for i in range(153600))==self.expected
                    self.verify_other()
                    return {'timeout_stopped':True,'steps':step,'peripheral_stores':len(self.peripheral)}
                assert self.pixel_writes==0 and not self.peripheral
                return {'guard_rejected':True,'steps':step,'peripheral_stores':0}
            if self.pc==BASE+self.symbols.get('delay_ticks',self.symbols['input_delay']):
                assert tuple(self.read(self.pc+i*4,4) for i in range(len(getattr(self,'delay_words',(0xe25cc001,0x1afffffd)))))==getattr(self,'delay_words',(0xe25cc001,0x1afffffd))
                assert self.r[12]==0x100000
                self.verify_frame()
                self.round+=1
                if self.round==len(self.values):
                    return {'guard_rejected':False,'sample_pairs_verified':self.round,
                            'steps':step,'peripheral_stores':len(self.peripheral),
                            'framebuffer_halfword_writes':self.pixel_writes}
                self.r[12]=1
            self.step()
        raise ValueError('Touch execution bound exceeded')

def main(experiment='touch', model_type=Touch):
    out=ROOT/f'analysis/{experiment}-probe'
    meta=json.loads((out/'build.json').read_text())
    data=(out/f'{experiment}-candidate.bin').read_bytes()
    assert hashlib.sha256(data).hexdigest()==meta['sha256']
    cases=[('buffer_1',BUFFERS[0],[],12,None),('buffer_2',BUFFERS[1],[],12,None),
           ('wrong_mode',BUFFERS[0],[],0,None),
           ('lcd_off',BUFFERS[0],[(0xfffec000,0x80,4)],12,None),
           ('wrong_width',BUFFERS[0],[(0xfffec004,479,4)],12,None),
           ('wrong_height',BUFFERS[0],[(0xfffec008,271,4)],12,None),
           ('data_only',BUFFERS[0],[(0xfffec000,0x200081,4)],12,None),
           ('unknown_buffer',0x11000000,[],12,None),
           ('wrong_dma_length',BUFFERS[0],[(0xfffee3cc,0,2)],12,None),
           ('wrong_format',BUFFERS[0],[(BUFFERS[0],0x3000,2)],12,None),
           ('adc_uninitialized',BUFFERS[0],[(0xfffe6014,0,2)],12,None),
           ('gpio1_not_output',BUFFERS[0],[(0xfffbb434,2,4)],12,None),
           ('gpio3_not_output',BUFFERS[0],[(0xfffbe434,0x8000,4)],12,None),
           ('timer_stuck',BUFFERS[0],[],12,'timer'),
           ('adc_stuck',BUFFERS[0],[],12,'adc')]
    results=[]
    for name,selected,changes,mode,fault in cases:
        model=model_type(data,meta['symbols'],selected,changes=[],mode=mode,fault=fault)
        for address,value,size in changes:model.put(address,value,size)
        result=model.run()
        assert result.get('guard_rejected',False)==(name not in ('buffer_1','buffer_2','timer_stuck','adc_stuck'))
        results.append({'case':name,**result})
    boot=(ROOT/'analysis/gcd/resident-boot-candidate.bin').read_bytes()
    loader=Handoff(boot,0x10800000,data)
    handoff=loader.run(max_steps=len(data)*5+1000)
    assert handoff['outcome']=='staged_entry_reached' and handoff['copied_bytes']==len(data)
    assert bytes(loader.memory[BASE+i] for i in range(len(data)))==data
    report={'payload_sha256':meta['sha256'],'cases':results,'handoff':handoff,
            'device_io':False,'scope':'Synthetic ARM instruction model, delayed readiness, bounded stuck ADC/timer; no hardware/cache emulation.'}
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
