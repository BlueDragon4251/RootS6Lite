#!/usr/bin/env python3
"""Local, opt-in SM-P613 CYE1 boot experiment packager; never runs in CI.

Requires the user's SHA256-pinned stock boot.img and a independently inspected,
CI-built, non-KernelSU Image. Keeps the original ramdisk/DTB and Samsung
SignerVer02 trailer. Replaces the OEM-signed AVB footer with a *self-consistent
but UNSIGNED* hash footer; bootloader acceptance is NOT established.

This is not an official Samsung image and carries no claim of safe booting.
"""
import argparse
import gzip
import hashlib
import io
import json
import re
import shlex
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from compare_full_cye1_export_abi import compare as compare_exports


STOCK_BOOT_SHA256 = "06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655"
STOCK_CONFIG_SHA256 = "1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208"
STOCK_PUBLIC_CERT_DER_SHA256 = "ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1"
PUBLIC_CERT_CONFIG_PATH = "certs/roots6lite-p613-cye1-oem-public.pem"
STOCK_KERNELRELEASE = "4.14.190-perf-28683246-abP613XXS8CYE1"
MKBOOTIMG_COMMIT = "028bdc06ce87ab1ee23204feb5cd5ee406484618"
AVBTOOL_COMMIT = "386fb90492db3bd6bc484a579bcde5b43a2a0292"
PARTITION_SIZE = 100663296
STOCK_DT_BYTES = 442884
STOCK_RAMDISK_BYTES = 725007


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aligned(value: int, page: int) -> int:
    return (value + page - 1) // page * page


def boot_v2_layout(data: bytes) -> dict:
    if len(data) < 1660 or data[:8] != b"ANDROID!":
        raise ValueError("Missing Android boot header")
    kernel_size = struct.unpack_from("<I", data, 8)[0]
    ramdisk_size = struct.unpack_from("<I", data, 16)[0]
    second_size = struct.unpack_from("<I", data, 24)[0]
    page, version = struct.unpack_from("<II", data, 36)
    recovery_size = struct.unpack_from("<I", data, 1632)[0]
    header_size, dtb_size = struct.unpack_from("<II", data, 1644)
    if version != 2 or page != 4096 or header_size != 1660:
        raise ValueError("Expected Samsung Android boot v2, 4096-byte pages")
    pos = page
    offsets = {}
    for name, size in (("kernel", kernel_size), ("ramdisk", ramdisk_size), ("second", second_size), ("recovery", recovery_size), ("dtb", dtb_size)):
        offsets[name] = (pos, pos + size)
        pos = aligned(pos + size, page)
    if offsets["dtb"][1] > len(data):
        raise ValueError("Truncated DTB")
    return {"page": page, "header_size": header_size, "kernel_size": kernel_size,
            "ramdisk_size": ramdisk_size, "dtb_size": dtb_size,
            "payload_end": pos, "offsets": offsets}


def stock_metadata(data: bytes, layout: dict, original_image_size: int) -> bytes:
    start = layout["payload_end"]
    if not start < original_image_size < len(data):
        raise ValueError("Invalid signed stock image boundary")
    tail = data[start:original_image_size]
    if len(tail) != 528 or not tail.startswith(b"SEANDROIDENFORCESignerVer02"):
        raise ValueError("Unexpected CYE1 Samsung signer trailer: do not guess")
    return tail


def run(*args: str) -> str:
    result = subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True)
    return result.stdout


def pinned_tool(script: Path, commit: str) -> None:
    if not script.is_file():
        raise ValueError(f"Missing tool {script}")
    head = run("git", "-C", str(script.parent), "rev-parse", "HEAD").strip()
    if head != commit:
        raise ValueError(f"Tool {script} has commit {head}, expected {commit}")


def parse_avb_info(text: str) -> tuple[int, str]:
    original = re.search(r"^Original image size:\s*(\d+) bytes\s*$", text, re.M)
    salt = re.search(r"^\s*Salt:\s*([a-f0-9]{64})\s*$", text, re.M)
    if not original or not salt or not re.search(r"^\s*Partition Name:\s*boot\s*$", text, re.M):
        raise ValueError("Unexpected stock AVB hash footer layout")
    if not re.search(r"^Algorithm:\s*SHA256_RSA4096\s*$", text, re.M):
        raise ValueError("Unexpected stock AVB signature algorithm")
    return int(original.group(1)), salt.group(1)


def verify_image_payload(candidate: bytes, raw_image: bytes, stock_boot: bytes, avb_original_size: int) -> dict:
    orig = boot_v2_layout(stock_boot)
    new = boot_v2_layout(candidate)
    if candidate[:8] != stock_boot[:8] or new["ramdisk_size"] != orig["ramdisk_size"] or new["dtb_size"] != orig["dtb_size"]:
        raise ValueError("Android header mismatch")
    if new["ramdisk_size"] != STOCK_RAMDISK_BYTES or new["dtb_size"] != STOCK_DT_BYTES:
        raise ValueError("Unrecognized stock ramdisk/DTB sizes")
    for section in ("ramdisk", "dtb"):
        x, y = new["offsets"][section]
        a, b = orig["offsets"][section]
        if candidate[x:y] != stock_boot[a:b]:
            raise ValueError(f"Stock {section} changed")
    start, end = new["offsets"]["kernel"]
    if gzip.decompress(candidate[start:end]) != raw_image:
        raise ValueError("Gzip kernel did not roundtrip")
    trailer = stock_metadata(stock_boot, orig, avb_original_size)
    if candidate[new["payload_end"]:new["payload_end"] + 528] != trailer:
        raise ValueError("Samsung signer block changed")
    # Header, address, command line and OS patch level must be copied through
    # mkbootimg. The kernel size and 32-byte v2 SHA-1 ID are intentionally new.
    old_head = bytearray(stock_boot[:4096])
    new_head = bytearray(candidate[:4096])
    for blob in (old_head, new_head):
        blob[8:12] = b"\0" * 4
        blob[576:608] = b"\0" * 32
    if old_head != new_head:
        raise ValueError("Unapproved Android header modification")
    return {"kernel_gzip_bytes": end - start, "ramdisk_sha256": sha256(candidate[new["offsets"]["ramdisk"][0]:new["offsets"]["ramdisk"][1]]),
            "dtb_sha256": sha256(candidate[new["offsets"]["dtb"][0]:new["offsets"]["dtb"][1]]),
            "samsung_signer_trailer_sha256": sha256(trailer)}


def replace_kernel_arg(unpack_output: str, image: Path) -> list[str]:
    args = shlex.split(unpack_output.strip())
    if args.count("--kernel") != 1 or args.count("--header_version") != 1:
        raise ValueError("Unexpected unpack_bootimg output")
    args[args.index("--kernel") + 1] = str(image)
    return args


def tar_odin(boot: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo(name="boot.img")
        info.size = boot.stat().st_size
        info.mtime = 0
        info.mode = 0o644
        with boot.open("rb") as source:
            tar.addfile(info, source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-boot", required=True, type=Path)
    parser.add_argument("--kernel-image", required=True, type=Path)
    parser.add_argument("--expected-kernel-sha256", required=True)
    parser.add_argument("--stock-ikconfig", required=True, type=Path)
    parser.add_argument("--built-config", required=True, type=Path)
    parser.add_argument("--module-symvers", required=True, type=Path)
    parser.add_argument("--abi-manifest", required=True, type=Path)
    parser.add_argument("--abi-reference", required=True, type=Path)
    parser.add_argument("--stock-public-cert", required=True, type=Path)
    parser.add_argument("--mkbootimg-directory", required=True, type=Path)
    parser.add_argument("--avbtool-directory", required=True, type=Path)
    parser.add_argument("--output-tar", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    mk = args.mkbootimg_directory / "mkbootimg.py"
    unpack = args.mkbootimg_directory / "unpack_bootimg.py"
    avb = args.avbtool_directory / "avbtool.py"
    pinned_tool(mk, MKBOOTIMG_COMMIT)
    pinned_tool(unpack, MKBOOTIMG_COMMIT)
    pinned_tool(avb, AVBTOOL_COMMIT)
    stock = args.stock_boot.read_bytes()
    if len(stock) != PARTITION_SIZE or sha256(stock) != STOCK_BOOT_SHA256:
        raise ValueError("Stock boot does not match exact P613XXS8CYE1 reference")
    image = args.kernel_image.read_bytes()
    if sha256(image) != args.expected_kernel_sha256.lower() or len(image) < 45000000 or image[56:60] != b"ARMd":
        raise ValueError("Unexpected compiled ARM64 Image (size, PE header, or digest)")
    if STOCK_KERNELRELEASE.encode() not in image:
        raise ValueError("Kernel release string mismatches Samsung stock vermagic")
    if b"KernelSU" in image:
        raise ValueError("Baseline Image unexpectedly contains KernelSU string")
    original_config = args.stock_ikconfig.read_bytes()
    if sha256(original_config) != STOCK_CONFIG_SHA256:
        raise ValueError("Original stock IKCONFIG SHA256 mismatch")
    expected_config = original_config.replace(
        b'CONFIG_SYSTEM_TRUSTED_KEYS=""',
        f'CONFIG_SYSTEM_TRUSTED_KEYS="{PUBLIC_CERT_CONFIG_PATH}"'.encode(),
    )
    if expected_config == original_config or args.built_config.read_bytes() != expected_config:
        raise ValueError("Effective CYE1 Kconfig deviates from stock beyond public certificate addition")
    # OpenSSL emits binary DER; subprocess text mode would corrupt it.
    cert = subprocess.run(["openssl", "x509", "-in", str(args.stock_public_cert), "-outform", "DER"],
                          check=True, capture_output=True).stdout
    if sha256(cert) != STOCK_PUBLIC_CERT_DER_SHA256 or image.count(cert) != 1:
        raise ValueError("OEM stock module-signing public certificate not uniquely embedded in compiled Image")
    abi = compare_exports(json.loads(args.abi_manifest.read_text()),
                          args.abi_reference.read_bytes(), args.module_symvers.read_bytes())
    if abi["reconstructed_stock_export_parity"] != "YES" or abi["exact_export_name_crc_class_matches"] != 12530:
        raise ValueError("CYE1 full reconstructed export name/CRC/class mismatch")
    avb_info = run(sys.executable, str(avb), "info_image", "--image", str(args.stock_boot))
    original_size, salt = parse_avb_info(avb_info)
    stock_layout = boot_v2_layout(stock)
    tail = stock_metadata(stock, stock_layout, original_size)

    with tempfile.TemporaryDirectory(prefix="roots6lite-baseline-") as temp_name:
        temp = Path(temp_name)
        stock_parts = temp / "stock_parts"
        stock_parts.mkdir()
        unpacked = run(sys.executable, str(unpack), "--boot_img", str(args.stock_boot), "--out", str(stock_parts), "--format", "mkbootimg")
        original_args = replace_kernel_arg(unpacked, stock_parts / "kernel")
        noop = temp / "noop.img"
        run(sys.executable, str(mk), *original_args, "-o", str(noop))
        if noop.read_bytes() != stock[:stock_layout["payload_end"]]:
            raise ValueError("AOSP no-op repack does NOT reproduce original Samsung boot payload")

        compressed = temp / "Image.gz"
        compressed.write_bytes(gzip.compress(image, compresslevel=9, mtime=0))
        candidate = temp / "boot.img"
        run(sys.executable, str(mk), *replace_kernel_arg(unpacked, compressed), "-o", str(candidate))
        with candidate.open("ab") as stream:
            stream.write(tail)
        # The OEM private AVB key is unavailable. The only honest test variant
        # for an *unlocked* device is a new, unsigned, internally consistent
        # hash footer. This is not a Samsung-signed image.
        run(sys.executable, str(avb), "add_hash_footer", "--image", str(candidate),
            "--partition_name", "boot", "--partition_size", str(PARTITION_SIZE),
            "--algorithm", "NONE", "--salt", salt)
        if candidate.stat().st_size != PARTITION_SIZE:
            raise ValueError("AVB partition size wrong")
        data = candidate.read_bytes()
        details = verify_image_payload(data, image, stock, original_size)
        unsigned_info = run(sys.executable, str(avb), "info_image", "--image", str(candidate))
        if not re.search(r"^Algorithm:\s*NONE\s*$", unsigned_info, re.M):
            raise ValueError("AVB algorithm is not explicitly unsigned")
        run(sys.executable, str(avb), "verify_image", "--image", str(candidate))
        args.output_tar.parent.mkdir(parents=True, exist_ok=True)
        tar_odin(candidate, args.output_tar)
        with tarfile.open(args.output_tar) as archive:
            names = archive.getnames()
            if names != ["boot.img"] or archive.extractfile("boot.img").read() != data:
                raise ValueError("Odin tar archive roundtrip failed")
        report = {
            "model": "SM-P613", "firmware": "P613XXS8CYE1", "mode": "NONROOT_BASELINE_BOOT_EXPERIMENT",
            "stock_boot_sha256": sha256(stock), "compiled_image_sha256": sha256(image),
            "compiled_image_bytes": len(image), "boot_image_sha256": sha256(data),
            "boot_image_bytes": len(data), "odin_tar_sha256": sha256(args.output_tar.read_bytes()),
            "odin_tar_bytes": args.output_tar.stat().st_size,
            "kernel_release": STOCK_KERNELRELEASE, "avb_algorithm": "NONE (unsigned)",
            "original_samsung_signer_block": "PRESERVED_BYTES_SIGNATURE_NOT_REVALIDATED",
            "physical_boot": "NOT_TESTED", "module_loading": "NOT_TESTED",
            "stock_module_signer_public_cert_sha256": STOCK_PUBLIC_CERT_DER_SHA256,
            "stock_module_signer_public_cert_embedded": True,
            "full_reconstructed_export_matches": abi["exact_export_name_crc_class_matches"],
            "module_symvers_sha256": abi["compiled_symvers_sha256"],
            "stock_config_byte_parity_except_public_cert": True,
            "recovery": "USER_MUST_HAVE_MATCHING_STOCK_ODIN_FIRMWARE_AND_DOWNLOAD_MODE",
            "flash_readiness": "UNVERIFIED_EXPERIMENTAL_ONLY", **details,
        }
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
