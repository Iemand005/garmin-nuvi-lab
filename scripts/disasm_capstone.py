#!/usr/bin/env python3
"""Portable offline ARM/Thumb disassembly via capstone (no device I/O).

Reads a raw image, disassembles an address range, and annotates PC-relative
literal loads. This is an analysis aid, not proof of the loaded image base or
of runtime behavior. capstone is an optional local dependency.
"""
import argparse
import struct
from pathlib import Path

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN
except ImportError as exc:
    raise SystemExit('capstone is required: python -m pip install capstone') from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('--base', type=lambda s: int(s, 0), required=True)
    p.add_argument('--start', type=lambda s: int(s, 0), default=0)
    p.add_argument('--end', type=lambda s: int(s, 0), default=None)
    p.add_argument('--thumb', action='store_true')
    p.add_argument('--output', type=Path)
    a = p.parse_args()

    image = a.image.read_bytes()
    end = len(image) if a.end is None else min(a.end, len(image))
    if not 0 <= a.start < end:
        raise SystemExit('Empty or invalid range')
    code = image[a.start:end]
    addr = a.base + a.start
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if a.thumb else CS_MODE_ARM)
    md.detail = True

    lines = []
    for insn in md.disasm(code, addr):
        line = f'{insn.address:08x}: {insn.bytes.hex():<10} {insn.mnemonic:<8} {insn.op_str}'
        # Annotate ARM LDR Rt,[pc,#imm] literal loads.
        if not a.thumb and insn.mnemonic == 'ldr' and '[pc,' in insn.op_str:
            for op in insn.operands:
                if op.type == 3:  # ARM_OP_MEM
                    target = op.mem.disp
                    off = target - a.base
                    if 0 <= off <= len(image) - 4:
                        value = struct.unpack_from('<I', image, off)[0]
                        line += f'    ; [0x{target:08x}] = 0x{value:08x}'
        lines.append(line)
    text = '\n'.join(lines) + '\n'
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
