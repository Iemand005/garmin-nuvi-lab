"""Create ignored local output directories. Does not access devices."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for name in ('analysis/player/artwork','analysis/music','analysis/nuvi350/usb','evidence/nuvi350','backups','.local'):
    (ROOT/name).mkdir(parents=True,exist_ok=True)
print('Local output directories ready; no device I/O.')
