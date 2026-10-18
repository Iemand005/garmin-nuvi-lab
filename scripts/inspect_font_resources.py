#!/usr/bin/env python3
"""Identify XOR-masked SFNT resources locally; emit metadata, not font files."""
import argparse, json, pathlib, struct

p = argparse.ArgumentParser()
p.add_argument('directory', type=pathlib.Path)
p.add_argument('output', type=pathlib.Path)
a = p.parse_args()
rows = []
for path in sorted(a.directory.glob('*.bin')):
    original = path.read_bytes()
    key = original[0]
    data = bytes(x ^ key for x in original)
    row = dict(path=str(path), bytes=len(data), xor_key=hex(key),
               validation_scope='SFNT signature, table-directory bounds and selected name records; no glyph/checksum validation')
    if len(data) < 12 or data[:4] != b'\x00\x01\x00\x00':
        row['sfnt_structure_valid'] = False
        rows.append(row)
        continue
    count = struct.unpack_from('>H', data, 4)[0]
    tables = {}
    valid = 12 + count * 16 <= len(data)
    if valid:
        for i in range(count):
            tag, checksum, offset, length = struct.unpack_from('>4sIII', data, 12 + i*16)
            tables[tag.decode('ascii', errors='replace')] = (offset, length)
            valid = valid and offset + length <= len(data)
    names = {}
    if valid and 'name' in tables:
        start, length = tables['name']
        table = data[start:start+length]
        if len(table) >= 6:
            _, records, strings = struct.unpack_from('>HHH', table)
            for i in range(records):
                if 6 + (i+1)*12 > len(table):
                    valid = False
                    break
                platform, encoding, language, ident, size, offset = struct.unpack_from('>6H', table, 6+i*12)
                if ident not in (1,2,4,6) or strings + offset + size > len(table):
                    continue
                if platform not in (0,3):
                    continue
                if platform == 3 and language not in (0,0x409):
                    continue
                value = table[strings+offset:strings+offset+size].decode('utf-16be',errors='replace')
                names[str(ident)] = value
    row.update(sfnt_structure_valid=valid, table_count=count,
               table_tags=sorted(tables), names=names)
    rows.append(row)
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
