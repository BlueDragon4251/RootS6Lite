#!/usr/bin/env python3
"""Reconstruct the CYE1 export CRC table from an authenticated CWL1 control.

The stock CYE1 delta manifest was derived from the owner's verified boot Image.
The resulting table is a *derived* full export reference, not an independently
captured OEM Module.symvers or evidence of stock module signing/bootability.
"""

import argparse
import hashlib
import json
from pathlib import Path

from verify_oem_cye1_abi import parse_builtin_symvers


def reconstruct(manifest: dict, control_bytes: bytes) -> bytes:
    if hashlib.sha256(control_bytes).hexdigest() != manifest["reference_symvers_sha256"]:
        raise ValueError("CWL1 control Module.symvers SHA256 mismatch")
    control = parse_builtin_symvers(control_bytes.decode("utf-8"))
    if len(control) != manifest["research_builtin_export_count"]:
        raise ValueError("CWL1 control built-in export count mismatch")

    changed = manifest["changed_named_export_crcs"]
    added = manifest["new_stock_exports"]
    removed = manifest["removed_stock_exports"]
    names = [row["name"] for row in changed + added] + removed
    if len(names) != len(set(names)):
        raise ValueError("duplicate or overlapping delta symbol names")
    if len(control) - len(changed) - len(removed) != manifest["unchanged_named_export_crcs"]:
        raise ValueError("manifest unchanged-export count mismatch")

    result = dict(control)
    for row in changed:
        name = row["name"]
        if name not in control:
            raise ValueError(f"changed symbol absent from CWL1 control: {name}")
        if control[name] != (int(row["research_crc"], 16), row["group"]):
            raise ValueError(f"CWL1 control CRC or class differs from manifest: {name}")
        stock_crc = int(row["stock_crc"], 16)
        if stock_crc == control[name][0]:
            raise ValueError(f"manifest incorrectly marks an unchanged symbol: {name}")
        result[name] = (stock_crc, row["group"])
    for name in removed:
        if name not in result:
            raise ValueError(f"removed stock symbol absent from control: {name}")
        del result[name]
    for row in added:
        name = row["name"]
        if name in control:
            raise ValueError(f"new CYE1 symbol already present in control: {name}")
        if row["group"] != "normal (inferred and GPL cross-checked)":
            raise ValueError(f"unverified CYE1 added-symbol class: {name}")
        result[name] = (int(row["stock_crc"], 16), "normal")

    if len(result) != manifest["stock_builtin_export_count"]:
        raise ValueError("reconstructed CYE1 built-in export count mismatch")
    if sum(klass == "GPL" for _, klass in result.values()) != manifest["gpl_group_count_stock"]:
        raise ValueError("reconstructed CYE1 GPL export count mismatch")
    if sum(klass == "normal" for _, klass in result.values()) != manifest["normal_group_count_stock"]:
        raise ValueError("reconstructed CYE1 normal export count mismatch")

    return ("# name\tstock_crc\texport_class\n" + "".join(
        f"{name}\t0x{crc:08x}\t{klass}\n"
        for name, (crc, klass) in sorted(result.items())
    )).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--control-symvers", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    result = reconstruct(manifest, args.control_symvers.read_bytes())
    digest = hashlib.sha256(result).hexdigest()
    if manifest.get("reconstructed_stock_exports_sha256", digest) != digest:
        raise ValueError("reconstructed CYE1 export reference SHA256 mismatch")
    args.output.write_bytes(result)
    print(f"RECONSTRUCTED_STOCK_EXPORTS_SHA256={digest}")
    print(f"RECONSTRUCTED_STOCK_EXPORTS={manifest['stock_builtin_export_count']}")
    print("PROVENANCE=VERIFIED_CWL1_CONTROL_PLUS_AUTHENTICATED_CYE1_DELTA; FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
