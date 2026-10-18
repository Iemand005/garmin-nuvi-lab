"""Dry-run by default. --install only after explicit350 SD-test approval.
Adds only Garmin/Updater/0476/ldr.bin to the known Mac-reader SD.
Never targets Garmin internal media, rewrites0660, or copies stock firmware.
"""
from local_targets import expected_volume
from pathlib import Path
import argparse,hashlib,json,os,plistlib,subprocess
ROOT=Path(__file__).resolve().parents[1]
SHA='eaf9d182c812890f8c6ba3d4707f9455c13bc72aa70474ae81c967322412c6f4'
OLD='b83d37afe5b94a44e3fb924b7b2a4615843fe214f6ed7966fcf879cacc2583eb'
UUID=expected_volume('test_sd')
p=argparse.ArgumentParser(description=__doc__);p.add_argument('mount',type=Path);p.add_argument('--install',action='store_true');a=p.parse_args()
v=a.mount.resolve()
if v.parent!=Path('/Volumes') or not v.is_mount():raise SystemExit('Need mounted known SD')
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(v)],timeout=20))
if info.get('VolumeUUID')!=UUID or info.get('BusProtocol')!='Secure Digital' or not info.get('RemovableMedia'):raise SystemExit('Use known SD in Mac reader, never Garmin USB media')
if info.get('FilesystemType')!='msdos' or not info.get('WritableVolume') or not 0<info.get('TotalSize',0)<=32*1024**3:raise SystemExit('Unexpected card')
for d in (v/'Garmin',v/'Garmin/Updater'):
    if d.is_symlink() or not d.is_dir():raise SystemExit('Unexpected prior directory')
folder=v/'Garmin/Updater/0476';target=folder/'ldr.bin'
if folder.is_symlink() or (folder.exists() and not folder.is_dir()) or target.is_symlink():raise SystemExit('Unexpected target type')
if folder.exists():
    for x in folder.iterdir():
        if x.name=='ldr.bin':continue
        # macOS AppleDouble sidecar, inspected and preserved; not a Garmin script.
        if x.name!='._ldr.bin' or x.is_symlink() or not x.is_file() or x.stat().st_size>65536 or x.read_bytes()[:8]!=bytes.fromhex('0005160700020000'):
            raise SystemExit('Existing0476 folder contains unknown files; inspect manually')
if target.exists() and (not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() not in (OLD,SHA)):raise SystemExit('Unknown existing350 loader; refusing overwrite')
prior=v/'Garmin/Updater/0660/ldr.bin'
if not prior.is_file() or prior.is_symlink():raise SystemExit('Missing known200 experiment')
prior_sha=hashlib.sha256(prior.read_bytes()).hexdigest()
if prior_sha!='7a87149a1a45f66a1a696558cd44264613087cc53347eacda0aea39879f31696':raise SystemExit('Unexpected200 loader; inspect manually')
out=ROOT/'analysis/nuvi350-touchlab-probe';data=(out/'nuvi350-touchlab-candidate.bin').read_bytes();audit=json.loads((out/'audit.json').read_text())
if hashlib.sha256(data).hexdigest()!=SHA or audit['payload_sha256']!=SHA or len(data)!=4520 or len(audit['cases'])!=18:raise SystemExit('Candidate/audit mismatch')
if (sum(c['usb_initialized'] for c in audit['cases'])!=4 or
    sum(c['marker_visible'] for c in audit['cases'])!=8 or
    any(not c['no_touch_io'] for c in audit['cases']) or
    sum(not c['marker_visible'] and c['pixel_writes']==0 for c in audit['cases'])!=10):
    raise SystemExit('Missing display/USB initialization guards')
if (len(audit['usb_protocol']['cases'])!=32 or len(audit['completion_checks'])!=7 or
    len(audit['info_checks'])!=4 or len(audit['image_checks'])!=2 or
    any(c['blocks_verified']!=2400 or not c['setup_reset_cancel'] for c in audit['image_checks'])):
    raise SystemExit('Missing USB transfer/profile checks')
if audit['handoff']['entry_mode_r12']!=2 or audit['handoff']['copied_bytes']!=len(data):raise SystemExit('Missing350 handoff checks')
if len(audit.get('snapshot_checks',[]))!=4 or any(not c['no_touch_writes'] or c['pages']!=3 or c['lengths']!=7 or c['invalid_inputs']!=5 or not c['penirq_change'] for c in audit['snapshot_checks']):raise SystemExit('Missing bounded read-only snapshot checks')
report=dict(mount=str(v),uuid=UUID,target=str(target),bytes=len(data),sha256=SHA,existing200_sha256=prior_sha,install_requested=a.install,internal_garmin_writes=False)
if a.install:
    folder.mkdir(exist_ok=True)
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=SHA:
        old=target.read_bytes() if target.exists() else None
        temp=folder/'350-touchlab-stage.tmp'
        with temp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        if temp.read_bytes()!=data:raise SystemExit('Temporary readback mismatch')
        if (target.read_bytes() if target.exists() else None)!=old:raise SystemExit('Target changed while staging')
        os.replace(temp,target)
        with target.open('rb') as f:os.fsync(f.fileno())
    if target.read_bytes()!=data or hashlib.sha256(prior.read_bytes()).hexdigest()!=prior_sha:raise SystemExit('Final readback mismatch')
    report['readback_verified']=True
    (ROOT/'evidence/nuvi350/touchlab-card-install.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
