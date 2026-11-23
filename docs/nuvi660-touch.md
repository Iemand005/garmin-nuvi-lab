# nüvi 660 Euro touch input

This is a static analysis of the stock touch path in nüvi 660 Euro software 4.90 (hardware ID 596, usually written 0596). The addresses are analysis addresses in `analysis/nuvi660-4.90/app/app-4.90.bin`; they are not callable entry points after a RAM program has taken over the UI.

## Provenance

- Device update: `E:\Garmin\GUPDATE.GCD`, SHA-256 `E69221FB82E61AEF7E590C95FC574B0AEE1D614A6CCFB00459EAAF56117324D2`.
- Extracted application: 7,251,116 bytes, assumed base `0x10040000`, SHA-256 `91d92f8de3c097b3dcaeb319763a10d32b762287a63fb8390c1ba2b97f98327d`.
- Identifiers in the image: hardware ID 596, software 490.
- The image is Thumb code. Addresses below are virtual addresses; file offsets are `address - 0x10040000` while the address is inside the image.

The 660 does not use the nüvi 200's OMAP ADC path. It uses a TSC2046-compatible serial controller over the shared SPI master. Do not reuse the 200 debug probe's ADC/GPIO assumptions on the 660.

## Pipeline

1. `touch_get` at `0x100e8f58` either returns a cached coordinate or calls the TSC2046 sample core.
2. `touch_apply_calibration` at `0x100663da` converts the raw pair through a six-coefficient affine matrix and clamps it to the 480 × 272 logical screen.
3. The gesture task at `0x10066446` debounces contact, tracks movement, and decides when to emit press, drag, release, or repeat events.
4. The event builder at `0x10066366` posts the stock touch events through the firmware event bus.

## TSC2046 sampling

The SPI master is at `0xfffb0c00`. The transfer helpers are `0x100edac8` (write) and `0x100ed9da` (read), serialized by the semaphore at `0x10ac182c`. They perform 8-bit transfers on channel 0, selected through the per-channel configuration table at `0x106b4b21`. Relevant registers:

| Register | Role |
| --- | --- |
| `0xfffb0c24` | Per-channel configuration |
| `0xfffb0c2c` | Control/start |
| `0xfffb0c30` | Status; bit 1 waits for transmit-empty, bit 0 for receive-full |
| `0xfffb0c34` | Transmit byte |
| `0xfffb0c38` | Receive byte |

Touch-specific control and timing:

| Signal/register | Behavior |
| --- | --- |
| `0xfffbe42c` bit 14 | Pen contact, active low; bit 14 set means released |
| `0xfffbe4b0` write 2 | Assert touch chip select |
| `0xfffbe4f0` write 2 | Deassert touch chip select |
| `0xfffec700 + 8` | Decrementing timer used for settling |
| `0x5df` (1503) ticks | Settle after chip select assert, before conversion |
| `0x3f` (63) ticks | Settle after chip select deassert, before final contact check |

The sample core at `0x100dca20` runs this sequence:

1. If contact is already released, return with `pressed = 0`.
2. Take the touch semaphore at `0x10a30b9c` and wait for the `0x5df` settle period.
3. Recheck contact; release the bus and return if the finger lifted.
4. Assert chip select and read X, then Y, with command bytes `0xD9` and `0x99` (8-bit mode, PD01).
5. Deassert chip select, wait `0x3f` ticks, and recheck contact.
6. Call the pressure check at `0x100dc8c0`, which samples Z1 and Z2 with `0xB9` and `0xC9`.
7. Accept the sample only if the pressure result is in `1..849` (`0x351`); otherwise report `pressed = 0`.

Each axis command is sent twice. The first conversion is discarded and the second is used. Each conversion consists of the command and two 8-clock reads. The driver reconstructs a 9-bit value as:

```
value = (byte_a << 1) | (byte_b >> 7)
```

The raw result struct used by the rest of the touch code is six bytes: `s16 raw_x`, `s16 raw_y`, `u8 pressed`, plus padding. The pressure check uses the X value and the Z1/Z2 results in a floating-point calculation scaled by 1000; its exact electrical interpretation is not needed to parse the event stream.

The contact-poll wrapper at `0x100dcb78` waits for contact, delays `0x15f93` (90,003) timer ticks, and then calls the sample core. `0x100dcbac` is a second raw-read routine that calls the same core, but no direct caller was found in this image.

## Cached coordinates

`touch_get` gives another subsystem a way to replace sampling:

| Global | Meaning |
| --- | --- |
| `0x10ac15c8` | Cache valid flag |
| `0x10ac15ca` | Cached raw X |
| `0x10ac15cc` | Cached raw Y |
| `0x10ac15c4` | Previous `pressed` value |

`touch_cache_set` at `0x100e8f4c` writes the flag and both coordinates. Callers at `0x1014bc48` and `0x1014bc56` can therefore publish a coordinate and make `touch_get` skip the TSC2046 read. `touch_reset` at `0x100e8f8c` clears the cache, calls `0x100dc39a`, then calls the contact-poll wrapper.

## Calibration

`0x100663da` applies the matrix at `0x109066e0` (gesture state `0x109066b8` plus `0x28`). The six signed 32-bit values are 16.16 fixed point:

```
screen_x = (a * raw_x + b * raw_y + c) >> 16
screen_y = (d * raw_x + e * raw_y + f) >> 16

screen_x = clamp(screen_x, 0, 479)
screen_y = clamp(screen_y, 0, 271)
```

The default matrix ships at `0x10506034`:

| Coefficient | Raw s32 | 16.16 value |
| --- | ---: | ---: |
| a | 131490 | 2.006378 |
| b | -5221 | -0.079666 |
| c | -742272 | -11.326172 |
| d | 248 | 0.003784 |
| e | -80924 | -1.234802 |
| f | 19211884 | 293.150085 |

These are build defaults, not a per-unit calibration. The initialization routine at `0x10066608` copies them to `0x109066e0`, then tries to read 24 bytes from NV key `0x1046` into the same matrix. If the NV record exists, it replaces the defaults. The routine then copies the resulting matrix to `0x109066f8` (state `+0x40`).

The calibration solver at `0x10066658` turns two three-point sets into the six 16.16 coefficients. Its tail can persist the result to NV key `0x1046` through `0x1013f84e` and `0x1013f4d0`.

## Gesture state machine

The task entry is `0x10066446`. No direct `bl` caller was found, so it is probably reached through a scheduler or task table rather than a normal function call. Each poll calls `touch_get`, then `touch_apply_calibration`.

The state block is at `0x109066b8`:

| Offset | Type | Meaning |
| ---: | --- | --- |
| `+0x00` | `u8` | State: 0 idle, 1 debounce, 2 pressed, 3 release debounce |
| `+0x01` | `u8` | Drag-emit flag; initialized to 1 and cleared on the first press |
| `+0x02` | `u8` | Movement-seen flag used to choose release event 2 or 3 |
| `+0x03` | `u8` | Set at the initial press transition |
| `+0x04` | `s16` | Maximum axis movement since the current base point |
| `+0x06` | `s16` | Down/drag debounce timer |
| `+0x08` | `s16` | Hold-repeat timer |
| `+0x0a` | `s16` | Remaining hold repeats, initialized to 4 |
| `+0x0c` | `s16` | Saved timer restored when a release bounces back to pressed |
| `+0x10` | `s16` | Last calibrated X |
| `+0x12` | `s16` | Last calibrated Y |
| `+0x14` | `u8` | Last calibrated `pressed` |
| `+0x18` | `s16` | Last raw X |
| `+0x1a` | `s16` | Last raw Y |
| `+0x1c` | `u8` | Last raw `pressed` |
| `+0x20` | `s16` | Base calibrated X for movement |
| `+0x22` | `s16` | Base calibrated Y for movement |
| `+0x24` | `u8` | Base calibrated `pressed` |

State transitions:

- **0 idle:** on contact, enter state 1 with timer 2. No event yet.
- **1 debounce:** if contact disappears, return to 0. Otherwise decrement the timer. At zero, enter state 2, set timer 35, repeat timer 20, repeat count 4, clear movement, save the calibrated and raw positions, and emit event 0.
- **2 pressed:** if contact disappears, enter state 3 and save the current timer. Otherwise decrement the timer and update the maximum movement from the base point. If the drag-emit flag is set and either the timer reached zero or movement exceeds 10, emit event 1, set timer 10, update the saved positions, and clear the drag-emit flag.
- **2 pressed, repeat timer:** when the hold timer expires, decrement the remaining repeat count and reload 20 ticks, or reload 10 ticks once the count is exhausted. Each expiry emits event 4.
- **3 release debounce:** if contact returns, go back to state 2 and restore the saved timer. Otherwise decrement the timer; at zero, return to 0 and emit event 3 when the movement flag is set or event 2 when it is clear.

Observed event codes:

| Code | Emitted when |
| ---: | --- |
| 0 | Initial press after the two-poll debounce |
| 1 | Drag/Down-move path while state `+0x01` is nonzero |
| 2 | Release timeout with no movement flag |
| 3 | Release timeout with the movement flag set |
| 4 | Hold repeat, initially every 20 ticks, then every 10 after four repeats |

The code meanings are inferred from the surrounding conditions, not confirmed against a UI symbol table. In particular, the code-1 path is gated by state `+0x01`, which is set to 1 by initialization and cleared on the first press; no other writer to that byte was found in this image.

## Event injection

`0x10066366` builds a message in a 32-byte stack frame:

- `+0x14` (u16) = `0x39`
- `+0x16` (u8) = event code
- `+0x17..0x18` = raw X
- `+0x19..0x1a` = raw Y
- `+0x1c..0x1e` = calibrated X/Y
- `+0x10..0x13` = zero

When the global mode byte at `0x10d15f96` is 3 (the normal UI mode), it also builds a 12-byte payload at `sp + 4`:

| Offset | Contents |
| ---: | --- |
| `+0` | Raw X, `u16` |
| `+2` | Raw Y, `u16` |
| `+4` | Calibrated X, `u16` |
| `+6` | Calibrated Y, `u16` |
| `+8` | Calibrated pressed byte plus padding |

It then calls the event API:

- `0x1017c6d6(0x4a, event_code)` posts the one-byte event.
- `0x1017c60c(0x228, &payload, 12)` posts the coordinate event.

If the mode byte is not 3, the state machine still tracks the touch but these bus writes are skipped. After the dispatch, `0x10064562` is called with the message pointer and `0x108a26a0` is set to 1; this is probably input-activity or display-wake handling and was not resolved further.

## Address summary

| Address | Function |
| --- | --- |
| `0x100dca20` | TSC2046 sample core |
| `0x100dc8c0` | Pressure/contact-resistance check |
| `0x100dcb78` | Contact-poll wrapper |
| `0x100dcbac` | Alternate raw-read routine |
| `0x100e8f4c` | Publish cached coordinate |
| `0x100e8f58` | `touch_get` |
| `0x100e8f8c` | `touch_reset` |
| `0x100663da` | Apply affine calibration |
| `0x10066446` | Gesture/state task |
| `0x10066608` | Touch initialization and NV load |
| `0x10066658` | Three-point calibration solver |
| `0x10066366` | Build and post touch events |
| `0x100edac8` | SPI write byte |
| `0x100ed9da` | SPI read byte |

## Limits

This analysis establishes the stock code path, register use, calibration format, and event layout for one specific image. It does not prove a 660 hardware behavior by itself, does not identify the exact TSC2046 clone, and does not make these addresses stable across software versions. The event-code names are behavioral inferences. Per-unit touch accuracy depends on NV key `0x1046`, not on the ROM defaults shown above.
