"""Offline pixel-coordinate checks against photo-confirmed350 scan mapping."""
import struct,json
from pathlib import Path
from PIL import Image
from nuvi350_display import encode
from player_ui import rgb565
im=Image.new('RGB',(320,240),'black')
for xy,rgb in (((0,0),(255,0,0)),((319,0),(0,255,0)),((0,239),(0,0,255)),((319,239),(255,255,255))):im.putpixel(xy,rgb)
raw=encode(im,240,320,'ccw')
# Photo5017: uncorrected output reflected horizontally. Corrected scan is x'=y,y'=x.
for x,y,value in ((0,0,0xf800),(0,319,0x07e0),(239,0,0x001f),(239,319,0xffff)):
    assert struct.unpack_from('<H',raw,(y*240+x)*2)[0]==value
assert raw==rgb565(im.transpose(Image.Transpose.TRANSPOSE))
assert encode(im,320,240,'ccw')==rgb565(im)
assert len(raw)==153600 and encode(im,240,320,'ccw',False)!=raw
report=dict(photo_reference='IMG_5017.HEIC',portrait_mapping='scan_x=logical_y, scan_y=logical_x',four_color_corners_verified=True,landscape_unchanged=True,bytes=153600,device_io=False)
Path('evidence/nuvi350/encoding-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
