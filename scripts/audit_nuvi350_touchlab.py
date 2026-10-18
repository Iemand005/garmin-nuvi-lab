"""Offline audit of read-only350 touch controller snapshots. No device I/O."""
import struct
from audit_nuvi350_usb import USB350, main
REGS=((0xfffbe42c,0xfffbe430,0xfffbe434),
      (0xfffb0c24,0xfffb0c28,0xfffb0c2c),
      (0xfffb0c30,0xfffb0c14,0xfffb0c00))
class Snapshot350(USB350):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.snapshot_values={a:(0xa5a50000+i*0x1111)&0xffffffff for i,a in enumerate(sum(REGS,()))}
        self.snapshot_reads=[]
    def read(self,address,size):
        if address in self.snapshot_values:
            assert size==4
            self.snapshot_reads.append(address)
            return self.snapshot_values[address]
        return super().read(address,size)

def checks(data,meta,model_type):
    results=[]
    for width,height in ((320,240),(240,320)):
        for buffer in model_type.buffers:
            m=model_type(data,meta['symbols'],buffer,changes=[],mode=2,width=width,height=height)
            m.boot();pixel_writes=m.pixel_writes
            for index,registers in enumerate(REGS):
                expected=struct.pack('<HHIII',0x3554,index,*(m.snapshot_values[a] for a in registers))
                for length in (0,1,7,15,16,17,65535):
                    m.snapshot_reads=[]
                    packets,cmd=m.request(0xc0,0x59,0,index,length)
                    assert packets==[expected[:length]]
                    assert m.snapshot_reads==list(registers)
                # Simulate changing PENIRQ without any stores by the candidate.
                if index==0:
                    m.snapshot_values[registers[0]]^=1<<14
                    packet,_=m.request(0xc0,0x59,0,0,16)
                    assert struct.unpack('<HHIII',packet[0])[2]==m.snapshot_values[registers[0]]
            for bm,value,index in ((0xc0,1,0),(0xc0,0,3),(0xc0,0,65535),(0x40,0,0),(0xc1,0,0)):
                m.snapshot_reads=[]
                packets,cmd=m.request(bm,0x59,value,index,16)
                assert not packets and cmd==0x20 and not m.snapshot_reads
            assert not m.peripheral and m.pixel_writes==pixel_writes
            results.append(dict(width=width,height=height,buffer=hex(buffer),pages=3,lengths=7,invalid_inputs=5,penirq_change=True,no_touch_writes=True))
    return results

if __name__=='__main__':main('nuvi350-touchlab',Snapshot350,checks)
