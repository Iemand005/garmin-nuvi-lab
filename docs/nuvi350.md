# Porting the 200 experiment to the 350

The renderer and most of the USB protocol were reusable. The native entry, display profile, framebuffer guards, and touch path were not safe to assume compatible.

## Entry and display

The reviewed 350 loader path passes mode 2 instead of the 200's mode 12. Its resident handoff copies the executable into `0x10040000`. The native probe accepts only the two exact display dimensions found in this firmware, a palette-and-data TFT path, a known DMA buffer, and the verified DMA span/format. It checks the programmed DMA source twice before drawing.

The tested 350 scans 240 × 320 although the logical screen is 320 × 240. A photographed orientation test showed horizontal reflection with rotation alone. Correct host packing is a plain transpose: scan X = logical Y, scan Y = logical X. `check_nuvi350_encoding.py` checks RGB565 corners, full transpose equivalence, frame length, and unchanged landscape packing.

## Touch

The firmware names a TSC2046 driver and uses a serial controller at `0xfffb0c00`. The stock coordinate routine begins at `0x100d104c`; transfer helpers are at `0x100e0500` and `0x100e0412`. These are analysis addresses for software 6.20, not callable APIs after our RAM program takes over.

Stock code establishes contact input at `0xfffbe42c` bit 14, active low, and chip select through the GPIO bit-1 clear/set aliases at `0xfffbe4b0` / `0xfffbe4f0`. A read-only hardware test confirmed input transitions and inherited GPIO directions before any touch-drive writes were enabled. These register observations are not a connector pinout.

Measured inherited SPI configuration: SET1 `0x0b`, SET2 `0x8000`, CTRL idle, SYSSTATUS 1. The driver guards those states and preserves GPIO direction, mux, clocks, and reset configuration. Each command uses the stock 16-clock write pattern followed by two 8-clock reads. Coordinates use 8-bit conversions, with the first conversion of each axis discarded.

An initial test returned changing coordinates but frequently marked a held finger as released. Two issues were corrected together:

- End the final conversion with `0x98` (PD00) instead of `0x99` (PD01). TI's power table says PD01 disables PENIRQ; PD00 restores it after conversion.
- Preserve the stock post-chip-select settling requirement of 63 decrementing timer ticks, with a finite timeout, rather than an uncalibrated short instruction loop.

The corrected command sequence is D9, D9, 99, 98. All SPI polls are bounded; chip select is released on failures. A stuck settling timer reports failed transfer 13. The synthetic regression models reproduce the earlier PD01 false release and check timer wrap, slow progress, and a stuck counter. The successful physical test establishes the combined fix; it does not isolate the relative effect of each change.

Five displayed targets produce a per-unit affine mapping. `nuvi350_touch_xy.py` saves the local calibration and then shows a crosshair. The player validates the profile and coefficients before use. Synthetic test fixtures are not hardware defaults. The 350 currently omits the stock pressure/resistance qualification and does not implement a native buffered release queue.

## Model-specific recovery

The tested 350 has RESET behind its raised antenna. Use normal host ejection before resetting any mounted storage. Remove the SD card before recovery reset to stop retriggering the RAM program. The 200's slider procedure is not interchangeable with this model's controls. See Garmin's manual linked in [references](references.md).
