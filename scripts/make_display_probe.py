#!/usr/bin/env python3
"""Create baseline JPEGs locally for a future, separately approved viewer test."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parents[1] / 'artifacts' / 'display-probe'
out.mkdir(parents=True, exist_ok=True)
for i, accent in enumerate(('#13d9b0', '#ffb347'), 1):
    im = Image.new('RGB', (320, 240), '#101b2b')
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 14)
    small = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 10)
    title = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 22)
    d.rectangle((0, 0, 319, 239), outline='white', width=1)
    d.rectangle((8, 8, 311, 231), outline=accent, width=1)
    d.text((20, 20), 'GARMIN / LAB', font=title, fill=accent)
    d.text((20, 53), 'CUSTOM PIXELS   %02d'%i, font=font, fill='white')
    d.text((20, 78), '320 x 240 / baseline JPEG', font=small, fill='#b9cadb')
    colors = ['#ffffff','#ffff00','#00ffff','#00ff00','#ff00ff','#ff0000','#0000ff']
    for j,c in enumerate(colors): d.rectangle((20+j*40,105,59+j*40,139),fill=c)
    for j in range(280):
        g = round(j*255/279)
        d.line((20+j,149,20+j,165),fill=(g,g,g))
    d.text((20, 178), 'Image only / no firmware change',font=small,fill='white')
    d.text((20, 201), 'EDGE + COLOR + SCALE TEST',font=small,fill=accent)
    target = out / ('LAB_%02d.JPG'%i)
    im.save(target, 'JPEG', quality=92, progressive=False, subsampling=0)
    with Image.open(target) as check:
        assert check.size == (320,240) and check.mode == 'RGB'
        assert not check.info.get('progressive')
    print(target, target.stat().st_size)
