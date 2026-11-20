#!/usr/bin/env python3
"""Compare a NEW Samsung CYE1 research build with authenticated stock deltas.

The reference JSON covers the 46 names changed/missing in the older CWL1
control; it is NOT a complete original OEM Module.symvers. A positive result
for those names must never be interpreted as full module ABI compatibility.
"""

import argparse
import hashlib
import json
from pathlib import Path

from verify_oem_cye1_abi import parse_builtin_symvers


def compare(manifest: dict, symvers_bytes: bytes) -> dict:
    actual = parse_builtin_symvers(symvers_bytes.decode("utf-8"))
    references = manifest["changed_named_export_crcs"] + manifest["new_stock_exports"]
    if len({row["name"] for row in references}) != len(references):
        raise ValueError("Repeated OEM reference symbol")
    matches = []
    crc_mismatches = []
    missing = []
    class_mismatches = []
    for row in references:
        name = row["name"]
        if name not in actual:
            missing.append(name)
            continue
        crc, klass = actual[name]
        expected = int(row["stock_crc"], 16)
        expected_class = "GPL" if row["group"] == "GPL" else "normal"
        if klass != expected_class:
            class_mismatches.append({"name": name, "compiled": klass, "stock": expected_class})
        if crc != expected:
            crc_mismatches.append({"name": name, "compiled": f"0x{crc:08x}", "stock": f"0x{expected:08x}"})
        elif klass == expected_class:
            matches.append(name)

    compiled_count = len(actual)
    stock_count = manifest["stock_builtin_export_count"]
    checked = len(references)
    return {
        "basis": "Authenticated CYE1 OEM export deltas vs old CWL1 control (partial ABI check)",
        "compiled_symvers_sha256": hashlib.sha256(symvers_bytes).hexdigest(),
        "stock_builtin_export_count": stock_count,
        "compiled_builtin_export_count": compiled_count,
        "builtin_export_count_matches_stock": compiled_count == stock_count,
        "reference_export_count": checked,
        "reference_exports_matching_stock": len(matches),
        "reference_export_crcs_mismatching_stock": len(crc_mismatches),
        "reference_exports_missing": len(missing),
        "reference_export_class_mismatches": len(class_mismatches),
        "matching_export_names": sorted(matches),
        "crc_mismatches": sorted(crc_mismatches, key=lambda row: row["name"]),
        "missing_exports": sorted(missing),
        "class_mismatches": sorted(class_mismatches, key=lambda row: row["name"]),
        "listed_reference_parity": "YES" if len(matches) == checked else "NO",
        "complete_oem_module_abi_parity": "UNVERIFIED",
        "oem_signing_trust": "UNVERIFIED",
        "physical_stock_baseline_boot": "NOT_TESTED",
        "flash_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--symvers", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = compare(json.loads(args.manifest.read_text()), args.symvers.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"CYE1_LISTED_REFERENCE_PARITY={report['listed_reference_parity']}")
    print(f"CYE1_LISTED_REFERENCE_MATCHED={report['reference_exports_matching_stock']}/{report['reference_export_count']}")
    print(f"CYE1_FULL_OEM_ABI_PARITY={report['complete_oem_module_abi_parity']}")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
