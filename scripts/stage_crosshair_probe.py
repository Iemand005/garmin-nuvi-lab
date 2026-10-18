"""Plan, or explicitly install, the reviewed crosshair diagnostic on the known test SD.

Default is read-only. --install requires user approval to replace the prior
calibration ldr.bin. Never targets Garmin internal storage or formats media.
"""
from local_targets import expected_volume
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CARD_UUID = expected_volume('test_sd')
OLD = 'effc61d01bec9e631ebf263b202419dee347ab216de1083be66849c28e5e2c5c'
NEW = 'f3fd417f0b6f7c37a9eaaf004d7331bd994d27e9fbdebde781a9a8e39cc2cbf9'
digest = lambda b: hashlib.sha256(b).hexdigest()
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('mount', type=Path)
p.add_argument('--install', action='store_true')
a = p.parse_args()
mount = a.mount.resolve()
if mount.parent != Path('/Volumes') or mount.name == 'GARMIN' or not mount.is_mount():
    raise SystemExit('Need the mounted test SD, never GARMIN.')
info = plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(mount)], timeout=20))
if info.get('VolumeUUID') != CARD_UUID:
    raise SystemExit('Wrong volume UUID.')
if info.get('BusProtocol') != 'Secure Digital' or info.get('RemovableMedia') is not True:
    raise SystemExit('Use the Mac SD reader, not the Garmin USB connection.')
if not info.get('FilesystemType','').startswith('msdos') or not info.get('WritableVolume'):
    raise SystemExit('Need writable FAT16/FAT32; no formatting attempted.')
if not 0 < info.get('TotalSize',0) <= 32*1024**3:
    raise SystemExit('Unexpected card size.')
parts = [mount/'Garmin', mount/'Garmin/Updater', mount/'Garmin/Updater/0660']
if any(x.is_symlink() or not x.is_dir() for x in parts):
    raise SystemExit('Missing or symlinked prior experiment directory.')
target = parts[-1]/'ldr.bin'
if target.is_symlink() or not target.is_file() or target.stat().st_size > 200000:
    raise SystemExit('Unexpected loader file.')
old = target.read_bytes()
if digest(old) not in (OLD, NEW):
    raise SystemExit('Prior loader hash not recognized; refusing overwrite.')
out = ROOT/'analysis/crosshair-probe'
data = (out/'crosshair-candidate.bin').read_bytes()
audit = json.loads((out/'audit.json').read_text())
if digest(data) != NEW or audit['payload_sha256'] != NEW or len(audit['cases']) != 15:
    raise SystemExit('Local payload/audit mismatch.')
if sum(c.get('sample_pairs_verified',0)==18 for c in audit['cases']) != 2:
    raise SystemExit('Missing supported-framebuffer/input checks.')
if sum(c.get('guard_rejected',False) and c['peripheral_stores']==0 for c in audit['cases']) != 11:
    raise SystemExit('Missing guard rejection checks.')
if sum(c.get('timeout_stopped',False) for c in audit['cases']) != 2:
    raise SystemExit('Missing bounded timeout checks.')
report = {'mount': str(mount), 'uuid': CARD_UUID, 'target': str(target),
          'bytes': len(data), 'old_sha256': digest(old), 'sha256': NEW,
          'install_requested': a.install}
if a.install:
    if digest(old) == OLD:
        temporary = target.with_name('crosshair-stage.tmp')
        with temporary.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if temporary.stat().st_size != len(data) or digest(temporary.read_bytes()) != NEW:
            raise SystemExit('Temporary copy mismatch; original loader retained.')
        if target.read_bytes() != old:
            raise SystemExit('Loader changed while staging; original retained.')
        os.replace(temporary, target)
        with target.open('rb') as f:
            os.fsync(f.fileno())
    if target.stat().st_size != len(data) or digest(target.read_bytes()) != NEW:
        raise SystemExit('Final verification failed; do not insert card in Garmin.')
    report['readback_verified'] = True
    (ROOT/'evidence/crosshair-card-install.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
