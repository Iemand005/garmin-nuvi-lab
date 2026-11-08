#!/usr/bin/env python3
"""Build a guarded nüvi 200W (HWID 737 / software 4.00) rectangle candidate.

LOCAL CANDIDATE ONLY. This script never writes a mounted device or SD card. The
program runs from RAM at 0x10040000 after the stock SD loader handoff and parks;
a physical reset is required afterward. It only reads MMIO and saves/inverts/
restores 32x32 pixels inside the DMA-active framebuffer. No flash, no MMIO
writes, no filesystem calls.

Constant provenance: 4.00 GUPDATE.GCD on the tested unit, HWID 737. See
docs/nuvi200w-4.00.md. Requires the optional `keystone-engine` package.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
except ImportError as exc:
    raise SystemExit('install optional deps: python -m pip install capstone keystone-engine') from exc

ROOT = Path(__file__).resolve().parents[1]
STAGE = 0x10040000
HWID = 737
SOFTWARE = 400
FOOTER = 0xA55A
BUFFERS = (0x11F807C0, 0x11FC03E0)
DMA_BASE = 0xFFFEE3C0
DMA_LENGTH = 0x3FC1E
STRIDE = 480 * 2
PIXEL_HEADER = 32
RECT = 32
RECT_X = 224
RECT_Y = 120
ROW_SKIP = STRIDE - 2 * RECT
RECT_OFFSET = PIXEL_HEADER + RECT_Y * STRIDE + RECT_X * 2
COND = {'al': 0xE, 'eq': 0x0, 'ne': 0x1}


def arm_branch(address, target, cond='al'):
    delta = (target - (address + 8)) >> 2
    if not -(1 << 23) <= delta < (1 << 23):
        raise ValueError('branch out of range')
    return ((COND[cond] << 28) | 0x0A000000 | (delta & 0xFFFFFF)) & 0xFFFFFFFF


def arm_ldr_literal(address, rd, slot):
    disp = slot - (address + 8)
    if not -0xFFF <= disp <= 0xFFF:
        raise ValueError('literal out of range')
    if disp >= 0:
        return 0xE59F0000 | (rd << 12) | disp
    return 0xE51F0000 | (rd << 12) | (-disp)


class Program:
    def __init__(self):
        self.items = []

    def label(self, name):
        self.items.append(('label', name))

    def insn(self, text):
        self.items.append(('insn', text))

    def branch(self, target, cond='al'):
        self.items.append(('branch', cond, target))

    def load(self, rd, value):
        self.items.append(('load', rd, value))


def build():
    k = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    p = Program()
    p.label('entry')
    p.insn('cmp r12, #12')
    p.branch('park', 'ne')

    # Snapshot the DMA B1 start/end registers (halfword accesses).
    p.load(7, DMA_BASE)
    p.insn('ldrh r4, [r7, #8]')
    p.insn('ldrh r0, [r7, #10]')
    p.insn('orr r4, r4, r0, lsl #16')
    p.insn('ldrh r5, [r7, #12]')
    p.insn('ldrh r0, [r7, #14]')
    p.insn('orr r5, r5, r0, lsl #16')
    p.load(0, BUFFERS[0])
    p.insn('cmp r4, r0')
    p.branch('known', 'eq')
    p.load(0, BUFFERS[1])
    p.insn('cmp r4, r0')
    p.branch('park', 'ne')
    p.label('known')
    p.insn('sub r5, r5, r4')
    p.load(0, DMA_LENGTH)
    p.insn('cmp r5, r0')
    p.branch('park', 'ne')
    # Reject a source change while snapshotting.
    p.insn('ldrh r0, [r7, #8]')
    p.insn('ldrh r2, [r7, #10]')
    p.insn('orr r0, r0, r2, lsl #16')
    p.insn('cmp r0, r4')
    p.branch('park', 'ne')

    # r4 = framebuffer base. Save 32x32 pixels into payload scratch.
    p.load(0, RECT_OFFSET)
    p.insn('add r9, r4, r0')
    p.insn('mov r4, r9')
    p.load(8, 'scratch')
    p.insn('mov r6, #32')
    p.label('save_row')
    p.insn('mov r5, #32')
    p.label('save_pixel')
    p.insn('ldrh r0, [r4], #2')
    p.insn('strh r0, [r8], #2')
    p.insn('subs r5, r5, #1')
    p.branch('save_pixel', 'ne')
    p.insn('add r4, r4, #%d' % ROW_SKIP)
    p.insn('subs r6, r6, #1')
    p.branch('save_row', 'ne')

    # Invert the rectangle.
    p.insn('mov r4, r9')
    p.load(8, 'scratch')
    p.insn('mov r6, #32')
    p.load(2, 0xFFFF)
    p.label('invert_row')
    p.insn('mov r5, #32')
    p.label('invert_pixel')
    p.insn('ldrh r0, [r8], #2')
    p.insn('eor r0, r0, r2')
    p.insn('strh r0, [r4], #2')
    p.insn('subs r5, r5, #1')
    p.branch('invert_pixel', 'ne')
    p.insn('add r4, r4, #%d' % ROW_SKIP)
    p.insn('subs r6, r6, #1')
    p.branch('invert_row', 'ne')

    # Finite delay so the inverted square is visible if filmed.
    p.insn('mov r12, #0x01000000')
    p.label('delay')
    p.insn('subs r12, r12, #1')
    p.branch('delay', 'ne')

    # Restore the original pixels.
    p.insn('mov r4, r9')
    p.load(8, 'scratch')
    p.insn('mov r6, #32')
    p.label('restore_row')
    p.insn('mov r5, #32')
    p.label('restore_pixel')
    p.insn('ldrh r0, [r8], #2')
    p.insn('strh r0, [r4], #2')
    p.insn('subs r5, r5, #1')
    p.branch('restore_pixel', 'ne')
    p.insn('add r4, r4, #%d' % ROW_SKIP)
    p.insn('subs r6, r6, #1')
    p.branch('restore_row', 'ne')

    p.label('park')
    p.branch('park')

    # Layout: 16-byte header, code, identity/footer, literal pool, scratch.
    labels = {}
    offset = 16
    for item in p.items:
        if item[0] == 'label':
            labels[item[1]] = offset
        else:
            offset += 4
    code_end = offset
    hwid_off, version_off, footer_off = code_end, code_end + 2, code_end + 4
    literal_off = (code_end + 6 + 3) & ~3
    constants = []
    seen = set()
    for item in p.items:
        if item[0] == 'load':
            key = ('scratch',) if item[2] == 'scratch' else ('v', item[2])
            if key not in seen:
                seen.add(key)
                constants.append(key)
    scratch_off = literal_off + 4 * len(constants)
    pool_slot = {}
    values = {}
    for index, key in enumerate(constants):
        pool_slot[key] = STAGE + literal_off + 4 * index
        values[key] = STAGE + scratch_off if key[0] == 'scratch' else key[1]

    header = struct.pack(
        '<4I',
        arm_branch(0, 0x10),
        STAGE + footer_off,
        STAGE + hwid_off,
        STAGE + version_off,
    )
    code = bytearray()
    offset = 16
    for item in p.items:
        if item[0] == 'label':
            continue
        if item[0] == 'insn':
            encoding, count = k.asm(item[1])
            if count != 1 or len(encoding) != 4:
                raise SystemExit('instruction did not encode as one ARM word: ' + item[1])
            code.extend(encoding)
        elif item[0] == 'branch':
            code.extend(struct.pack('<I', arm_branch(STAGE + offset, STAGE + labels[item[2]], item[1])))
        else:
            key = ('scratch',) if item[2] == 'scratch' else ('v', item[2])
            code.extend(struct.pack('<I', arm_ldr_literal(STAGE + offset, item[1], pool_slot[key])))
        offset += 4
    identity = struct.pack('<3H', HWID, SOFTWARE, FOOTER) + b'\0\0'
    pool = b''.join(struct.pack('<I', values[key]) for key in constants)
    scratch = bytes(2048)
    payload = bytes(header) + bytes(code) + identity + pool + scratch
    if len(payload) != scratch_off + 2048:
        raise SystemExit('layout mismatch')
    if struct.unpack_from('<I', payload, 0)[0] != 0xEA000002:
        raise SystemExit('bad entry branch')
    footer_pointer = struct.unpack_from('<I', payload, 4)[0]
    if struct.unpack_from('<H', payload, footer_pointer - STAGE)[0] != FOOTER:
        raise SystemExit('footer pointer does not resolve')
    return payload, labels, {
        'base': STAGE, 'hwid': HWID, 'software_version': SOFTWARE,
        'buffers': [hex(b) for b in BUFFERS], 'dma_base': hex(DMA_BASE),
        'dma_length': hex(DMA_LENGTH), 'stride': STRIDE,
        'pixel_header': PIXEL_HEADER, 'rectangle': [RECT_X, RECT_Y, RECT, RECT],
        'scratch_offset': scratch_off, 'literal_offset': literal_off,
        'identity_offset': code_end, 'footer_offset': footer_off,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT / 'analysis' / 'nuvi200w-rectangle')
    a = ap.parse_args()
    payload, labels, info = build()
    a.out.mkdir(parents=True, exist_ok=True)
    candidate = a.out / 'nuvi200w-rectangle-candidate.bin'
    candidate.write_bytes(payload)

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    text = []
    for insn in md.disasm(payload[16:info['identity_offset']], STAGE + 16):
        text.append(f'{insn.address:08x}: {insn.bytes.hex():<10} {insn.mnemonic:<8} {insn.op_str}')
    (a.out / 'disassembly.txt').write_text('\n'.join(text) + '\n')

    sha = hashlib.sha256(payload).hexdigest()
    report = dict(info, bytes=len(payload), sha256=sha,
                  symbols={name: hex(value) for name, value in labels.items()},
                  status='LOCAL CANDIDATE ONLY; not deployed by this script',
                  device_writes=False)
    (a.out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
