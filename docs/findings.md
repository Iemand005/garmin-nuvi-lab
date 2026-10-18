# Verified hardware and results

The project started with two thrift-store navigators and a Raspberry Pi 4. Both original motherboards, LCDs, and touchscreens now run a Mac-connected Spotify remote. The Pi was not needed for this milestone.

| Observation | nüvi 200 | nüvi 350 NA |
| --- | --- | --- |
| Tested hardware ID | 0660 / decimal 660 | 0476 / decimal 476 |
| Tested stock software | 5.00 | 6.20 |
| Logical UI | 320 × 240 | 320 × 240 |
| Measured LCD scan | 320 × 240 | 240 × 320 |
| RAM entry address | `0x10040000` | `0x10040000` |
| Loader handoff mode | 12 | 2 |
| Touch path | OMAP ADC/GPIO sampling | TSC2046-style serial driver |
| Qualified playback input | Native buffered release events | Calibrated host-sampled releases |

The peripheral register layout and executable code establish ARM/Thumb and an OMAP1-style platform. Exact SoC and panel part numbers have not been confirmed by reading component markings. The firmware contains an embedded native execution environment; this is not a desktop OS with an established third-party application API.

## What proved screen control

1. Baseline JPEG patterns rendered through the stock picture viewer.
2. Small native SD-loaded programs changed selected framebuffer pixels while preserving the display's inherited timing and DMA setup.
3. A private USB endpoint accepted bounded RGB565 pixel blocks into the validated framebuffer.
4. The Mac streamed album artwork, text, progress, and button states.
5. Touch calibration and physical play/pause, previous, and next tests worked on both models.

USB mass storage alone proved none of the later steps. The new USB device is supplied by our temporary RAM program, not a discovered stock remote-display feature. Native code takes over the UI and does not return to Garmin's menu until reset.

## Approaches compared

| Approach | Result | Tradeoff |
| --- | --- | --- |
| Stock picture viewer | Physically verified | Useful static content; no established live control path |
| Existing motherboard with RAM code | Physically verified and used | Best hardware reuse; model-specific reverse engineering |
| Direct LCD connection to Pi | Not electrically investigated | Would require identifying the actual panel, signaling, supplies, and connector |
| Existing board plus external computer | Current implementation over USB | Mac supplies rendering and Spotify integration; Garmin supplies display and touch |

The selected route preserves the original LCD, touchscreen, speaker, controls, and enclosure without soldering or motherboard replacement. Speaker/button support beyond the touchscreen has not been implemented. No LCD part number, including the suggested Sharp LQ035Q1DH01, is established by these experiments.

## Limits

Compatibility is demonstrated only for the hardware/software combinations above. A stored GCD update is an analysis input, not a readback of running flash. The audits interpret a bounded ARM subset and synthetic registers/FIFOs; they do not emulate cache, electrical behavior, clocks, or the complete boot hardware preamble.

The 350's five calibration targets fitted with a largest residual of roughly five pixels. This is not an accuracy bound for the whole panel. The 350 host samples touch instead of consuming a native buffered queue, so very brief taps can be missed. Holding does not repeat; dragging out cancels a captured button. Playback is sent once per qualified release; ambiguous command failures stop rather than retry.
