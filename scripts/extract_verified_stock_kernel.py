#!/usr/bin/env python3
"""Extract only the gzip ARM64 kernel from a verified Samsung Android boot.img.

This never extracts the ramdisk, modifies the original image, or creates an
Odin/Android boot image. An exact supplied original-file digest is mandatory.
"""

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import struct


MAX_KERNEL_BYTES = 128 * 1024 * 1024
ARM64_IMAGE_MAGIC = 0x644D5241


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def extract(boot: bytes, expected_boot_sha: str, expected_image_sha: str) -> bytes:
    if sha256(boot) != expected_boot_sha.lower():
        raise ValueError("Original boot.img SHA256 does not match the trusted reference")
    if len(boot) < 4096 or boot[:8] != b"ANDROID!":
        raise ValueError("Not an Android boot image")

    kernel_bytes = struct.unpack_from("<I", boot, 8)[0]
    page_bytes = struct.unpack_from("<I", boot, 36)[0]
    if page_bytes not in (2048, 4096, 8192, 16384):
        raise ValueError(f"Unexpected Android boot page size {page_bytes}")
    if kernel_bytes <= 0 or page_bytes + kernel_bytes > len(boot):
        raise ValueError("Invalid kernel payload size in boot header")
    payload = boot[page_bytes : page_bytes + kernel_bytes]
    if not payload.startswith(b"\x1f\x8b\x08"):
        raise ValueError("Stock kernel payload is not expected gzip format")

    # The trusted stock metadata limits the uncompressed size; a larger or
    # malformed gzip stream must not be written to disk.
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
        image = stream.read(MAX_KERNEL_BYTES + 1)
        if len(image) > MAX_KERNEL_BYTES or stream.read(1):
            raise ValueError("Kernel decompression exceeded safety limit")
    if len(image) < 64 or struct.unpack_from("<I", image, 56)[0] != ARM64_IMAGE_MAGIC:
        raise ValueError("Decompressed bytes lack the ARM64 Linux Image header")
    if sha256(image) != expected_image_sha.lower():
        raise ValueError("Stock ARM64 Image SHA256 does not match trusted reference")
    return image


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", type=Path, required=True)
    p.add_argument("--boot-sha256", required=True)
    p.add_argument("--image-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    image = extract(args.boot.read_bytes(), args.boot_sha256, args.image_sha256)
    args.output.write_bytes(image)
    print(f"ORIGINAL_BOOT_SHA256_VERIFIED=YES")
    print(f"STOCK_IMAGE_SHA256={sha256(image)}")
    print(f"STOCK_IMAGE_BYTES={len(image)}")
    print("RAMDISK_EXTRACTED=NO")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
