import hashlib
import struct
import unittest

from audit_stock_firmware import FDT_MAGIC, fdt_metadata, parse_boot, parse_dtbo, scan_embedded_fdts


def synthetic_fdt():
    names = b"model\0compatible\0qcom,board-id\0"
    def prop(nameoff, value):
        padding = b"\0" * ((-len(value)) % 4)
        return struct.pack(">3I", 3, len(value), nameoff) + value + padding
    tree = (
        struct.pack(">I", 1) + b"\0" * 4
        + prop(0, b"Samsung test\0")
        + prop(6, b"qcom,atoll-ab-idp\0")
        + prop(17, struct.pack(">2I", 34, 0))
        + struct.pack(">2I", 2, 9)
    )
    off_struct = 40 + 16
    off_strings = off_struct + len(tree)
    total = off_strings + len(names)
    header = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings,
                         40, 17, 16, 0, len(names), len(tree))
    return header + b"\0" * 16 + tree + names


class TestStockAudit(unittest.TestCase):
    def test_raw_fdt_and_hardware_id(self):
        fdt = fdt_metadata(synthetic_fdt())
        self.assertEqual(fdt["model"], ["Samsung test"])
        self.assertEqual(fdt["sha256"], hashlib.sha256(synthetic_fdt()).hexdigest())
        self.assertEqual(fdt["qcom_board_id"], ["0x22", "0x0"])
        self.assertEqual(parse_dtbo(synthetic_fdt())["format"], "raw-fdt")

    def test_android_dtbo_table(self):
        dt = synthetic_fdt()
        header = struct.pack(">8I", 0xD7B7AB1E, 64 + len(dt), 32, 32, 1, 32, 4096, 0)
        entry = struct.pack(">8I", len(dt), 64, 34, 0, 0, 0, 0, 0)
        parsed = parse_dtbo(header + entry + dt)
        self.assertEqual(parsed["format"], "android-dtbo-table")
        self.assertEqual(parsed["entries"][0]["fdt"]["compatible"], ["qcom,atoll-ab-idp"])

    def test_embedded_fdt_hash_covers_exact_tree_only(self):
        original = synthetic_fdt()
        image = b"X" * 41 + original + b"not part of the FDT"
        found = scan_embedded_fdts(image)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["offset_bytes"], 41)
        self.assertEqual(found[0]["fdt"]["fdt_total_bytes"], len(original))
        self.assertEqual(found[0]["fdt"]["sha256"], hashlib.sha256(original).hexdigest())

    def test_dtbo_table_entry_has_fdt_sha256(self):
        original = synthetic_fdt()
        header = struct.pack(">8I", 0xD7B7AB1E, 64 + len(original), 32, 32, 1, 32, 4096, 0)
        entry = struct.pack(">8I", len(original), 64, 34, 0, 0, 0, 0, 0)
        parsed = parse_dtbo(header + entry + original)
        self.assertEqual(parsed["entries"][0]["fdt"]["sha256"], hashlib.sha256(original).hexdigest())

    def test_truncated_dtbo_rejected(self):
        with self.assertRaises(ValueError):
            fdt_metadata(FDT_MAGIC + b"\0" * 20)
        with self.assertRaises(ValueError):
            parse_dtbo(struct.pack(">8I", 0xD7B7AB1E, 32, 32, 32, 1, 32, 4096, 0))

    def test_boot_v2(self):
        boot = bytearray(4096)
        boot[:8] = b"ANDROID!"
        struct.pack_into("<8I", boot, 8, 512, 0, 1024, 0, 0, 0, 0, 4096)
        struct.pack_into("<I", boot, 40, 2)
        self.assertEqual(parse_boot(bytes(boot))["kernel_size"], 512)
        self.assertEqual(parse_boot(bytes(boot))["header_version"], 2)

    def test_boot_v4(self):
        boot = bytearray(4096)
        boot[:8] = b"ANDROID!"
        struct.pack_into("<4I", boot, 8, 2048, 256, 0, 1584)
        struct.pack_into("<I", boot, 40, 4)
        self.assertEqual(parse_boot(bytes(boot))["ramdisk_size"], 256)


if __name__ == "__main__":
    unittest.main()
