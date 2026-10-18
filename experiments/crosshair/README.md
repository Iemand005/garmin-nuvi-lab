# Crosshair and provisional contact diagnostic

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

Derived from physically demonstrated calibration payload. Same ADC/GPIO sequence, guard checks, bounded polls, raw bars/readouts and heartbeat. Adds 13-pixel white crosshair, restores its previous rectangle before rendering the next frame, and contact-color block at (260,48),36x8. Uses 10 bytes of existing local scratch, no flash/filesystem calls or additional peripheral commands.

Experimental gate: both raw values >50. Two consecutive accepted samples acquire/update the crosshair; a single invalid sample retains its last location; two invalid samples hide it. Amber means a pending transition, green accepted input, gray inactive. This is sample-count debounce, not pressure measurement or a timing guarantee. No clicks or persistent state.

Position uses shift/add approximation of provisional video fit: x=(113*ADC1//256)-59, y=307-(94*ADC0//256), clipped to x6..313,y6..233 so the marker remains in bounds. This is a coarse fit; a cursor offset must not be presented as calibrated accuracy.

Build: python3 scripts/make_crosshair_probe.py; python3 scripts/build_rectangle_probe.py --experiment crosshair. Audit: python3 scripts/audit_crosshair_probe.py. Checks18 pairs on each supported buffer, threshold boundaries, isolated valid/invalid samples, acquisition/release, cursor restoration and extrema/clipping, plus11 guard failures and2 timeouts, and full resident handoff. Audit is synthetic and does not emulate hardware/cache/pressure. Preserve calibration candidate for rollback.

Stage only with approved test SD replacement using stage_crosshair_probe.py (default read-only); --install pins known card UUID/Mac reader/prior calibration hash and verifies fsync/readback. Normal eject required. Keep test card out of Garmin until any mounted Garmin volumes are normally ejected. Use known-working startup sequence. Film slow drags, a hold, release and short taps; report cursor following, unwanted jumps and status transitions. Exact under-finger contact is obscured; assess coarse behavior first. Remove SD before recovery RESET; never reset while storage mounted.
