#!/usr/bin/env python3
"""Offline, read-only SM-P613 boot.img embedded IKCONFIG exporter.

Explicit opt-in: writes the extracted full kernel .config as a new local
text file. Never uploads firmware, exports ramdisks or changes boot images.
Review the exported config (which may include vendor build paths/strings)
before sharing it with anyone.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path

from audit_stock_firmware import MAX_UNCOMPRESSED_KERNEL, parse_boot

MAX_CONFIG = 4 * 1024 * 1024
IKSTART = b"IKCFG_ST"
IKEND = b"IKCFG_ED"


def _decode_gzip_with_limit(blob: bytes, maximum: int) -> bytes:
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("kernel/config data is not gzip")
    try:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = dec.decompress(blob, maximum + 1)
        if len(raw) > maximum or not dec.eof:
            raise ValueError("gzip payload incomplete or exceeds safety limit")
        raw += dec.flush()
    except zlib.error as error:
        raise ValueError("invalid gzip payload") from error
    if len(raw) > maximum or dec.unused_data:
        raise ValueError("gzip payload too large or contains unexpected trailing bytes")
    return raw


def extract_stock_ikconfig(stock_boot: bytes) -> bytes:
    """Return full stock kernel .config; caller decides where to save it."""
    header = parse_boot(stock_boot)
    if header.get("format") != "android-boot" or header.get("header_version") != 2:
        raise ValueError("expected Samsung Android boot header v2")
    start = header["page_size"]
    size = header["kernel_size"]
    if not (size > 0 and start + size <= len(stock_boot)):
        raise ValueError("kernel payload is missing or beyond boot image")
    kernel = _decode_gzip_with_limit(stock_boot[start : start + size],
                                     MAX_UNCOMPRESSED_KERNEL)
    begin = kernel.find(IKSTART)
    if begin < 0:
        raise ValueError("kernel does not embed IKCONFIG")
    begin += len(IKSTART)
    end = kernel.find(IKEND, begin)
    if end < 0 or end - begin > MAX_CONFIG:
        raise ValueError("invalid embedded IKCONFIG bounds")
    config = _decode_gzip_with_limit(kernel[begin:end], MAX_CONFIG)
    if not (config.startswith(b"#") or config.startswith(b"CONFIG_")):
        raise ValueError("embedded config has an unexpected text format")
    return config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path, required=True, help="Verified original boot.img")
    p.add_argument("--output", type=Path, required=True, help="New local .config output file")
    p.add_argument("--expect-config-sha256", type=str,
                   help="Optional expected plain config SHA256 from prior JSON audit")
    a = p.parse_args(argv)
    try:
        if a.output.exists():
            raise ValueError("output file already exists; choose a new path (no overwrites)")
        if a.boot.resolve() == a.output.resolve():
            raise ValueError("output must not overwrite stock boot image")
        config = extract_stock_ikconfig(a.boot.read_bytes())
        digest = hashlib.sha256(config).hexdigest()
        if a.expect_config_sha256 and digest != a.expect_config_sha256.lower():
            raise ValueError("IKCONFIG SHA256 differs from previous stock audit report")
        a.output.write_bytes(config)
        print(f"Exported stock kernel .config: {len(config)} bytes, SHA256 {digest}")
        print(f"Saved to {a.output}. Review its contents before sharing.")
    except (OSError, ValueError, struct.error) as error:
        print(f"IKCONFIG export failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
