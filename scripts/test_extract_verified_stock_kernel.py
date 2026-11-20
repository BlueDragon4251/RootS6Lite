"""Offline tests; never require a real firmware image."""

import gzip
import hashlib
import struct
import unittest

from extract_verified_stock_kernel import extract


def digest(b):
    return hashlib.sha256(b).hexdigest()


def make_boot(image=None, page=4096):
    if image is None:
        header = bytearray(64)
        struct.pack_into("<I", header, 56, 0x644D5241)
        image = bytes(header) + b"example-test-kernel"
    compressed = gzip.compress(image)
    boot = bytearray(page + len(compressed))
    boot[:8] = b"ANDROID!"
    struct.pack_into("<I", boot, 8, len(compressed))
    struct.pack_into("<I", boot, 36, page)
    boot[page:] = compressed
    return bytes(boot), image


class ExtractStockKernelTests(unittest.TestCase):
    def test_verified_original_and_image(self):
        boot, image = make_boot()
        self.assertEqual(extract(boot, digest(boot), digest(image)), image)

    def test_rejects_untrusted_boot(self):
        boot, image = make_boot()
        with self.assertRaisesRegex(ValueError, "trusted reference"):
            extract(boot, "f" * 64, digest(image))

    def test_rejects_mismatched_decompressed_kernel(self):
        boot, image = make_boot()
        with self.assertRaisesRegex(ValueError, "does not match trusted reference"):
            extract(boot, digest(boot), "0" * 64)

    def test_rejects_wrong_architecture_magic(self):
        boot, image = make_boot(image=b"X" * 100)
        with self.assertRaisesRegex(ValueError, "ARM64 Linux Image header"):
            extract(boot, digest(boot), digest(image))

    def test_rejects_bad_page_size(self):
        boot, image = make_boot(page=4096)
        changed = bytearray(boot)
        struct.pack_into("<I", changed, 36, 1234)
        with self.assertRaisesRegex(ValueError, "page size"):
            extract(bytes(changed), digest(changed), digest(image))


if __name__ == "__main__":
    unittest.main()
