"""Verify stock OTG one-bit replay and live readbacks in compiled ARM candidate."""
import json
from audit_usb_probe import USB, protocol_checks
from audit_touch_probe import main,ROOT,BASE,BUFFERS

class USB2(USB):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.otg={4:0x30000,8:0xc0000000,12:0x10000}
        self.otg_writes=[]

    def read(self,address,size):
        if address in (0xfffb0404,0xfffb0408,0xfffb040c):
            assert size==4
            return self.otg[address-0xfffb0400]
        return super().read(address,size)

    def write(self,address,value,size):
        state=BASE+self.symbols['scratch']
        if state+64<=address and address+size<=state+68:
            assert size==2 and address%2==0
            self.put(address,value,size)
            return
        if address==0xfffb040c:
            assert size==4 and value==(self.otg[12]|0x40000)
            self.otg_writes.append(value)
            self.otg[12]=value
            return
        super().write(address,value,size)

    def decorate_frame(self,expected):
        super().decorate_frame(expected)
        state=BASE+self.symbols['scratch']
        values=(self.regs.get(0x18,0),self.regs.get(0x20,0),
                self.read(state+66,2),self.read(state+64,2),self.otg[12]>>16)
        table=self.payload[self.symbols['register_glyphs']:self.symbols['register_glyphs']+4096]
        for y,value in zip((62,78,94,110,126),values):
            for digit,ch in enumerate(f'{value:04X}'):
                tile=table[int(ch,16)*256:(int(ch,16)+1)*256]
                for row in range(16):
                    for col in range(8):
                        x,yy=60+digit*8+col,y+row
                        if self.visible and ((yy==self.y and abs(x-self.x)<=6) or (x==self.x and abs(yy-self.y)<=6)):continue
                        offset=yy*640+x*2
                        expected[offset:offset+2]=tile[row*16+col*2:row*16+col*2+2]
        assert self.otg_writes==[0x50000], 'Unexpected OTG writes'

if __name__=='__main__':
    main('usb2',USB2)
    out=ROOT/'analysis/usb2-probe'
    meta=json.loads((out/'build.json').read_text())
    data=(out/'usb2-candidate.bin').read_bytes()
    report=json.loads((out/'audit.json').read_text())
    report['usb_protocol']=protocol_checks(data,meta,USB2)
    for offset,value in ((4,0),(8,0)):
        model=USB2(data,meta['symbols'],BUFFERS[0],changes=[],mode=12)
        model.otg[offset]=value
        model.call('usb_init')
        assert not model.usb_writes and not model.otg_writes
    report['usb_protocol']['otg_guards_rejected']=2
    report['usb_protocol']['otg_write']='Only CTRL read-modify-write OR0x40000, all other bits preserved'
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print('USB2 protocol and OTG guard checks passed.')
