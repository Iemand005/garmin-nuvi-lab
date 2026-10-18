#!/usr/bin/env python3
"""Install ONLY the two JPEGs explicitly approved by the user for HWID 0660."""
from local_targets import expected_volume
from pathlib import Path
import datetime, hashlib, json, os, plistlib, subprocess
import xml.etree.ElementTree as E

def read_exact_file(path):
    left = path.stat().st_size
    chunks = []
    with path.open('rb', buffering=0) as f:
        while left:
            block = f.read(min(left, 65536))
            if not block:
                raise IOError('Unexpected EOF: ' + str(path))
            chunks.append(block)
            left -= len(block)
    return b''.join(chunks)

volume = Path('/Volumes/GARMIN')
info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)]))
if info.get('VolumeUUID') != expected_volume('nuvi200'):
    raise SystemExit('Volume identity mismatch')
root = E.fromstring(read_exact_file(volume / 'Garmin/GarminDevice.xml'))
ns = {'g': root.tag.split('}')[0][1:]}
model = root.find('g:Model', ns)
if model.find('g:PartNumber', ns).text != '006-B0660-00':
    raise SystemExit('Model identity mismatch')
folder = volume / 'JPEG'
if not folder.is_dir():
    raise SystemExit('JPEG directory absent')
manifest = json.loads(Path('artifacts/display-probe/manifest.json').read_text())
plans = []
for name in ('LAB_01.JPG', 'LAB_02.JPG'):
    source = Path('artifacts/display-probe') / name
    data = source.read_bytes()
    expected = next(row['sha256'] for row in manifest if Path(row['path']).name == name)
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit('Local test image changed: ' + name)
    plans.append((folder / name, data, expected))
space = os.statvfs(volume)
if space.f_bavail * space.f_frsize < sum(len(data) for _, data, _ in plans) + 65536:
    raise SystemExit('Insufficient free space')
results = []
for target, data, expected in plans:
    if target.exists():
        # A matching copy is safe to verify again; never overwrite anything.
        if hashlib.sha256(read_exact_file(target)).hexdigest() != expected:
            raise SystemExit('Refusing to overwrite existing image: ' + str(target))
        action = 'existing identical copy verified'
    else:
        with target.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        action = 'created new file'
    actual = hashlib.sha256(read_exact_file(target)).hexdigest()
    if actual != expected:
        raise SystemExit('Device copy verification failed: ' + str(target))
    row = dict(path=str(target), bytes=len(data), sha256=actual, verified=True, action=action)
    results.append(row)
    print(json.dumps(row), flush=True)
report = dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              authorization='User waived full backup and explicitly approved these two JPEG writes.',
              files=results)
Path('evidence/jpeg-install-report.json').write_text(json.dumps(report, indent=2))
print('Both approved images are installed and verified.', flush=True)
