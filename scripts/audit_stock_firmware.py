#!/usr/bin/env python3
"""Offline, read-only stock firmware metadata collector for SM-P613.

No firmware bytes or private data are uploaded. Output contains file and
embedded DTB/DTBO SHA256, boot header/layout and compressed kernel hashes only.
Python 3 stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path


FDT_MAGIC = b"\xd0\x0d\xfe\xed"
DTBO_MAGIC = 0xD7B7AB1E
MAX_FDT = 8 * 1024 * 1024
MAX_UNCOMPRESSED_KERNEL = 128 * 1024 * 1024


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


def aligned_size(size: int, page_size: int) -> int:
    return (size + page_size - 1) // page_size * page_size


def parse_boot(data: bytes) -> dict:
    """Parse Android boot header. Avoid collecting cmdline, names or ramdisk."""
    if len(data) < 64 or data[:8] != b"ANDROID!":
        return {"format": "not-standard-android-boot-header"}
    version = struct.unpack_from("<I", data, 40)[0]
    if version > 4:
        return {"format": "android-boot-unrecognized-version", "header_version": version}
    if version <= 2:
        kernel_size, _, ramdisk_size, _, second_size, _, _, page_size = struct.unpack_from("<8I", data, 8)
        if page_size < 512 or page_size & (page_size - 1):
            raise ValueError("invalid boot page size")
        result = {"format": "android-boot", "header_version": version, "page_size": page_size,
                  "kernel_size": kernel_size, "ramdisk_size": ramdisk_size, "second_size": second_size}
        # AOSP boot_img_hdr_v1/v2 packed offsets (bootimg.h). Do not
        # interpret a vendor image as one of the newer header versions.
        if version >= 1:
            if len(data) < 1648:
                raise ValueError("truncated boot header v1")
            recovery_size, recovery_offset, header_size = struct.unpack_from("<IQI", data, 1632)
            result.update({"recovery_dtbo_size": recovery_size,
                           "recovery_dtbo_offset": recovery_offset,
                           "header_size": header_size})
        if version == 2:
            if len(data) < 1660:
                raise ValueError("truncated boot header v2")
            dtb_size, dtb_addr = struct.unpack_from("<IQ", data, 1648)
            result.update({"dtb_size": dtb_size,
                           "dtb_addr": f"0x{dtb_addr:x}"})
        return result
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from("<4I", data, 8)
    return {"format": "android-boot", "header_version": version, "header_size": header_size,
            "kernel_size": kernel_size, "ramdisk_size": ramdisk_size}


def embedded_ikconfig_metadata(image: bytes) -> dict:
    """Inspect only ABI-related Kconfig fields; never export the full config."""
    begin = image.find(b"IKCFG_ST")
    if begin < 0:
        return {"status": "not-found"}
    begin += len(b"IKCFG_ST")
    end = image.find(b"IKCFG_ED", begin)
    if end < 0 or end - begin > 4 * 1024 * 1024:
        return {"status": "invalid-ikconfig-boundaries"}
    try:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        plain = dec.decompress(image[begin:end], 4 * 1024 * 1024 + 1)
        if not dec.eof or len(plain) > 4 * 1024 * 1024:
            return {"status": "invalid-or-oversized-ikconfig"}
        plain += dec.flush()
        if len(plain) > 4 * 1024 * 1024:
            return {"status": "oversized-ikconfig"}
    except zlib.error:
        return {"status": "invalid-gzip-ikconfig"}
    wanted = {
        "CONFIG_LOCALVERSION", "CONFIG_LOCALVERSION_AUTO", "CONFIG_MODVERSIONS",
        "CONFIG_MODULE_SIG", "CONFIG_MODULE_SIG_FORCE", "CONFIG_MODULE_SIG_ALL",
        "CONFIG_MODULE_SIG_SHA512", "CONFIG_KPROBES", "CONFIG_KALLSYMS",
        "CONFIG_KALLSYMS_ALL", "CONFIG_IKCONFIG", "CONFIG_IKCONFIG_PROC",
        "CONFIG_BUILD_ARM64_DT_OVERLAY", "CONFIG_MODULE_SIG_KEY",
    }
    selected = {}
    for row in plain.decode("utf-8", "replace").splitlines():
        if row.startswith("CONFIG_") and "=" in row:
            name, value = row.split("=", 1)
            if name in wanted:
                selected[name] = value
        elif row.startswith("# CONFIG_") and row.endswith(" is not set"):
            name = row[2:].split(" ", 1)[0]
            if name in wanted:
                selected[name] = "n"
    return {"status": "found", "size_bytes": len(plain),
            "sha256": hashlib.sha256(plain).hexdigest(), "selected": selected}


def boot_payload_metadata(data: bytes, header: dict) -> dict:
    """Hash the stock kernel segment; safely inspect gzip without exposing bytes."""
    if header.get("format") != "android-boot" or header.get("header_version", 5) > 2:
        return {"format": "unsupported-header-for-kernel-audit"}
    offset = header["page_size"]
    size = header["kernel_size"]
    if not (size > 0 and offset + size <= len(data)):
        raise ValueError("stock kernel payload extends beyond boot image")
    payload = data[offset : offset + size]
    magic = payload[:8]
    compression = (
        "gzip" if magic.startswith(b"\x1f\x8b")
        else "lz4-frame" if magic.startswith(b"\x04\x22\x4d\x18")
        else "lz4-legacy" if magic.startswith(b"\x02\x21\x4c\x18")
        else "xz" if magic.startswith(b"\xfd7zXZ\x00")
        else "zstd" if magic.startswith(b"\x28\xb5\x2f\xfd")
        else "unknown-or-raw"
    )
    result = {"offset_bytes": offset, "size_bytes": size,
              "sha256": hashlib.sha256(payload).hexdigest(), "compression": compression}
    if compression == "gzip":
        try:
            dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = dec.decompress(payload, MAX_UNCOMPRESSED_KERNEL + 1)
            if len(raw) > MAX_UNCOMPRESSED_KERNEL:
                result["gzip_status"] = "decompressed-size-exceeds-safety-limit"
            elif not dec.eof:
                result["gzip_status"] = "incomplete-or-size-limited-stream"
            else:
                raw += dec.flush()
                if len(raw) > MAX_UNCOMPRESSED_KERNEL:
                    result["gzip_status"] = "decompressed-size-exceeds-safety-limit"
                else:
                    result["gzip_status"] = "complete"
                    result["gzip_trailing_bytes"] = len(dec.unused_data)
                    result["decompressed_size_bytes"] = len(raw)
                    result["decompressed_sha256"] = hashlib.sha256(raw).hexdigest()
                    result["embedded_ikconfig"] = embedded_ikconfig_metadata(raw)
                    result["arm64_image_magic"] = (
                        len(raw) >= 60 and struct.unpack_from("<I", raw, 56)[0] == 0x644D5241
                    )
                    match = re.search(rb"Linux version ([^\s\x00]{1,120})", raw)
                    if match:
                        result["embedded_linux_release"] = match.group(1).decode("ascii", "replace")
        except zlib.error:
            result["gzip_status"] = "invalid-gzip-stream"
    return result


def boot_layout_metadata(data: bytes, header: dict) -> dict:
    """Validate boot v0-v2 segment offsets from AOSP's alignment rules."""
    if header.get("format") != "android-boot" or header.get("header_version", 5) > 2:
        return {"format": "unsupported-header-for-layout-audit"}
    page_size = header["page_size"]
    kernel_end = page_size + aligned_size(header["kernel_size"], page_size)
    ramdisk_end = kernel_end + aligned_size(header["ramdisk_size"], page_size)
    second_end = ramdisk_end + aligned_size(header["second_size"], page_size)
    if second_end > len(data):
        raise ValueError("boot image segments exceed file size")
    result = {"kernel_offset": page_size, "ramdisk_offset": kernel_end,
              "second_offset": ramdisk_end}
    recovery_size = header.get("recovery_dtbo_size", 0)
    recovery_offset = header.get("recovery_dtbo_offset", 0)
    if recovery_size:
        if recovery_offset != second_end or recovery_offset + recovery_size > len(data):
            raise ValueError("recovery DTBO header offset is inconsistent")
        result["recovery_dtbo"] = {
            "offset_bytes": recovery_offset, "size_bytes": recovery_size,
            "sha256": hashlib.sha256(data[recovery_offset : recovery_offset + recovery_size]).hexdigest(),
            "table": parse_dtbo(data[recovery_offset : recovery_offset + recovery_size]),
        }
    if header.get("header_version") == 2 and header.get("dtb_size", 0):
        dtb_offset = second_end + aligned_size(recovery_size, page_size)
        size = header["dtb_size"]
        if dtb_offset + size > len(data):
            raise ValueError("DTB region exceeds boot image")
        result["dtb_region"] = {
            "offset_bytes": dtb_offset, "size_bytes": size,
            "sha256": hashlib.sha256(data[dtb_offset : dtb_offset + size]).hexdigest(),
        }
    return result


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
        output["kernel_payload"] = boot_payload_metadata(data, output["boot"])
        output["boot_layout"] = boot_layout_metadata(data, output["boot"])
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
    report = {"audit_schema": 3, "mode": "read-only / offline / metadata only",
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
