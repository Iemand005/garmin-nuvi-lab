"""Extract the nested boot-stage candidate from our exact local nüvi 200 image.

This is analysis only. The output is not a deployed loader or a device readback.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
source = ROOT/'analysis/gcd/boot-candidate.bin'
data = source.read_bytes()
expected_source = hashlib.sha256(data).hexdigest()
offset, base = 0x29720, 0x10000000
branch, end, hw, version = struct.unpack_from('<4I', data, offset)
size = end + 6 - base
if branch != 0xea000002 or not 16 <= size <= len(data)-offset:
    raise SystemExit('Nested image header/bounds differ; inspect manually.')
image = data[offset:offset+size]
if not all(16 <= pointer-base <= size-2 for pointer in (end, hw, version)):
    raise SystemExit('Nested image pointers are out of bounds.')
hwid = struct.unpack_from('<H',image,hw-base)[0]
sw = struct.unpack_from('<H',image,version-base)[0]
if (hwid,sw,image[end-base:end-base+2]) != (660,500,b'\x5a\xa5'):
    raise SystemExit('Unexpected identity or footer.')
digest = hashlib.sha256(image).hexdigest()
if digest != '851c682a619bc0faf366159ff3ecbacb33243f5829b767106b03affb00b5f4cf':
    raise SystemExit('Nested image differs from reviewed bytes.')
output = ROOT/'analysis/gcd/resident-boot-candidate.bin'
output.write_bytes(image)
report = {'container':source.name,'container_sha256':expected_source,
          'container_raw_offset':hex(offset),'assumed_base':hex(base),
          'bytes':size,'sha256':digest,'hwid':hwid,'software_version':sw,
          'end_pointer':hex(end),'footer':image[-6:].hex(),
          'status':'embedded update image; not a readback of running device'}
(ROOT/'analysis/gcd/resident-boot-candidate.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
