"""Small offline tests for the post-link KernelSU research symbol gate."""

import tempfile
import unittest
from pathlib import Path

from verify_kernelsu_research_symbols import REQUIRED_CONFIG, REQUIRED_HOOK_SYMBOLS, audit


class KernelSUResearchSymbolAuditTests(unittest.TestCase):
    def check(self, config_lines, symbol_lines):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".config"
            symbols = Path(directory) / "System.map"
            config.write_text("\n".join(config_lines) + "\n")
            symbols.write_text("\n".join(symbol_lines) + "\n")
            return audit(config, symbols)

    def test_valid_nonflashable_linked_hooks(self):
        result = self.check(REQUIRED_CONFIG, [
            f"ffff000000001000 T {name}" for name in REQUIRED_HOOK_SYMBOLS
        ])
        self.assertTrue(result["KSU_CONFIG_VALID"])
        self.assertTrue(result["KSU_MANUAL_HOOKS_LINKED"])
        self.assertEqual(result["FLASH_ALLOWED"], "NO")

    def test_reject_missing_hook(self):
        result = self.check(REQUIRED_CONFIG, [
            f"ffff000000001000 T {name}" for name in REQUIRED_HOOK_SYMBOLS[:-1]
        ])
        self.assertFalse(result["KSU_MANUAL_HOOKS_LINKED"])
        self.assertIn("ksu_handle_sys_read", result["MISSING_OR_NON_TEXT_HOOK_SYMBOLS"])

    def test_reject_nontext_symbol(self):
        result = self.check(REQUIRED_CONFIG, [
            f"ffff000000001000 D {name}" for name in REQUIRED_HOOK_SYMBOLS
        ])
        self.assertFalse(result["KSU_MANUAL_HOOKS_LINKED"])

    def test_reject_unconfigured(self):
        result = self.check(REQUIRED_CONFIG[:-1], [
            f"ffff000000001000 T {name}" for name in REQUIRED_HOOK_SYMBOLS
        ])
        self.assertFalse(result["KSU_CONFIG_VALID"])
        self.assertIn("CONFIG_PROCA_S_OS=y", result["MISSING_CONFIG"])


if __name__ == "__main__":
    unittest.main()
