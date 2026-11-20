import hashlib
import unittest

from compare_full_cye1_export_abi import compare, parse_reference
from reconstruct_cye1_export_reference import reconstruct


CONTROL = (
    b"0x00000001 foo vmlinux EXPORT_SYMBOL\n"
    b"0x00000002 bar vmlinux EXPORT_SYMBOL_GPL\n"
    b"0x0000000a module_export some_module EXPORT_SYMBOL\n"
)


def manifest():
    return {
        "reference_symvers_sha256": hashlib.sha256(CONTROL).hexdigest(),
        "research_builtin_export_count": 2,
        "stock_builtin_export_count": 3,
        "unchanged_named_export_crcs": 1,
        "gpl_group_count_stock": 1,
        "normal_group_count_stock": 2,
        "changed_named_export_crcs": [
            {"name": "foo", "research_crc": "0x00000001", "stock_crc": "0x00000003", "group": "normal"},
        ],
        "new_stock_exports": [
            {"name": "baz", "stock_crc": "0x00000004", "group": "normal (inferred and GPL cross-checked)"},
        ],
        "removed_stock_exports": [],
    }


class ReconstructedCye1ExportTests(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest()
        self.reference = reconstruct(self.manifest, CONTROL)
        self.manifest["reconstructed_stock_exports_sha256"] = hashlib.sha256(self.reference).hexdigest()

    def test_reconstruction_excludes_external_module_exports(self):
        symbols = parse_reference(self.reference)
        self.assertEqual(symbols, {"bar": (2, "GPL"), "baz": (4, "normal"), "foo": (3, "normal")})

    def test_complete_reconstructed_reference_match_never_authorizes_flash(self):
        compiled = b"0x00000003 foo vmlinux EXPORT_SYMBOL\n0x00000002 bar vmlinux EXPORT_SYMBOL_GPL\n0x00000004 baz vmlinux EXPORT_SYMBOL\n"
        report = compare(self.manifest, self.reference, compiled)
        self.assertEqual(report["reconstructed_stock_export_parity"], "YES")
        self.assertEqual(report["exact_export_name_crc_class_matches"], 3)
        self.assertEqual(report["complete_oem_module_abi_parity"], "UNVERIFIED")
        self.assertFalse(report["flash_allowed"])

    def test_crc_missing_extra_and_class_drift_are_distinct(self):
        compiled = b"0x00000007 foo vmlinux EXPORT_SYMBOL_GPL\n0x00000002 bar vmlinux EXPORT_SYMBOL_GPL\n0x00000008 extra vmlinux EXPORT_SYMBOL\n"
        report = compare(self.manifest, self.reference, compiled)
        self.assertEqual(report["reconstructed_stock_export_parity"], "NO")
        self.assertEqual(report["exact_export_name_crc_class_matches"], 1)
        self.assertEqual(report["missing_stock_exports"], ["baz"])
        self.assertEqual(report["extra_compiled_exports"], ["extra"])
        self.assertEqual([x["name"] for x in report["crc_mismatches"]], ["foo"])
        self.assertEqual([x["name"] for x in report["class_mismatches"]], ["foo"])

    def test_tampered_reference_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            compare(self.manifest, self.reference.replace(b"00000003", b"00000009"), CONTROL)

    def test_bad_control_hash_and_manifest_delta_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            reconstruct(self.manifest, CONTROL + b"\n")
        self.manifest["changed_named_export_crcs"][0]["research_crc"] = "0x0000ffff"
        with self.assertRaisesRegex(ValueError, "differs from manifest"):
            reconstruct(self.manifest, CONTROL)

    def test_duplicate_reference_rejected(self):
        reference = b"# name\tstock_crc\texport_class\nfoo\t0x00000001\tnormal\nfoo\t0x00000001\tnormal\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_reference(reference)


if __name__ == "__main__":
    unittest.main()
