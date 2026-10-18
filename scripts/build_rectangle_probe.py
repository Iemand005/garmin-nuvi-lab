"""Assemble a LOCAL candidate and extract ELF .text without installing a linker.

Never installs a loader on any mounted volume. Rejects unresolved relocations.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import subprocess

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--experiment', choices=['rectangle','dashboard','touch','calibration','crosshair','buttons','usb','usb2','usb3','music','player','nuvi350-rectangle','nuvi350-marker','nuvi350-usb','nuvi350-touchlab','nuvi350-touchxy','nuvi350-touchxy2'], default='rectangle')
a=p.parse_args()
out=root/f'analysis/{a.experiment}-probe'
out.mkdir(parents=True,exist_ok=True)
obj=out/'probe.o'
subprocess.run(['xcrun','clang','-target','armv5-none-eabi','-c',
                str(root/f'experiments/{a.experiment}/probe.S'),'-o',str(obj)],check=True, cwd=root)
b=obj.read_bytes()
if b[:7]!=b'\x7fELF\x01\x01\x01':
    raise SystemExit('Unexpected object format')
shoff=struct.unpack_from('<I',b,32)[0]
entsize,count,strings=struct.unpack_from('<HHH',b,46)
sections=[struct.unpack_from('<10I',b,shoff+i*entsize) for i in range(count)]
stringsec=sections[strings]
names=b[stringsec[4]:stringsec[4]+stringsec[5]]
symbols={}
payload=None
for section in sections:
    name=names[section[0]:].split(b'\0',1)[0].decode()
    if section[1] in (4,9) and section[5]:
        raise SystemExit('Unresolved relocation section: '+name)
    if name=='.text':
        payload=b[section[4]:section[4]+section[5]]
    if section[1]==2:
        strings_section=sections[section[6]]
        table=b[strings_section[4]:strings_section[4]+strings_section[5]]
        for pos in range(section[4],section[4]+section[5],section[9]):
            n,value,size,info,other,index=struct.unpack_from('<IIIBBH',b,pos)
            symbol=table[n:].split(b'\0',1)[0].decode()
            if symbol:symbols[symbol]=value
if payload is None:raise SystemExit('No .text')
if struct.unpack_from('<I',payload,4)[0]!=0x10040000+symbols['footer']:
    raise SystemExit('Footer pointer mismatch')
candidate=out/f'{a.experiment}-candidate.bin'
candidate.write_bytes(payload)
listing=subprocess.check_output(['xcrun','llvm-objdump','-d','--triple=armv5-none-eabi',str(obj)],text=True)
(out/'disassembly.txt').write_text(listing)
report={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
        'base':'0x10040000','symbols':symbols,
        'status':'LOCAL CANDIDATE ONLY; not deployed by this script',
        'device_writes':False}
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
