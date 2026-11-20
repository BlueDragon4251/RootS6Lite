"""Synthetic tests for the fail-closed CYE1 research export/CRC audit."""

import copy
import hashlib
import unittest

import verify_oem_cye1_abi as verify


class CYE1CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.symvers = (
            "0x00000001\talpha\tvmlinux\tEXPORT_SYMBOL\n"
            "0x00000002\tbeta\tvmlinux\tEXPORT_SYMBOL\n"
            "0x00000003\tgpl_symbol\tvmlinux\tEXPORT_SYMBOL_GPL\n"
            "0x12345678\tmodule_local\tother_module\tEXPORT_SYMBOL\n"
        ).encode()
        self.manifest = {
            "reference_symvers_sha256": hashlib.sha256(self.symvers).hexdigest(),
            "research_builtin_export_count": 3,
            "stock_builtin_export_count": 4,
            "changed_named_export_crcs": [
                {"group": "normal", "name": "alpha", "research_crc": "0x00000001", "stock_crc": "0x11111111"},
            ],
            "new_stock_exports": [
                {"group": "normal", "name": "new_stock_only", "stock_crc": "0x44444444"},
            ],
            "removed_stock_exports": [],
            "unchanged_named_export_crcs": 2,
            "gpl_group_count_stock": 1,
            "normal_group_count_stock": 3,
            "gpl_crc_values_matching_research": 1,
        }

    def test_reports_real_mismatch_without_flash_approval(self):
        report = verify.audit(self.manifest, self.symvers)
        self.assertEqual(report["research_builtin_exports"], 3)
        self.assertEqual(report["shared_export_crc_mismatches"], 1)
        self.assertEqual(report["missing_oem_cye1_exports"], 1)
        self.assertEqual(report["oem_cye1_export_crc_parity"], "NO")
        self.assertIs(report["flash_allowed"], False)

    def test_rejects_different_research_symvers(self):
        with self.assertRaisesRegex(ValueError, "differs from authenticated"):
            verify.audit(self.manifest, self.symvers.replace(b"0x00000001", b"0x00000009"))

    def test_rejects_wrong_research_crc_even_with_updated_hash(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["changed_named_export_crcs"][0]["research_crc"] = "0x00000004"
        with self.assertRaisesRegex(ValueError, "CRC drift"):
            verify.audit(manifest, self.symvers)

    def test_rejects_duplicate_export_names(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["new_stock_exports"].append(manifest["new_stock_exports"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify.audit(manifest, self.symvers)

    def test_rejects_incorrect_stock_count(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["stock_builtin_export_count"] = 5
        with self.assertRaisesRegex(ValueError, "stock export count"):
            verify.audit(manifest, self.symvers)

    def test_rejects_unexpected_oem_only_export_in_research(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["new_stock_exports"][0]["name"] = "beta"
        with self.assertRaisesRegex(ValueError, "already present"):
            verify.audit(manifest, self.symvers)

    def test_rejects_duplicate_vmlinux_symbol(self):
        with self.assertRaisesRegex(ValueError, "duplicate built-in"):
            verify.parse_builtin_symvers(
                "0x00000001\talpha\tvmlinux\tEXPORT_SYMBOL\n"
                "0x00000001\talpha\tvmlinux\tEXPORT_SYMBOL\n"
            )

    def test_rejects_mismatched_gpl_parity(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["gpl_crc_values_matching_research"] = 0
        with self.assertRaisesRegex(ValueError, "GPL CRC parity"):
            verify.audit(manifest, self.symvers)


if __name__ == "__main__":
    unittest.main()
