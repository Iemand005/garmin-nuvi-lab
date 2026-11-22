#!/usr/bin/env python3
"""Assemble a nüvi 200W (HWID 737) probe.S into a raw ldr.bin payload.

LOCAL CANDIDATE ONLY. Uses Keystone to assemble ARM and emits a flat binary with
the 16-byte Garmin header/footer-pointer layout expected by the stock SD loader.
No device writes.
"""
import argparse, hashlib, json, struct
from pathlib import Path
try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
except ImportError as exc:
    raise SystemExit('install optional deps: python -m pip install capstone keystone-engine') from exc

ROOT = Path(__file__).resolve().parents[1]
STAGE = 0x10040000
FOOTER = 0xA55A


def parse_source(src: str):
    lines = []
    labels = {}
    for raw in src.splitlines():
        line = raw.split('@')[0].split('/*')[0].rstrip()
        if not line.strip() or line.lstrip().startswith('*') or line.lstrip().startswith('*/'):
            continue
        # handle /* ... */ single-line comments crudely
        if '/*' in line and '*/' in line:
            line = line[:line.index('/*')] + line[line.index('*/')+2:]
        line = line.strip()
        if not line:
            continue
        if line.endswith(':'):
            labels.setdefault(len(lines), line[:-1])
            # mark label at next instruction index
            lines.append(('label', line[:-1]))
        else:
            # split label: instr on same line
            if ':' in line and not line.startswith('.'):
                maybe, rest = line.split(':', 1)
                if rest.strip() and ' ' not in maybe and maybe.isidentifier():
                    lines.append(('label', maybe))
                    line = rest.strip()
            lines.append(('line', line))
    return lines


def assemble(asm_text: str, out_dir: Path, name: str):
    ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    # Keystone can assemble many directives, but .equ/.hword/.word layout and our
    # custom header are easier to handle by a tiny two-pass assembler for this subset.
    items = []
    equ = {}
    for raw in asm_text.splitlines():
        line = raw.split('@', 1)[0].strip()
        if not line:
            continue
        if line.startswith('/*') or line.startswith('*') or line.startswith('*/'):
            continue
        if '/*' in line and '*/' in line:
            line = (line[:line.index('/*')] + line[line.index('*/')+2:]).strip()
        if not line:
            continue
        if line.lower().startswith('.equ'):
            # .equ NAME, VALUE
            rest = line[4:].strip()
            k, v = [x.strip() for x in rest.split(',', 1)]
            equ[k] = int(v, 0)
            continue
        if line.endswith(':') and not line.startswith('.'):
            items.append(('label', line[:-1]))
            continue
        if ':' in line and line.split(':',1)[0].isidentifier() and not line.startswith('.'):
            lbl, rest = line.split(':', 1)
            items.append(('label', lbl.strip()))
            line = rest.strip()
            if not line:
                continue
        items.append(('op', line))

    def eval_expr(expr, pc=None, labels=None):
        e = expr.strip()
        # replace labels/equ names
        # handle STAGE + (footer - probe_start)
        def repl(tok):
            if tok in equ: return str(equ[tok])
            if labels and tok in labels: return str(labels[tok])
            return tok
        # tokenize simple identifiers
        import re
        e2 = re.sub(r'\b[A-Za-z_\.][A-Za-z0-9_\.]*\b', lambda m: repl(m.group(0)), e)
        e2 = e2.replace('#', '')
        return eval(e2, {'__builtins__': {}}, {})

    # pass 1: sizes
    labels = {}
    pc = STAGE
    for kind, val in items:
        if kind == 'label':
            labels[val] = pc
        else:
            op = val.split(None, 1)[0].lower()
            if op in ('.syntax', '.arch', '.arm', '.section', '.global'):
                pass
            elif op == '.balign':
                align = eval_expr(val.split(None,1)[1], pc, labels)
                pad = (-pc) % align
                pc += pad
            elif op == '.word':
                args = [a.strip() for a in val.split(None,1)[1].split(',')]
                pc += 4 * len(args)
            elif op == '.hword':
                args = [a.strip() for a in val.split(None,1)[1].split(',')]
                pc += 2 * len(args)
            elif op == '.space':
                pc += eval_expr(val.split(None,1)[1], pc, labels)
            elif op == '.ltorg':
                # rough: count literal loads after? easier: force emit now in pass2 by collecting
                # We'll handle ltorg by emitting deferred literals.
                # mark placeholder; pass2 will determine.
                items.append  # no-op
                pass
            else:
                pc += 4

    # Better approach: manual encoding via Keystone per-instruction, manage ltorg/pools.
    # Build with explicit pool emission.
    return build_with_pools(items, equ, ks, out_dir, name)


def build_with_pools(items, equ, ks, out_dir: Path, name: str):
    # Collect instructions and directives in order; handle .ltorg by placing pending literals.
    # We'll do a simple two-pass with fixed literal pool slots.
    import re

    def is_insn(op):
        return op not in ('.syntax','.arch','.arm','.section','.global','.balign','.word','.hword','.space','.ltorg')

    # Pass A: determine layout with estimated ltorg size? Simpler: require explicit ltorg and
    # compute exact pool by scanning ldr= pseudo-instructions that keystone turns into literals.
    # Keystone in raw mode doesn't auto-literal-pool. So we expand ldr rx, =value ourselves.

    # Expand pseudo ldr rd, =expr into movw/movt or literal load.
    expanded = []
    for kind, val in items:
        if kind == 'label':
            expanded.append((kind, val))
            continue
        op = val.split(None, 1)[0].lower()
        if op == 'ldr' and '=' in val:
            # ldr rN, =expr
            m = re.match(r'ldr\s+(r\d+|lr|sp|pc)\s*,\s*=(.+)', val, re.I)
            if not m:
                expanded.append((kind, val)); continue
            rd, expr = m.group(1), m.group(2).strip()
            expanded.append(('literal', (rd.lower(), expr)))
        else:
            expanded.append((kind, val))

    # pass 1: assign addresses, literals get 4 bytes insn + 4 bytes pool entry placed at .ltorg
    labels = {}
    pc = STAGE
    lit_pool = []  # literals pending for next ltorg
    lit_slots = {} # id -> slot address
    deferred_lits = [] # list of (pc_of_insn, rd, expr, pool_index_placeholder)
    # We need to assign pool slots at ltorg. Do two passes.
    # Pass1: compute PC counting literal insns as 4, and at ltorg add 4*pending.
    pending = []
    ltorg_sizes = []  # (index_in_stream, count)
    stream = []  # (pc_or_none, kind, val)
    for kind, val in expanded:
        if kind == 'label':
            labels[val] = pc
            stream.append((pc, kind, val))
        elif kind == 'literal':
            pending.append(val)
            stream.append((pc, 'literal_insn', val))
            pc += 4
        else:
            op = val.split(None, 1)[0].lower()
            if op in ('.syntax','.arch','.arm','.section','.global'):
                stream.append((pc, kind, val))
            elif op == '.balign':
                align = int(val.split(None,1)[1], 0)
                pad = (-pc) % align
                if pad:
                    stream.append((pc, 'pad', pad))
                    pc += pad
                stream.append((pc, kind, val))
            elif op == '.word':
                args = [a.strip() for a in val.split(None,1)[1].split(',')]
                stream.append((pc, 'word_args', args))
                pc += 4 * len(args)
            elif op == '.hword':
                args = [a.strip() for a in val.split(None,1)[1].split(',')]
                stream.append((pc, 'hword_args', args))
                pc += 2 * len(args)
            elif op == '.space':
                n = eval_expr(val.split(None,1)[1], pc, labels)
                stream.append((pc, 'space_n', n))
                pc += n
            elif op == '.ltorg':
                # emit pending literals
                if pending:
                    stream.append((pc, 'ltorg', list(pending)))
                    pc += 4 * len(pending)
                    pending = []
                else:
                    stream.append((pc, 'ltorg', []))
            else:
                stream.append((pc, 'insn', val))
                pc += 4
    if pending:
        # implicit ltorg at end
        stream.append((pc, 'ltorg', list(pending)))
        pc += 4 * len(pending)
        pending = []

    # pass 1b: fix label addresses after ltorg insertion? labels were recorded at encounter time - ok.
    # but labels after ltorg got shifted? No, we incremented pc in order. Need to recompute labels.
    labels = {}
    for pc_i, kind, val in stream:
        if kind == 'label':
            labels[val] = pc_i

    def eval_expr(expr, pc_cur=0):
        e = expr.strip()
        # replace known names
        def repl(m):
            tok = m.group(0)
            if tok.lower() in ('r0','r1','r2','r3','r4','r5','r6','r7','r8','r9','r10','r11','r12','r13','r14','r15','sp','lr','pc'):
                return tok
            if tok in equ: return str(equ[tok])
            if tok in labels: return str(labels[tok])
            return tok
        e2 = re.sub(r'\b[A-Za-z_\.][A-Za-z0-9_\.]*\b', repl, e)
        e2 = e2.replace('#', '')
        return int(eval(e2, {'__builtins__': {}}, {}))

    # pass 2: emit bytes
    out = bytearray()
    cur = STAGE
    # build literal slot map: for each ltorg, assign addresses
    ltorg_iter = iter([s for s in stream if s[1] == 'ltorg'])
    # precompute literal slot addresses per ltorg occurrence
    ltorg_slots = {}
    for pc_i, kind, val in stream:
        if kind == 'ltorg':
            for j, lit in enumerate(val):
                ltorg_slots[(pc_i, j)] = pc_i + 4*j
    # map each literal_insn to its ltorg slot in order
    lit_queue = []  # (ltorg_pc, index)
    for pc_i, kind, val in stream:
        if kind == 'ltorg':
            for j in range(len(val)):
                pass
    # assign literal_insn -> slot
    ltorgs = [(pc_i, val) for pc_i, kind, val in stream if kind == 'ltorg']
    lit_insns = [(pc_i, val) for pc_i, kind, val in stream if kind == 'literal_insn']
    if sum(len(v) for _,v in ltorgs) != len(lit_insns):
        raise SystemExit(f'literal/ltorg mismatch {len(lit_insns)} vs {sum(len(v) for _,v in ltorgs)}')
    slot_for = {}
    li = 0
    for lt_pc, lits in ltorgs:
        for j, lit in enumerate(lits):
            slot_for[lit_insns[li][0]] = (lt_pc + 4*j, lit)
            li += 1

    for pc_i, kind, val in stream:
        if cur != pc_i:
            # pad if needed
            if pc_i < cur:
                raise SystemExit(f'layout went backwards at {pc_i:#x} < {cur:#x}')
            out.extend(b'\x00' * (pc_i - cur))
            cur = pc_i
        if kind in ('label',):
            continue
        if kind == 'op':
            op0 = val.split(None,1)[0].lower() if isinstance(val, str) else ''
            if op0 in ('.syntax','.arch','.arm','.section','.global','.balign'):
                continue
        if kind == 'pad':
            out.extend(b'\x00' * val); cur += val
        elif kind == 'literal_insn':
            rd, expr = val
            slot_addr, _ = slot_for[pc_i]
            # LDR rd, [pc, #offset]
            rn = 15
            rd_n = ['r0','r1','r2','r3','r4','r5','r6','r7','r8','r9','r10','r11','r12','r13','r14','r15'].index(rd) if rd.startswith('r') else {'sp':13,'lr':14,'pc':15}[rd]
            off = slot_addr - (pc_i + 8)
            if off < 0:
                # LDR rd, [pc, #-off]
                enc = 0xE51F0000 | (rd_n << 12) | (-off & 0xFFF)
            else:
                enc = 0xE59F0000 | (rd_n << 12) | (off & 0xFFF)
            out.extend(struct.pack('<I', enc)); cur += 4
        elif kind == 'ltorg':
            for j, (rd, expr) in enumerate(val):
                v = eval_expr(expr, pc_i + 4*j) & 0xFFFFFFFF
                out.extend(struct.pack('<I', v)); cur += 4
        elif kind == 'insn':
            # let keystone assemble, substituting equ/label immediates
            ins = val
            # Replace = not expected here. Replace label refs in branches etc. Keystone handles symbols poorly; substitute.
            def repl(m):
                tok = m.group(0)
                if tok in equ: return str(equ[tok])
                if tok in labels:
                    # for branches keystone wants target; keep as number? easier to replace with #label for non-branch? No.
                    return tok
                return tok
            # For branch instructions, resolve target
            op = ins.split()[0].lower()
            if op in ('b','bl','beq','bne','bhs','blo','bhi','bls','bgt','ble','bge','blt','bcs','bcc'):
                target = ins.split()[-1]
                if target in labels:
                    # encode branch manually
                    cond_map = {'b':0xE,'bl':0xE,'beq':0,'bne':1,'bhs':2,'blo':3,'bhi':8,'bls':9,'bgt':0xC,'ble':0xD,'bge':0xA,'blt':0xB,'bcs':2,'bcc':3}
                    cond = cond_map[op]
                    link = 1 if op == 'bl' else 0
                    delta = (labels[target] - (pc_i + 8)) >> 2
                    enc = (cond<<28)|(0xA<<24)|(link<<24)|(delta & 0xFFFFFF)
                    out.extend(struct.pack('<I', enc)); cur += 4
                    continue
            # substitute equ/labels in immediates
            def sub_imm(m):
                tok=m.group(0)
                if tok in equ: return str(equ[tok])
                if tok in labels: return str(labels[tok])
                return tok
            ins2 = re.sub(r'\b[A-Za-z_\.][A-Za-z0-9_\.]*\b', sub_imm, ins)
            try:
                enc, cnt = ks.asm(ins2, pc_i)
            except Exception as e:
                raise SystemExit(f'asm failed at {pc_i:#x}: {ins} / {ins2}: {e}')
            if cnt != 1:
                raise SystemExit(f'expected 1 insn at {pc_i:#x}: {ins}')
            out.extend(bytes(enc)); cur += 4
        elif kind == 'op':
            if isinstance(val, list):
                # pre-parsed args from pass1: .word/.hword stored as (pc, kind, args)
                raise SystemExit(f'unhandled pre-parsed op at {pc_i:#x}: {val}')
            sval = val.strip()
            opn = sval.split(None,1)[0].lower()
            if opn == '.word':
                for a in sval.split(None,1)[1].split(','):
                    out.extend(struct.pack('<I', eval_expr(a.strip(), pc_i) & 0xFFFFFFFF)); cur += 4
            elif opn == '.hword':
                for a in sval.split(None,1)[1].split(','):
                    out.extend(struct.pack('<H', eval_expr(a.strip(), pc_i) & 0xFFFF)); cur += 2
            elif opn == '.space':
                n = eval_expr(sval.split(None,1)[1], pc_i)
                out.extend(b'\x00'*n); cur += n
            else:
                raise SystemExit(f'unhandled op {val} at {pc_i:#x}')
        elif kind == 'word_args':
            for a in val:
                out.extend(struct.pack('<I', eval_expr(a, pc_i) & 0xFFFFFFFF)); cur += 4
        elif kind == 'hword_args':
            for a in val:
                out.extend(struct.pack('<H', eval_expr(a, pc_i) & 0xFFFF)); cur += 2
        elif kind == 'space_n':
            out.extend(b'\x00'*val); cur += val
        else:
            raise SystemExit(f'unhandled {kind} {val} at {pc_i:#x}')

    payload = bytes(out)
    # Patch header pointers? Our .S already has them as .word STAGE + (footer-probe_start).
    # With labels resolved, those were emitted. Verify footer.
    if len(payload) < 16:
        raise SystemExit('payload too small')
    entry = struct.unpack_from('<I', payload, 0)[0]
    footer_ptr = struct.unpack_from('<I', payload, 4)[0]
    if footer_ptr < STAGE or footer_ptr - STAGE + 2 > len(payload):
        raise SystemExit('bad footer ptr')
    if struct.unpack_from('<H', payload, footer_ptr - STAGE)[0] != FOOTER:
        raise SystemExit('footer mismatch')
    return payload, labels


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path, help='probe.S file')
    ap.add_argument('--out', type=Path, required=True, help='output dir')
    ap.add_argument('--name', required=True, help='output base name')
    args = ap.parse_args()
    src = args.source.read_text()
    payload, labels = assemble(src, args.out, args.name)
    args.out.mkdir(parents=True, exist_ok=True)
    bin_path = args.out / f'{args.name}.bin'
    bin_path.write_bytes(payload)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    dis = []
    for insn in md.disasm(payload, STAGE):
        dis.append(f'{insn.address:08x}: {insn.bytes.hex():<10} {insn.mnemonic:<8} {insn.op_str}')
    (args.out / f'{args.name}.disassembly.txt').write_text('\n'.join(dis) + '\n')
    report = {
        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
        'base': hex(STAGE), 'symbols': {k: hex(v) for k,v in labels.items()},
        'source': str(args.source), 'status': 'LOCAL CANDIDATE ONLY; not deployed by this script',
        'device_writes': False,
    }
    (args.out / f'{args.name}.build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
