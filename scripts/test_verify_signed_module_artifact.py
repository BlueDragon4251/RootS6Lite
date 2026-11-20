"""Unit tests for detached research-kernel module signature framing."""

import struct
import unittest

from verify_signed_module_artifact import MAGIC, signed_payload_and_signature


class SignedModuleFramingTests(unittest.TestCase):
    def test_split_valid_module(self):
        payload = b"\x7fELFkernel-module-data"
        sig = b"pkcs7-signature"
        info = bytes((0, 0, 2, 0, 0, 0, 0, 0)) + struct.pack(">I", len(sig))
        self.assertEqual(signed_payload_and_signature(payload + sig + info + MAGIC),
                         (payload, sig))

    def test_missing_trailer(self):
        with self.assertRaisesRegex(ValueError, "missing module signature marker"):
            signed_payload_and_signature(b"\x7fELFunsigned")

    def test_unsupported_signer_record(self):
        payload = b"\x7fELF"
        info = bytes((0, 0, 1, 0, 0, 0, 0, 0)) + struct.pack(">I", 3)
        with self.assertRaisesRegex(ValueError, "unsupported module signature header"):
            signed_payload_and_signature(payload + b"sig" + info + MAGIC)

    def test_out_of_bounds_sig_len(self):
        payload = b"\x7fELF"
        info = bytes((0, 0, 2, 0, 0, 0, 0, 0)) + struct.pack(">I", 2000)
        with self.assertRaisesRegex(ValueError, "outside ELF payload"):
            signed_payload_and_signature(payload + b"sig" + info + MAGIC)


if __name__ == "__main__":
    unittest.main()
