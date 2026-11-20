#!/usr/bin/env python3
"""Audit a research KernelSU Module.symvers against authenticated CYE1 deltas.

The checked-in manifest was independently reconstructed from the user's
SHA256-verified OEM boot Image. It records only changed/added exports, not the
full proprietary kernel or any signing credentials. This check deliberately
never converts a successful research build into flash approval.
"""

import argparse
import hashlib
import json
from pathlib import Path


def parse_builtin_symvers(content: str) -> dict[str, tuple[int, str]]:
    """Return vmlinux exports only; external module exports are excluded."""
    result = {}
    for number, line in enumerate(content.splitlines(), 1):
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"malformed Module.symvers line {number}")
        crc, name, owner, export = parts[:4]
        if owner != "vmlinux":
            continue
        if export not in ("EXPORT_SYMBOL", "EXPORT_SYMBOL_GPL"):
            raise ValueError(f"unexpected export class for {name}")
        if name in result:
            raise ValueError(f"duplicate built-in export {name}")
        if not crc.startswith("0x") or len(crc) != 10:
            raise ValueError(f"invalid CRC for {name}")
        try:
            result[name] = (int(crc, 16), "GPL" if export.endswith("_GPL") else "normal")
        except ValueError as exc:
            raise ValueError(f"invalid CRC for {name}") from exc
    if not result:
        raise ValueError("no built-in exports found")
    return result


def audit(manifest: dict, symvers: bytes) -> dict:
    digest = hashlib.sha256(symvers).hexdigest()
    if digest != manifest["reference_symvers_sha256"]:
        raise ValueError("research Module.symvers differs from authenticated comparison control")
    entries = parse_builtin_symvers(symvers.decode("utf-8"))
    if len(entries) != manifest["research_builtin_export_count"]:
        raise ValueError("research built-in export count differs from CYE1 reference")

    changed = manifest["changed_named_export_crcs"]
    new = manifest["new_stock_exports"]
    removed = manifest["removed_stock_exports"]
    changed_names = {x["name"] for x in changed}
    added_names = {x["name"] for x in new}
    removed_names = {x["name"] for x in removed}
    if len(changed_names) != len(changed) or len(added_names) != len(new):
        raise ValueError("duplicate changed or added export name in OEM manifest")
    if changed_names & added_names or changed_names & removed_names or added_names & removed_names:
        raise ValueError("overlapping OEM export delta groups")

    for entry in changed:
        name = entry["name"]
        if name not in entries:
            raise ValueError(f"changed reference export missing: {name}")
        actual_crc, actual_class = entries[name]
        if actual_crc != int(entry["research_crc"], 16):
            raise ValueError(f"research CRC drift for {name}")
        if actual_class != entry["group"]:
            raise ValueError(f"research export class drift for {name}")
        if actual_crc == int(entry["stock_crc"], 16):
            raise ValueError(f"manifest incorrectly marks matching CRC for {name}")
    for entry in new:
        if entry["name"] in entries:
            raise ValueError(f"OEM-only export already present in research: {entry['name']}")
        int(entry["stock_crc"], 16)
    for entry in removed:
        if entry["name"] not in entries:
            raise ValueError(f"removed export missing from research: {entry['name']}")

    if len(entries) + len(new) - len(removed) != manifest["stock_builtin_export_count"]:
        raise ValueError("stock export count is inconsistent with delta groups")
    if len(entries) - len(changed) - len(removed) != manifest["unchanged_named_export_crcs"]:
        raise ValueError("unchanged export count is inconsistent")

    gpl_research = sum(1 for _, klass in entries.values() if klass == "GPL")
    gpl_changed = sum(1 for x in changed if x["group"] == "GPL")
    gpl_added = sum(1 for x in new if x["group"] == "GPL")
    gpl_removed = sum(1 for x in removed if x["group"] == "GPL")
    if gpl_research + gpl_added - gpl_removed != manifest["gpl_group_count_stock"]:
        raise ValueError("GPL export count differs from original CYE1")
    if manifest["stock_builtin_export_count"] - manifest["gpl_group_count_stock"] != manifest["normal_group_count_stock"]:
        raise ValueError("stock normal/GPL group counts are inconsistent")
    if gpl_research - gpl_changed - gpl_removed != manifest["gpl_crc_values_matching_research"]:
        raise ValueError("GPL CRC parity count is inconsistent")

    compatible = not (changed or new or removed)
    return {
        "evidence": "authenticated OEM CYE1 Image delta manifest, not a full firmware comparison",
        "research_symvers_sha256": digest,
        "research_builtin_exports": len(entries),
        "oem_cye1_builtin_exports": manifest["stock_builtin_export_count"],
        "shared_export_crc_mismatches": len(changed),
        "missing_oem_cye1_exports": len(new),
        "extra_research_exports": len(removed),
        "oem_cye1_export_crc_parity": "YES" if compatible else "NO",
        "oem_module_signature_trust": "UNVERIFIED",
        "oem_toolchain_equivalence": "UNVERIFIED",
        "physical_stock_baseline_boot": "NOT_TESTED",
        "flash_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--symvers", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.manifest.read_text()), args.symvers.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
