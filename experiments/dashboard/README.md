# Native dashboard / heartbeat experiment

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

Prepared locally after the user reported successful inversion AND restoration
by the rectangle probe, followed by recovery (“Okay, all set”). Installed and read-back verified on the
approved SD card; native dashboard execution and repeated central animation confirmed by the
user’s 2.935-second video IMG_5002.MOV. Evidence and limits are recorded in
`evidence/dashboard-video/observation.json`. See
`evidence/dashboard-card-install.json` and latest `notes/current-status.md` for
ejection and physical-test state.

The 156,128-byte loader embeds a 320×240 RGB565 screen. It retains the proven
mode, LCD, dimensions, DMA bounds, known-buffer, prefix-format and stable-source
guards. On acceptance it copies pixels into the active framebuffer, preserves
the prefix, then repeatedly inverts/restores the same 32×32 central square.
Guard rejection parks. No flash, filesystem, MMIO writes, touch handling,
interrupt handling or return to Garmin firmware. Delay duration is uncalibrated;
watchdog behavior and sustained LCD operation remain physical-test questions.

SHA-256: `f742cae4bffa6816f8bcc9dad0eb9394d99d5a5eb439eecaba5b98d3ca89eb0e`.

Build locally:

```
python3 scripts/make_dashboard_probe.py
python3 scripts/build_rectangle_probe.py --experiment dashboard
python3 scripts/audit_dashboard_probe.py
```

The audit interprets actual instructions for both supported buffers, checks
three complete blink cycles against exact expected pixels, preserves the other
buffer and both prefixes, and rejects eight invalid configurations without
writes. It interprets the resident handoff copying all payload bytes to entry.
Delays are accelerated; it does not emulate hardware, caches or watchdogs.

Deployment requires approval to replace only the prior SD
`Garmin/Updater/0660/ldr.bin`, on card UUID
`<configured test_sd volume UUID>`. Keep the card in the Mac reader while
staging; use `scripts/stage_dashboard_probe.py MOUNT` for read-only planning,
then `--install` only after approval. It verifies identity, prior loader hash,
new payload/audit, and readback. It refuses Garmin internal storage. The
original rectangle candidate remains local for rollback.

After verified copy and normal safe ejection: insert the card in Garmin,
record the screen and use the previously successful startup/reset sequence.
Observe custom screen, repeated blinking, colors, edges, tearing, or restart.
Do not infer a failed load from no visible effect alone. To recover, remove
SD before the verified physical RESET. Do not reset while host volumes remain
mounted. Keep USB power attached as needed; no battery or cable modifications.
