"""Small, stock-binary-free tests for the guarded CYE1 boot packager."""
import struct
import unittest

from package_cye1_baseline_odintar import (
    aligned, boot_v2_layout, parse_avb_info, replace_kernel_arg, stock_metadata,
)


class BootPackageTests(unittest.TestCase):
    def test_alignment(self):
        self.assertEqual(aligned(4097, 4096), 8192)
        self.assertEqual(aligned(8192, 4096), 8192)

    def test_only_header_v2_is_accepted(self):
        data = bytearray(4096 * 4)
        data[:8] = b"ANDROID!"
        struct.pack_into("<II", data, 36, 4096, 1)
        struct.pack_into("<I", data, 1644, 1660)
        with self.assertRaisesRegex(ValueError, "Expected Samsung Android boot v2"):
            boot_v2_layout(bytes(data))
        struct.pack_into("<I", data, 40, 2)
        layout = boot_v2_layout(bytes(data))
        self.assertEqual(layout["payload_end"], 4096)

    def test_samsung_metadata_requires_full_struct(self):
        layout = {"payload_end": 4096}
        data = b"x" * 4096 + b"SEANDROIDENFORCESignerVer02" + b"\0" * 501 + b"x" * 99
        trailer = stock_metadata(data, layout, 4096 + 528)
        self.assertEqual(len(trailer), 528)
        with self.assertRaisesRegex(ValueError, "Unexpected CYE1 Samsung"):
            stock_metadata(b"x" * 5000, layout, 4096 + 528)

    def test_replaces_exactly_one_kernel_argument(self):
        cmd = "--header_version 2 --kernel /tmp/old --ramdisk '/tmp/a b'"
        from pathlib import Path
        args = replace_kernel_arg(cmd, Path("new.gz"))
        self.assertEqual(args[args.index("--kernel") + 1], "new.gz")
        self.assertIn("/tmp/a b", args)

    def test_stock_avb_is_a_signed_boot_hash(self):
        desc = """Original image size: 20263440 bytes
Algorithm:                SHA256_RSA4096
      Partition Name:        boot
      Salt:                  618de7695a6e6fef760ab7c35bea5a05d2f943d1de9df0f766fb753ec3226d69
"""
        size, salt = parse_avb_info(desc)
        self.assertEqual(size, 20263440)
        self.assertEqual(len(salt), 64)
        with self.assertRaisesRegex(ValueError, "Unexpected stock AVB"):
            parse_avb_info(desc.replace("SHA256_RSA4096", "NONE"))


if __name__ == "__main__":
    unittest.main()
