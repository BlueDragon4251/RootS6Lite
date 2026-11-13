#!/usr/bin/env python3
"""Gate a non-flashable KernelSU Next research build on linked hook symbols.

This check proves only that expected manual-hook entry points are present in
the linked kernel. It does not establish Samsung ABI compatibility, bootability,
root functionality, or permission to flash any output.
"""

import argparse
import json
from pathlib import Path


REQUIRED_CONFIG = (
    "CONFIG_KSU=y",
    "CONFIG_KSU_MANUAL_HOOK=y",
    "# CONFIG_KPROBES is not set",
    "CONFIG_MODULE_SIG_FORCE=y",
    "CONFIG_SECURITY_SELINUX=y",
    "CONFIG_FIVE=y",
    "CONFIG_PROCA=y",
    "CONFIG_PROCA_S_OS=y",
)
REQUIRED_HOOK_SYMBOLS = (
    "ksu_handle_execveat",
    "ksu_handle_faccessat",
    "ksu_handle_stat",
    "ksu_handle_sys_read",
)


def audit(config_file: Path, system_map_file: Path) -> dict:
    settings = set(config_file.read_text(encoding="utf-8").splitlines())
    missing_config = [entry for entry in REQUIRED_CONFIG if entry not in settings]

    symbol_types = {}
    for line in system_map_file.read_text(encoding="utf-8").splitlines():
        cols = line.split()
        if len(cols) == 3 and cols[2] in REQUIRED_HOOK_SYMBOLS:
            symbol_types[cols[2]] = cols[1]
    missing_hooks = [name for name in REQUIRED_HOOK_SYMBOLS if symbol_types.get(name, "").lower() != "t"]
    result = {
        "RESEARCH_ONLY": "YES",
        "FLASH_ALLOWED": "NO",
        "KSU_CONFIG_VALID": not missing_config,
        "KSU_MANUAL_HOOKS_LINKED": not missing_hooks,
        "KSU_HOOK_SYMBOL_TYPES": symbol_types,
        "MISSING_CONFIG": missing_config,
        "MISSING_OR_NON_TEXT_HOOK_SYMBOLS": missing_hooks,
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
        "KSU_ROOT_TEST": "NOT_PERFORMED",
        "STOCK_MODULE_ABI": "UNVERIFIED",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--system-map", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.config, args.system_map)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"KSU_MANUAL_HOOKS_LINKED={'YES' if result['KSU_MANUAL_HOOKS_LINKED'] else 'NO'}")
    print(f"KSU_RESEARCH_CONFIG_VALID={'YES' if result['KSU_CONFIG_VALID'] else 'NO'}")
    print("FLASH_ALLOWED=NO")
    if not result["KSU_CONFIG_VALID"] or not result["KSU_MANUAL_HOOKS_LINKED"]:
        parser.exit(1, "KernelSU Next research symbol/configuration audit failed\n")


if __name__ == "__main__":
    main()
