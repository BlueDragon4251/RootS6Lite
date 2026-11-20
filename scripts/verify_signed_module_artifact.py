#!/usr/bin/env python3
"""Cryptographically check detached PKCS#7 signatures in a research CI ZIP.

The verified certificate belongs to this *one experimental CI kernel*, not
to Samsung's stock firmware. Passing does not establish device bootability.
"""

import argparse
import subprocess
import struct
import tempfile
import zipfile
from pathlib import Path


MAGIC = b"~Module signature appended~\n"
INFO_SIZE = 12


def signed_payload_and_signature(blob: bytes) -> tuple[bytes, bytes]:
    if not blob.endswith(MAGIC):
        raise ValueError("missing module signature marker")
    end = len(blob) - len(MAGIC)
    if end < INFO_SIZE:
        raise ValueError("truncated module signature header")
    info = blob[end - INFO_SIZE : end]
    sig_len = struct.unpack(">I", info[-4:])[0]
    if info[2] != 2 or info[3:5] != b"\x00\x00" or sig_len == 0:
        raise ValueError("unsupported module signature header")
    begin = end - INFO_SIZE - sig_len
    if begin <= 0:
        raise ValueError("module signature outside ELF payload")
    return blob[:begin], blob[begin : end - INFO_SIZE]


def verify_archive(path: Path) -> int:
    with zipfile.ZipFile(path) as artifact:
        candidates = sorted(
            x for x in artifact.namelist()
            if x.startswith("_signed_modules/lib/modules/")
            and "/kernel/" in x and x.endswith(".ko")
        )
        if not candidates:
            raise ValueError("no signed modules in the kernel staging tree")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            der = temp / "signing.der"
            pem = temp / "signing.pem"
            payload = temp / "module.unsigned"
            signature = temp / "signature.der"
            der.write_bytes(artifact.read("_evidence/ci-ephemeral-signing-cert.der"))
            subprocess.run(
                ["openssl", "x509", "-inform", "DER", "-in", str(der),
                 "-out", str(pem)], check=True, capture_output=True,
            )
            for candidate in candidates:
                unsigned, sig = signed_payload_and_signature(artifact.read(candidate))
                payload.write_bytes(unsigned)
                signature.write_bytes(sig)
                result = subprocess.run(
                    ["openssl", "cms", "-verify", "-binary", "-inform", "DER",
                     "-noverify", "-certfile", str(pem), "-content", str(payload),
                     "-in", str(signature), "-out", "/dev/null"],
                    capture_output=True, text=True,
                )
                if result.returncode:
                    raise ValueError(
                        f"PKCS#7 signature invalid for {candidate}: {result.stderr.strip()}"
                    )
                print(f"CRYPTOGRAPHIC_MODULE_SIGNATURE=VERIFIED {candidate}")
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    arguments = parser.parse_args()
    count = verify_archive(arguments.artifact)
    print(f"VERIFIED_MODULE_COUNT={count}")
    print("STOCK_MODULE_TRUST=UNVERIFIED; FLASH_ALLOWED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
