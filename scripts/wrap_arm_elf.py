#!/usr/bin/env python3
"""Add an ELF32 envelope for offline objdump, never execute/flash this file.

Base address is a user-supplied hypothesis, not discovered by this wrapper.
All bytes are labelled .text for convenience, including embedded data.
"""
import argparse, pathlib, struct
p = argparse.ArgumentParser()
p.add_argument('input', type=pathlib.Path)
p.add_argument('output', type=pathlib.Path)
p.add_argument('--base', type=lambda s:int(s,0), required=True)
a = p.parse_args()
b = a.input.read_bytes()
names = b'\x00.text\x00.shstrtab\x00'
dataoff = 0x100
stroff = dataoff + len(b)
shoff = (stroff + len(names) + 3) & ~3
header = struct.pack('<16sHHIIIIIHHHHHH', b'\x7fELF\x01\x01\x01'+bytes(9),
                     1, 40, 1, 0, 0, shoff, 0x05000000, 52, 0, 0, 40, 3, 2)
out = bytearray(header)
out.extend(bytes(dataoff-len(out)))
out.extend(b)
out.extend(names)
out.extend(bytes(shoff-len(out)))
out.extend(bytes(40))
out.extend(struct.pack('<IIIIIIIIII', 1,1,6,a.base,dataoff,len(b),0,0,4,0))
out.extend(struct.pack('<IIIIIIIIII', 7,3,0,0,stroff,len(names),0,0,1,0))
a.output.write_bytes(out)
print(a.output, 'analysis-only ELF, assumed base', hex(a.base))
