"""Audit calibration readouts against independent formatting and raster copies."""
from audit_touch_probe import Touch, SEQ0, SEQ1, main

class Calibration(Touch):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.values += [(0x123,0x256),(0x378,0x09a),(0x0bc,0x0de)]

    def verify_frame(self):
        expected=bytearray(self.expected)
        def paint(x,y,width,height,color):
            for row in range(y,y+height):
                for col in range(x,x+width):
                    expected[row*640+col*2:row*640+col*2+2]=color.to_bytes(2,'little')
        for y,value in zip((112,160),self.values[self.round]):
            paint(32,y,256,12,0x2945)
            paint(32,y,value>>2,12,0x16d6)
        paint(284,18,12,12,0x16d6 if self.round%2==0 else 0x2945)
        table=self.payload[self.symbols['hex_glyphs']:self.symbols['hex_glyphs']+4096]
        for y,value in zip((88,136),self.values[self.round]):
            for digit,ch in enumerate(f'{value:03X}'):
                tile=table[int(ch,16)*256:(int(ch,16)+1)*256]
                for row in range(16):
                    start=(y+row)*640+(210+8*digit)*2
                    expected[start:start+16]=tile[row*16:row*16+16]
        self.decorate_frame(expected)
        actual=bytes(self.mem[self.selected+32+i] for i in range(153600))
        assert actual==expected, 'Raw hex/bar frame differs'
        sequence=SEQ0+[(0xfffe6020,0x8000)]+SEQ1+[(0xfffe6020,0x9000)]+SEQ0
        assert self.peripheral==[(a,v,2 if a==0xfffe6020 else 4) for a,v in sequence]*(self.round+1)
        self.verify_other()

    def decorate_frame(self, expected):
        pass

if __name__=='__main__':
    main('calibration', Calibration)
