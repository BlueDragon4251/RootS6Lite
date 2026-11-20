"""Synthetic malformed/valid ELF coverage for the linked preinit gate."""

import struct
import unittest

from verify_kernelsu_preinit_elf import inspect


class KernelSUPreinitElfTests(unittest.TestCase):
    def make_image(self):
        runner = bytearray(0x4500)
        runner[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into(
            "<HHIQQQIHHHHHH", runner, 16,
            2, 183, 1, 0x402044, 64, 0, 0, 64, 56, 3, 0, 0, 0,
        )
        struct.pack_into("<IIQQQQQQ", runner, 64, 1, 5, 0, 0x400000, 0x400000, 0x3000, 0x3000, 65536)
        struct.pack_into("<IIQQQQQQ", runner, 120, 1, 6, 0x4000, 0x414000, 0x414000, 0x100, 0x200, 65536)
        struct.pack_into("<IIQQQQQQ", runner, 176, 0x6474E551, 6, 0, 0, 0, 0, 0, 16)
        image = b"\0" * 128 + bytes(runner)
        system_map = (
            "0000000000010000 T _text\n"
            "0000000000010080 T ksu_preinit_runner_start\n"
            f"{0x10080 + len(runner):016x} T ksu_preinit_runner_end\n"
        )
        return image, system_map

    def test_statical_arm64_elf_passes(self):
        image, symbol_map = self.make_image()
        result = inspect(image, symbol_map)
        self.assertTrue(result["KSU_PREINIT_ELF_LAYOUT_VALID"])
        self.assertEqual(result["KSU_PREINIT_RUNNER_BYTES"], 0x4500)
        self.assertEqual(result["PAGE_CONGRUENCE_VERIFIED"], [4096, 65536])
        self.assertEqual(result["FLASH_ALLOWED"], "NO")

    def test_misaligned_load_fails(self):
        image, symbol_map = self.make_image()
        broken = bytearray(image)
        struct.pack_into("<Q", broken, 128 + 120 + 8, 0x4001)
        with self.assertRaisesRegex(ValueError, "page congruence"):
            inspect(bytes(broken), symbol_map)

    def test_dynamic_elf_fails(self):
        image, symbol_map = self.make_image()
        broken = bytearray(image)
        struct.pack_into("<I", broken, 128 + 176, 2)
        with self.assertRaisesRegex(ValueError, "dynamically linked"):
            inspect(bytes(broken), symbol_map)

    def test_missing_linked_blob_fails(self):
        image, symbol_map = self.make_image()
        with self.assertRaisesRegex(ValueError, "Required linked symbols absent"):
            inspect(image, symbol_map.replace("ksu_preinit_runner_end", "another_name"))


if __name__ == "__main__":
    unittest.main()
