"""Save an offline Thumb/ARM window with PC-relative literal values annotated."""
import argparse
from pathlib import Path
import re
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('start',type=lambda s:int(s,0))
p.add_argument('end',type=lambda s:int(s,0))
p.add_argument('output',type=Path)
p.add_argument('--resident',action='store_true')
p.add_argument('--arm',action='store_true')
p.add_argument('--image-dir',type=Path,default=ROOT/'analysis/gcd')
a=p.parse_args()
base=0x10000000 if a.resident else 0x10040000
stem='resident-boot' if a.resident else 'fw-all'
raw=(a.image_dir/f'{stem}-candidate.bin').read_bytes()
elf=a.image_dir/f'{stem}-analysis.elf'
listing=subprocess.check_output(['xcrun','llvm-objdump','-d',
    '--triple='+('armv5-none-eabi' if a.arm else 'thumbv5-none-eabi'),
    f'--start-address={a.start}',f'--stop-address={a.end}',str(elf)],text=True)
lines=[]
for line in listing.splitlines():
    if re.search(r'\bldr\s+r\d+, \[pc,',line):
        m=re.search(r'@ (0x[0-9a-f]+)',line)
        if m:
            offset=int(m[1],16)-base
            if 0<=offset<=len(raw)-4:
                line+=f' ; literal={struct.unpack_from("<I",raw,offset)[0]:#010x}'
    lines.append(line)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
