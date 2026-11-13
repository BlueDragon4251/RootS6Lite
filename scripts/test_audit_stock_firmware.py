import gzip
import hashlib
import struct
import unittest

from audit_stock_firmware import (FDT_MAGIC, boot_layout_metadata, boot_payload_metadata,
                                  fdt_metadata, parse_boot, parse_dtbo, scan_embedded_fdts)


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

    def test_boot_v2_extended_header_fields(self):
        boot = bytearray(4096)
        boot[:8] = b"ANDROID!"
        struct.pack_into("<8I", boot, 8, 512, 0, 1024, 0, 0, 0, 0, 4096)
        struct.pack_into("<I", boot, 40, 2)
        struct.pack_into("<IQI", boot, 1632, 256, 12288, 1660)
        struct.pack_into("<IQ", boot, 1648, 1024, 0x123400000)
        info = parse_boot(bytes(boot))
        self.assertEqual(info["recovery_dtbo_size"], 256)
        self.assertEqual(info["recovery_dtbo_offset"], 12288)
        self.assertEqual(info["header_size"], 1660)
        self.assertEqual(info["dtb_size"], 1024)
        self.assertEqual(info["dtb_addr"], "0x123400000")

    def test_gzip_stock_kernel_is_hashed_and_decompressed_safely(self):
        raw = bytearray(128)
        struct.pack_into("<I", raw, 56, 0x644D5241)
        raw.extend(b"Linux version 4.14.190-perf-test recorded separately")
        packed = gzip.compress(bytes(raw), mtime=0)
        image = b"\0" * 4096 + packed
        info = {"format": "android-boot", "header_version": 2, "page_size": 4096,
                "kernel_size": len(packed)}
        result = boot_payload_metadata(image, info)
        self.assertEqual(result["compression"], "gzip")
        self.assertEqual(result["gzip_status"], "complete")
        self.assertEqual(result["sha256"], hashlib.sha256(packed).hexdigest())
        self.assertEqual(result["decompressed_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(result["arm64_image_magic"])
        self.assertEqual(result["embedded_linux_release"], "4.14.190-perf-test")

    def test_android_v2_recovery_table_and_dtb_layout(self):
        fdt = synthetic_fdt()
        recovery = (struct.pack(">8I", 0xD7B7AB1E, 64 + len(fdt), 32, 32, 1, 32, 4096, 0)
                    + struct.pack(">8I", len(fdt), 64, 34, 0, 0, 0, 0, 0) + fdt)
        page = 4096
        rec_off = page * 3
        dtb_off = rec_off + page
        boot = bytearray(dtb_off + len(fdt))
        boot[:8] = b"ANDROID!"
        struct.pack_into("<8I", boot, 8, 64, 0, 64, 0, 0, 0, 0, page)
        struct.pack_into("<I", boot, 40, 2)
        struct.pack_into("<IQI", boot, 1632, len(recovery), rec_off, 1660)
        struct.pack_into("<IQ", boot, 1648, len(fdt), 0)
        boot[rec_off:rec_off + len(recovery)] = recovery
        boot[dtb_off:dtb_off + len(fdt)] = fdt
        result = boot_layout_metadata(bytes(boot), parse_boot(bytes(boot)))
        self.assertEqual(result["ramdisk_offset"], page * 2)
        self.assertEqual(result["recovery_dtbo"]["table"]["format"], "android-dtbo-table")
        self.assertEqual(result["recovery_dtbo"]["table"]["entries"][0]["fdt"]["sha256"],
                         hashlib.sha256(fdt).hexdigest())
        self.assertEqual(result["dtb_region"]["offset_bytes"], dtb_off)

    def test_boot_payload_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            boot_payload_metadata(b"\0" * 4096,
                                  {"format": "android-boot", "header_version": 2,
                                   "page_size": 4096, "kernel_size": 100})

    def test_boot_v4(self):
        boot = bytearray(4096)
        boot[:8] = b"ANDROID!"
        struct.pack_into("<4I", boot, 8, 2048, 256, 0, 1584)
        struct.pack_into("<I", boot, 40, 4)
        self.assertEqual(parse_boot(bytes(boot))["ramdisk_size"], 256)


if __name__ == "__main__":
    unittest.main()
