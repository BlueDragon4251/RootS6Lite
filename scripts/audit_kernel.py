#!/usr/bin/env python3
"""Compare a kernel source Makefile with the user's actual SM-P613 kernel.

This is only a version/provenance preflight; a matching version is NOT a
complete stock-boot compatibility proof.
"""
import argparse
import json
import re
from pathlib import Path


def read_kernel_version(makefile: Path) -> str:
    text = makefile.read_text(encoding="utf-8")
    values = {}
    for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL", "EXTRAVERSION"):
        match = re.search(r"^" + key + r"\s*[:?+]?=\s*([^\n#]*)", text, re.M)
        if not match:
            raise ValueError(f"Kernel Makefile missing {key}")
        values[key] = match.group(1).strip()
    return ".".join(values[k] for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL")) + values["EXTRAVERSION"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--makefile", type=Path, required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--expected", default="4.14.190")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--markdown", type=Path, required=True)
    p.add_argument("--require-match", action="store_true")
    args = p.parse_args()

    actual = read_kernel_version(args.makefile)
    matched = actual == args.expected
    result = {
        "device": "SM-P613",
        "target_firmware": "P613XXS8CYE1",
        "source": args.reference,
        "source_kernel_version": actual,
        "stock_kernel_version": args.expected,
        "kernel_version_exact_match": matched,
        "flash_safe": False,
        "note": "A matching version alone is not enough: stock defconfig, toolchain, device tree, and real-device baseline boot must also be verified.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(
        f"## SM-P613 source audit\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| Source | `{args.reference}` |\n"
        f"| Source kernel | `{actual}` |\n"
        f"| Samsung stock kernel | `{args.expected}` |\n"
        f"| Exact source version match | **{'YES' if matched else 'NO'}** |\n"
        f"| Safe to flash | **NO — not validated** |\n\n"
        f"{'Version mismatch: this source is not a replacement for the stock One UI kernel.' if not matched else 'Version matches, but additional provenance and live boot checks are required.'}\n",
        encoding="utf-8",
    )
    print(f"Source kernel: {actual}; target: {args.expected}; match: {matched}; FLASH_SAFE=NO")
    if args.require_match and not matched:
        raise SystemExit("Refusing stock-mode build: kernel source version does not match device")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
