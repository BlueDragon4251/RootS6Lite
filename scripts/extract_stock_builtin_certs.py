#!/usr/bin/env python3
"""Discover public X.509 DER certificates embedded in a decompressed kernel.

This is read-only and does not recover or infer private signing keys.
"""
import argparse
import hashlib
import json
from pathlib import Path

from cryptography import x509


def find_certs(image: bytes):
    start = 0
    seen = set()
    while True:
        pos = image.find(b"\x30\x82", start)
        if pos < 0:
            break
        start = pos + 1
        if pos + 4 > len(image):
            continue
        length = int.from_bytes(image[pos + 2:pos + 4], "big") + 4
        if not 500 <= length <= 8192 or pos + length > len(image):
            continue
        der = image[pos:pos + length]
        try:
            cert = x509.load_der_x509_certificate(der)
        except ValueError:
            continue
        fingerprint = hashlib.sha256(der).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        yield pos, der, cert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="decompressed ARM64 Image")
    parser.add_argument("--out", type=Path, help="optional directory for public DER certs")
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
    data = args.image.read_bytes()
    results = []
    for pos, der, cert in find_certs(data):
        digest = hashlib.sha256(der).hexdigest()
        results.append({
            "offset": pos,
            "length": len(der),
            "sha256": digest,
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
        })
        if args.out:
            (args.out / f"cert-{pos:08x}-{digest[:12]}.der").write_bytes(der)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
