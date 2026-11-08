"""Interpret the nüvi 200W candidate's ARM subset against synthetic DMA state.

No device I/O. Unsupported instructions, out-of-model reads, and writes outside
the selected rectangle or candidate scratch area raise immediately. The known
two-instruction delay loop is accelerated; hardware and timing are not emulated.
The model deliberately omits LCD-control provenance because the 200W candidate
gates only on the DMA source buffer and transfer length.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x10040000
BUFFERS = (0x11F807C0, 0x11FC03E0)
DMA_LENGTH = 0x3FC1E
STRIDE = 480 * 2
FRAME_BYTES = 480 * 272 * 2
RECT_X, RECT_Y, RECT = 224, 120, 32
RECT_SKIP = 32 + RECT_Y * STRIDE + RECT_X * 2
RECT_START = RECT_Y * STRIDE + RECT_X * 2
MASK = 0xFFFFFFFF


class Model:
    buffers = BUFFERS

    def __init__(self, payload, symbols, scratch_offset, selected, changes=None, mode=12):
        self.payload, self.symbols = payload, symbols
        self.selected = selected
        self.mem = {BASE + i: v for i, v in enumerate(payload)}
        self.r = [0] * 16
        self.r[12] = mode
        self.pc = BASE
        self.n = self.z = self.c = self.v = False
        self.writes = []
        self.observed_inversion = False
        self.delay_accelerated = False
        for start in self.buffers:
            self.put(start, 0x4000, 2)
            for i in range(32, 32 + FRAME_BYTES):
                self.mem[start + i] = (i * 37 + (start & 255)) & 255
        self.before = {start: bytes(self.mem[start + i] for i in range(32, 32 + FRAME_BYTES))
                       for start in self.buffers}
        for address, value, size in [
            (0xFFFEE3C8, selected & 65535, 2),
            (0xFFFEE3CA, selected >> 16, 2),
            (0xFFFEE3CC, (selected + DMA_LENGTH) & 65535, 2),
            (0xFFFEE3CE, (selected + DMA_LENGTH) >> 16, 2),
        ]:
            self.put(address, value, size)
        for address, value, size in changes or []:
            self.put(address, value, size)
        self.allowed_pixels = {selected + RECT_SKIP + row * STRIDE + col * 2 + i
                               for row in range(RECT) for col in range(RECT) for i in range(2)}
        self.allowed_scratch = set(range(BASE + scratch_offset, BASE + scratch_offset + 2048))

    def put(self, address, value, size):
        for i in range(size):
            self.mem[address + i] = (value >> (i * 8)) & 255

    def read(self, address, size):
        return sum(self.mem[address + i] << (i * 8) for i in range(size))

    def write(self, address, value, size):
        if size != 2 or any(a not in self.allowed_pixels | self.allowed_scratch
                            for a in range(address, address + size)):
            raise ValueError(f'Forbidden write at {address:#x}')
        self.writes.append((self.pc, address, value & 65535))
        self.put(address, value, size)

    def rr(self, index):
        return self.pc + 8 if index == 15 else self.r[index]

    def cond(self, code):
        return [self.z, not self.z, self.c, not self.c, self.n, not self.n, self.v, not self.v,
                self.c and not self.z, not self.c or self.z, self.n == self.v, self.n != self.v,
                not self.z and self.n == self.v, self.z or self.n != self.v, True, False][code]

    def operand(self, w):
        if w & (1 << 25):
            value, rotate = w & 255, ((w >> 8) & 15) * 2
            return ((value >> rotate) | (value << ((32 - rotate) % 32))) & MASK
        value = self.rr(w & 15)
        if w & (1 << 4):
            raise ValueError('Unsupported register shift')
        kind, shift = (w >> 5) & 3, (w >> 7) & 31
        if kind == 0:
            return (value << shift) & MASK
        if kind == 1:
            return value >> (shift or 32)
        raise ValueError('Unsupported shifter')

    def verify_frame(self, inverted):
        for row in range(RECT):
            for col in range(RECT):
                offset = RECT_START + row * STRIDE + col * 2
                expected = int.from_bytes(self.before[self.selected][offset:offset + 2], 'little')
                if inverted:
                    expected ^= 65535
                actual = self.read(self.selected + 32 + offset, 2)
                if actual != expected:
                    raise ValueError('Rectangle contents differ')

    def run(self):
        for step in range(50000):
            if self.pc == BASE + self.symbols['park']:
                for start in self.buffers:
                    after = bytes(self.mem[start + i] for i in range(32, 32 + FRAME_BYTES))
                    if after != self.before[start]:
                        raise ValueError('Frame not fully restored')
                sites = sorted({hex(pc - BASE) for pc, _, _ in self.writes})
                return {'steps_interpreted': step, 'halfword_writes': len(self.writes),
                        'write_sites_raw': sites, 'inversion_observed': self.observed_inversion,
                        'both_frames_restored': True, 'delay_accelerated': self.delay_accelerated,
                        'no_mmio_writes': True}
            if self.pc == BASE + self.symbols['delay']:
                if (self.read(self.pc, 4) != 0xE25CC001
                        or self.read(self.pc + 4, 4) != 0x1AFFFFFD
                        or self.r[12] != 0x01000000):
                    raise ValueError('Delay loop differs from reviewed form')
                self.verify_frame(inverted=True)
                self.observed_inversion = True
                self.delay_accelerated = True
                self.r[12] = 1
            self.step()
        raise ValueError('Execution bound exceeded')

    def step(self):
        if not (self.pc == BASE or BASE + self.symbols['entry'] <= self.pc < BASE + self.symbols['park']):
            raise ValueError(f'Execution escaped code: {self.pc:#x}')
        w = self.read(self.pc, 4)
        nxt = self.pc + 4
        if not self.cond(w >> 28):
            self.pc = nxt
            return
        if (w >> 25) & 7 == 5:
            if w & (1 << 24):
                raise ValueError('Unexpected subroutine call')
            delta = w & 0xFFFFFF
            if delta & 0x800000:
                delta -= 1 << 24
            nxt = (self.pc + 8 + delta * 4) & MASK
        elif w & 0x0E000090 == 0x00000090 and w & 0x60 == 0x20:
            if not w & (1 << 22):
                raise ValueError('Unsupported halfword offset')
            rn, rd = (w >> 16) & 15, (w >> 12) & 15
            delta = ((w >> 4) & 0xF0) | (w & 15)
            address = self.rr(rn)
            indexed = (address + (delta if w & (1 << 23) else -delta)) & MASK
            pre = bool(w & (1 << 24))
            effective = indexed if pre else address
            if w & (1 << 20):
                self.r[rd] = self.read(effective, 2)
            else:
                self.write(effective, self.rr(rd), 2)
            if not pre or w & (1 << 21):
                self.r[rn] = indexed
        elif (w >> 26) & 3 == 1:
            if w & (1 << 25) or not w & (1 << 24) or w & (1 << 21) or not w & (1 << 20) or w & (1 << 22):
                raise ValueError('Unexpected word memory instruction')
            rn, rd = (w >> 16) & 15, (w >> 12) & 15
            delta = w & 0xFFF
            self.r[rd] = self.read(self.rr(rn) + (delta if w & (1 << 23) else -delta), 4)
        elif (w >> 26) & 3 == 0:
            op, rn, rd = (w >> 21) & 15, (w >> 16) & 15, (w >> 12) & 15
            a, b = self.rr(rn), self.operand(w)
            if op in (0, 8):
                result = a & b
            elif op == 1:
                result = a ^ b
            elif op in (2, 10):
                result = (a - b) & MASK
            elif op == 4:
                result = (a + b) & MASK
            elif op == 12:
                result = a | b
            elif op == 13:
                result = b
            else:
                raise ValueError(f'Unsupported data opcode: {op}')
            if op in (8, 10) or w & (1 << 20):
                self.n, self.z = bool(result & 0x80000000), result == 0
                if op in (2, 10):
                    self.c = a >= b
                    self.v = bool((a ^ b) & (a ^ result) & 0x80000000)
                elif op not in (0, 8):
                    raise ValueError('Unsupported arithmetic flags')
            if op not in (8, 10):
                if rd == 15:
                    raise ValueError('Unexpected computed branch')
                self.r[rd] = result
        else:
            raise ValueError(f'Unsupported instruction: {w:#x}')
        self.pc = nxt


def main():
    out = ROOT / 'analysis' / 'nuvi200w-rectangle'
    meta = json.loads((out / 'build.json').read_text())
    symbols = {name: int(value, 16) if isinstance(value, str) else value
               for name, value in meta['symbols'].items()}
    data = (out / 'nuvi200w-rectangle-candidate.bin').read_bytes()
    if hashlib.sha256(data).hexdigest() != meta['sha256']:
        raise SystemExit('Build hash mismatch')
    cases = [
        ('buffer_1', BUFFERS[0], [], 12, True),
        ('buffer_2', BUFFERS[1], [], 12, True),
        ('wrong_mode', BUFFERS[0], [], 0, False),
        ('unknown_buffer', 0x11000000, [], 12, False),
        ('wrong_dma_length', BUFFERS[0], [(0xFFFEE3CC, 0, 2)], 12, False),
    ]
    results = []
    for name, selected, changes, mode, success in cases:
        result = Model(data, symbols, meta['scratch_offset'], selected, changes, mode).run()
        if result['inversion_observed'] != success:
            raise SystemExit('Unexpected result: ' + name)
        if not success and result['halfword_writes']:
            raise SystemExit('Rejected case wrote memory: ' + name)
        result['case'] = name
        results.append(result)
    report = {'payload_sha256': meta['sha256'],
              'scope': 'synthetic ARM subset for nüvi 200W 480x272; finite delay accelerated; no hardware emulation',
              'cases': results, 'device_io': False,
              'deployment_status': 'pending suitable FAT SD card and stock reset verification'}
    (out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
