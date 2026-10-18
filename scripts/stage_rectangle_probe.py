"""Copy the reviewed probe to an explicitly identified removable card.

Default is read-only planning. --install is only for the authorized experiment
AFTER reset/recovery verification. Never formats, overwrites, or targets GARMIN.
"""
from local_targets import expected_volume
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EXPECTED='4e1068d56579ec68146a2b795a4dd487224b40f415986404beaa1c91da57e1fd'
p=argparse.ArgumentParser()
p.add_argument('mount',type=Path)
p.add_argument('--uuid',required=True)
p.add_argument('--install',action='store_true')
p.add_argument('--reset-verified',action='store_true')
a=p.parse_args()
mount=a.mount.resolve()
if mount.parent!=Path('/Volumes') or mount.name=='GARMIN' or not mount.is_mount():
    raise SystemExit('Target must be a mounted spare card directly under /Volumes, never GARMIN.')
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(mount)]))
uuid=info.get('VolumeUUID')
if uuid!=a.uuid or uuid==expected_volume('nuvi200'):
    raise SystemExit('Target UUID mismatch or Garmin volume.')
internal_sd = (info.get('BusProtocol') == 'Secure Digital'
               and info.get('RemovableMedia') is True)
if (info.get('Internal',True) and not internal_sd) or not info.get('FilesystemType','').startswith('msdos'):
    raise SystemExit('Need a removable FAT16/FAT32 card; no formatting will be attempted.')
if info.get('TotalSize',0) > 32*1024**3:
    raise SystemExit('Card volume exceeds the documented 32 GB support; use a smaller card.')
if not info.get('WritableVolume',False):
    raise SystemExit('Card is read-only.')
target=mount/'Garmin/Updater/0660'
if target.exists():
    raise SystemExit('Updater/0660 already exists; refusing to replace or mix files.')
if any(x.is_symlink() for x in [mount/'Garmin',mount/'Garmin/Updater']):
    raise SystemExit('Unexpected symlink in destination.')
source=ROOT/'analysis/rectangle-probe/rectangle-candidate.bin'
data=source.read_bytes()
audit=json.loads((ROOT/'analysis/rectangle-probe/audit.json').read_text())
if hashlib.sha256(data).hexdigest()!=EXPECTED or audit['payload_sha256']!=EXPECTED:
    raise SystemExit('Candidate or audit hash differs from reviewed build.')
if len(audit['cases'])!=10:
    raise SystemExit('Missing expected audit cases.')
if os.statvfs(mount).f_bavail*os.statvfs(mount).f_frsize<65536:
    raise SystemExit('Insufficient free space.')
report={'mount':str(mount),'uuid':uuid,'target':str(target/'ldr.bin'),
        'bytes':len(data),'sha256':EXPECTED,'install_requested':a.install}
if not a.install:
    print(json.dumps(report,indent=2))
    raise SystemExit(0)
if not a.reset_verified:
    raise SystemExit('Verify physical reset/recovery before installing this executable trigger.')
target.mkdir(parents=True,exist_ok=False)
dest=target/'ldr.bin'
with dest.open('xb') as f:
    f.write(data)
    f.flush()
    os.fsync(f.fileno())
with dest.open('rb') as f:
    copied=f.read(len(data))
if len(copied)!=len(data) or hashlib.sha256(copied).hexdigest()!=EXPECTED:
    raise SystemExit('Card read-back verification failed; do not insert it in Garmin.')
report['readback_verified']=True
(ROOT/'evidence/rectangle-card-install.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
