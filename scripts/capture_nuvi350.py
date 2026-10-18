"""Read-only, identity-guarded capture of selected firmware files to the Mac.
Not a full backup. Never writes to the device. Copy hash verified locally.
"""
from local_targets import expected_volume
from pathlib import Path
import hashlib,json,plistlib,subprocess,xml.etree.ElementTree as ET,time
ROOT=Path(__file__).resolve().parents[1];mount=Path('/Volumes/nuvi')
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(mount)]))
if info.get('VolumeUUID')!=expected_volume('nuvi350') or info.get('BusProtocol')!='USB':raise SystemExit('Unexpected volume')
r=ET.fromstring((mount/'Garmin/GarminDevice.xml').read_bytes());ns={'g':r.tag.split('}')[0][1:]}
if r.findtext('g:Model/g:PartNumber',namespaces=ns)!='006-B0476-00':raise SystemExit('Unexpected hardware ID')
out=ROOT/'evidence/nuvi350/firmware';out.mkdir(parents=True,exist_ok=True);report=[]
for name in ('GUPDATE.GCD','006B047800.bin','006B048201.bin','fs_image.ver'):
    source=mount/'Garmin'/name;target=out/name
    if source.is_symlink():raise SystemExit('Unexpected symlink')
    before=source.stat();h=hashlib.sha256();count=0;started=time.monotonic()
    with source.open('rb') as src,target.open('wb') as dst:
        while True:
            chunk=src.read(262144)
            if not chunk:break
            dst.write(chunk);h.update(chunk);count+=len(chunk)
    after=source.stat();actual=hashlib.sha256(target.read_bytes()).hexdigest()
    if count!=before.st_size or before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns or actual!=h.hexdigest():raise SystemExit('Copy verification failed')
    row=dict(file=name,bytes=count,sha256=actual,local_copy_verified=True,seconds=round(time.monotonic()-started,2))
    report.append(row);print(json.dumps(row),flush=True)
(ROOT/'evidence/nuvi350/firmware-copy.json').write_text(json.dumps({'scope':'Selected firmware only, not full backup','device_writes':False,'files':report},indent=2)+'\n')
