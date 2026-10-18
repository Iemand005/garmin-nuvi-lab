"""Offline native rawXY audit; synthetic SPI, not electrical/timing emulation."""
import struct
from audit_nuvi350_usb import main,BASE
from audit_nuvi350_touchlab import Snapshot350,checks as snapshot_checks

class TouchXY350(Snapshot350):
    final_command=0x99
    def __init__(self,*args,raw=(101,202),pen=True,fault=None,release=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.snapshot_values.update({0xfffbe42c:0x04ae if pen else 0x44ae,0xfffbe430:6,0xfffbe434:0xeeb9,
            0xfffb0c24:11,0xfffb0c28:0x8000,0xfffb0c2c:28,0xfffb0c30:2,0xfffb0c14:1,0xfffb0c00:16})
        self.raw=raw;self.fault=fault;self.release=release;self.cs=False;self.tx=None;self.pending=False;self.transfer=-1;self.polls=0;self.spi_rx=0
        self.spi_trace=[]
    def read(self,address,size):
        if address==0xfffb0c30 and self.pending:
            assert size==4
            self.polls+=1
            if self.fault==self.transfer or self.polls<3:return 0
            self.pending=False;self.snapshot_values[0xfffb0c2c]&=~3
            if self.transfer%3:
                group=self.transfer//3
                val=(7,self.raw[0],9,self.raw[1])[group]
                self.spi_rx=(val>>1) if self.transfer%3==1 else (val&1)<<7
                self.snapshot_values[address]=3
            else:self.snapshot_values[address]=2
        if address==0xfffb0c38:
            assert size==4
            self.snapshot_values[0xfffb0c30]&=~1
            return self.spi_rx
        return super().read(address,size)
    def step(self):
        w=super().read(self.pc,4)
        if self.cond(w>>28) and (w>>26)&3==0 and (w>>21)&15==15:
            assert not w&(1<<20) and (w>>12)&15!=15
            self.r[(w>>12)&15]=(~self.operand(w))&0xffffffff
            self.pc+=4;return
        super().step()
    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if address in (state+96,state+98):
            assert size==2;self.put(address,value,size);return
        if address in (0xfffbe4b0,0xfffbe4f0):
            assert size==4 and value==2
            if address==0xfffbe4b0:
                assert not self.cs
                self.cs=True;self.transfer=-1;self.snapshot_values[0xfffbe430]&=~2
            else:
                assert self.cs
                self.cs=False;self.snapshot_values[0xfffbe430]|=2
                if self.release:self.snapshot_values[0xfffbe42c]|=1<<14
            self.peripheral.append((address,value,size));return
        if address==0xfffb0c34:
            assert size==4 and self.cs and not self.pending
            self.tx=value;self.snapshot_values[0xfffb0c30]&=~2
            self.peripheral.append((address,value,size));return
        if address==0xfffb0c2c:
            assert size==4 and self.cs and not self.pending
            self.transfer+=1
            command=self.transfer%3==0
            assert value==(0x3e if command else 0x1d)
            assert self.tx==((self.final_command if self.transfer==9 else (0xd9 if self.transfer<6 else 0x99)) if command else 0)
            self.spi_trace.append((self.transfer,self.tx,value));self.pending=True;self.polls=0
            self.snapshot_values[address]=value
            self.peripheral.append((address,value,size));return
        super().write(address,value,size)

def sample(m):
    packets,cmd=m.request(0xc0,0x5a,0,0,16)
    assert len(packets)==1 and len(packets[0])==16
    fields=struct.unpack('<8H',packets[0]);assert fields[:2]==(0x3558,1)
    assert not m.cs
    if fields[2]!=4:assert m.snapshot_values[0xfffbe430]&2
    return fields

def checks(data,meta,model_type):
    snapshots=snapshot_checks(data,meta,model_type)
    cases=[]
    def model(**kw):
        m=model_type(data,meta['symbols'],model_type.buffers[0],changes=[],mode=2,**kw);m.boot();return m
    for raw in ((0,0),(101,202),(255,255),(0,255),(255,0)):
        m=model(raw=raw);fields=sample(m)
        assert fields[2:6]==(3,*raw,0) and fields[6]==2
        assert len(m.spi_trace)==12 and len(m.peripheral)==26
        assert sample(m)[2:6]==(3,*raw,0),'repeat sampler failed'
        cases.append(dict(case='valid',raw=raw,transfers=12,repeated=True))
    m=model(pen=False);fields=sample(m)
    assert fields[2]==0 and not m.peripheral
    cases.append(dict(case='pen_up',touch_writes=0))
    for address,value in ((0xfffbe434,0xaeb9),(0xfffbe434,0xeebb),(0xfffbe430,4),
            (0xfffb0c24,0),(0xfffb0c24,0x2b),(0xfffb0c28,0),(0xfffb0c28,0x8400),
            (0xfffb0c14,0),(0xfffb0c2c,1),(0xfffb0c30,0),(0xfffb0c30,3)):
        m=model();m.snapshot_values[address]=value
        assert sample(m)[2]==4 and not m.peripheral
        cases.append(dict(case='guard',address=hex(address),value=value,touch_writes=0))
    for transfer in range(12):
        m=model(fault=transfer);fields=sample(m)
        assert fields[2]&~16==9 and fields[5]==transfer+1
        assert len(m.spi_trace)==transfer+1 and not m.cs
        assert sample(m)[2]==4,'timed out hardware did not fail closed on retry'
        cases.append(dict(case='timeout',transfer=transfer,cleanup=True,retry_rejected=True))
    m=model(release=True);fields=sample(m)
    assert fields[2]==17 and fields[7]&(1<<14)
    cases.append(dict(case='released_during_sample',valid=False))
    for raw in ((256,0),(0,511)):
        m=model(raw=raw);fields=sample(m);assert fields[2]==33
        cases.append(dict(case='out_of_range',raw=raw,valid=False))
    for bm,value,index,length in ((0xc0,1,0,16),(0xc0,0,1,16),(0xc0,0,0,0),(0xc0,0,0,15),
            (0xc0,0,0,17),(0xc0,0,0,65535),(0x40,0,0,16),(0xc1,0,0,16)):
        m=model();packets,cmd=m.request(bm,0x5a,value,index,length)
        assert not packets and cmd==0x20 and not m.peripheral
        cases.append(dict(case='invalid_request',bm=bm,value=value,index=index,length=length,touch_writes=0))
    return dict(read_only_snapshots=snapshots,raw_xy=cases,no_actions=True)

if __name__=='__main__':main('nuvi350-touchxy',TouchXY350,checks)
