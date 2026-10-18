"""Check crosshair clipping/restoration and contact transitions in actual ARM code."""
from audit_calibration_probe import Calibration
from audit_touch_probe import main, BASE

class Crosshair(Calibration):
    step_budget=3000000

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.values=[(0,17),(50,500),(500,50),(500,500),(0,17),
                     (459,528),(462,539),(486,528),(0,17),(470,338),
                     (272,386),(0,17),(0,17),(51,51),(51,51),
                     (1023,1023),(0,17),(0,17)]
        self.good=self.bad=self.visible=0
        self.x=self.y=0

    def write(self,address,value,size):
        start=BASE+self.symbols['scratch']
        if start<=address and address+size<=start+10:
            assert size==2 and address%2==0
            self.put(address,value,size)
            return
        super().write(address,value,size)

    def decorate_frame(self,expected):
        a,b=self.values[self.round]
        if min(a,b)>50:
            self.bad=0
            self.good=min(2,self.good+1)
            color=0xfd20
            if self.good==2:
                self.x=max(6,min(313,(113*b)//256-59))
                self.y=max(6,min(233,307-(94*a)//256))
                self.visible=1
                color=0x16d6
        else:
            self.good=0
            self.bad=min(2,self.bad+1)
            color=0xfd20
            if self.bad==2:
                self.visible=0
                color=0x2945
        def pixel(x,y,color):
            offset=y*640+x*2
            expected[offset:offset+2]=color.to_bytes(2,'little')
        if self.visible:
            for delta in range(-6,7):
                pixel(self.x+delta,self.y,0xffff)
                pixel(self.x,self.y+delta,0xffff)
        for y in range(48,56):
            for x in range(260,296):pixel(x,y,color)
        # Heartbeat is drawn last, including when a marker overlaps it.
        for y in range(18,30):
            for x in range(284,296):pixel(x,y,0x16d6 if self.round%2==0 else 0x2945)
        state=BASE+self.symbols['scratch']
        actual=[self.read(state+2*i,2) for i in range(5)]
        assert actual==[self.good,self.bad,self.visible,self.x,self.y], 'Contact state mismatch'

if __name__=='__main__':main('crosshair',Crosshair)
