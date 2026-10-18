"""Artwork-led player: watchOS-inspired glass controls with Spotify accents."""
from functools import lru_cache
import math,struct
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance
S=3
FG='#ffffff';GREEN='#1ed760'
BUTTON_CENTERS=((1,62),(2,160),(3,258))
BUTTON_REGIONS=((18,144,105,192),(116,144,203,192),(214,144,301,192))
@lru_cache(maxsize=32)
def font(n,bold=False):
    f=ImageFont.truetype('/System/Library/Fonts/SFNS.ttf',round(n*S))
    f.set_variation_by_axes([100,max(17,min(96,n)),400,600 if bold else 400]);return f

def box(v):return tuple(round(x*S) for x in v)
def smooth_rect(draw,rect,r,fill,outline=None):
    x0,y0,x1,y1=rect;r=min(r,(x1-x0)/2,(y1-y0)/2);points=[]
    for cx,cy,start in ((x1-r,y0+r,-90),(x1-r,y1-r,0),(x0+r,y1-r,90),(x0+r,y0+r,180)):
        for i in range(19):
            a=math.radians(start+i*5);c,s=math.cos(a),math.sin(a)
            points.append(box((cx+r*math.copysign(abs(c)**.5,c),cy+r*math.copysign(abs(s)**.5,s))))
    draw.polygon(points,fill=fill)
    if outline:draw.line(points+[points[0]],fill=outline,width=S,joint='curve')

@lru_cache(maxsize=8)
def ambient(pixels):
    tint=Image.frombytes('RGB',(40,30),pixels).filter(ImageFilter.GaussianBlur(4))
    tint=ImageEnhance.Color(tint).enhance(1.25).resize((320*S,240*S),Image.Resampling.BICUBIC)
    base=Image.new('RGB',tint.size);d=ImageDraw.Draw(base)
    for y in range(240*S):
        t=y/(240*S-1)
        c=tuple(round(a*(1-t)+b*t) for a,b in zip((3,18,58),(27,76,91)))
        d.line((0,y,320*S,y),fill=c)
    # Keep white labels legible even on a very bright cover.
    tint=ImageEnhance.Brightness(tint).enhance(.6)
    return Image.blend(base,tint,.42)

def render(track,art=None,active=0):
    if active not in (0,1,2,3):raise ValueError('Invalid active button')
    if art is None:
        source=Image.new('RGB',(88*S,88*S),'#24475a');cd=ImageDraw.Draw(source)
        cd.line(box((37,56,37,29,56,25,56,51)),fill='#afcad8',width=3*S)
        cd.ellipse(box((26,51,38,60)),fill='#afcad8');cd.ellipse(box((45,46,57,55)),fill='#afcad8')
    else:source=art.convert('RGB')
    small=ImageOps.fit(source,(40,30),method=Image.Resampling.BILINEAR)
    im=ambient(small.tobytes()).copy();d=ImageDraw.Draw(im)
    def text(x,y,s,n=12,fill=FG,bold=False):d.text((round(x*S),round(y*S)),s,font=font(n,bold),fill=fill)
    def fit(s,width,n,bold=False):
        s=' '.join(str(s).split())
        if d.textlength(s,font=font(n,bold))<=width*S:return s
        while s and d.textlength(s+'…',font=font(n,bold))>width*S:s=s[:-1]
        return s+'…'
    # Small Spotify signature, leaving the cover and song as the visual focus.
    d.ellipse(box((16,14,29,27)),fill=GREEN)
    for y,w in ((18,9),(21,8),(24,6)):
        d.arc(box((22.5-w/2,y-1,22.5+w/2,y+3)),195,345,fill='#13363e',width=2)
    text(35,15,'Spotify',10,fill='#d8e9ec',bold=True)
    cover=ImageOps.fit(source,(96*S,96*S),method=Image.Resampling.LANCZOS)
    mask=Image.new('L',cover.size,0);smooth_rect(ImageDraw.Draw(mask),(0,0,96,96),12,255)
    # Soft shadow and continuous cover corners echo the reference without a card container.
    shadow=Image.new('RGBA',im.size);sd=ImageDraw.Draw(shadow)
    smooth_rect(sd,(18,41,114,137),12,(0,0,0,110))
    shadow=shadow.filter(ImageFilter.GaussianBlur(4*S))
    im=Image.alpha_composite(im.convert('RGBA'),shadow).convert('RGB')
    im.paste(cover,(18*S,38*S),mask);d=ImageDraw.Draw(im)
    title=' '.join(str(track.get('title','Open Spotify')).split()) or 'No track selected'
    # CarPlay-like landscape hierarchy: cover left, readable metadata right.
    lines=[];line=''
    for word in title.split():
        candidate=(line+' '+word).strip()
        if line and d.textlength(candidate,font=font(17,True))>170*S:
            lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    # One optical left edge; vertically center the complete metadata block to the cover.
    titles=[fit(lines[0],170,17,True)]
    if len(lines)>1:titles.append(fit(' '.join(lines[1:]),170,17,True))
    artist=fit(track.get('artist',''),170,13)
    album=fit(track.get('album',''),170,10)
    rows=[(line,17,True,FG,21) for line in titles]
    if artist:rows.append((artist,13,False,'#c0d5de',23))
    if album:rows.append((album,10,False,'#9bb9c8',19))
    height=sum(row[4] for row in rows)-rows[-1][4]+rows[-1][1]
    y=38+(96-height)/2
    for label,n,bold,color,advance in rows:
        f=font(n,bold);bounds=d.textbbox((0,0),label,font=f)
        d.text((132*S-bounds[0],round(y*S)-bounds[1]),label,font=f,fill=color)
        y+=advance
    duration=max(0,float(track.get('duration',0) or 0));position=max(0,float(track.get('position',0) or 0))
    fraction=min(1,position/duration) if duration else 0
    # Existing broad touch regions stay in place beneath the circular controls.
    for button,cx in BUTTON_CENTERS:
        down=active==button;radius=(24 if button==2 else 21)-(2 if down else 0);cy=169+(1 if down else 0)
        overlay=Image.new('RGBA',im.size);od=ImageDraw.Draw(overlay)
        rect=(cx-radius,cy-radius,cx+radius,cy+radius)
        od.ellipse(box(rect),fill=(220,246,255,65 if down else 32),outline=(225,247,255,160 if down else 100),width=S)
        # A brighter top rim gives restrained depth rather than a solid button tile.
        od.arc(box(rect),205,330,fill=(255,255,255,175 if down else 130),width=S)
        im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB');d=ImageDraw.Draw(im)
        scale=.9 if down else 1
        def p(x,y):return box((cx+x*scale,cy+y*scale))
        ink='#ffffff' if not down else '#c0f8d4'
        if button==2:
            if track.get('state')=='playing':
                for x in (-7,3):d.rounded_rectangle((*p(x,-9),*p(x+4,9)),radius=1.2*S,fill=ink)
            else:d.polygon([p(-5,-10),p(-5,10),p(10,0)],fill=ink)
        elif button==1:
            d.rounded_rectangle((*p(-10,-8),*p(-7,8)),radius=S/2,fill=ink)
            d.polygon([p(9,-9),p(-6,0),p(9,9)],fill=ink)
        else:
            d.rounded_rectangle((*p(7,-8),*p(10,8)),radius=S/2,fill=ink)
            d.polygon([p(-9,-9),p(6,0),p(-9,9)],fill=ink)
    d.rounded_rectangle(box((24,207,296,209)),radius=S,fill='#627c89')
    if fraction:
        end=24+272*fraction
        d.rounded_rectangle(box((24,207,end,209)),radius=S,fill='#dcebf0')
        d.ellipse(box((end-2,206,end+2,210)),fill=GREEN)
    def stamp(t):return f'{int(t)//60}:{int(t)%60:02}'
    text(24,217,stamp(position),10,fill='#afc8d3')
    end=stamp(duration);text(296-d.textlength(end,font=font(10))/S,217,end,10,fill='#afc8d3')
    return im.resize((320,240),Image.Resampling.LANCZOS)
def rgb565(im):
    return b''.join(struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3)) for r,g,b in im.convert('RGB').getdata())
