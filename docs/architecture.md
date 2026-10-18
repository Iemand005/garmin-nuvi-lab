# Runtime and protocol

The Mac runs `player_ui.py` (Pillow rendering), reads Spotify metadata through Apple Events, retrieves artwork from the validated Spotify artwork host, and sends changed pixel blocks through a native IOKit helper. The Garmin executes a model-specific ARM program loaded from SD into RAM. It retains the stock-initialized display, DMA, and peripheral configuration where verified.

There is no cloud credential or OAuth token in this experiment. macOS may ask for permission to automate Spotify and to connect the USB accessory.

## Layers

- `experiments/*/probe.S`: guarded RAM entry, framebuffer access, touch acquisition, and private USB EP0 handling.
- `scripts/build_rectangle_probe.py`: Xcode clang assembly, relocation rejection, ELF text extraction, symbols, SHA-256, disassembly.
- `scripts/audit_*.py`: synthetic ARM/register/FIFO checks, error paths, bounded calls, boot-copy handoff models.
- `scripts/*_usb_host.c`: IOKit control requests with identity/capability validation and timeouts.
- `scripts/spotify_player.py`: the 200 host, native event queue, frame tracking, metadata and artwork helpers.
- `scripts/spotify_nuvi350_controls.py`: the 350 host using measured affine touch calibration.
- `scripts/stage_*.py`: dry-run by default, explicit install, configured target identity, pinned prior/candidate hashes, readback verification.

Only one host may own the lab USB interface at a time. Close the active host before launching calibration, another bridge, or a one-shot diagnostic.

## Private USB protocol

The temporary device identifies as VID:PID `091e:fffe`, with a 64-byte EP0. This identity is for this experiment, not a newly assigned public USB product ID.

| Request | Direction | Function |
| --- | --- | --- |
| `51` | OUT | Set bounded legacy RAM value |
| `52` | IN | Legacy status, 16 bytes |
| `53` | OUT | Bounded legacy printable text pairs |
| `54` / `55` | IN / OUT | Peek / acknowledge native release event queue (200) |
| `56` | IN | Capability; image transport requires version 2 |
| `57` | OUT | One 64-byte pixel block, index 0–2399, value 0 |
| `58` | IN | 350 identity and measured display profile, 16 bytes |
| `59` | IN | 350 fixed read-only GPIO/SPI snapshot page 0–2, 16 bytes |
| `5a` | IN | 350 bounded raw touch acquisition, exactly 16 bytes |

Request numbers are hexadecimal. IN uses `bmRequestType=0xc0`; OUT uses `0x40`. The 350 still exposes compatibility queue requests but does not generate native queued button events. Its playback host never treats that empty queue as touch input.

A logical RGB565 frame is 153,600 bytes, transferred in 2,400 independently acknowledged blocks. Host state records only acknowledged blocks. A new SETUP or reset cancels an incomplete OUT transfer. Firmware rejects wrong lengths, indices, request fields, display profiles, and unsupported initialization states.

## 350 raw reply

Eight little-endian halfwords: magic `0x3558`, version 1, flags, raw axis A, raw axis B, failed-transfer number, SPI status, GPIO input.

Flags: 1 initial contact; 2 valid coordinates; 4 rejected configuration; 8 transfer/timer failure; 16 contact inconsistent or released before the final check; 32 out-of-range coordinates. Only flags 3 is a valid position. Only flags 0 qualifies a clean lift in the host. Guard or transfer errors stop playback control.
