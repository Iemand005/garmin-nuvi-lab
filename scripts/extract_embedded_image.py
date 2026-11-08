#!/usr/bin/env python3
"""Locate and extract a Garmin embedded image header from a local blob.

Read-only analysis. An image is: branch word, end/hwid/version pointers relative
to a caller-supplied base, then `end + 6` bytes ending in the 0xa55a footer. This
is the same layout used by the nüvi 200/200W resident boot and application
stages. Auto-scan is bounded and requires the identity pointers and footer to
agree; it does not prove the image is live flash or safe to execute.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

BASE_HEADER = 0xEA000002


def candidate_at(data, off, base):
    if off + 16 > len(data):
        return None
    branch, end, hw, ver = struct.unpack_from('<4I', data, off)
    if branch != BASE_HEADER:
        return None
    if not base + 16 <= end <= base + len(data) - off:
        return None
    if not all(base + 16 <= p <= base + len(data) - off - 1 for p in (hw, ver)):
        return None
    size = end + 6 - base
    image = data[off:off + size]
    if image[-6:-4] != b'\x5a\xa5':
        return None
    return {
        'offset': off,
        'size': size,
        'hwid': struct.unpack_from('<H', image, hw - base)[0],
        'software_version': struct.unpack_from('<H', image, ver - base)[0],
        'hwid_pointer': hw,
        'version_pointer': ver,
        'image': image,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--base', type=lambda s: int(s, 0), required=True)
    p.add_argument('--offset', type=lambda s: int(s, 0), default=None)
    p.add_argument('--expect-hwid', type=int)
    p.add_argument('--expect-sw', type=int)
    a = p.parse_args()

    data = a.input.read_bytes()
    offsets = [a.offset] if a.offset is not None else range(0, max(1, len(data) - 16), 4)
    hits = [h for h in (candidate_at(data, o, a.base) for o in offsets) if h]
    if a.expect_hwid is not None:
        hits = [h for h in hits if h['hwid'] == a.expect_hwid]
    if a.expect_sw is not None:
        hits = [h for h in hits if h['software_version'] == a.expect_sw]
    if len(hits) != 1:
        raise SystemExit(f'Expected exactly one matching image, found {len(hits)}')

    hit = hits[0]
    image = hit.pop('image')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(image)
    report = {
        'container': a.input.name,
        'container_bytes': len(data),
        'container_sha256': hashlib.sha256(data).hexdigest(),
        'raw_offset': hex(hit['offset']),
        'assumed_base': hex(a.base),
        'bytes': hit['size'],
        'sha256': hashlib.sha256(image).hexdigest(),
        'hwid': hit['hwid'],
        'software_version': hit['software_version'],
        'hwid_pointer': hex(hit['hwid_pointer']),
        'version_pointer': hex(hit['version_pointer']),
        'footer': image[-6:].hex(' '),
        'status': 'embedded update image; not a readback of running device',
    }
    (a.output.with_suffix('.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
