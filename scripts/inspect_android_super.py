#!/usr/bin/env python3
"""Streaming Android sparse + liblp super image inspector and extractor.

Uses official AOSP libsparse and liblp metadata layout. It never modifies,
flashes or tries to mount the supplied image. Optional single-partition
extraction creates a new file, refusing to overwrite existing data. No
third-party Python dependencies or full raw-super image conversion.
"""

import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct


SPARSE_MAGIC = 0xED26FF3A
GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030
SPARSE_HEADER = struct.Struct("<IHHHHIIII")
CHUNK_HEADER = struct.Struct("<HHII")
PARTITION_ENTRY = struct.Struct("<36sIIII")
EXTENT_ENTRY = struct.Struct("<QIQI")
SECTOR_SIZE = 512
GEOMETRY_OFFSET = 4096
GEOMETRY_SIZE = 4096
METADATA_OFFSET = GEOMETRY_OFFSET + 2 * GEOMETRY_SIZE
CHUNK_RAW, CHUNK_FILL, CHUNK_SKIP, CHUNK_CRC = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class SparseReader:
    """Logical random-access reads over sparse chunks, without expanding them."""

    def __init__(self, path: Path):
        self.path = path
        self.file = path.open("rb")
        try:
            self._initialize()
        except BaseException:
            self.file.close()
            raise

    def _initialize(self) -> None:
        self.file_size = self.path.stat().st_size
        first = self.file.read(SPARSE_HEADER.size)
        require(len(first) == SPARSE_HEADER.size, "truncated image header")
        (magic, major, _minor, header_size, chunk_header_size, block_size,
         total_blocks, total_chunks, _crc) = SPARSE_HEADER.unpack(first)
        self.sparse = magic == SPARSE_MAGIC
        self.chunks = []
        self.starts = []
        if not self.sparse:
            self.size = self.file_size
            return
        require(major == 1 and header_size >= 28 and chunk_header_size >= 12,
                "unsupported Android sparse version/header")
        require(block_size >= 512 and block_size % 4 == 0,
                "invalid sparse block size")
        require(0 < total_chunks < 2_000_000 and total_blocks > 0,
                "invalid sparse chunk/block count")
        self.size = total_blocks * block_size
        require(header_size <= self.file_size, "truncated sparse header extension")
        self.file.seek(header_size)
        logical = 0
        for index in range(total_chunks):
            packed = self.file.read(chunk_header_size)
            require(len(packed) == chunk_header_size, f"truncated chunk header {index}")
            kind, _reserved, chunk_blocks, total_size = CHUNK_HEADER.unpack_from(packed)
            require(total_size >= chunk_header_size, f"invalid size of chunk {index}")
            size = chunk_blocks * block_size
            data_size = total_size - chunk_header_size
            if kind == CHUNK_RAW:
                require(data_size == size, f"invalid RAW chunk length {index}")
            elif kind == CHUNK_FILL:
                require(data_size == 4, f"invalid FILL chunk length {index}")
            elif kind == CHUNK_SKIP:
                require(data_size == 0, f"invalid SKIP chunk length {index}")
            elif kind == CHUNK_CRC:
                require(data_size == 4 and chunk_blocks == 0,
                        f"invalid CRC chunk {index}")
            else:
                raise ValueError(f"unsupported sparse chunk type {kind:04x}")
            data_offset = self.file.tell()
            require(data_offset + data_size <= self.file_size,
                    f"truncated sparse data chunk {index}")
            if size:
                self.starts.append(logical)
                self.chunks.append((logical, logical + size, kind, data_offset))
                logical += size
            self.file.seek(data_size, 1)
        require(logical == self.size, "sparse chunks do not cover declared image size")

    def read(self, offset: int, size: int) -> bytes:
        require(offset >= 0 and size >= 0 and offset + size <= self.size,
                "read outside logical image")
        if not self.sparse:
            self.file.seek(offset)
            data = self.file.read(size)
            require(len(data) == size, "truncated raw image")
            return data
        output = bytearray()
        end = offset + size
        while offset < end:
            i = bisect.bisect_right(self.starts, offset) - 1
            require(i >= 0, "sparse read maps outside a chunk")
            begin, chunk_end, kind, data_offset = self.chunks[i]
            require(offset < chunk_end, "sparse read in a chunk gap")
            take = min(end, chunk_end) - offset
            if kind == CHUNK_RAW:
                self.file.seek(data_offset + offset - begin)
                payload = self.file.read(take)
                require(len(payload) == take, "truncated RAW chunk")
                output.extend(payload)
            elif kind == CHUNK_FILL:
                self.file.seek(data_offset)
                word = self.file.read(4)
                relative = offset - begin
                output.extend((word * ((relative % 4 + take + 3) // 4 + 1))
                              [relative % 4:relative % 4 + take])
            else:
                output.extend(b"\x00" * take)
            offset += take
        return bytes(output)

    def close(self) -> None:
        self.file.close()


def _checksum_ok(data: bytes, digest_start: int) -> bool:
    masked = bytearray(data)
    original = masked[digest_start:digest_start + 32]
    masked[digest_start:digest_start + 32] = b"\x00" * 32
    return hashlib.sha256(masked).digest() == original


def _ascii_name(data: bytes) -> str:
    raw = data.split(b"\x00", 1)[0]
    require(bool(re.fullmatch(rb"[A-Za-z0-9_]+", raw)),
            "invalid liblp partition name")
    return raw.decode("ascii")


def inspect_super(reader: SparseReader) -> dict:
    geo_head = reader.read(GEOMETRY_OFFSET, 52)
    magic, geo_size = struct.unpack_from("<II", geo_head)
    require(magic == GEOMETRY_MAGIC, "liblp primary geometry not found at 4096")
    require(52 <= geo_size <= GEOMETRY_SIZE, "invalid liblp geometry size")
    geometry = reader.read(GEOMETRY_OFFSET, geo_size)
    require(_checksum_ok(geometry, 8), "liblp geometry checksum mismatch")
    max_size, slot_count, logical_block_size = struct.unpack_from("<III", geometry, 40)
    require(max_size % SECTOR_SIZE == 0 and 128 <= max_size <= 4 * 1024 * 1024,
            "invalid liblp metadata max size")
    require(1 <= slot_count <= 4 and logical_block_size % SECTOR_SIZE == 0,
            "invalid metadata slot count or logical block size")

    meta_offset = METADATA_OFFSET
    header_start = reader.read(meta_offset, 128)
    magic, major, minor, header_size = struct.unpack_from("<IHHI", header_start)
    require(magic == HEADER_MAGIC and major == 10 and 0 <= minor <= 2,
            "unsupported liblp metadata header/version")
    require(header_size == (256 if minor >= 2 else 128),
            "unexpected liblp metadata header size")
    header = reader.read(meta_offset, header_size)
    require(_checksum_ok(header, 12), "liblp metadata header checksum mismatch")
    tables_size = struct.unpack_from("<I", header, 44)[0]
    require(tables_size <= max_size - header_size,
            "liblp metadata exceeds declared maximum")
    tables = reader.read(meta_offset + header_size, tables_size)
    require(hashlib.sha256(tables).digest() == header[48:80],
            "liblp metadata tables checksum mismatch")

    def table(index: int, expected_size: int) -> list[bytes]:
        offset, count, record_size = struct.unpack_from("<III", header, 80 + index * 12)
        require(record_size == expected_size and count <= 500_000,
                f"invalid liblp table {index} dimensions")
        require(offset <= tables_size and count * record_size <= tables_size - offset,
                f"liblp table {index} is outside metadata")
        return [tables[offset + n * record_size:offset + (n + 1) * record_size]
                for n in range(count)]

    partitions = table(0, PARTITION_ENTRY.size)
    extents = table(1, EXTENT_ENTRY.size)
    groups = table(2, 48)
    devices = table(3, 64)
    require(len(devices) >= 1, "liblp has no physical block device")
    results = []
    seen = set()
    for part in partitions:
        name_raw, attrs, first, count, group = PARTITION_ENTRY.unpack(part)
        name = _ascii_name(name_raw)
        require(name not in seen, "duplicate liblp partition name")
        seen.add(name)
        require(first <= len(extents) and count <= len(extents) - first,
                f"partition {name} references invalid extents")
        require(group < len(groups), f"partition {name} references invalid group")
        size = 0
        layouts = []
        for item in extents[first:first + count]:
            sectors, target_type, target_data, source = EXTENT_ENTRY.unpack(item)
            require(target_type in (0, 1), f"partition {name} unknown extent type")
            if target_type == 0:
                require(source < len(devices), f"partition {name} invalid block device")
                require(source != 0 or (target_data + sectors) * SECTOR_SIZE <= reader.size,
                        f"partition {name} extent exceeds image size")
            size += sectors * SECTOR_SIZE
            layouts.append({"kind": "linear" if target_type == 0 else "zero",
                            "bytes": sectors * SECTOR_SIZE, "device_index": source,
                            "physical_sector": target_data if target_type == 0 else None})
        results.append({"name": name, "size_bytes": size, "attributes": attrs,
                        "extent_count": count, "extents": layouts})
    return {"type": "Android sparse" if reader.sparse else "raw",
            "logical_image_size_bytes": reader.size,
            "sparse_input_size_bytes": reader.file_size,
            "metadata_version": f"{major}.{minor}", "metadata_slot_count": slot_count,
            "physical_device_count": len(devices), "partitions": results}


def extract_partition(reader: SparseReader, partition: dict, output: Path) -> str:
    """Copy one validated logical partition; never overwrite an existing file."""
    require(not output.exists(), f"output already exists: {output}")
    require(partition["size_bytes"] > 0, "refusing to extract empty partition")
    for extent in partition["extents"]:
        require(extent["kind"] == "zero" or extent["device_index"] == 0,
                "cannot extract a partition backed by an external block device")
    partial = output.with_name(output.name + ".partial")
    digest = hashlib.sha256()
    written = 0
    chunk_size = 1024 * 1024
    with partial.open("xb") as destination:
        for extent in partition["extents"]:
            count = extent["bytes"]
            physical = (extent["physical_sector"] or 0) * SECTOR_SIZE
            copied = 0
            while copied < count:
                take = min(chunk_size, count - copied)
                if extent["kind"] == "zero":
                    block = b"\x00" * take
                else:
                    block = reader.read(physical + copied, take)
                destination.write(block)
                digest.update(block)
                copied += take
                written += take
    require(written == partition["size_bytes"], "partition copy is incomplete")
    partial.rename(output)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="original super.img (sparse or raw)")
    parser.add_argument("--json", action="store_true", help="print detailed JSON instead")
    parser.add_argument("--extract-partition", metavar="NAME",
                        help="copy only the named logical partition into a new file")
    parser.add_argument("--output", type=Path, help="output path for --extract-partition")
    args = parser.parse_args()
    if args.output and not args.extract_partition:
        parser.error("--output requires --extract-partition")
    if args.extract_partition and not args.output:
        parser.error("--extract-partition requires --output")
    reader = SparseReader(args.image)
    try:
        report = inspect_super(reader)
        if args.extract_partition:
            match = next((p for p in report["partitions"]
                          if p["name"] == args.extract_partition), None)
            require(match is not None,
                    f"partition not found: {args.extract_partition}")
            digest = extract_partition(reader, match, args.output)
            print(f"Extracted {match['name']} to {args.output}")
            print(f"Bytes: {match['size_bytes']:,}, SHA256: {digest}")
            return
    finally:
        reader.close()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Format: {report['type']}, metadata: {report['metadata_version']}, "
              f"slots: {report['metadata_slot_count']}")
        print(f"Logical super size: {report['logical_image_size_bytes']:,} bytes")
        for partition in report["partitions"]:
            print(f"{partition['name']:<24} {partition['size_bytes']:>14,} bytes "
                  f"({partition['extent_count']} extent(s))")


if __name__ == "__main__":
    main()
