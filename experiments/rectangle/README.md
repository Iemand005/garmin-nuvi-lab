# Original-motherboard rectangle probe

> Historical lab-stage notes. See the [current development guide](../../docs/development.md) for the working player and local setup.

**State: installed and hash-verified on the approved SD card; visible effect reported.**
On 2026-10-17 the user observed the distinctive 32×32 inversion on the startup
screen after Loading Maps, followed by a frozen screen. This is strong physical
evidence of native payload execution and framebuffer control. Exact trigger,
pixel restoration, and post-probe baseline recovery remain to be confirmed.
Physical RESET recovery was verified before deployment. See notes/current-status.md.

## Exact candidate

Source: `probe.S`. Build: `python3 scripts/build_rectangle_probe.py`.
Audit: `python3 scripts/audit_rectangle_probe.py`.
Candidate: `analysis/rectangle-probe/rectangle-candidate.bin` (2,468 bytes).
SHA-256: `4e1068d56579ec68146a2b795a4dd487224b40f415986404beaa1c91da57e1fd`.
The binary is assembled with the existing Xcode clang. Extraction refuses
unresolved ELF relocations. No tools or dependencies were installed.

Target is exclusively nüvi 200, HWID 0660 / software 5.00. The nested boot
image comes from its stored update, not a readback of the installed boot stage.
The reported distinctive rectangle now supports compatibility for this specific
unit and payload; it does not validate other devices or stock maintenance loaders.

## What the code does

The probe starts at `0x10040000` using the observed mode-12 loader convention.
It has no stack, subroutine calls, filesystem code, flash-programming code,
stock RAM-loader initialization, or writes to peripheral registers.

It reads the LCD and DMA registers, and requires:

- Mode 12; LCD enabled; TFT; palette-and-data loading.
- Timing fields indicating exactly 320×240 pixels.
- Programmed DMA B1 source equal to `0x11f69f80` or `0x11fb4fc0`.
- DMA end-minus-start exactly `0x2581e`.
- Palette prefix's format field equal to `0x4000`.
- Same DMA source on a second snapshot.

On a match it saves a 32×32 rectangle at x=144,y=104 into its own scratch
space, XORs each 16-bit pixel with `0xffff`, waits a finite CPU-loop delay,
restores every saved pixel, and parks in a branch-to-self loop. **It does not
return to Garmin's menu.** A rejected configuration also parks, with no pixel
writes. The display, watchdog, or peripheral state may prevent any visible
change; no visible rectangle would therefore be inconclusive.

Expected success observation: a small inverted square near the center of the
screen flashes briefly, then the previous pixels return. Delay wall time is
uncalibrated. Film the screen before inserting the card to capture a short flash.

The only three store sites are scratch-save, framebuffer-invert, and
framebuffer-restore. For a successful modeled run they execute 3,072 halfword
writes: 1,024 to scratch and 2,048 to the same 1,024 screen pixels. The other
framebuffer, prefix, and all surrounding pixels remain unchanged in the model.

## Evidence for pixel layout

TI OMAP5912 Display Interface Reference Guide SPRU764B, page 19, documents
16-bit TFT pixels as RGB565 and a required 32-byte palette prefix. This related
processor reference alone is not proof of the installed processor.
https://www.ti.com/lit/ug/spru764b/spru764b.pdf

The stronger device-specific cross-check is this unit's main firmware raw
`0x9f6f4..0x9f744`: buffer switching writes the two source addresses and their
end address to the LCD DMA registers. Raw literal offsets `0x9f8bc..0x9f8c4`
contain DMA base `0xfffee3c0` and those two prefix addresses. The nested boot
display setup initializes the same prefixes and fills 153,600 pixel bytes.
The test leaves all timing and backlight settings untouched.

## Offline audit and its limits

`analysis/rectangle-probe/audit.json` records ten interpreted cases. Both known
buffers produce the intended inversion and complete restoration. Wrong mode,
disabled LCD, wrong width/height, unsupported palette-loading mode, unknown
buffer, wrong DMA length, and wrong palette format stop with zero writes.

The interpreter refuses unsupported instructions and any write outside the
selected 32×32 pixel area or the candidate's 2,048-byte scratch area. It checks
the inverted frame before accelerating the exact two-instruction delay loop.
It does not emulate LCD scanout, DMA behavior, interrupts, MMU/cache behavior,
watchdogs, power, or the entire preceding firmware. This is not proof of
electrical operation or universal safety on the device.

## Removable-media plan

Use an identified spare FAT16/FAT32 card. Do not format it automatically. Do
not target the mounted GARMIN volume. Preserve all existing card files; if the
target updater folder already exists, stop rather than replacing its contents.

The planned sole payload file is `/Garmin/Updater/0660/ldr.bin` on the card.
No `update.txt`, stock boot loader, GCD, or firmware-update package is needed
for this custom payload. The main firmware caller raw `0x11fa5a` passes volume
index 1 to its loader, which formats `%u:/Garmin/Updater/%04u/ldr.bin`.
Its preceding check requires a nonempty loader and skips it if a matching
`last_id.bin` is present. These are disassembly conclusions; triggering on
card insertion still needs physical verification.

Before inserting the prepared card:

1. Confirm a documented reset method that can recover a stopped CPU. A reset
   button is preferable; do not assume the ordinary on/off switch will work.
   Test reset on normal firmware with no test card inserted, after safe eject.
2. Confirm normal USB storage returns after reset. Keep the existing local
   original firmware copies and partial backups; no new full backup is required.
3. Copy and read-back-verify the exact candidate on the spare card, then safely
   eject the card. Keep it out of the Garmin until ready to observe the test.
4. With the Garmin normally running, start filming and insert the card.
   Observe briefly. It may flash the rectangle, remain unchanged, or reset.
5. Remove the test card before resetting the unit so the loader cannot trigger
   again. Use the verified reset method, then confirm USB storage is accessible.

Removing the card prevents this specific SD-file trigger on a later boot; it
is not a guarantee against every possible crash or device fault. The full
launch/recovery sequence remains untested. No battery disconnection, firmware
update, internal-file changes, or electrical modifications are part of this test.
