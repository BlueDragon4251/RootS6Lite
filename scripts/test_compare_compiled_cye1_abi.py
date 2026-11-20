import unittest

from compare_compiled_cye1_abi import compare


class CompareCye1AbiTests(unittest.TestCase):
    def setUp(self):
        self.reference = {
            "stock_builtin_export_count": 2,
            "changed_named_export_crcs": [
                {"name": "foo", "stock_crc": "0x00000001", "group": "normal"},
            ],
            "new_stock_exports": [
                {"name": "bar", "stock_crc": "0x00000002", "group": "GPL"},
            ],
        }

    def test_reference_match_does_not_authorize_flash(self):
        data = b"0x00000001 foo vmlinux EXPORT_SYMBOL\n0x00000002 bar vmlinux EXPORT_SYMBOL_GPL\n"
        result = compare(self.reference, data)
        self.assertEqual(result["listed_reference_parity"], "YES")
        self.assertEqual(result["complete_oem_module_abi_parity"], "UNVERIFIED")
        self.assertFalse(result["flash_allowed"])

    def test_mismatch_missing_and_count_detected(self):
        data = b"0x00000003 foo vmlinux EXPORT_SYMBOL\n"
        result = compare(self.reference, data)
        self.assertEqual(result["reference_export_crcs_mismatching_stock"], 1)
        self.assertEqual(result["missing_exports"], ["bar"])
        self.assertFalse(result["builtin_export_count_matches_stock"])
        self.assertEqual(result["listed_reference_parity"], "NO")

    def test_wrong_class_detected(self):
        data = b"0x00000001 foo vmlinux EXPORT_SYMBOL_GPL\n0x00000002 bar vmlinux EXPORT_SYMBOL_GPL\n"
        result = compare(self.reference, data)
        self.assertEqual(result["reference_export_class_mismatches"], 1)
        self.assertEqual(result["listed_reference_parity"], "NO")

    def test_reject_duplicate_reference(self):
        self.reference["new_stock_exports"].append(self.reference["changed_named_export_crcs"][0])
        with self.assertRaisesRegex(ValueError, "Repeated"):
            compare(self.reference, b"0x00000001 foo vmlinux EXPORT_SYMBOL\n")


if __name__ == "__main__":
    unittest.main()
