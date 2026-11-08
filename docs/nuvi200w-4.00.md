# nüvi 200W, software 4.00 (HWID 737)

Local analysis of one connected unit. Nothing here has been deployed or executed
on hardware yet. The 5.00/6.20 procedures for the 200 and 350 are not
interchangeable with this model.

## Tested identity

| Field | Value |
| --- | --- |
| Model | nüvi 200W |
| Part number | `006-B0737-00` |
| Software | `400` (4.00) |
| Unit ID | `3389490173` |
| Registration | `2UPVSXT` |
| Internal flash | `G:`, FAT, 515,497,984 bytes |
| Stock USB | `091e:22e1` mass storage |

Firmware came from `G:\Garmin\GUPDATE.GCD` (5,783,040 bytes, SHA-256
`02c052df006fb2799adcbabf09ade05b4973910dc6cd566551ffe2f9d3ef9c2f`). The
`0x2bd` records inside the GCD are the bulk image data; the two candidate blobs
are `analysis/nuvi200w-4.00/gcd/boot-candidate.bin` and `fw-all-candidate.bin`.

## Image bases

`scripts/extract_embedded_image.py` finds the standard Garmin header (branch
word `0xea000002`, end/hwid/version pointers relative to a base, `0xa55a`
footer) without assuming the macOS-only tooling.

- Resident boot: offset `0x2932c` in `boot-candidate.bin`, 167,716 bytes, base
  `0x10000000`. SHA-256
  `536c46d42b39bde4a0f2a659a9f2c7fbf4ef1c56df4c6bc461e0edf5c55e152f`.
- Application: offset `0` in `fw-all-candidate.bin`, 5,436,320 bytes, base
  `0x10040000`. SHA-256
  `a5ebcd44936b6450931eef430c774dc2a2796ce41208ed4b82bdbe2ab9b7d9a6`.
- Staging/entry address for a loaded program: `0x10040000`.

Both headers report HWID 737 and software 400 with the `5a a5` footer. These are
update images extracted from the GCD, not a readback of running device memory.

## SD loader handoff

The application builds `<vol>:/Garmin/Updater/<HWID%04u>/ldr.bin`
(format string at `0x101612bc`; HWID at `0x10426af4` = 737, version at
`0x10426af6`). It calls through `0x100e79fa(0xc, buffer, length, 0)`, which
forwards to `0x10232c2c`: set `r12 = 12`, `r11 = source`, `r10 = length`,
`r9 = 0`, then branch to `0x10000000`.

The resident boot at `0x10000000` compares `r12` with 12, requires the
destination (`0x10040000`) below the source, a nonzero length, and
`source + length <= 0x12000000`. It copies the payload to `0x10040000`, reads
the pointer in payload word 1, checks that its halfword is `0xa55a`, then enters
the veneer at `0x1001e18c`. The veneer sets `r12 = 12`, clears `r9`/`r10`/`r11`,
places `0x10040000` in `r0`, and jumps with CPSR `0xdf` (ARM, IRQ/FIQ
disabled).

A hosted program therefore starts at `0x10040000` with:

- `r0 = 0x10040000`
- `r12 = 12`; `r9 = r10 = r11 = 0`
- `r1 = r2 = r3 = 0`
- ARM state, IRQ and FIQ masked

Only the RAM at and above `0x10040000` is replaced. No flash write occurs on
this path, so a reset reloads stock firmware.

## Display profile (480 x 272)

| Item | Value |
| --- | --- |
| Framebuffers | `0x11f807c0`, `0x11fc03e0` |
| DMA registers | `0xfffee3c0` (B1 start at `+8`, end at `+12`, halfword pairs) |
| DMA span | `0x3fc1e` = 480 x 272 x 2 + 30 |
| Row stride | 960 bytes |
| Pixel header | 32 bytes before pixel 0 |
| LCD control | `0xfffec000` |
| Extra literal | `0x106e15b8` |

These were read from the 4.00 application and are specific to the 200W. The
older 200 profile (`0x11f69f80`/`0x11fb4fc0`, `0x2581e`, stride 640) and the
350 profile do not apply.

## Candidate builder and audit

`scripts/build_nuvi200w_rectangle.py` assembles a guarded 480 x 272 probe with
keystone (ARM only) into `analysis/nuvi200w-rectangle/`:

- 16-byte header: branch to `0x10`, footer/hwid/version pointers.
- Guards: `r12 == 12`; DMA source is one of the two framebuffers; end minus
  start is exactly `0x3fc1e`; the source re-read is unchanged.
- Saves 32 x 32 pixels at (224, 120), inverts them, waits a finite delay,
  restores them, then parks on a branch-to-self.
- Only halfword reads from MMIO and saved/inverted/restored pixel writes plus
  its own scratch area are possible; rejected cases park without writing.

Current candidate: 2,360 bytes, SHA-256
`df2b0c90671cf1f6ed7025537a1ac218fd286168657da112d48d49687cc2d7be`.

`scripts/audit_nuvi200w_rectangle.py` interprets the ARM subset against
synthetic DMA state. It confirms both framebuffers restore, 3,072 halfword
writes at the save/invert/restore sites, the reviewed delay loop, and no writes
for wrong mode, unknown buffer, or wrong DMA length. This is a model, not
hardware emulation.

Rebuild and audit with the local virtual environment:

```
.\.venv\Scripts\python.exe scripts\build_nuvi200w_rectangle.py
.\.venv\Scripts\python.exe scripts\audit_nuvi200w_rectangle.py
```

## Safety and recovery

- The SD `ldr.bin` path replaces RAM above `0x10040000`; it does not program
  flash. Do not use an updater path that writes flash.
- Eject the mounted volume normally before unplugging. Remove the SD card before
  the recovery reset so the loader does not retrigger the RAM program.
- The 200 family uses a power slider reset. The exact 200W procedure has not
  been verified on this unit; confirm it on stock firmware first.
- A successful probe is a 32 x 32 inversion visible to a camera, followed by a
  frozen screen (the program parks). A clean stock boot after reset is the
  recovery check.

## Open items

- No suitable SD card is inserted: the slot reports RAW/empty and the only
  attached large card is exFAT and is not device media. Deployment needs a
  FAT16/FAT32 card of at most 32 GB.
- The 200W reset procedure and the (224, 120) rectangle on the physical panel
  remain unverified.
- Region A before offset `0x2932c` in `boot-candidate.bin` was not fully
  reverse-engineered; it is not needed for this handoff chain.
- The 200W palette-format guard was intentionally omitted to avoid false
  negatives; safety rests on the DMA buffer and length identity.
