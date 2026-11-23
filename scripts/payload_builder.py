#!/usr/bin/env python3
"""Shared assembler for nüvi SD-loader probe.S payloads.

LOCAL CANDIDATE ONLY. Uses Keystone to assemble ARM and emits a flat binary with
the 16-byte Garmin header/footer-pointer layout expected by the stock SD loader.
No device writes.

Dedicated model builders pass the expected HWID and device name so a 200W source
cannot silently be emitted as a 660 payload, or vice versa.
"""
import argparse, hashlib, json, struct
from pathlib import Path
try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
except ImportError as exc:
    raise SystemExit('install optional deps: python -m pip install capstone keystone-engine') from exc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = 0x10040000
FOOTER = 0xA55A


def assemble(asm_text: str, out_dir: Path, name: str, expected_hwid=None,
             device: str = 'unknown', default_stage: int = DEFAULT_STAGE):
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

    stage = int(equ.get('STAGE', default_stage))
    return build_with_pools(items, equ, ks, out_dir, name, stage, expected_hwid, device)


def build_with_pools(items, equ, ks, out_dir: Path, name: str, stage: int,
                     expected_hwid=None, device: str = 'unknown'):
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
    pc = stage
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
            elif op in ('.byte', '.ascii', '.asciz', '.string'):
                enc, _cnt = ks.asm(val, pc)
                raw = bytes(enc)
                stream.append((pc, 'raw_bytes', raw))
                pc += len(raw)
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
    cur = stage
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
        elif kind == 'raw_bytes':
            out.extend(val); cur += len(val)
        else:
            raise SystemExit(f'unhandled {kind} {val} at {pc_i:#x}')

    payload = bytes(out)
    # Our .S already has the header pointers as .word stage + (symbol - probe_start).
    if len(payload) < 16:
        raise SystemExit('payload too small')
    branch = struct.unpack_from('<I', payload, 0)[0]
    footer_ptr = struct.unpack_from('<I', payload, 4)[0]
    hwid_ptr = struct.unpack_from('<I', payload, 8)[0]
    version_ptr = struct.unpack_from('<I', payload, 12)[0]

    def read_hword(addr, what):
        off = addr - stage
        if off < 0 or off + 2 > len(payload):
            raise SystemExit(f'bad {what} pointer {addr:#x} outside payload')
        return struct.unpack_from('<H', payload, off)[0]

    if (branch >> 24) != 0xEA:
        raise SystemExit(f'bad header branch {branch:#x}')
    footer = read_hword(footer_ptr, 'footer')
    hwid = read_hword(hwid_ptr, 'hwid')
    version = read_hword(version_ptr, 'version')
    if footer != FOOTER:
        raise SystemExit(f'footer mismatch: {footer:#06x}, expected {FOOTER:#06x}')
    if expected_hwid is not None and hwid != expected_hwid:
        raise SystemExit(f'{device} builder expected HWID {expected_hwid}, source header reports {hwid}')
    return payload, labels, {'hwid': hwid, 'version': version, 'footer': footer,
                             'branch': branch, 'stage': stage}


def build_cli(expected_hwid: int, device: str, default_stage: int = DEFAULT_STAGE):
    ap = argparse.ArgumentParser(description=f'Build a {device} payload from probe.S')
    ap.add_argument('source', type=Path, help='probe.S file')
    ap.add_argument('--out', type=Path, required=True, help='output dir')
    ap.add_argument('--name', required=True, help='output base name')
    args = ap.parse_args()
    src = args.source.read_text()
    payload, labels, info = assemble(src, args.out, args.name, expected_hwid, device, default_stage)
    args.out.mkdir(parents=True, exist_ok=True)
    bin_path = args.out / f'{args.name}.bin'
    bin_path.write_bytes(payload)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    dis = []
    for insn in md.disasm(payload, info['stage']):
        dis.append(f'{insn.address:08x}: {insn.bytes.hex():<10} {insn.mnemonic:<8} {insn.op_str}')
    (args.out / f'{args.name}.disassembly.txt').write_text('\n'.join(dis) + '\n')
    report = {
        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
        'base': hex(info['stage']), 'symbols': {k: hex(v) for k,v in labels.items()},
        'device': device, 'expected_hwid': expected_hwid,
        'hwid': info['hwid'], 'version': info['version'], 'footer': hex(info['footer']),
        'source': str(args.source), 'status': 'LOCAL CANDIDATE ONLY; not deployed by this script',
        'device_writes': False,
    }
    (args.out / f'{args.name}.build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
