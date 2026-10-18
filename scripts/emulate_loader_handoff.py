"""Bounded offline ARM interpretation of the extracted mode-12 handoff.

No device I/O, emulated peripherals, or executable output. Start AFTER hardware
initialization; stop BEFORE executing staged bytes or normal startup. This is
not a complete ARM emulator or proof of behavior on the physical unit.
"""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
BOOT = 0x10000000
DEST = 0x10040000
MASK = 0xffffffff

class Handoff:
    def __init__(self, image, source, payload, length=None, *, mode=12, copy_entry=0xb0, fallbacks=(0x130,), veneer=0x1e560):
        self.memory = {BOOT+i: v for i, v in enumerate(image)}
        self.memory.update({source+i: v for i, v in enumerate(payload)})
        self.reg = [0] * 16
        self.reg[8], self.reg[10], self.reg[11] = mode, len(payload) if length is None else length, source
        self.pc = BOOT + copy_entry
        self.copy_entry=copy_entry;self.fallbacks=fallbacks;self.veneer=veneer
        self.flags = dict(N=False, Z=False, C=False, V=False)
        self.copies = []
        self.cpsr_writes = []
        self.payload_length = len(payload)

    def read(self, address, size):
        return sum(self.memory[address+i] << (8*i) for i in range(size))

    def regread(self, index):
        return self.pc+8 if index == 15 else self.reg[index]

    def condition(self, code):
        n,z,c,v = (self.flags[k] for k in ('N','Z','C','V'))
        table = [z,not z,c,not c,n,not n,v,not v,c and not z,not c or z,n==v,n!=v,not z and n==v,z or n!=v,True,False]
        return table[code]

    def operand(self, word):
        if word & (1 << 25):
            value, rotate = word & 255, ((word >> 8) & 15)*2
            return ((value >> rotate) | (value << ((32-rotate) % 32))) & MASK
        if word & 0xff0:
            raise ValueError('Unsupported shifted operand')
        return self.regread(word & 15)

    def subtract_flags(self, a, b, result):
        self.flags.update(N=bool(result & 0x80000000), Z=result==0,
                          C=a>=b, V=bool((a^b) & (a^result) & 0x80000000))

    def run(self, max_steps=2000):
        for step in range(max_steps):
            if self.pc == DEST:
                return {'outcome':'staged_entry_reached', 'steps':step,
                        'copied_bytes':len(self.copies), 'entry_mode_r12':self.reg[12],
                        'cpsr_writes':self.cpsr_writes}
            if self.pc in tuple(BOOT+x for x in self.fallbacks):
                return {'outcome':'normal_startup_fallback', 'steps':step,
                        'copied_bytes':len(self.copies)}
            if not (BOOT+self.copy_entry <= self.pc < BOOT+max(self.fallbacks) or BOOT+self.veneer <= self.pc < BOOT+self.veneer+0x20):
                raise ValueError(f'Execution escaped allowed code ranges: {self.pc:#x}')
            word = self.read(self.pc,4)
            next_pc = self.pc+4
            if not self.condition(word >> 28):
                self.pc = next_pc
                continue
            if word == 0xe121f004:  # MSR CPSR_c,r4; record only, no peripherals.
                self.cpsr_writes.append(self.reg[4])
            elif (word >> 25) & 7 == 5:  # B / BL
                delta = word & 0xffffff
                if delta & 0x800000:
                    delta -= 1 << 24
                if word & (1 << 24):
                    self.reg[14] = next_pc
                next_pc = (self.pc+8+delta*4) & MASK
            elif word == 0xe1d000b0:  # LDRH r0,[r0]
                self.reg[0] = self.read(self.reg[0],2)
            elif (word >> 26) & 3 == 1:  # immediate LDR / STR(B), pre/post index
                if word & (1 << 25):
                    raise ValueError('Unsupported register memory offset')
                rn,rd = (word>>16)&15,(word>>12)&15
                address = self.regread(rn)
                delta = word & 0xfff
                indexed = (address + (delta if word & (1<<23) else -delta)) & MASK
                pre = bool(word & (1<<24))
                effective = indexed if pre else address
                size = 1 if word & (1<<22) else 4
                if word & (1<<20):
                    self.reg[rd] = self.read(effective,size)
                else:
                    if size != 1 or not DEST <= effective < DEST+self.payload_length:
                        raise ValueError('Write escaped staging sandbox')
                    self.memory[effective] = self.regread(rd) & 255
                    self.copies.append(effective)
                if not pre or word & (1<<21):
                    self.reg[rn] = indexed
            elif (word >> 26) & 3 == 0:  # required data processing subset
                op,rn,rd = (word>>21)&15,(word>>16)&15,(word>>12)&15
                a,b = self.regread(rn),self.operand(word)
                if op in (2,10):
                    result = (a-b)&MASK
                elif op == 4:
                    result = (a+b)&MASK
                elif op == 13:
                    result = b
                else:
                    raise ValueError(f'Unsupported data opcode {op}')
                if op == 10 or word & (1<<20):
                    if op not in (2,10):
                        raise ValueError('Unsupported flags operation')
                    self.subtract_flags(a,b,result)
                if op != 10:
                    if rd == 15:
                        next_pc = result
                    else:
                        self.reg[rd] = result
            else:
                raise ValueError(f'Unsupported instruction {word:#x} at {self.pc:#x}')
            self.pc = next_pc
        raise ValueError('Instruction limit reached')

def main():
    image = (ROOT/'analysis/gcd/resident-boot-candidate.bin').read_bytes()
    expected_hash = '851c682a619bc0faf366159ff3ecbacb33243f5829b767106b03affb00b5f4cf'
    if hashlib.sha256(image).hexdigest() != expected_hash:
        raise SystemExit('Unexpected input image; inspect before interpreting.')
    # Synthetic NON-CODE bytes: observe control transfer, never execute payload.
    payload = bytearray(b'NOT!'+struct.pack('<I',DEST+16)+b'XXXXXXXX'+b'\x5a\xa5'+bytes(6))
    cases = [('valid_marker',0x11000000,payload,None,'staged_entry_reached'),
             ('bad_marker',0x11000000,payload[:16]+bytes(8),None,'normal_startup_fallback'),
             ('zero_length',0x11000000,payload,0,'normal_startup_fallback'),
             ('source_below_staging',DEST-0x100,payload,None,'normal_startup_fallback'),
             ('source_exceeds_limit',0x12000000,payload,None,'normal_startup_fallback')]
    results=[]
    for name,source,data,length,expected in cases:
        machine=Handoff(image,source,data,length)
        result=machine.run()
        result['case']=name
        if result['outcome'] != expected:
            raise SystemExit(f'Unexpected emulation result: {result}')
        if name=='valid_marker' and bytes(machine.memory[DEST+i] for i in range(len(data))) != data:
            raise SystemExit('Staged copy differs from source')
        results.append(result)
    report={'input_sha256':expected_hash,'scope':'mode-12 subset only, hardware preamble skipped, staged payload never executed',
            'results':results,'device_io':False}
    (ROOT/'analysis/gcd/handoff-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
