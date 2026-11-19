#!/usr/bin/env python3
"""Verify real ARM64 call instructions to KernelSU manual hooks in vmlinux.

Research evidence only: call-site presence cannot establish runtime safety,
Samsung security-policy compatibility, bootability, or flash readiness.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path


HOOKS = (
    "ksu_handle_execveat",
    "ksu_handle_faccessat",
    "ksu_handle_stat",
    "ksu_handle_sys_read",
)
LABEL = re.compile(r"^\s*([0-9a-fA-F]+) <([^>]+)>:\s*$")
CALL = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{8}\s+)?"
    r"bl\s+(?:[0-9a-fA-Fx]+\s+)?<"
    r"(ksu_handle_(?:execveat|faccessat|stat|sys_read))"
    r"(?:\+0x[0-9a-fA-F]+)?>"
)


def audit_disassembly(lines) -> dict:
    calls = {hook: [] for hook in HOOKS}
    caller = None
    for line in lines:
        label = LABEL.match(line)
        if label:
            caller = label.group(2)
            continue
        match = CALL.match(line)
        if match:
            calls[match.group(2)].append(
                {"address": match.group(1), "caller": caller or "UNKNOWN"}
            )
    # A KSU function calling another KSU handler would not establish that the
    # Samsung syscall entry point has actually been patched and linked.
    non_ksu_calls = {
        hook: [call for call in found if not call["caller"].startswith("ksu_")]
        for hook, found in calls.items()
    }
    missing = [hook for hook in HOOKS if not non_ksu_calls[hook]]
    return {
        "RESEARCH_ONLY": "YES",
        "FLASH_ALLOWED": "NO",
        "KSU_MANUAL_CALL_EDGES_LINKED": not missing,
        "KSU_MANUAL_CALL_EDGES": non_ksu_calls,
        "MISSING_MANUAL_CALL_EDGES": missing,
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
        "CALL_EDGES_PROVE_RUNTIME_CORRECTNESS": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objdump", required=True, type=Path)
    parser.add_argument("--vmlinux", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not args.vmlinux.is_file():
        parser.error(f"Missing linked vmlinux: {args.vmlinux}")
    process = subprocess.Popen(
        [str(args.objdump), "-d", str(args.vmlinux)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    result = audit_disassembly(process.stdout)
    stderr = process.stderr.read() if process.stderr else ""
    status = process.wait()
    if status:
        parser.exit(status, f"objdump failed ({status}): {stderr[-1200:]}\n")
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for hook, calls in result["KSU_MANUAL_CALL_EDGES"].items():
        print(f"{hook}: {len(calls)} linked BL call(s)")
    print("FLASH_ALLOWED=NO")
    if not result["KSU_MANUAL_CALL_EDGES_LINKED"]:
        parser.exit(1, f"Missing real ARM64 manual hook call(s): {result['MISSING_MANUAL_CALL_EDGES']}\n")


if __name__ == "__main__":
    main()
