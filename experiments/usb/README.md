# NUVI / USB: first bidirectional runtime experiment

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

Candidate168800bytes SHA256ca7ce7e0cbb6c34651ed18644ffc99ecd1af3235807f5c491d249aa73e490576. Firmware provenance and protocol in notes/usb-investigation.md. Builds with make_usb_probe.py then build_rectangle_probe.py --experiment usb; audit_usb_probe.py checks actual ARM instructions under synthetic FIFO model. Last working buttons candidate remains under analysis/buttons-probe/ for rollback.

SD installer stage_usb_probe.py pins known Mac SD reader/UUID and prior buttons hash; default read-only. User authorized continuing USB experiment. --install changes only SD test ldr.bin with atomic/fsync/readback, never internal Garmin storage. Normal eject before physical removal. If GARMIN is mounted, keep testSD out and cableattached, lockslider then normal hosteject before starting test. No reset while host storage mounted.

After safe startup with SD: title NUVI / USB, USB status red=guardfail, amber=waiting, green=configured. Leave Mac USB connected, center/unlock slider. Host first checks enumeration/status; only after magic/version verified send counter321 and confirm display, then watch coordinates/contact during touch. Host tool under analysis/usb/usb-lab-host; status | set321 (with space) | watch. Do not run firmware updaters or claim normal mounted-storage control. This candidate implements no storage interface. A status/color alone cannot prove a bidirectional roundtrip. If guardfail/noenumeration, capture screen and fresh Mac metadata; do not repeatedly reset/rewrite blindly. Remove SD before recoveryRESET; first normal-eject any remounted host storage.
