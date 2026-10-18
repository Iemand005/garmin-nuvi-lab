"""Send an orientation/color image to the validated350 RAM framebuffer only."""
from pathlib import Path
import argparse,json,struct,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from spotify_bridge import Channel,ROOT
from player_ui import rgb565

def calibration():
    scale=3;im=Image.new('RGB',(320*scale,240*scale),'#101820');d=ImageDraw.Draw(im)
    def text(x,y,s,size=16,color='white'):
        f=ImageFont.truetype('/System/Library/Fonts/SFNS.ttf',size*scale)
        d.text((x*scale,y*scale),s,font=f,fill=color)
    text(12,8,'TOP LEFT',10);text(250,8,'TOP RIGHT',10)
    text(67,42,'NUVI 350',30)
    text(65,82,'MAC DISPLAY LINK',18)
    d.polygon([(160*scale,21*scale),(151*scale,33*scale),(169*scale,33*scale)],fill='white')
    for left,color,label in ((16,'#ff0000','R'),(90,'#00ff00','G'),(164,'#0000ff','B'),(238,'#ffffff','W')):
        d.rounded_rectangle((left*scale,122*scale,(left+66)*scale,173*scale),radius=5*scale,fill=color)
        text(left+26,179,label,15)
    text(12,218,'BOTTOM LEFT',10);text(232,218,'BOTTOM RIGHT',10)
    return im.resize((320,240),Image.Resampling.LANCZOS)

def encode(image,width,height,rotation,mirror=True):
    if image.size!=(320,240):raise ValueError('Need320x240logicalimage')
    if (width,height)==(240,320):
        # Physical photo5017 established horizontal reflection with rotation alone.
        # Pre-flip+CCW rotation equals a plain axis transpose for this panel.
        if mirror:image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        image=image.transpose(Image.Transpose.ROTATE_90 if rotation=='ccw' else Image.Transpose.ROTATE_270)
    elif (width,height)!=(320,240):raise ValueError('Unsupportedscanprofile')
    data=rgb565(image)
    if len(data)!=153600:raise ValueError('Badframesize')
    return data

def send(image,rotation,mirror=True):
    channel=Channel(ROOT/'analysis/nuvi350/usb/nuvi350-usb-host')
    try:
        info=channel.rpc('info');data=encode(image,info['width'],info['height'],rotation,mirror)
        started=time.monotonic()
        for index in range(2400):channel.rpc(f'chunk {index} {data[index*64:index*64+64].hex()}')
        result=dict(info=info,rotation=rotation,mirror_compensated=mirror,bytes=len(data),blocks=2400,all_blocks_acknowledged=True,seconds=round(time.monotonic()-started,3),device_storage_writes=False)
        (ROOT/'evidence/nuvi350/display-send.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    finally:channel.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--send',action='store_true');p.add_argument('--rotation',choices=('ccw','cw'),default='ccw');p.add_argument('--no-mirror',action='store_true');a=p.parse_args()
    image=calibration();image.save(ROOT/'analysis/nuvi350/display-calibration.png')
    if a.send:send(image,a.rotation,not a.no_mirror)
    else:print('Local preview generated; no device I/O')
if __name__=='__main__':main()
