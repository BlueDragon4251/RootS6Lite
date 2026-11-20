#!/usr/bin/env python3
"""Read-only audit of Samsung's P619 base plus P613 CYE1 source overlay.

Does not execute, extract, patch, compile, package, or flash kernel sources.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile
import zipfile


EXPECTED_BUNDLE_SHA256 = "e3e144de155e5d82477b83c5642146fefb1a8af272061ec2a6b4532a6a03234f"
BASE_ZIP = "SM-P619_14_Opensource.zip"
CYE1_ZIP = (
    "SM-P613_14_Opensource_P613XXS8CYE1_P613KOS8CYE1_P619NKOSACYE1.zip"
)
CYE1_TAR = "P613XXS8CYE1_kernel.tar.gz"
CONFIG = "Kernel/arch/arm64/configs/gta4xlvewifi_eur_open_defconfig"
CYE1_EXPECTED_FILES = {
    CONFIG,
    "Kernel/techpack/audio/dsp/q6lsm.c",
    "Kernel/techpack/audio/4.0/dsp/q6lsm.c",
}
REQUIRED_CONFIG_LINES = {
    "CONFIG_FIVE=y",
    "CONFIG_PROCA=y",
    "CONFIG_PROCA_S_OS=y",
    "CONFIG_MODULE_SIG_FORCE=y",
    "CONFIG_RKP_NS_PROT=y",
    "CONFIG_USB_NOTIFY_LAYER_V34=y",
    "# CONFIG_KPROBES is not set",
    "CONFIG_SEC_GTA4XLVEWIFI_EUR_OPEN=y",
}
EXPORT_RE = re.compile(rb"\bEXPORT_SYMBOL(?:_GPL)?\s*\(\s*([A-Za-z0-9_]+)\s*\)")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_regular_member(member: tarfile.TarInfo) -> str:
    name = member.name.removeprefix("./")
    parts = name.split("/")
    if name.startswith("/") or ".." in parts or "" in parts:
        raise ValueError(f"Unsafe tar path: {member.name}")
    return name


def scan_base_kernel(zipped: zipfile.ZipFile, expected_exports: set[str]) -> dict:
    if "Kernel.tar.gz" not in zipped.namelist():
        raise ValueError("Samsung base ZIP has no Kernel.tar.gz")
    exported: set[str] = set()
    makefile = None
    files = 0
    with zipped.open("Kernel.tar.gz") as stream:
        with tarfile.open(fileobj=stream, mode="r|gz") as archive:
            for member in archive:
                name = check_regular_member(member)
                if not member.isfile():
                    continue
                files += 1
                if name != "Makefile" and not name.endswith(".c"):
                    continue
                entry = archive.extractfile(member)
                if entry is None:
                    raise ValueError(f"Unable to read {name}")
                with entry:
                    data = entry.read()
                if name == "Makefile":
                    makefile = data.decode("utf-8", errors="replace")
                else:
                    exported.update(n.decode("ascii") for n in EXPORT_RE.findall(data))
    if makefile is None:
        raise ValueError("Base kernel Makefile not found")
    for key, value in [("VERSION", 4), ("PATCHLEVEL", 14), ("SUBLEVEL", 190)]:
        if not re.search(rf"(?m)^{key}\s*=\s*{value}\s*$", makefile):
            raise ValueError(f"Base kernel is not Linux 4.14.190 ({key})")
    missing = sorted(expected_exports - exported)
    if missing:
        raise ValueError(f"CYE1 OEM exports absent from base source: {missing}")
    return {"source_files_read": files, "verified_cye1_export_names": sorted(expected_exports)}


def scan_cye1_overlay(zipped: zipfile.ZipFile) -> dict:
    if CYE1_TAR not in zipped.namelist():
        raise ValueError(f"CYE1 supplement missing {CYE1_TAR}")
    files: set[str] = set()
    config = None
    with zipped.open(CYE1_TAR) as stream:
        with tarfile.open(fileobj=stream, mode="r|gz") as archive:
            for member in archive:
                name = check_regular_member(member)
                if not member.isfile():
                    continue
                files.add(name)
                if name == CONFIG:
                    entry = archive.extractfile(member)
                    if entry is None:
                        raise ValueError("CYE1 defconfig is unreadable")
                    with entry:
                        config = entry.read().decode("utf-8")
    if files != CYE1_EXPECTED_FILES:
        raise ValueError(f"Unexpected CYE1 source overlay: {sorted(files)}")
    if config is None:
        raise ValueError("CYE1 Wi-Fi defconfig missing")
    lines = set(config.splitlines())
    missing = sorted(REQUIRED_CONFIG_LINES - lines)
    if missing:
        raise ValueError(f"CYE1 source security/config gate missing: {missing}")
    return {"overlay_files": sorted(files), "verified_config_lines": sorted(REQUIRED_CONFIG_LINES)}


def audit(bundle: Path, manifest: Path) -> dict:
    actual_sha = file_sha256(bundle)
    if actual_sha != EXPECTED_BUNDLE_SHA256:
        raise ValueError(f"Samsung bundle SHA256 mismatch: {actual_sha}")
    reference = json.loads(manifest.read_text(encoding="utf-8"))
    expected_exports = {row["name"] for row in reference["new_stock_exports"]}
    if len(expected_exports) != 21:
        raise ValueError("Unexpected CYE1 OEM reference export count")
    with zipfile.ZipFile(bundle) as outer:
        members = outer.namelist()
        if len(members) != 7 or len(members) != len(set(members)):
            raise ValueError("Expected exactly seven distinct Samsung archives")
        if BASE_ZIP not in members or CYE1_ZIP not in members:
            raise ValueError("Base or CYE1 supplemental source absent")
        if any(not n.endswith(".zip") or "/" in n or "\\" in n for n in members):
            raise ValueError("Unexpected outer archive member name")
        if outer.testzip() is not None:
            raise ValueError("Outer Samsung ZIP failed CRC validation")
        # Nested entries fit in RAM independently (<240MB); source files are streamed.
        with zipfile.ZipFile(outer.open(BASE_ZIP)) as base:
            base_report = scan_base_kernel(base, expected_exports)
        with zipfile.ZipFile(outer.open(CYE1_ZIP)) as overlay:
            overlay_report = scan_cye1_overlay(overlay)
    return {
        "source": "Samsung OSRC SM-P619 base plus SM-P613 P613XXS8CYE1 overlay",
        "archive_sha256": actual_sha,
        "archive_members": sorted(members),
        "base_kernel": base_report,
        "cye1_overlay": overlay_report,
        "source_level_export_coverage": "21/21",
        "binary_crc_parity": "NOT_TESTED",
        "stock_equivalent_boot": "NOT_TESTED",
        "kernelsu_runtime": "NOT_TESTED",
        "flash_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--oem-manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.bundle, args.oem_manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SAMSUNG_CYE1_SOURCE_LEVEL_EXPORT_COVERAGE=21/21")
    print("STOCK_EQUIVALENT_BOOT=NOT_TESTED")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
