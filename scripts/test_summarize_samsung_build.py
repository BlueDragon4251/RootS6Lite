#!/usr/bin/env python3
"""Run with: python3 -m unittest discover -s scripts -p 'test_*.py'."""

import unittest
from summarize_samsung_build import classify, render_markdown, summarize


class BuildDiagnosticsTests(unittest.TestCase):
    def test_first_compiler_error_not_make_cascade(self):
        lines = [
            "drivers/foo.c:10:7: error: invalid operands to binary expression",
            "make[2]: *** [scripts/Makefile.build:282:drivers/foo.o] Error 1",
            "make: *** [Makefile:1072:Image] Error 2",
        ]
        result = summarize(lines, 2)
        self.assertEqual(result["first_reported_error"]["line"], 1)
        self.assertEqual(result["counts"]["make_failure_or_cascade"], 2)
        self.assertIn("NOT FLASHABLE", render_markdown(result, lines))

    def test_warning_is_not_an_error(self):
        result = summarize(["foo.c:4: warning: loose prototype"], 0)
        self.assertIsNone(result["first_reported_error"])
        self.assertEqual(result["counts"]["warning"], 1)

    def test_environment_failure_and_linker(self):
        self.assertEqual(classify("bash: xyz: command not found"), "environment_error")
        self.assertEqual(classify("ld.lld: error: undefined symbol: foo"), "compiler_or_linker_error")

    def test_samsung_wrapper_forbidden_warning(self):
        lines = [
            "diagmem.c:184:11: warning: cast to smaller integer type",
            "error, forbidden warning: diagmem.c:184",
            "make[4]: *** [scripts/Makefile.build:361:diagmem.o] Error 1",
        ]
        result = summarize(lines, 2)
        self.assertEqual(result["first_reported_error"]["kind"], "wrapper_rejected_warning")
        self.assertEqual(result["counts"]["make_failure_or_cascade"], 1)

    def test_empty_log_and_nonzero_exit(self):
        result = summarize([], 137)
        self.assertEqual(result["exit_code"], 137)
        self.assertIsNone(result["first_reported_error"])


if __name__ == "__main__":
    unittest.main()
