#!/usr/bin/env python3
"""Offline, read-only stock firmware metadata collector for SM-P613.

No firmware bytes or private data are uploaded. Output contains file and
embedded DTB/DTBO SHA256, boot header fields and hardware identifiers only.
Python 3 stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


FDT_MAGIC = b"\xd0\x0d\xfe\xed"
DTBO_MAGIC = 0xD7B7AB1E
MAX_FDT = 8 * 1024 * 1024


def be32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def fdt_metadata(data: bytes, offset: int = 0) -> dict:
    """Validate an FDT and inspect root properties; no external dtc needed."""
    if offset < 0 or offset + 40 > len(data) or data[offset : offset + 4] != FDT_MAGIC:
        raise ValueError("missing FDT header")
    total = be32(data, offset + 4)
    off_struct = be32(data, offset + 8)
    off_strings = be32(data, offset + 12)
    version = be32(data, offset + 20)
    size_strings = be32(data, offset + 32)
    size_struct = be32(data, offset + 36)
    if not (40 <= total <= MAX_FDT and offset + total <= len(data)):
        raise ValueError("invalid FDT size")
    if not (16 <= version <= 20):
        raise ValueError("unsupported FDT version")
    if off_struct + size_struct > total or off_strings + size_strings > total:
        raise ValueError("invalid FDT structure/string bounds")
    structs = data[offset + off_struct : offset + off_struct + size_struct]
    strings = data[offset + off_strings : offset + off_strings + size_strings]
    pos = 0
    depth = 0
    root: dict[str, bytes] = {}
    saw_end = False
    while pos + 4 <= len(structs):
        token = be32(structs, pos)
        pos += 4
        if token == 1:  # FDT_BEGIN_NODE
            end = structs.find(b"\0", pos)
            if end < 0:
                raise ValueError("invalid FDT node name")
            pos = (end + 4) & ~3
            depth += 1
        elif token == 2:  # FDT_END_NODE
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced FDT nodes")
        elif token == 3:  # FDT_PROP
            if pos + 8 > len(structs):
                raise ValueError("truncated FDT property")
            length = be32(structs, pos)
            nameoff = be32(structs, pos + 4)
            pos += 8
            if length > len(structs) - pos or nameoff >= len(strings):
                raise ValueError("invalid FDT property bounds")
            end = strings.find(b"\0", nameoff)
            if end < 0:
                raise ValueError("invalid FDT property name")
            if depth == 1:
                name = strings[nameoff:end].decode("ascii", "replace")
                root[name] = structs[pos : pos + length]
            pos = (pos + length + 3) & ~3
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            if depth != 0:
                raise ValueError("unbalanced FDT end")
            saw_end = True
            break
        else:
            raise ValueError(f"unknown FDT token {token}")
    if not saw_end:
        raise ValueError("missing FDT_END token")

    def text_prop(name: str):
        raw = root.get(name)
        return [x.decode("utf-8", "replace") for x in raw.rstrip(b"\0").split(b"\0")] if raw else []

    def ints_prop(name: str):
        raw = root.get(name)
        return [f"0x{be32(raw, i):x}" for i in range(0, len(raw), 4)] if raw and len(raw) % 4 == 0 else []

    return {
        "sha256": hashlib.sha256(data[offset : offset + total]).hexdigest(),
        "fdt_total_bytes": total,
        "model": text_prop("model"),
        "compatible": text_prop("compatible"),
        "qcom_board_id": ints_prop("qcom,board-id"),
        "qcom_msm_id": ints_prop("qcom,msm-id"),
        "qcom_pmic_id": ints_prop("qcom,pmic-id"),
        "dtbo_version": ints_prop("dtbo-version"),
    }


def parse_dtbo(data: bytes) -> dict:
    """Parse Android DTBO table or a raw FDT blob from a source build."""
    if data[:4] == FDT_MAGIC:
        return {"format": "raw-fdt", "entries": [{"index": 0, "fdt": fdt_metadata(data)}]}
    if len(data) < 32 or be32(data, 0) != DTBO_MAGIC:
        return {"format": "not-android-dtbo-or-raw-fdt"}
    magic, total, header_size, entry_size, count, entries_off, page_size, version = struct.unpack_from(">8I", data)
    if magic != DTBO_MAGIC or not (32 <= header_size <= len(data)) or total > len(data):
        raise ValueError("invalid Android DTBO header")
    if not (32 <= entry_size <= 256 and count <= 512 and entries_off + entry_size * count <= total):
        raise ValueError("invalid Android DTBO entry table")
    entries = []
    for i in range(count):
        off = entries_off + i * entry_size
        dt_size, dt_off, dt_id, dt_rev = struct.unpack_from(">4I", data, off)
        if dt_off + dt_size > total or dt_size < 40:
            raise ValueError(f"invalid DTBO entry {i} range")
        entry = {"index": i, "dt_size": dt_size, "id": dt_id, "rev": dt_rev}
        entry["fdt"] = fdt_metadata(data[dt_off : dt_off + dt_size])
        entries.append(entry)
    return {"format": "android-dtbo-table", "version": version, "page_size": page_size, "entries": entries}


def parse_boot(data: bytes) -> dict:
    if len(data) < 64 or data[:8] != b"ANDROID!":
        return {"format": "not-standard-android-boot-header"}
    version = struct.unpack_from("<I", data, 40)[0]
    if version > 4:
        return {"format": "android-boot-unrecognized-version", "header_version": version}
    if version <= 2:
        kernel_size, _, ramdisk_size, _, second_size, _, _, page_size = struct.unpack_from("<8I", data, 8)
        if page_size < 512 or page_size & (page_size - 1):
            raise ValueError("invalid boot page size")
        return {"format": "android-boot", "header_version": version, "page_size": page_size,
                "kernel_size": kernel_size, "ramdisk_size": ramdisk_size, "second_size": second_size}
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from("<4I", data, 8)
    return {"format": "android-boot", "header_version": version, "header_size": header_size,
            "kernel_size": kernel_size, "ramdisk_size": ramdisk_size}


def scan_embedded_fdts(data: bytes) -> list[dict]:
    found = []
    start = 0
    while True:
        offset = data.find(FDT_MAGIC, start)
        if offset < 0:
            return found
        start = offset + 4
        try:
            fdt = fdt_metadata(data, offset)
        except ValueError:
            continue
        found.append({"offset_bytes": offset, "fdt": fdt})
        if len(found) >= 100:
            return found


def inspect(path: Path, kind: str) -> dict:
    data = path.read_bytes()
    output = {"filename": path.name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if data.startswith(b"\x04\x22\x4d\x18"):
        output["format"] = "lz4-frame-compressed; decompress to .img before inspection"
    elif kind == "dtbo":
        output["dtbo"] = parse_dtbo(data)
    else:
        output["boot"] = parse_boot(data)
        output["embedded_fdts"] = scan_embedded_fdts(data)
    return output


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path, help="Original P613XXS8CYE1 boot.img")
    p.add_argument("--recovery", type=Path, help="Original recovery.img")
    p.add_argument("--dtbo", type=Path, help="Original dtbo.img, if present")
    p.add_argument("--output", type=Path, help="Write JSON report to this file")
    a = p.parse_args(argv)
    if not any([a.boot, a.recovery, a.dtbo]):
        p.error("specify at least one of --boot, --recovery or --dtbo")
    report = {"audit_schema": 2, "mode": "read-only / offline / metadata only",
              "caution": "Build compatibility and bootability cannot be inferred from these hashes alone.",
              "files": {}}
    try:
        for kind in ("boot", "recovery", "dtbo"):
            path = getattr(a, kind)
            if path is not None:
                report["files"][kind] = inspect(path, kind)
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if a.output:
            a.output.write_text(text, encoding="utf-8")
            print(f"Wrote {a.output}")
        else:
            print(text, end="")
    except (OSError, ValueError, struct.error) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
