"""Set nüvi 660 display color over private USB vendor request 0x51.

Requires pyusb and a libusb/WinUSB backend bound to VID 091e PID fffe.
Install with: .venv\\Scripts\\pip.exe install pyusb
On Windows, bind the device with Zadig (WinUSB or libusbK) first.
"""

import argparse
import sys

NAMED = {
    "black": 0x0000,
    "white": 0xFFFF,
    "red": 0xF800,
    "green": 0x07E0,
    "blue": 0x001F,
    "yellow": 0xFFE0,
    "cyan": 0x07FF,
    "magenta": 0xF81F,
    "orange": 0xFC00,
    "purple": 0x781F,
}


def parse_color(text):
    s = text.strip().lower()
    if s in NAMED:
        return NAMED[s]
    if s.startswith("#"):
        s = s[1:]
    if s.startswith("0x"):
        s = s[2:]
    if "," in s:
        parts = [int(p, 0) for p in s.split(",")]
        if len(parts) != 3:
            raise ValueError("expected r,g,b")
        r, g, b = parts
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    if len(s) == 6:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    if len(s) == 4:
        return int(s, 16)
    raise ValueError("use rrggbb, 0xRRRR, r,g,b, or a color name")


def main():
    parser = argparse.ArgumentParser(description="Set nüvi 660 display color over USB")
    parser.add_argument("color", nargs="?", help="rrggbb, 0xRRRR, r,g,b, or name")
    parser.add_argument("--list", action="store_true", help="list Garmin USB devices")
    parser.add_argument("--vendor", type=lambda x: int(x, 0), default=0x091E)
    parser.add_argument("--product", type=lambda x: int(x, 0), default=0xFFFE)
    args = parser.parse_args()

    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise SystemExit("pyusb missing: .venv\\Scripts\\pip.exe install pyusb") from exc

    if args.list:
        found = usb.core.find(find_all=True, idVendor=args.vendor)
        rows = list(found)
        if not rows:
            print("no Garmin USB devices found")
        for dev in rows:
            print(f"{dev.idVendor:04x}:{dev.idProduct:04x} bus={dev.bus} addr={dev.address}")
        return

    if args.color is None:
        parser.error("color is required unless --list is used")

    try:
        color = parse_color(args.color)
    except ValueError as exc:
        parser.error(str(exc))

    dev = usb.core.find(idVendor=args.vendor, idProduct=args.product)
    if dev is None:
        others = list(usb.core.find(find_all=True, idVendor=args.vendor))
        if others:
            detail = ", ".join(f"{d.idProduct:04x}" for d in others)
            raise SystemExit(f"VID {args.vendor:04x} found but PID {args.product:04x} missing; saw PID(s): {detail}")
        raise SystemExit(f"device {args.vendor:04x}:{args.product:04x} not found")

    try:
        dev.set_configuration()
    except Exception:
        pass

    if sys.platform.startswith("linux"):
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except Exception:
            pass

    dev.ctrl_transfer(0x40, 0x51, color, 0, b"")
    print(f"sent RGB565 0x{color:04X}")


if __name__ == "__main__":
    main()
