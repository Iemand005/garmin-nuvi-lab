# Build and development

Run commands from the repository root. The tested host is macOS with Python 3.9 and Pillow 11.3; rendering uses the installed SFNS and Menlo fonts. Native hosts use IOKit/CoreFoundation. ARM assembly uses Xcode clang and llvm-objdump, without installing a cross-linker.

## Initialize local outputs

```sh
python3 -m pip install -r requirements.txt
python3 scripts/prepare_workspace.py
```

`analysis/`, `evidence/`, `backups/`, `.local/`, `notes/`, and downloaded `research/` material are ignored. Device firmware, maps, XML, licenses, tracks, images, logs, and calibration do not belong in commits.

## Configure device identities

Copy `config/targets.example.json` to `.local/targets.json`. Read the **VolumeUUID** from `diskutil info -plist /Volumes/NAME` for each actual volume, then replace the placeholders locally. Do not use a remembered disk number, a device hardware ID, or a copied example UUID. Leave unknown identities unconfigured; tools should refuse them.

The `test_sd` target must be the removable FAT card in the Mac's SD reader, not Garmin internal storage or the card exposed over Garmin USB. Existing stagers also require reviewed candidate hashes, matching audit reports, and an expected previous loader. Configuring a UUID does not bypass those checks or make a new device compatible.

Do not run a stager merely to inspect its code. It can query mounted storage even in planning mode. Hardware writes need explicit approval and a reviewed recovery path; use normal ejection afterward. Private local configuration retains the original lab identities without publishing them.

## Offline checks

```sh
python3 scripts/check_player_host.py
python3 scripts/check_nuvi350_encoding.py
python3 scripts/check_nuvi350_input.py
python3 scripts/check_nuvi350_touch_capture.py
```

These check frame tracking, bounded artwork URLs, event/pressed-state behavior, transpose/RGB565 packing, calibrated hit regions, hold suppression, drag cancellation, and inconsistent-contact handling. The input tests use synthetic calibration, not the private measurement file used by the live device.

## Native build and audits

```sh
python3 scripts/build_rectangle_probe.py --experiment player
python3 scripts/build_rectangle_probe.py --experiment nuvi350-touchxy2
```

Outputs go into `analysis/<experiment>-probe/`: ELF object, disassembly, candidate bytes, symbol map, and SHA-256. Generated `.rgb565` assets under `experiments/` are lab graphics, not Garmin firmware. The matching `make_*_probe.py` scripts document how they were generated; changing fonts or regenerating assets can change pinned build hashes.

The matching audits are `audit_player_probe.py` and `audit_nuvi350_touchxy2.py`. The latter covers the display/USB guards, all pixel blocks, setup/completion ordering, malformed requests, raw sampling, per-transfer timeout cleanup, contact-mode regression, timer wrap, and a stuck settling counter. These are synthetic checks, not electrical or complete hardware emulation.

Full audits need the corresponding resident boot candidate under `analysis/gcd/` for the 200 and `analysis/nuvi350/gcd/` for the 350. Firmware is intentionally not shipped. `inspect_gcd.py INPUT OUTPUT_DIR` inventories and extracts selected records from an owner's GCD copy; `wrap_arm_elf.py` and `disasm_window.py` support local analysis. `extract_nested_boot.py` is specific to the reviewed 200 image. The reviewed 350 nested resident candidate is at boot-image offset `0x2766c`, size 141044; verify its header/identity/footer against the analysis before treating it as a handoff input. Update images are not running-flash readbacks.

## Compile native USB hosts

```sh
xcrun clang -Wall -Wextra -Werror scripts/player_usb_host.c \
  -framework IOKit -framework CoreFoundation \
  -o analysis/player/player-usb-host
xcrun clang -Wall -Wextra -Werror scripts/nuvi350_usb_host.c \
  -framework IOKit -framework CoreFoundation \
  -o analysis/nuvi350/usb/nuvi350-touchxy-host
```

Other display-only diagnostic scripts use `analysis/nuvi350/usb/nuvi350-usb-host` or `nuvi350-touch-host`; compile the same C source to the required name if using them. The host checks native identity and capabilities before ready. Only one host should open the lab interface at a time.

## Run against an already reviewed RAM payload

The following commands require the correct native program already running on the Garmin, no mounted Garmin storage, and an appropriate macOS USB-accessory approval. They do not stage or flash firmware:

```sh
# 200: native queued release events drive playback.
python3 scripts/spotify_player.py --run --seconds 1800

# 350: first measure the actual unit, then run its calibrated player.
python3 scripts/nuvi350_touch_xy.py --seconds 600
python3 scripts/spotify_nuvi350_controls.py --seconds 1800
```

Run the two 350 commands sequentially, closing calibration before starting the player. Calibration asks for five target holds/lifts, writes `evidence/nuvi350/touch-calibration.json`, and shows a crosshair. Confirm tracking before using playback controls. Calibration and player input stop on rejected controller states or persistent inconsistency.

The 350 player requires a clean idle state before it arms, two good samples for a press, and two clean pen-up samples for release. A held button fires once. Leaving a captured button cancels it. No playback action is retried after an ambiguous failure. The current sampled path can miss short taps; a native event queue is a possible future improvement.

Ctrl-C closes a bridge. The displayed RAM frame can remain after the host exits. To return to the stock UI, normally eject any mounted Garmin media, remove the test SD, and use the model's documented reset procedure. No factory reset is part of this workflow.
