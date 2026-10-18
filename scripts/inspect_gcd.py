#!/usr/bin/env python3
"""Read-only GCD TLV inventory; extracts selected concatenated records locally.

Uses LE uint16 ID/length records after the eight-byte header. Does not
validate Garmin checkpoint checksums or produce flashable firmware.
"""
import argparse, collections, hashlib, json, pathlib, re, struct

p = argparse.ArgumentParser()
p.add_argument('input', type=pathlib.Path)
p.add_argument('output', type=pathlib.Path)
a = p.parse_args()
b = a.input.read_bytes()
if b[:8] != b'GARMINd\x00':
    raise SystemExit('Unexpected header: refusing this input')
a.output.mkdir(parents=True, exist_ok=True)
off, records, payloads = 8, [], collections.defaultdict(bytearray)
while off < len(b):
    if off + 4 > len(b):
        raise SystemExit('Truncated record header at ' + hex(off))
    ident, size = struct.unpack_from('<HH', b, off)
    end = off + 4 + size
    if end > len(b):
        raise SystemExit('Truncated payload at ' + hex(off))
    content = b[off+4:end]
    row = dict(offset=off, id=hex(ident), size=size)
    if ident in (1, 3, 6, 7, 0xffff):
        row['hex'] = content.hex(' ')
    if ident == 5:
        row['text'] = content.decode('ascii', errors='replace')
    records.append(row)
    if ident in (8, 0x2bd):
        payloads[ident].extend(content)
    off = end
summary = dict(input=str(a.input), bytes=len(b),
               sha256=hashlib.sha256(b).hexdigest(),
               consumed_exactly=(off == len(b)),
               record_count=len(records),
               counts=dict(collections.Counter(r['id'] for r in records)),
               records=records, extracted={})
for ident, data in payloads.items():
    name = {8:'boot-candidate.bin', 0x2bd:'fw-all-candidate.bin'}[ident]
    (a.output/name).write_bytes(data)
    summary['extracted'][name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                     first_32_bytes=data[:32].hex(' '))
    strings = [(m.start(), m.group().decode('ascii')) for m in re.finditer(rb'[\x20-\x7e]{6,}', data)]
    (a.output/(name+'.strings.txt')).write_text('\n'.join('%08x %s'%s for s in strings))
(a.output/'inventory.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k:v for k,v in summary.items() if k != 'records'}, indent=2))
