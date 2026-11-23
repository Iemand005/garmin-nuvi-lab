#!/usr/bin/env python3
"""Assemble a nüvi 660 Euro (HWID 596) probe.S into a raw ldr.bin payload.

LOCAL CANDIDATE ONLY. Delegates to the shared payload builder and rejects any
source whose header is not HWID 596. No device writes.
"""
try:
    from payload_builder import build_cli
except ModuleNotFoundError:
    from scripts.payload_builder import build_cli


if __name__ == '__main__':
    build_cli(expected_hwid=596, device='nüvi 660 Euro')
