"""Synthetic objdump coverage for the linked manual-hook gate."""

import unittest

from verify_kernelsu_call_edges import audit_disassembly


class CallEdgeTests(unittest.TestCase):
    def test_accepts_real_arm64_calls_from_syscall_functions(self):
        data = [
            "ffff000000000000 <do_execve>:\n",
            "ffff000000000008: 94001000 bl ffff000000001000 <ksu_handle_execveat>\n",
            "ffff000000000100 <do_faccessat>:\n",
            "ffff000000000108: 94001000 bl ffff000000001100 <ksu_handle_faccessat>\n",
            "ffff000000000200 <__arm64_sys_newfstatat>:\n",
            "ffff000000000208: 94001000 bl ffff000000001200 <ksu_handle_stat>\n",
            "ffff000000000300 <__arm64_sys_read>:\n",
            "ffff000000000308: 94001000 bl ffff000000001300 <ksu_handle_sys_read>\n",
        ]
        result = audit_disassembly(data)
        self.assertTrue(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["FLASH_ALLOWED"], "NO")
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_execveat"][0]["caller"], "do_execve")

    def test_rejects_symbol_labels_without_calls(self):
        result = audit_disassembly(["ffff000000001000 <ksu_handle_execveat>:\n"])
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(len(result["MISSING_MANUAL_CALL_EDGES"]), 4)

    def test_rejects_internal_kernelsu_calls_as_kernel_hooks(self):
        lines = [
            "ffff000000000000 <ksu_test_helper>:\n",
            "ffff000000000008: 94001000 bl ffff000000001000 <ksu_handle_execveat>\n",
        ]
        result = audit_disassembly(lines)
        self.assertIn("ksu_handle_execveat", result["MISSING_MANUAL_CALL_EDGES"])

    def test_accepts_objdump_without_raw_opcode(self):
        lines = [
            "ffff000000000000 <__arm64_sys_read>:\n",
            "ffff000000000008: bl ffff000000001000 <ksu_handle_sys_read>\n",
        ]
        result = audit_disassembly(lines)
        self.assertEqual(len(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_read"]), 1)


if __name__ == "__main__":
    unittest.main()
