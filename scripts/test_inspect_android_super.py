"""Small synthetic Android sparse and liblp images; no real firmware required."""

import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import inspect_android_super as super_image


def add_digest(blob: bytearray, offset: int) -> None:
    blob[offset:offset + 32] = b"\x00" * 32
    blob[offset:offset + 32] = hashlib.sha256(blob).digest()


def build_raw() -> bytearray:
    image = bytearray(64 * 4096)
    geo = bytearray(52)
    struct.pack_into("<II", geo, 0, super_image.GEOMETRY_MAGIC, 52)
    struct.pack_into("<III", geo, 40, 4096, 1, 4096)
    add_digest(geo, 8)
    image[4096:4096 + len(geo)] = geo

    partition = struct.pack("<36sIIII", b"vendor", 1, 0, 1, 0)
    extent = struct.pack("<QIQI", 8, 0, 64, 0)
    group = struct.pack("<36sIQ", b"default", 0, 0)
    device = struct.pack("<QIIQ36sI", 32, 4096, 0, len(image), b"super", 0)
    tables = partition + extent + group + device
    header = bytearray(128)
    struct.pack_into("<IHHI", header, 0, super_image.HEADER_MAGIC, 10, 0, 128)
    struct.pack_into("<I", header, 44, len(tables))
    header[48:80] = hashlib.sha256(tables).digest()
    offset = 0
    for index, entry in enumerate((partition, extent, group, device)):
        struct.pack_into("<III", header, 80 + index * 12, offset, 1, len(entry))
        offset += len(entry)
    add_digest(header, 12)
    image[12288:12288 + 128] = header
    image[12288 + 128:12288 + 128 + len(tables)] = tables
    return image


def build_sparse(image: bytes) -> bytes:
    header = super_image.SPARSE_HEADER.pack(super_image.SPARSE_MAGIC, 1, 0,
                                            28, 12, 4096, 64, 3, 0)
    first = super_image.CHUNK_HEADER.pack(super_image.CHUNK_RAW, 0, 8,
                                           12 + 8 * 4096) + image[:8 * 4096]
    second = super_image.CHUNK_HEADER.pack(super_image.CHUNK_FILL, 0, 1, 16)
    third = super_image.CHUNK_HEADER.pack(super_image.CHUNK_SKIP, 0, 55, 12)
    return header + first + second + b"\x11\x22\x33\x44" + third


class SuperInspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "super.img"

    def test_raw_geometry_and_partition(self):
        self.path.write_bytes(build_raw())
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        result = super_image.inspect_super(reader)
        self.assertEqual(result["type"], "raw")
        self.assertEqual(result["metadata_version"], "10.0")
        self.assertEqual(result["partitions"][0]["name"], "vendor")
        self.assertEqual(result["partitions"][0]["size_bytes"], 4096)

    def test_sparse_partition_without_expansion(self):
        raw = build_raw()
        self.path.write_bytes(build_sparse(raw))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        self.assertEqual(reader.size, len(raw))
        self.assertEqual(reader.read(4096, 52), raw[4096:4096 + 52])
        self.assertEqual(reader.read(8 * 4096 - 4, 12),
                         raw[8 * 4096 - 4:8 * 4096] + b"\x11\x22\x33\x44" * 2)
        self.assertEqual(reader.read(9 * 4096, 16), bytes(16))
        result = super_image.inspect_super(reader)
        self.assertEqual(result["type"], "Android sparse")
        self.assertEqual(result["partitions"][0]["name"], "vendor")

    def test_extract_only_vendor_from_sparse_without_expanding_super(self):
        self.path.write_bytes(build_sparse(build_raw()))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        vendor = super_image.inspect_super(reader)["partitions"][0]
        output = Path(self.temp.name) / "vendor.img"
        sha = super_image.extract_partition(reader, vendor, output)
        expected = b"\x11\x22\x33\x44" * 1024
        self.assertEqual(output.read_bytes(), expected)
        self.assertEqual(sha, hashlib.sha256(expected).hexdigest())
        self.assertFalse((Path(self.temp.name) / "vendor.img.partial").exists())

    def test_extract_refuses_existing_target(self):
        self.path.write_bytes(build_sparse(build_raw()))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        vendor = super_image.inspect_super(reader)["partitions"][0]
        output = Path(self.temp.name) / "vendor.img"
        output.write_bytes(b"keep existing user data")
        with self.assertRaisesRegex(ValueError, "already exists"):
            super_image.extract_partition(reader, vendor, output)
        self.assertEqual(output.read_bytes(), b"keep existing user data")

    def test_extract_refuses_external_physical_device(self):
        self.path.write_bytes(build_sparse(build_raw()))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        vendor = super_image.inspect_super(reader)["partitions"][0]
        vendor["extents"][0]["device_index"] = 1
        output = Path(self.temp.name) / "vendor.img"
        with self.assertRaisesRegex(ValueError, "external block device"):
            super_image.extract_partition(reader, vendor, output)
        self.assertFalse(output.exists())

    def test_rejects_truncated_raw_chunk(self):
        # A truncated trailing SKIP has no physical data, so corrupt RAW instead.
        data = build_sparse(build_raw())
        self.path.write_bytes(data[:100])
        with self.assertRaisesRegex(ValueError, "truncated sparse data"):
            super_image.SparseReader(self.path)

    def test_rejects_invalid_geometry_checksum(self):
        raw = build_raw()
        raw[4110] ^= 1
        self.path.write_bytes(build_sparse(raw))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        with self.assertRaisesRegex(ValueError, "geometry checksum"):
            super_image.inspect_super(reader)

    def test_rejects_bad_partition_table_checksum(self):
        raw = build_raw()
        raw[12288 + 128] ^= 1
        self.path.write_bytes(build_sparse(raw))
        reader = super_image.SparseReader(self.path)
        self.addCleanup(reader.close)
        with self.assertRaisesRegex(ValueError, "tables checksum"):
            super_image.inspect_super(reader)


if __name__ == "__main__":
    unittest.main()
