# Raw touchscreen calibration capture

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

Local candidate only; not installed. Derived from physically demonstrated Touch Lab. Same guarded framebuffer and exact stock ADC/GPIO sequence, bounded timer/conversion waits and red failure indicator. Adds three-digit hexadecimal raw readings for ADC0/1 at (210,88)/(210,136), and four static calibration targets at (18,18), (300,18), (18,220), (300,220). No calibration, pressure/press detection or persistent recording yet. No new peripheral addresses or commands. No filesystem/flash calls.

Build: python3 scripts/make_calibration_probe.py then python3 scripts/build_rectangle_probe.py --experiment calibration. Audit: python3 scripts/audit_calibration_probe.py. Fifteen cases pass, including six raw pairs on each supported framebuffer, every hex glyph, eleven guard rejects and two bounded timeouts. Full resident-loader handoff verified in software. This does not emulate real electronics or prove physical operation.

Candidate 160760 bytes SHA256 effc61d01bec9e631ebf263b202419dee347ab216de1083be66849c28e5e2c5c. stage_calibration_probe.py defaults read-only, --install replaces only known Touch Lab ldr.bin on original UUID SD in Mac reader with fsync/readback checks. No internal Garmin writes. Preserve touch candidate for rollback.

Physical experiment after reviewed card replacement and normal safe ejection: use known-working startup sequence. Film entire screen with readouts legible. Leave untouched for two seconds, hold target1 for two seconds, lift for one second, then repeat2,3,4, center, finish untouched two seconds. Targets do not advance automatically: continuous readings captured in video, fit offline later. Use light fingertip pressure and hold center of target; do not use sharp objects. Exit by removing SD before RESET, with host volumes safely unmounted. Report red indicator/freeze rather than repeatedly retrying.
