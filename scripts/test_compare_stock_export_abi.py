"""Synthetic, self-contained tests for raw-kernel ABI CRC reconstruction."""

import hashlib
import io
import struct
import unittest
from unittest import mock
import zipfile

import compare_stock_export_abi as audit


class KernelCRCAuditTests(unittest.TestCase):
    def fixture(self, changed_gpl: int = 0, break_anchor: bool = False):
        normal = [f"n{i:03d}" for i in range(20)]
        gpl = [f"z{i:03d}" for i in range(8)]
        names = normal + gpl
        base = 0x10000000
        normal_start = base + 0x100
        gpl_start = normal_start + len(normal) * 16
        crc_start = base + 0x400
        crc_gpl_start = crc_start + len(normal) * 4
        crc_end = crc_start + len(names) * 4
        original_crcs = {name: 0x10001234 + i * 17011 for i, name in enumerate(names)}
        lines = [
            f"{base:016x} T _text",
            f"{normal_start:016x} R __start___ksymtab",
            f"{gpl_start:016x} R __start___ksymtab_gpl",
            f"{gpl_start + len(gpl) * 16:016x} R __stop___ksymtab_gpl",
            f"{crc_start:016x} R __start___kcrctab",
            f"{crc_gpl_start:016x} R __start___kcrctab_gpl",
            f"{crc_end:016x} R __stop___kcrctab_gpl",
            f"{crc_end:016x} r __kstrtab_{names[0]}",
        ]
        for i, name in enumerate(names):
            lines.append(f"{normal_start + i * 16:016x} r __ksymtab_{name}")
        research = bytearray(4096)
        struct.pack_into(f"<{len(names)}I", research, 0x400,
                         *(original_crcs[name] for name in names))
        research_strtab = b"".join(name.encode() + b"\x00" for name in names)
        research[0x400 + len(names) * 4:0x400 + len(names) * 4 + len(research_strtab)] = research_strtab

        new_names = ["n017a", "n018a"]
        normal_stock = sorted(normal + new_names)
        stock_names = normal_stock + gpl
        stock_crcs = dict(original_crcs)
        stock_crcs["n019"] = 0x7abcdef1
        stock_crcs[new_names[0]] = 0x1234abcd
        stock_crcs[new_names[1]] = 0x2234abcd
        for i in range(changed_gpl):
            stock_crcs[gpl[i]] += 1
        stock = bytearray(4096)
        struct.pack_into(f"<{len(stock_names)}I", stock, 0x800,
                         *(stock_crcs[name] for name in stock_names))
        stock_strings_start = 0x800 + len(stock_names) * 4
        # kstrtab emission follows source/link object order, not lexical order;
        # preserve the same prefix in both binaries and append new names.
        stock_strtab = research_strtab + b"".join(x.encode() + b"\0" for x in new_names)
        stock[stock_strings_start:stock_strings_start + len(stock_strtab)] = stock_strtab
        if break_anchor:
            stock[0x800] ^= 0xFF
        symvers = "".join(
            f"0x{original_crcs[name]:08x}\t{name}\tvmlinux\tEXPORT_SYMBOL\n"
            for name in names
        ).encode()
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as z:
            z.writestr("_out/arch/arm64/boot/Image", research)
            z.writestr("_out/System.map", "\n".join(lines) + "\n")
            z.writestr("_out/Module.symvers", symvers)
        return bytes(stock), zbuf.getvalue(), symvers

    def audited(self, stock, zip_bytes, symvers):
        with mock.patch.object(audit, "STOCK_IMAGE_SHA256", hashlib.sha256(stock).hexdigest()), \
             mock.patch.object(audit, "RESEARCH_SYMVERS_SHA256", hashlib.sha256(symvers).hexdigest()):
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as artifact:
                return audit.compare(stock, artifact)

    def test_recovers_added_symbols_and_single_changed_crc(self):
        stock, archive, symvers = self.fixture()
        result = self.audited(stock, archive, symvers)
        self.assertEqual(result["stock_builtin_export_count"], 30)
        self.assertEqual(result["research_builtin_export_count"], 28)
        self.assertEqual(len(result["new_stock_exports"]), 2)
        self.assertEqual([x["name"] for x in result["changed_named_export_crcs"]], ["n019"])
        self.assertEqual(result["unchanged_named_export_crcs"], 27)

    def test_rejects_untrusted_stock_hash(self):
        stock, archive, symvers = self.fixture()
        with self.assertRaisesRegex(ValueError, "authenticated CYE1 digest"):
            with zipfile.ZipFile(io.BytesIO(archive)) as artifact:
                audit.compare(stock, artifact)

    def test_rejects_missing_stock_crc_anchor(self):
        stock, archive, symvers = self.fixture(break_anchor=True)
        with self.assertRaisesRegex(ValueError, "CRC: anchor missing"):
            self.audited(stock, archive, symvers)

    def test_rejects_weak_gpl_alignment(self):
        stock, archive, symvers = self.fixture(changed_gpl=2)
        with self.assertRaisesRegex(ValueError, "GPL group parity weak"):
            self.audited(stock, archive, symvers)

    def test_rejects_duplicate_anchor(self):
        with self.assertRaisesRegex(ValueError, "not unique"):
            audit.unique_anchor(b"ab" * 40, b"ab" * 16, "test")


if __name__ == "__main__":
    unittest.main()
