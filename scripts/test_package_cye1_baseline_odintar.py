"""Small, stock-binary-free tests for the guarded CYE1 boot packager."""
import struct
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from package_cye1_baseline_odintar import (
    aligned, boot_v2_layout, parse_avb_info, replace_kernel_arg,
    stock_metadata, verify_ksu_inputs, verify_ksu_hook_manifest,
    KNOWN_FAILED_KSU_IMAGE_SHA256,
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

    def test_ksu_mode_rejects_missing_provenance_inputs(self):
        args = SimpleNamespace(ksu_config=None, system_map=None, baseline_image=None,
                               ksu_provenance=None, ksu_hooks_manifest=None)
        with self.assertRaisesRegex(ValueError, "KernelSU mode requires"):
            verify_ksu_inputs(args, b"KernelSU")

    def test_rejects_known_failed_ksu_image_before_reading_other_inputs(self):
        with patch("package_cye1_baseline_odintar.sha256", return_value=KNOWN_FAILED_KSU_IMAGE_SHA256):
            with self.assertRaisesRegex(ValueError, "Known failed on-device"):
                verify_ksu_inputs(SimpleNamespace(), b"fixture")

    def test_five_hook_manifest_requires_reboot_and_unmodified_detector(self):
        manifest = (
            "KPROBES_REMAIN_DISABLED=YES\n"
            "HOOKS=execve,execveat,compat_execve,compat_execveat,faccessat,read,newfstatat,reboot\n"
            "UPSTREAM_REBOOT_HOOK_DETECTOR=UNCHANGED\n"
        )
        verify_ksu_hook_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "provenance missing"):
            verify_ksu_hook_manifest(manifest.replace(",reboot", ""))
        with self.assertRaisesRegex(ValueError, "provenance missing"):
            verify_ksu_hook_manifest(manifest.replace("=UNCHANGED", "=REPLACED"))
        with self.assertRaisesRegex(ValueError, "incorrectly claims reboot"):
            verify_ksu_hook_manifest(manifest + "NO_OBSOLETE_REBOOT_HOOK=upstream_missing\n")


if __name__ == "__main__":
    unittest.main()
