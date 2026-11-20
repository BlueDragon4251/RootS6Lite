"""Synthetic objdump coverage for the linked manual-hook gate."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from verify_kernelsu_call_edges import audit_disassembly


def instruction(caller, hook, offset="", opcode="94001000 "):
    return [
        f"ffff000000000000 <{caller}>:\n",
        f"ffff000000000008: {opcode}bl ffff000000001000 <{hook}{offset}>\n",
    ]


def samsung_disassembly():
    # Spell this inventory independently from the production expectation so
    # removing a required entry point from either side is caught by tests.
    pairs = [
        ("do_execve", "ksu_handle_execveat"),
        ("do_execveat", "ksu_handle_execveat"),
        ("SyS_execve", "ksu_handle_execveat"),
        ("SyS_execveat", "ksu_handle_execveat"),
        ("compat_SyS_execve", "ksu_handle_execveat"),
        ("compat_SyS_execveat", "ksu_handle_execveat"),
        ("SyS_faccessat", "ksu_handle_faccessat"),
        ("SyS_newfstatat", "ksu_handle_stat"),
        ("SyS_read", "ksu_handle_sys_read"),
        ("SyS_reboot", "ksu_handle_sys_reboot"),
    ]
    return [line for caller, hook in pairs for line in instruction(caller, hook)]


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
            "ffff000000000400 <__arm64_sys_reboot>:\n",
            "ffff000000000408: 94001000 bl ffff000000001400 <ksu_handle_sys_reboot>\n",
        ]
        result = audit_disassembly(data)
        self.assertTrue(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["FLASH_ALLOWED"], "NO")
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_execveat"][0]["caller"], "do_execve")

    def test_rejects_symbol_labels_without_calls(self):
        result = audit_disassembly(["ffff000000001000 <ksu_handle_execveat>:\n"])
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(len(result["MISSING_MANUAL_CALL_EDGES"]), 5)

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

    def test_old_four_handler_audit_is_not_complete(self):
        result = audit_disassembly(samsung_disassembly()[:-2])
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["MISSING_MANUAL_CALL_EDGES"], ["ksu_handle_sys_reboot"])

    def test_reboot_symbol_without_call_does_not_count(self):
        lines = samsung_disassembly()[:-2] + [
            "ffff000000001400 <ksu_handle_sys_reboot>:\n",
            "ffff000000001400: d65f03c0 ret\n",
        ]
        result = audit_disassembly(lines)
        self.assertEqual(result["MISSING_MANUAL_CALL_EDGES"], ["ksu_handle_sys_reboot"])

    def test_unknown_caller_does_not_count(self):
        result = audit_disassembly(instruction("SyS_read", "ksu_handle_sys_read")[1:])
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_read"], [])
        self.assertEqual(result["REJECTED_MANUAL_CALL_EDGES"][0]["reason"], "UNKNOWN_CALLER")

    def test_section_header_resets_caller(self):
        lines = [
            "ffff000000000000 <SyS_read>:\n",
            "Disassembly of section .init.text:\n",
            instruction("SyS_read", "ksu_handle_sys_read")[1],
        ]
        result = audit_disassembly(lines)
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_read"], [])

    def test_nonzero_target_offset_does_not_count_as_entry_call(self):
        result = audit_disassembly(instruction("SyS_read", "ksu_handle_sys_read", "+0x8"))
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_read"], [])
        self.assertEqual(result["REJECTED_MANUAL_CALL_EDGES"][0]["reason"], "NONZERO_TARGET_OFFSET")

    def test_explicit_zero_target_offset_is_entry_call(self):
        result = audit_disassembly(instruction("SyS_read", "ksu_handle_sys_read", "+0x0"))
        self.assertEqual(len(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_read"]), 1)

    def test_strict_samsung_profile_accepts_all_ten_expected_calls(self):
        result = audit_disassembly(samsung_disassembly(), profile="samsung-cye1")
        self.assertTrue(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["CALL_EDGE_PROFILE"], "samsung-cye1")
        self.assertEqual(result["MISSING_MANUAL_CALLERS"], {})
        self.assertEqual(result["UNEXPECTED_MANUAL_CALL_EDGES"], [])
        self.assertEqual(sum(map(len, result["KSU_MANUAL_CALL_EDGES"].values())), 10)
        self.assertEqual(result["CALL_EDGES_PROVE_RUNTIME_CORRECTNESS"], "NO")
        self.assertEqual(result["FLASH_ALLOWED"], "NO")

    def test_strict_samsung_profile_requires_compat_callers(self):
        lines = samsung_disassembly()
        del lines[8:12]
        result = audit_disassembly(lines, profile="samsung-cye1")
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["MISSING_MANUAL_CALL_EDGES"], [])
        self.assertEqual(result["MISSING_MANUAL_CALLERS"]["ksu_handle_execveat"], [
            "compat_SyS_execve", "compat_SyS_execveat",
        ])

    def test_strict_samsung_profile_rejects_hook_in_wrong_syscall(self):
        lines = samsung_disassembly()
        lines[-2] = "ffff000000000000 <SyS_read>:\n"
        result = audit_disassembly(lines, profile="samsung-cye1")
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["MISSING_MANUAL_CALL_EDGES"], ["ksu_handle_sys_reboot"])
        self.assertEqual(result["UNEXPECTED_MANUAL_CALL_EDGES"][0]["reason"], "UNEXPECTED_SAMSUNG_CALLER")

    def test_strict_samsung_profile_rejects_extra_wrong_caller(self):
        lines = samsung_disassembly() + instruction("accidental_helper", "ksu_handle_sys_reboot")
        result = audit_disassembly(lines, profile="samsung-cye1")
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["MISSING_MANUAL_CALL_EDGES"], [])
        self.assertEqual(result["MISSING_MANUAL_CALLERS"], {})
        self.assertEqual(result["UNEXPECTED_MANUAL_CALL_EDGES"][0]["caller"], "accidental_helper")

    def test_tail_branch_is_not_reported_as_bl(self):
        lines = instruction("SyS_reboot", "ksu_handle_sys_reboot")
        lines[1] = lines[1].replace("bl ", "b ")
        result = audit_disassembly(lines)
        self.assertEqual(result["KSU_MANUAL_CALL_EDGES"]["ksu_handle_sys_reboot"], [])

    def test_unknown_profile_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown call-edge profile"):
            audit_disassembly([], profile="misspelled")

    def test_internal_calls_do_not_replace_expected_external_callers(self):
        lines = samsung_disassembly()[:-2] + instruction("kernelsu_init", "ksu_handle_sys_reboot")
        result = audit_disassembly(lines, profile="samsung-cye1")
        self.assertFalse(result["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertEqual(result["MISSING_MANUAL_CALLERS"], {"ksu_handle_sys_reboot": ["SyS_reboot"]})


class CallEdgeCliTests(unittest.TestCase):
    def invoke_fake_objdump(self, lines, exit_code=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            objdump = root / "objdump"
            objdump.write_text(
                "#!" + sys.executable + "\nimport sys\n"
                "sys.stderr.write('x' * 131072)\n"
                "sys.stderr.flush()\n"
                f"sys.stdout.write({''.join(lines)!r})\n"
                f"sys.exit({exit_code})\n"
            )
            objdump.chmod(0o700)
            kernel = root / "vmlinux"
            kernel.write_bytes(b"test input")
            report = root / "report.json"
            script = Path(__file__).with_name("verify_kernelsu_call_edges.py")
            proc = subprocess.run(
                [sys.executable, str(script), "--objdump", str(objdump),
                 "--vmlinux", str(kernel), "--report", str(report),
                 "--profile", "samsung-cye1"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(report.read_text()) if report.exists() else None
            return proc, data

    def test_large_stderr_does_not_deadlock_streaming_disassembly(self):
        proc, report = self.invoke_fake_objdump(samsung_disassembly())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(report["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertIn("ksu_handle_sys_reboot: 1 linked BL call(s)", proc.stdout)

    def test_objdump_error_is_not_a_successful_report(self):
        proc, report = self.invoke_fake_objdump(samsung_disassembly(), exit_code=2)
        self.assertEqual(proc.returncode, 2)
        self.assertIsNone(report)
        self.assertIn("objdump failed (2)", proc.stderr)

    def test_missing_reboot_cli_fails_and_writes_evidence(self):
        proc, report = self.invoke_fake_objdump(samsung_disassembly()[:-2])
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(report["KSU_MANUAL_CALL_EDGES_LINKED"])
        self.assertIn("ksu_handle_sys_reboot", proc.stderr)


if __name__ == "__main__":
    unittest.main()
