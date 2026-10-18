"""Remove only the two explicitly approved display probes, after identity/hash checks."""
import hashlib
import json
import plistlib
import subprocess
from datetime import datetime, timezone
from local_targets import expected_volume
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VOLUME = Path('/Volumes/GARMIN')
EXPECTED = {
    'LAB_01.JPG': 'aab412bd05e000dc7d1016317d86f272353c557e92b90026d3e127900b555ff4',
    'LAB_02.JPG': 'f744ab2d49d042d1d2516c8290cbc7989315c949209cbc4c1ff4a0fc35f86044',
}

def bounded_read(path):
    with path.open('rb') as stream:
        return stream.read(path.stat().st_size)

def main():
    if not VOLUME.is_mount():
        raise SystemExit('GARMIN is not mounted; no changes made.')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(VOLUME)]))
    if info.get('VolumeUUID') != expected_volume('nuvi200'):
        raise SystemExit('Unexpected volume UUID; no changes made.')
    model = ET.fromstring(bounded_read(VOLUME / 'Garmin/GarminDevice.xml'))
    part = model.findtext('{*}Model/{*}PartNumber')
    if part != '006-B0660-00':
        raise SystemExit('Unexpected device model; no changes made.')
    # Validate all present targets and preserved local originals before any deletion.
    for name, expected in EXPECTED.items():
        local = ROOT / 'artifacts/display-probe' / name
        if hashlib.sha256(bounded_read(local)).hexdigest() != expected:
            raise SystemExit(f'Local original mismatch: {name}; no changes made.')
        target = VOLUME / 'JPEG' / name
        if target.is_symlink():
            raise SystemExit(f'Unexpected symlink: {name}; no changes made.')
        if target.exists() and hashlib.sha256(bounded_read(target)).hexdigest() != expected:
            raise SystemExit(f'Device file mismatch: {name}; no changes made.')
    report = {'authorization': 'User explicitly approved deleting only LAB_01.JPG and LAB_02.JPG',
              'volume_uuid': info['VolumeUUID'], 'files': []}
    report_path = ROOT / 'evidence/jpeg-removal-report.json'
    for name in EXPECTED:
        target = VOLUME / 'JPEG' / name
        existed = target.exists()
        if existed:
            target.unlink()
        absent = not target.exists()
        report['files'].append({'path': f'JPEG/{name}', 'removed': existed, 'verified_absent': absent})
        report['updated_utc'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'{name}: {"removed" if existed else "already absent"}, absence verified={absent}', flush=True)
        if not absent:
            raise SystemExit('Deletion verification failed.')

if __name__ == '__main__':
    main()
