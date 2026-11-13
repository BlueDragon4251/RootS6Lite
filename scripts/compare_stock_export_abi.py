#!/usr/bin/env python3
"""Compare verified Samsung OEM kernel export CRCs with a research control.

No firmware repacking, device access, or flashing. This reconstructs the
non-GPL and GPL `__kcrctab` arrays from the **raw ARM64 Image**, locating
them through long unique reference anchors and the contiguous `__kstrtab`
name list. It hard-checks the inferred name-to-CRC mapping against the
control's System.map and Module.symvers and checks normal/GPL group parity.

The reference may differ from OEM in source/ABI. Outputs are a forensic
comparison, *not* a guarantee of module compatibility or bootability.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile


STOCK_IMAGE_SHA256 = "14defad3fe7854da3cadc43b2c01e96a48a27a4a0e847043c989c45c66fb8228"
RESEARCH_SYMVERS_SHA256 = "a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94"
SYMBOL = re.compile(r"^([0-9a-fA-F]{16}) [a-zA-Z] (__ksymtab_|__kstrtab_)(\S+)$")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def unique_anchor(haystack: bytes, needle: bytes, label: str) -> int:
    if len(needle) < 32:
        raise ValueError(f"{label}: anchor too short")
    first = haystack.find(needle)
    if first < 0 or haystack.find(needle, first + 1) >= 0:
        raise ValueError(f"{label}: anchor missing or not unique")
    return first


def nul_names(image: bytes, start: int, count: int) -> list[str]:
    if not 0 <= start < len(image):
        raise ValueError("invalid kstrtab offset")
    # Symbol names are NUL-terminated (and limited in size); do not consume
    # unbounded kernel data when encountering an invalid string table.
    names = []
    cursor = start
    for _ in range(count):
        end = image.find(b"\x00", cursor, min(cursor + 256, len(image)))
        if end <= cursor:
            raise ValueError("invalid or unterminated exported symbol name")
        name = image[cursor:end].decode("ascii")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.]*", name):
            raise ValueError(f"unexpected exported symbol name {name!r}")
        names.append(name)
        cursor = end + 1
    if len(set(names)) != len(names):
        raise ValueError("duplicate export name in kstrtab")
    return names


def control_map(content: str) -> tuple[dict[str, int], list[str], list[str], int]:
    addresses: dict[str, int] = {}
    entries: list[tuple[int, str]] = []
    straddrs: list[int] = []
    for line in content.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        addr, _kind, symbol = parts
        try:
            value = int(addr, 16)
        except ValueError:
            continue
        if symbol in (
            "_text", "__start___ksymtab", "__start___ksymtab_gpl",
            "__stop___ksymtab_gpl", "__start___kcrctab",
            "__start___kcrctab_gpl", "__stop___kcrctab_gpl",
        ):
            addresses[symbol] = value
        elif symbol.startswith("__ksymtab_"):
            entries.append((value, symbol[len("__ksymtab_"):]))
        elif symbol.startswith("__kstrtab_"):
            straddrs.append(value)
    if len(addresses) != 7 or not straddrs:
        raise ValueError("missing reference linker boundary symbol")
    entries.sort()
    normal_start = addresses["__start___ksymtab"]
    gpl_start = addresses["__start___ksymtab_gpl"]
    stop = addresses["__stop___ksymtab_gpl"]
    if [a for a, _ in entries] != list(range(normal_start, stop, 16)):
        raise ValueError("control ksymtab entries are not contiguous 16-byte entries")
    normal = [name for addr, name in entries if addr < gpl_start]
    gpl = [name for addr, name in entries if addr >= gpl_start]
    if normal != sorted(normal) or gpl != sorted(gpl):
        raise ValueError("control ksymtab group is not name-sorted")
    if (gpl_start - normal_start) // 16 != len(normal):
        raise ValueError("bad reference normal/GPL split")
    return addresses, normal, gpl, min(straddrs)


def compare(stock_image: bytes, artifact: zipfile.ZipFile) -> dict:
    if sha256(stock_image) != STOCK_IMAGE_SHA256:
        raise ValueError("stock Image does not match authenticated CYE1 digest")
    control_image = artifact.read("_out/arch/arm64/boot/Image")
    symvers = artifact.read("_out/Module.symvers")
    if sha256(symvers) != RESEARCH_SYMVERS_SHA256:
        raise ValueError("research control Module.symvers digest mismatch")
    refs = {}
    for line in symvers.decode().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            refs[parts[1]] = int(parts[0], 16)
    addresses, normal, gpl, kstr_addr = control_map(
        artifact.read("_out/System.map").decode()
    )
    base = addresses["_text"]
    count = len(normal) + len(gpl)
    crc_start = addresses["__start___kcrctab"] - base
    crc_end = addresses["__stop___kcrctab_gpl"] - base
    kstr_start = kstr_addr - base
    if crc_end - crc_start != count * 4 or crc_end != kstr_start:
        raise ValueError("control CRC table and kstrtab are not contiguous")
    research_crcs = struct.unpack_from(f"<{count}I", control_image, crc_start)
    control_names = normal + gpl
    if set(nul_names(control_image, kstr_start, count)) != set(control_names):
        raise ValueError("reference linker names disagree with kstrtab contents")
    if any(research_crcs[i] != refs[name] for i, name in enumerate(control_names)):
        raise ValueError("reference CRC arrays disagree with Module.symvers names")

    # Require independent unique anchors for both the start of the CRC table
    # and immediately following kstrtab in the stock raw Image.
    stock_start = unique_anchor(stock_image, control_image[crc_start:crc_start + 64], "CRC")
    stock_strings = unique_anchor(stock_image, control_image[kstr_start:kstr_start + 64], "kstrtab")
    delta = stock_strings - stock_start
    if delta <= 0 or delta % 4:
        raise ValueError("stock kcrctab/kstrtab offsets inconsistent")
    stock_count = delta // 4
    if stock_count < count or stock_count > count + 200:
        raise ValueError("unexpected stock exported symbol count")
    stock_names = nul_names(stock_image, stock_strings, stock_count)
    new_names = sorted(set(stock_names) - set(control_names))
    removed_names = sorted(set(control_names) - set(stock_names))
    if removed_names or stock_count != count + len(new_names):
        raise ValueError("stock exports removed or duplicated: cannot assign CRC names safely")
    stock_crcs = struct.unpack_from(f"<{stock_count}I", stock_image, stock_start)

    # The old Samsung `__ksymtab` and `__ksymtab_gpl` sort by name.
    # New CYE1 exports must be confined to the normal group; this is
    # corroborated *independently* by matching GPL CRCs at the table tail.
    normal_stock = sorted(normal + new_names)
    gpl_stock = gpl
    if stock_count != len(normal_stock) + len(gpl_stock):
        raise ValueError("stock export group count does not add up")
    old_gpl_crcs = research_crcs[len(normal):]
    new_gpl_crcs = stock_crcs[len(normal_stock):]
    gpl_matches = sum(a == b for a, b in zip(old_gpl_crcs, new_gpl_crcs))
    if gpl_matches < len(gpl) * 0.95:
        raise ValueError("GPL group parity weak; new symbols may belong to GPL group")

    stock_by_name = dict(zip(normal_stock + gpl_stock, stock_crcs))
    changed = [
        {"name": name, "research_crc": f"0x{refs[name]:08x}",
         "stock_crc": f"0x{stock_by_name[name]:08x}",
         "group": "GPL" if name in gpl_stock else "normal"}
        for name in control_names if refs[name] != stock_by_name[name]
    ]
    added = [
        {"name": name, "stock_crc": f"0x{stock_by_name[name]:08x}",
         "group": "normal (inferred and GPL cross-checked)"}
        for name in new_names
    ]
    return {
        "SOURCE": "AUTHENTICATED_CYE1_RAW_ARM64_IMAGE",
        "RESEARCH_CONTROL": "PINNED_AOSP_CLANG10_SAMSUNG_OSRC_CWL1",
        "stock_image_sha256": sha256(stock_image),
        "reference_symvers_sha256": sha256(symvers),
        "stock_crc_table_offset": stock_start,
        "stock_kstrtab_offset": stock_strings,
        "stock_builtin_export_count": stock_count,
        "research_builtin_export_count": count,
        "normal_group_count_stock": len(normal_stock),
        "gpl_group_count_stock": len(gpl_stock),
        "gpl_crc_values_matching_research": gpl_matches,
        "unchanged_named_export_crcs": count - len(changed),
        "changed_named_export_crcs": changed,
        "new_stock_exports": added,
        "removed_stock_exports": removed_names,
        "OEM_MODULE_LOADING": "NOT_TESTED",
        "KERNEL_BOOT": "NOT_TESTED",
        "FLASH_ALLOWED": "NO",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock-image", required=True, type=Path)
    p.add_argument("--research-artifact", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    args = p.parse_args()
    with zipfile.ZipFile(args.research_artifact) as artifact:
        report = compare(args.stock_image.read_bytes(), artifact)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"STOCK_BUILTIN_EXPORTS={report['stock_builtin_export_count']}")
    print(f"RESEARCH_BUILTIN_EXPORTS={report['research_builtin_export_count']}")
    print(f"UNCHANGED_NAMED_EXPORT_CRCS={report['unchanged_named_export_crcs']}")
    print(f"CHANGED_NAMED_EXPORT_CRCS={len(report['changed_named_export_crcs'])}")
    print(f"NEW_STOCK_EXPORTS={len(report['new_stock_exports'])}")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
