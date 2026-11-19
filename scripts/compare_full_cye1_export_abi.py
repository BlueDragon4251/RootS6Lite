#!/usr/bin/env python3
"""Compare all compiled vmlinux exports to a derived stock CYE1 reference.

The reference is reconstructed from a pinned CWL1 control and stock Image
delta. Even a perfect match is NOT full binary/module ABI or boot validation.
"""

import argparse
import hashlib
import json
from pathlib import Path

from verify_oem_cye1_abi import parse_builtin_symvers


def parse_reference(data: bytes) -> dict[str, tuple[int, str]]:
    lines = data.decode("utf-8").splitlines()
    if not lines or lines[0] != "# name\tstock_crc\texport_class":
        raise ValueError("unexpected reconstructed reference header")
    symbols = {}
    for number, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"malformed reference row {number}")
        name, crc, klass = parts
        if not name or name in symbols or klass not in ("GPL", "normal"):
            raise ValueError(f"duplicate or invalid reference entry at row {number}")
        if len(crc) != 10 or not crc.startswith("0x"):
            raise ValueError(f"invalid reference CRC at row {number}")
        symbols[name] = (int(crc, 16), klass)
    return symbols


def compare(manifest: dict, reference_bytes: bytes, compiled_bytes: bytes) -> dict:
    reference_digest = hashlib.sha256(reference_bytes).hexdigest()
    if reference_digest != manifest["reconstructed_stock_exports_sha256"]:
        raise ValueError("reconstructed CYE1 reference SHA256 mismatch")
    expected = parse_reference(reference_bytes)
    actual = parse_builtin_symvers(compiled_bytes.decode("utf-8"))
    if len(expected) != manifest["stock_builtin_export_count"]:
        raise ValueError("reference export count differs from CYE1 manifest")
    if sum(klass == "GPL" for _, klass in expected.values()) != manifest["gpl_group_count_stock"]:
        raise ValueError("reference GPL class count differs from CYE1 manifest")
    # Revalidate the explicit OEM delta records as an additional provenance
    # check; the remaining names are inherited from the pinned CWL1 control.
    for row in manifest["changed_named_export_crcs"] + manifest["new_stock_exports"]:
        name = row["name"]
        klass = "GPL" if row["group"] == "GPL" else "normal"
        if expected.get(name) != (int(row["stock_crc"], 16), klass):
            raise ValueError(f"reference CYE1 delta differs from manifest: {name}")

    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    crc_mismatches = []
    class_mismatches = []
    for name in sorted(expected.keys() & actual.keys()):
        stock_crc, stock_class = expected[name]
        compiled_crc, compiled_class = actual[name]
        if compiled_crc != stock_crc:
            crc_mismatches.append({"name": name, "stock": f"0x{stock_crc:08x}", "compiled": f"0x{compiled_crc:08x}"})
        if compiled_class != stock_class:
            class_mismatches.append({"name": name, "stock": stock_class, "compiled": compiled_class})
    # An export can have both CRC and class drift; avoid a misleading count.
    matches = sum(actual.get(name) == record for name, record in expected.items())
    parity = not (missing or extra or crc_mismatches or class_mismatches)
    return {
        "reference_provenance": "derived from SHA256-verified CWL1 Module.symvers and authenticated stock Image delta",
        "reference_sha256": reference_digest,
        "compiled_symvers_sha256": hashlib.sha256(compiled_bytes).hexdigest(),
        "stock_reference_export_count": len(expected),
        "compiled_builtin_export_count": len(actual),
        "exact_export_name_crc_class_matches": matches,
        "missing_stock_exports": missing,
        "extra_compiled_exports": extra,
        "crc_mismatches": crc_mismatches,
        "class_mismatches": class_mismatches,
        "reconstructed_stock_export_parity": "YES" if parity else "NO",
        "direct_full_oem_symvers_capture": "NOT_AVAILABLE",
        "complete_oem_module_abi_parity": "UNVERIFIED",
        "stock_module_signature_trust": "UNVERIFIED",
        "physical_stock_baseline_boot": "NOT_TESTED",
        "flash_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--symvers", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = compare(json.loads(args.manifest.read_text()), args.reference.read_bytes(), args.symvers.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(f"CYE1_RECONSTRUCTED_EXPORT_PARITY={report['reconstructed_stock_export_parity']}")
    print(f"CYE1_EXACT_EXPORT_MATCHES={report['exact_export_name_crc_class_matches']}/{report['stock_reference_export_count']}")
    print(f"CYE1_EXTRA_COMPILED_EXPORTS={len(report['extra_compiled_exports'])}")
    print(f"CYE1_MISSING_STOCK_EXPORTS={len(report['missing_stock_exports'])}")
    print(f"CYE1_CRC_MISMATCHES={len(report['crc_mismatches'])}")
    print("COMPLETE_OEM_MODULE_ABI_PARITY=UNVERIFIED; FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
