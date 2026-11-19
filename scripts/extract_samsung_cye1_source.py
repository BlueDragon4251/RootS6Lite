#!/usr/bin/env python3
"""Unpack verified Samsung 2025 P619 base + exact P613 CYE1 overlay for CI.

Only creates a temporary research source tree. Does not alter the original ZIP,
create Odin packages, or establish permission to flash a device.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import zipfile

from audit_samsung_cye1_bundle import (
    BASE_ZIP,
    CYE1_EXPECTED_FILES,
    CYE1_TAR,
    CYE1_ZIP,
    EXPECTED_BUNDLE_SHA256,
    REQUIRED_CONFIG_LINES,
    file_sha256,
)


def normalized_name(raw: str) -> str:
    if raw in (".", "./"):
        return ""
    if raw.startswith("./"):
        raw = raw[2:]
    path = PurePosixPath(raw)
    if raw.startswith("/") or "\\" in raw or any(p in ("", "..") for p in raw.split("/")):
        raise ValueError(f"Unsafe tar member: {raw}")
    if path == PurePosixPath("."):
        return ""
    return path.as_posix()


def within_root(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def unpack_base(archive: tarfile.TarFile, root: Path) -> dict:
    count = 0
    symlinks = 0
    for member in archive:
        rel = normalized_name(member.name)
        if not rel:
            continue
        dst = root / rel
        if not within_root(dst, root):
            raise ValueError(f"Tar member escapes destination: {member.name}")
        if member.isdir():
            dst.mkdir(parents=True, exist_ok=True)
        elif member.issym():
            if member.linkname.startswith("/") or "\\" in member.linkname:
                raise ValueError(f"Absolute/backslash symlink: {member.name}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not within_root(dst.parent / member.linkname, root):
                raise ValueError(f"Symlink escapes destination: {member.name}")
            dst.symlink_to(member.linkname)
            symlinks += 1
        elif member.isfile():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_symlink():
                raise ValueError(f"Refuse to overwrite symlink: {member.name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"No payload for: {member.name}")
            with stream, dst.open("xb") as out:
                shutil.copyfileobj(stream, out, length=1024 * 1024)
            dst.chmod(member.mode & 0o777)
            count += 1
        else:
            raise ValueError(f"Unsupported tar entry type: {member.name}")
    return {"base_regular_files": count, "base_symlinks": symlinks}


def apply_cye1_overlay(archive: tarfile.TarFile, root: Path) -> dict:
    seen: set[str] = set()
    hashes: dict[str, str] = {}
    for member in archive:
        name = normalized_name(member.name)
        if not name or member.isdir():
            continue
        if not member.isfile() or name not in CYE1_EXPECTED_FILES or name in seen:
            raise ValueError(f"Unexpected CYE1 overlay entry: {name}")
        seen.add(name)
        destination = root / name.removeprefix("Kernel/")
        if not within_root(destination, root) or destination.is_symlink():
            raise ValueError(f"Unsafe CYE1 overlay destination: {name}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"CYE1 overlay would overwrite a non-file: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError(f"Overlay member unreadable: {name}")
        # The destination is a fresh isolated tree; chmod is needed because
        # Samsung marks some upstream source files read-only.
        if destination.exists():
            destination.chmod(destination.stat().st_mode | 0o200)
        with stream, destination.open("wb") as out:
            shutil.copyfileobj(stream, out, length=1024 * 1024)
        hashes[name] = file_sha256(destination)
    if seen != CYE1_EXPECTED_FILES:
        raise ValueError(f"Unexpected CYE1 overlay file set: {sorted(seen)}")
    return hashes


def extract(bundle: Path, root: Path, expected_sha256: str = EXPECTED_BUNDLE_SHA256) -> dict:
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Source output must be empty: {root}")
    digest = file_sha256(bundle)
    if digest != expected_sha256:
        raise ValueError(f"Samsung bundle SHA256 mismatch: {digest}")
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as outer:
        if outer.testzip() is not None:
            raise ValueError("Samsung bundle failed ZIP CRC")
        if len(outer.namelist()) != 7 or len(set(outer.namelist())) != 7:
            raise ValueError("Expected exactly seven distinct Samsung ZIP members")
        with zipfile.ZipFile(outer.open(BASE_ZIP)) as zipped:
            with zipped.open("Kernel.tar.gz") as contents:
                with tarfile.open(fileobj=contents, mode="r|gz") as tar:
                    stats = unpack_base(tar, root)
        with zipfile.ZipFile(outer.open(CYE1_ZIP)) as zipped:
            with zipped.open(CYE1_TAR) as contents:
                with tarfile.open(fileobj=contents, mode="r|gz") as tar:
                    overlays = apply_cye1_overlay(tar, root)

    config = (root / "arch/arm64/configs/gta4xlvewifi_eur_open_defconfig").read_text()
    missing = REQUIRED_CONFIG_LINES - set(config.splitlines())
    if missing:
        raise ValueError(f"Required CYE1 config lines missing: {sorted(missing)}")
    makefile = (root / "Makefile").read_text()
    for line in ("VERSION = 4", "PATCHLEVEL = 14", "SUBLEVEL = 190"):
        if line not in makefile.splitlines():
            raise ValueError(f"Wrong kernel source release: {line}")
    return {
        "bundle_sha256": digest,
        "source": "Samsung P619 base + P613XXS8CYE1 three-file overlay",
        **stats,
        "overlay_file_sha256": overlays,
        "flash_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--kernel-out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = extract(args.bundle, args.kernel_out)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("SOURCE_RELEASE=SM-P619_BASE_PLUS_P613XXS8CYE1_OVERLAY")
    print(f"BASE_REGULAR_FILES={report['base_regular_files']}")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
