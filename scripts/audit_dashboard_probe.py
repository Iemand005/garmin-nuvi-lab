"""Bounded offline checks of dashboard instructions, memory writes and handoff.

Uses the rectangle interpreter; delay loops are checked then accelerated.
No device I/O, hardware emulation, timing guarantee, or touch support.
"""
from pathlib import Path
import hashlib
import json
from audit_rectangle_probe import Model, BASE, BUFFERS
from emulate_loader_handoff import Handoff

ROOT = Path(__file__).resolve().parents[1]

class Dashboard(Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected = self.payload[self.symbols['screen']:self.symbols['screen']+153600]
        assert len(self.expected) == 153600
        self.prefixes = {b: bytes(self.mem.get(b+i, 0) for i in range(32)) for b in BUFFERS}
        self.stores = {}

    def write(self, address, value, size):
        pixel = self.selected + 32 <= address and address + size <= self.selected + 153632
        scratch = BASE+self.symbols['scratch'] <= address and address+size <= BASE+self.symbols['scratch']+2048
        if size != 2 or address % 2 or not (pixel or scratch):
            raise ValueError(f'Forbidden dashboard store {address:#x}')
        site = self.pc - BASE
        self.stores[site] = self.stores.get(site, 0) + 1
        self.put(address, value, size)

    def frame(self, start):
        return bytes(self.mem[start+i] for i in range(32, 153632))

    def verify(self, inverted):
        expected = bytearray(self.expected)
        if inverted:
            for row in range(104, 136):
                for col in range(144*2, 176*2):
                    expected[row*640+col] ^= 255
        assert self.frame(self.selected) == expected, 'Unexpected rendered pixels'
        for b in BUFFERS:
            assert bytes(self.mem.get(b+i, 0) for i in range(32)) == self.prefixes[b], 'Prefix changed'
            if b != self.selected:
                assert self.frame(b) == self.before[b], 'Unselected buffer changed'

    def run(self):
        on = off = 0
        for step in range(500000):
            if self.pc == BASE+self.symbols['park']:
                assert not self.stores, 'Guard failure wrote memory'
                return {'guard_rejected': True, 'halfword_writes': 0, 'steps': step}
            if self.pc in (BASE+self.symbols['delay'], BASE+self.symbols['delay_off']):
                assert self.read(self.pc,4) == 0xe25cc001
                assert self.read(self.pc+4,4) == 0x1afffffd
                assert self.r[12] == 0x01000000
                inverted = self.pc == BASE+self.symbols['delay']
                self.verify(inverted)
                on += int(inverted)
                off += int(not inverted)
                if off == 3:
                    assert on == 3
                    assert sum(self.stores.values()) == 76800 + 1024 + 3*2048
                    assert len(self.stores) == 4
                    return {'guard_rejected': False, 'complete_blinks': off,
                            'halfword_writes': sum(self.stores.values()),
                            'write_sites_raw': {hex(k): v for k,v in self.stores.items()},
                            'steps': step, 'other_buffer_and_prefixes_preserved': True}
                self.r[12] = 1
            self.step()
        raise ValueError('Execution bound exceeded')

def main():
    out = ROOT/'analysis/dashboard-probe'
    meta = json.loads((out/'build.json').read_text())
    data = (out/'dashboard-candidate.bin').read_bytes()
    assert hashlib.sha256(data).hexdigest() == meta['sha256']
    cases = [('buffer_1', BUFFERS[0], [], 12, False),
             ('buffer_2', BUFFERS[1], [], 12, False),
             ('wrong_mode', BUFFERS[0], [], 0, True),
             ('disabled_lcd', BUFFERS[0], [(0xfffec000,0x80,4)], 12, True),
             ('wrong_width', BUFFERS[0], [(0xfffec004,479,4)], 12, True),
             ('wrong_height', BUFFERS[0], [(0xfffec008,271,4)], 12, True),
             ('data_only_mode', BUFFERS[0], [(0xfffec000,0x200081,4)], 12, True),
             ('unknown_buffer', 0x11000000, [], 12, True),
             ('wrong_dma_length', BUFFERS[0], [(0xfffee3cc,0,2)], 12, True),
             ('wrong_palette_format', BUFFERS[0], [(BUFFERS[0],0x3000,2)], 12, True)]
    results = []
    for name, buffer, changes, mode, reject in cases:
        result = Dashboard(data, meta['symbols'], buffer, changes, mode).run()
        assert result['guard_rejected'] == reject
        results.append({'case': name, **result})
    boot = (ROOT/'analysis/gcd/resident-boot-candidate.bin').read_bytes()
    handoff = Handoff(boot, 0x10800000, data)
    outcome = handoff.run(max_steps=len(data)*5+1000)
    assert outcome['outcome'] == 'staged_entry_reached'
    assert outcome['copied_bytes'] == len(data) and outcome['entry_mode_r12'] == 12
    assert bytes(handoff.memory[BASE+i] for i in range(len(data))) == data
    report = {'payload_sha256': meta['sha256'], 'bytes': len(data),
              'scope': 'Synthetic ARM subset; three blinks per supported buffer. Delays accelerated. No hardware emulation.',
              'cases': results, 'handoff': outcome, 'device_io': False}
    (out/'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
