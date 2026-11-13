#!/usr/bin/env python3
"""Validate the *embedded* KernelSU Next ARM64 preinit ELF without flashing.

The pinned upstream requests 64 KiB PT_LOAD congruence. Some old Android
binutils ignore ``-z noseparate-code``; inspect the actual linked runner,
not the command-line flags, before drawing any conclusions.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path


PAGE_SIZES = (4096, 65536)
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PT_GNU_STACK = 0x6474E551
PF_X = 1


def inspect(image: bytes, system_map: str) -> dict:
    addresses = {}
    expected = ("_text", "ksu_preinit_runner_start", "ksu_preinit_runner_end")
    for line in system_map.splitlines():
        columns = line.split()
        if len(columns) == 3 and columns[2] in expected:
            addresses[columns[2]] = int(columns[0], 16)
    missing = [symbol for symbol in expected if symbol not in addresses]
    if missing:
        raise ValueError("Required linked symbols absent: " + ", ".join(missing))

    offset = addresses["ksu_preinit_runner_start"] - addresses["_text"]
    size = addresses["ksu_preinit_runner_end"] - addresses["ksu_preinit_runner_start"]
    if offset < 0 or size < 64 or offset + size > len(image):
        raise ValueError(f"Runner address range outside Image: offset={offset}, size={size}")
    runner = image[offset : offset + size]
    if runner[:4] != b"\x7fELF" or runner[4:7] != b"\x02\x01\x01":
        raise ValueError("Embedded runner is not a 64-bit little-endian ELF")

    (
        elf_type,
        machine,
        version,
        entry,
        ph_offset,
        _sh_offset,
        _elf_flags,
        elf_header_size,
        ph_entry_size,
        ph_count,
        _sh_entry_size,
        _sh_count,
        _sh_names,
    ) = struct.unpack_from("<HHIQQQIHHHHHH", runner, 16)
    if (elf_type, machine, version, elf_header_size, ph_entry_size) != (2, 183, 1, 64, 56):
        raise ValueError("Unexpected preinit ELF type, machine, or header layout")
    if not 1 <= ph_count <= 16 or ph_offset + ph_entry_size * ph_count > len(runner):
        raise ValueError("Program header table exceeds embedded ELF")

    loads = []
    has_entry_segment = False
    has_non_executable_stack = False
    for i in range(ph_count):
        kind, flags, file_offset, vaddr, _paddr, file_size, memory_size, alignment = (
            struct.unpack_from("<IIQQQQQQ", runner, ph_offset + i * ph_entry_size)
        )
        if kind in (PT_INTERP, PT_DYNAMIC):
            raise ValueError("Embedded preinit runner is dynamically linked")
        if kind == PT_GNU_STACK:
            has_non_executable_stack = not bool(flags & PF_X)
        if kind != PT_LOAD:
            continue
        if file_size > memory_size or file_offset + file_size > len(runner):
            raise ValueError(f"PT_LOAD {i} has invalid file/memory extent")
        if alignment < max(PAGE_SIZES):
            raise ValueError(f"PT_LOAD {i} alignment insufficient: {alignment}")
        for page_size in PAGE_SIZES:
            if file_offset % page_size != vaddr % page_size:
                raise ValueError(f"PT_LOAD {i} fails {page_size}-byte page congruence")
        if flags & PF_X and vaddr <= entry < vaddr + memory_size:
            has_entry_segment = True
        loads.append({
            "file_offset": file_offset,
            "vaddr": vaddr,
            "file_bytes": file_size,
            "memory_bytes": memory_size,
            "alignment": alignment,
            "flags": flags,
        })
    if not loads or not has_entry_segment:
        raise ValueError("No executable PT_LOAD contains the ELF entry point")
    if not has_non_executable_stack:
        raise ValueError("GNU_STACK is absent or executable")
    return {
        "RESEARCH_ONLY": "YES",
        "FLASH_ALLOWED": "NO",
        "KSU_PREINIT_ELF_LAYOUT_VALID": True,
        "KSU_PREINIT_ELF_STATIC": True,
        "KSU_PREINIT_RUNNER_SHA256": hashlib.sha256(runner).hexdigest(),
        "KSU_PREINIT_RUNNER_BYTES": size,
        "KSU_PREINIT_RUNNER_IMAGE_OFFSET": offset,
        "KSU_PREINIT_ENTRY": f"0x{entry:x}",
        "PT_LOAD_SEGMENTS": loads,
        "PAGE_CONGRUENCE_VERIFIED": list(PAGE_SIZES),
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--system-map", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.image.read_bytes(), args.system_map.read_text())
    except (ValueError, struct.error) as error:
        report = {"FLASH_ALLOWED": "NO", "KSU_PREINIT_ELF_LAYOUT_VALID": False, "error": str(error)}
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(f"KSU_PREINIT_ELF_LAYOUT_VALID={'YES' if report['KSU_PREINIT_ELF_LAYOUT_VALID'] else 'NO'}")
    print("FLASH_ALLOWED=NO")
    if not report["KSU_PREINIT_ELF_LAYOUT_VALID"]:
        parser.exit(1, "KernelSU preinit ELF layout audit failed: " + report["error"] + "\n")


if __name__ == "__main__":
    main()
