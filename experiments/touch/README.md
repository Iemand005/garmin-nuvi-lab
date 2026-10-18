# Raw touchscreen sampling experiment

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

Installed and read-back verified on the approved SD card; physical raw-touch
response pending. See `evidence/touch-card-install.json` and latest
`notes/current-status.md` for ejection/test state.

For the physically tested nüvi200 HWID0660 / stored software5.00 only.
User authorized proceeding with this next SD experiment after reporting the
dashboard ran for about one minute and returning the SD card to the Mac reader.
This is a first raw-coordinate experiment, not a calibrated touchscreen UI.

The payload retains the proven LCD/DMA guards, draws a320×240 screen, and polls
the original ADC for two channels, represented by two bars. It leaves ADC
clocks, pin mux and GPIO directions as initialized by stock Garmin firmware;
new guards reject an uninitialized ADC or relevant pins configured as inputs.
No flash, filesystem, battery, power-controller or firmware-update operations.

Unlike the dashboard, this test performs peripheral writes: the exact existing
stock touchscreen selector0/1 GPIO sequences and single ADC conversion commands.
It does not call stock code or enable interrupts. Timer and conversion polls
are finite; a timeout produces a red indicator and stops. It uses the stock
settling delay of0x2f1 decrementing timer ticks. No assumed voltage, physical
connector mapping, or external electrical connections are involved.

## Device-specific evidence

- Main0x1007831a calls0x100e6d54 to obtain x/y plus valid flag, then
 0x100781e8 applies six calibration coefficients and clamps to319×239.
-0x100e6d54 consumes raw state produced by the ADC sampling code. Initial
 sampling at0x100e6dc2 reads logical0/1 with threshold100; runtime processing
 at0x100dc7cc also measures additional channels for contact validity.
- Selector0 at0x100dc2d8..2f0 and selector1 at0x100dc316..32c are independently
 interpreted from the stock binary in `analysis/touch/stock-selector-proof.json`.
 The candidate audit requires that exact store order/value/address/width.
- Both stock board-variant tables map logical0/1 to physical ADC0/1.
- Single-conversion routine0x100dcd36..60 drains the result, writes channel
 command with bit15, waits for status bit0 at0xfffe6018, reads0xfffe6034 and
 masks ten bits. Candidate bounds the wait rather than spinning indefinitely.
- Background touch validation/calibration is not reproduced. Bars always show
 raw readings, including noise or release values. Their labels are axis
 candidates; orientation and scaling must be checked by actual corner/drag tests.

Related Linux OMAP16xx GPIO source was consulted as architectural context:
https://raw.githubusercontent.com/torvalds/linux/master/arch/arm/mach-omap1/gpio16xx.c
Device-specific instruction traces, not a presumed discrete touch-controller
part number, determine the implemented sequence.

## Build and validation

```
python3 scripts/make_touch_probe.py
python3 scripts/build_rectangle_probe.py --experiment touch
python3 scripts/audit_touch_probe.py
```

`input-body.S` is maintained source; generator combines it with the prior
dashboard guards and full-frame copy. It also builds preview.png and RGB565.
Payload156524bytes, SHA-256
`b3d80591606d87c8e2dfb7c36915bec18ce2e0a0d718cce3a3c775fc09dafcab`.

The15-case audit covers both framebuffers with three different raw pairs,
eleven guard rejections with no writes, two stuck-hardware cases that stop,
exact peripheral store sequences, exact expected bars, and untouched alternate
frame/prefix. The resident handoff copy also passes. This synthetic instruction
model does not establish electrical operation, caches, ADC readiness on real
hardware, touch validity, or sustained uptime. The prior working dashboard is
preserved locally for rollback.

## Deployment and physical observation

`scripts/stage_touch_probe.py MOUNT` defaults to a read-only plan. `--install`
is authorized for this experiment, on the original2GB SD UUID
<configured test_sd volume UUID> in the Mac reader. It accepts only the known
dashboard or this exact candidate at the existing ldr.bin path, checks audit,
atomically replaces the file, fsyncs and verifies readback. Never target GARMIN.

Normal safe-eject the SD before removal. With Garmin not mounted to the Mac,
use the previously successful card-present startup/RESET sequence, retain USB
power, and move slider to CENTER/unlocked for testing. Record initial screen,
press/hold at center, drag left/right then up/down, then release. Report which
bar changes, direction/range, and whether the top-right indicator flashes or
turns red. Empty bars alone are inconclusive. Remove SD before recovery RESET.
