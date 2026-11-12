#!/usr/bin/env python3
"""Validate the actual official Samsung SM-P613 Android 14 OSRC source archive.

Does NOT certify compatibility with stock firmware P613XXS8CYE1.
"""
import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path

ZIP_SHA = "728e592f5ad856773e093a01adebedb06a5ef2554c85813ae275a842eecb13b7"
KERNEL_SHA = "4ef99eebc13604a8dc9d9037901f912fefe1f0ed0dff116e6baa176e4221a1b7"
FILES = {
    "./Makefile": "92eb4a8acb7273bab2252a4f55e6cbf063633524df33c4bb05ff963e28b08b4e",
    "./build_kernel.sh": "6d57e075bfbbfa51ebfb83507c994c0bf049bf0cf90cd61ad518cfef09953e02",
    "./arch/arm64/configs/gta4xlvewifi_eur_open_defconfig": "cf9b979f1b7cf2ac5d7c8fbdeb69da98734bf37abba598bcc6670725eba80059",
}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--extract-kernel", action="store_true")
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    observed = sha(args.archive)
    if observed != ZIP_SHA:
        raise SystemExit("Official Samsung ZIP checksum mismatch: " + observed)

    with zipfile.ZipFile(args.archive) as archive:
        expected_names = {"Kernel.tar.gz", "Platform.tar.gz", "README_Kernel.txt", "README_Platform.txt"}
        if set(archive.namelist()) != expected_names:
            raise SystemExit("Unexpected Samsung ZIP contents")
        if "gta4xlvewifi_eur_open_defconfig" not in archive.read("README_Kernel.txt").decode("utf-8", "replace"):
            raise SystemExit("Missing Samsung build instructions")
        kernel_tar = args.workdir / "Kernel.tar.gz"
        with archive.open("Kernel.tar.gz") as source, kernel_tar.open("wb") as dest:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                dest.write(chunk)

    if sha(kernel_tar) != KERNEL_SHA:
        raise SystemExit("Kernel.tar.gz checksum mismatch")
    with tarfile.open(kernel_tar, "r:gz") as archive:
        data = {}
        for name, digest in FILES.items():
            member = archive.getmember(name)
            if not member.isfile():
                raise SystemExit("Not a regular file: " + name)
            content = archive.extractfile(member).read()
            if hashlib.sha256(content).hexdigest() != digest:
                raise SystemExit("Invalid Samsung source file: " + name)
            data[name] = content.decode("utf-8", "replace")
        mk = data["./Makefile"]
        def get_version(name):
            match = re.search(r"^" + name + r"\s*=\s*(\S+)", mk, re.M)
            if not match:
                raise SystemExit("Missing kernel version field: " + name)
            return match.group(1)
        version = ".".join(get_version(k) for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))
        if version != "4.14.190":
            raise SystemExit("Unexpected kernel version: " + version)
        config = data["./arch/arm64/configs/gta4xlvewifi_eur_open_defconfig"]
        for flag in ("CONFIG_KALLSYMS=y", "CONFIG_KALLSYMS_ALL=y", "# CONFIG_KPROBES is not set"):
            if flag not in config:
                raise SystemExit("Unexpected defconfig: " + flag)
        if args.extract_kernel:
            dest = args.workdir / "kernel"
            dest.mkdir(exist_ok=True)
            for member in archive.getmembers():
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise SystemExit("Unsafe archive path: " + member.name)
                if member.issym() or member.islnk():
                    link = Path(member.linkname)
                    if link.is_absolute() or ".." in link.parts:
                        raise SystemExit("Unsafe symlink: " + member.name)
            archive.extractall(dest)

    report = {
        "device": "SM-P613",
        "samsung_source_firmware": "P613XXU4CWL1",
        "target_stock_firmware": "P613XXS8CYE1",
        "archive_sha256": observed,
        "kernel_tar_sha256": KERNEL_SHA,
        "kernel_version": version,
        "defconfig": "gta4xlvewifi_eur_open_defconfig",
        "kallsyms": True,
        "kprobes": False,
        "toolchain_included": False,
        "required_toolchain": "Qualcomm clang 10.0 + Android aarch64 GCC 4.9",
        "stock_compatibility_verified": False,
        "flash_approved": False,
    }
    (args.workdir / "samsung-source-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = (
        "# SM-P613 source validation\n\n"
        "- Official OSRC source: P613XXU4CWL1 (Android 14)\n"
        "- Kernel: 4.14.190; device target also 4.14.190, but newer Samsung build.\n"
        "- gta4xlvewifi_eur_open_defconfig verified; KALLSYMS enabled, KPROBES disabled.\n"
        "- Missing toolchains: Qualcomm Clang 10.0 / Android GCC 4.9.\n"
        "- **NOT FLASHABLE / DO NOT FLASH.** Real stock-baseline boot verification outstanding.\n"
    )
    (args.workdir / "samsung-source-summary.md").write_text(summary)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
