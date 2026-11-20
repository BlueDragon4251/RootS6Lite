#!/usr/bin/env python3
"""Verify real ARM64 call instructions to KernelSU manual hooks in vmlinux.

Research evidence only: call-site presence cannot establish runtime safety,
Samsung security-policy compatibility, bootability, or flash readiness.

The samsung-cye1 profile also requires every known exec/syscall caller from
the pinned Clang 10 Samsung 4.14 build, including the reboot supercall bridge.
It does not infer source placement or correct argument values from a BL alone.
"""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path


HOOKS = (
    "ksu_handle_execveat",
    "ksu_handle_faccessat",
    "ksu_handle_stat",
    "ksu_handle_sys_read",
    "ksu_handle_sys_reboot",
)
SAMSUNG_CYE1_CALLERS = {
    "ksu_handle_execveat": (
        "do_execve", "do_execveat", "SyS_execve", "SyS_execveat",
        "compat_SyS_execve", "compat_SyS_execveat",
    ),
    "ksu_handle_faccessat": ("SyS_faccessat",),
    "ksu_handle_stat": ("SyS_newfstatat",),
    "ksu_handle_sys_read": ("SyS_read",),
    "ksu_handle_sys_reboot": ("SyS_reboot",),
}
PROFILES = ("generic", "samsung-cye1")
LABEL = re.compile(r"^\s*([0-9a-fA-F]+) <([^>]+)>:\s*$")
CALL = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{8}\s+)?"
    r"bl\s+(?:[0-9a-fA-Fx]+\s+)?<"
    r"(ksu_handle_(?:execveat|faccessat|stat|sys_read|sys_reboot))"
    r"(?:\+0x([0-9a-fA-F]+))?>"
)


def audit_disassembly(lines, profile: str = "generic") -> dict:
    if profile not in PROFILES:
        raise ValueError(f"Unknown call-edge profile: {profile}")
    calls = {hook: [] for hook in HOOKS}
    rejected = []
    unexpected = []
    caller = None
    for line in lines:
        if line.startswith("Disassembly of section "):
            caller = None
            continue
        label = LABEL.match(line)
        if label:
            caller = label.group(2)
            continue
        match = CALL.match(line)
        if not match:
            continue
        hook = match.group(2)
        call = {"address": match.group(1), "caller": caller or "UNKNOWN"}
        # Internal calls, unlabelled code, or branches into a handler's middle
        # do not prove that a real kernel entry point invokes the handler.
        reason = None
        if caller is None:
            reason = "UNKNOWN_CALLER"
        elif caller.startswith(("ksu_", "kernelsu_")):
            reason = "INTERNAL_KSU_CALLER"
        elif match.group(3) and int(match.group(3), 16) != 0:
            reason = "NONZERO_TARGET_OFFSET"
        elif profile == "samsung-cye1" and caller not in SAMSUNG_CYE1_CALLERS[hook]:
            reason = "UNEXPECTED_SAMSUNG_CALLER"
        if reason:
            rejected.append({"hook": hook, **call, "reason": reason})
            if reason != "INTERNAL_KSU_CALLER":
                unexpected.append({"hook": hook, **call, "reason": reason})
            continue
        calls[hook].append(call)
    missing = [hook for hook in HOOKS if not calls[hook]]
    missing_callers = {}
    if profile == "samsung-cye1":
        for hook, expected in SAMSUNG_CYE1_CALLERS.items():
            observed = {call["caller"] for call in calls[hook]}
            absent = [name for name in expected if name not in observed]
            if absent:
                missing_callers[hook] = absent
    return {
        "RESEARCH_ONLY": "YES",
        "FLASH_ALLOWED": "NO",
        "CALL_EDGE_PROFILE": profile,
        "KSU_MANUAL_CALL_EDGES_LINKED": not (missing or missing_callers or unexpected),
        "KSU_MANUAL_CALL_EDGES": calls,
        "MISSING_MANUAL_CALL_EDGES": missing,
        "MISSING_MANUAL_CALLERS": missing_callers,
        "REJECTED_MANUAL_CALL_EDGES": rejected,
        "UNEXPECTED_MANUAL_CALL_EDGES": unexpected,
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
        "CALL_EDGES_PROVE_RUNTIME_CORRECTNESS": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objdump", required=True, type=Path)
    parser.add_argument("--vmlinux", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="generic")
    args = parser.parse_args()
    if not args.vmlinux.is_file():
        parser.error(f"Missing linked vmlinux: {args.vmlinux}")
    # stderr may be larger than a pipe buffer. Spool it while streaming the
    # potentially enormous disassembly so neither pipe can deadlock the child.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        with subprocess.Popen(
            [str(args.objdump), "-d", str(args.vmlinux)],
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            result = audit_disassembly(process.stdout, profile=args.profile)
            process.stdout.close()
            status = process.wait()
        errors.seek(0)
        stderr = errors.read()
    if status:
        parser.exit(status, f"objdump failed ({status}): {stderr[-1200:]}\n")
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for hook, calls in result["KSU_MANUAL_CALL_EDGES"].items():
        print(f"{hook}: {len(calls)} linked BL call(s)")
    print("FLASH_ALLOWED=NO")
    if not result["KSU_MANUAL_CALL_EDGES_LINKED"]:
        parser.exit(
            1,
            "ARM64 manual hook call audit failed: "
            f"missing hooks={result['MISSING_MANUAL_CALL_EDGES']}, "
            f"missing callers={result['MISSING_MANUAL_CALLERS']}, "
            f"unexpected calls={result['UNEXPECTED_MANUAL_CALL_EDGES']}\n",
        )


if __name__ == "__main__":
    main()
