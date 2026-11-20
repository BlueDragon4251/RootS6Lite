"""Small, stock-binary-free tests for the guarded CYE1 boot packager."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from package_cye1_baseline_odintar import (
    aligned, boot_v2_layout, parse_avb_info, replace_kernel_arg,
    stock_metadata, verify_ksu_inputs, verify_ksu_hook_manifest,
    verify_ksu_raw_call_edges, verify_ksu_trace, pinned_tool,
    KNOWN_FAILED_KSU_IMAGE_SHA256S, KSU_UPSTREAM_REVISION,
    NONFLASHABLE_KSU_DIAGNOSTIC_MARKER,
    reject_nonflashable_diagnostic,
)
from instrument_kernelsu_boot_trace import INIT_PATH, RUNTIME_PATH, REQUIRED_CONFIG, marker_counts
from verify_kernelsu_call_edges import SAMSUNG_CYE1_CALLERS


HOOK_MANIFEST = (
    "KPROBES_REMAIN_DISABLED=YES\n"
    "HOOKS=execve,execveat,compat_execve,compat_execveat,faccessat,read,newfstatat,reboot\n"
    "UPSTREAM_REBOOT_HOOK_DETECTOR=UNCHANGED\n"
)


def raw_call_fixture():
    """Ten distinct functions, with backwards BL offsets to five handlers."""
    base = 0xFFFFFF8008080000
    image = bytearray(struct.pack("<I", 0xD503201F) * 256)  # NOPs, 1024-byte text.
    symbols = {"_text": base}
    sites = {}
    for index, hook in enumerate(SAMSUNG_CYE1_CALLERS):
        symbols[hook] = base + 0x80 + index * 0x20
    for index, (hook, caller) in enumerate(
            (hook, caller) for hook, callers in SAMSUNG_CYE1_CALLERS.items() for caller in callers):
        symbols[caller] = base + 0x200 + index * 0x20
        sites[caller] = symbols[caller] + 4 - base
        delta = (symbols[hook] - (base + sites[caller])) // 4
        struct.pack_into("<I", image, sites[caller], 0x94000000 | (delta & 0x03FFFFFF))
    lines = [f"{address:016x} T {name}" for name, address in sorted(symbols.items(), key=lambda item: item[1])]
    lines += [f"{base + len(image):016x} A _etext"]
    return bytes(image), "\n".join(lines) + "\n", sites, symbols


def trace_fixture():
    manifest = {
        "schema_version": 1, "expected_upstream_commit": KSU_UPSTREAM_REVISION,
        "mode": "logging-only", "FLASH_ALLOWED": "NO",
        "POLICY_OR_HOOK_FLOW_CHANGED": False, "CONFIG_KSU_DEBUG_ENABLED_BY_THIS_SCRIPT": False,
        "sources": {path: {"before_sha256": "a" * 64, "after_sha256": "b" * 64}
                    for path in (INIT_PATH, RUNTIME_PATH)},
        "markers": sorted(marker_counts()), "source_marker_counts": marker_counts(),
    }
    image = b"KernelSU\0" + b"".join((marker + "\n\0").encode() for marker in manifest["markers"])
    return manifest, image, "\n".join(REQUIRED_CONFIG) + "\n"


class BootPackageTests(unittest.TestCase):
    def test_alignment(self):
        self.assertEqual(aligned(4097, 4096), 8192)
        self.assertEqual(aligned(8192, 4096), 8192)

    def test_only_header_v2_is_accepted(self):
        data = bytearray(4096 * 4)
        data[:8] = b"ANDROID!"
        struct.pack_into("<II", data, 36, 4096, 1)
        struct.pack_into("<I", data, 1644, 1660)
        with self.assertRaisesRegex(ValueError, "Expected Samsung Android boot v2"):
            boot_v2_layout(bytes(data))
        struct.pack_into("<I", data, 40, 2)
        layout = boot_v2_layout(bytes(data))
        self.assertEqual(layout["payload_end"], 4096)

    def test_samsung_metadata_requires_full_struct(self):
        layout = {"payload_end": 4096}
        data = b"x" * 4096 + b"SEANDROIDENFORCESignerVer02" + b"\0" * 501 + b"x" * 99
        trailer = stock_metadata(data, layout, 4096 + 528)
        self.assertEqual(len(trailer), 528)
        with self.assertRaisesRegex(ValueError, "Unexpected CYE1 Samsung"):
            stock_metadata(b"x" * 5000, layout, 4096 + 528)

    def test_replaces_exactly_one_kernel_argument(self):
        cmd = "--header_version 2 --kernel /tmp/old --ramdisk '/tmp/a b'"
        args = replace_kernel_arg(cmd, Path("new.gz"))
        self.assertEqual(args[args.index("--kernel") + 1], "new.gz")
        self.assertIn("/tmp/a b", args)

    def test_stock_avb_is_a_signed_boot_hash(self):
        desc = """Original image size: 20263440 bytes
Algorithm:                SHA256_RSA4096
      Partition Name:        boot
      Salt:                  618de7695a6e6fef760ab7c35bea5a05d2f943d1de9df0f766fb753ec3226d69
"""
        size, salt = parse_avb_info(desc)
        self.assertEqual(size, 20263440)
        self.assertEqual(len(salt), 64)
        with self.assertRaisesRegex(ValueError, "Unexpected stock AVB"):
            parse_avb_info(desc.replace("SHA256_RSA4096", "NONE"))

    def test_ksu_mode_rejects_missing_provenance_inputs(self):
        args = SimpleNamespace(ksu_config=None, system_map=None, baseline_image=None,
                               ksu_provenance=None, ksu_hooks_manifest=None)
        with self.assertRaisesRegex(ValueError, "KernelSU mode requires"):
            verify_ksu_inputs(args, b"KernelSU")

    def test_rejects_both_device_failed_ksu_images_before_reading_other_inputs(self):
        # Explicit identities stop a future edit from accidentally dropping the
        # first failure while adding another, or using a TAR hash as Image hash.
        failed_images = {
            "b3d551884c1fd95ed5632deac3691bbe343f30a3dfb91833c48c57c12ba418a7",
            "83f2e337b2563b4e0414ec4d59e374f6d345e199b17df43487ebf44cbe986c11",
        }
        self.assertTrue(failed_images.issubset(KNOWN_FAILED_KSU_IMAGE_SHA256S))
        for digest in failed_images:
            with self.subTest(image_sha256=digest):
                with patch("package_cye1_baseline_odintar.sha256", return_value=digest):
                    with self.assertRaisesRegex(ValueError, "Known failed on-device.*" + digest):
                        verify_ksu_inputs(SimpleNamespace(), b"fixture")

    def test_unlisted_image_still_requires_provenance(self):
        with patch("package_cye1_baseline_odintar.sha256", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "KernelSU mode requires"):
                verify_ksu_inputs(SimpleNamespace(), b"fixture")

    def test_no_hide_diagnostic_is_rejected_before_normal_ksu_gates(self):
        # Assert actual sentinel bytes, not just the imported constant, so a
        # drift between the diagnostic generator and packager fails the test.
        self.assertEqual(NONFLASHABLE_KSU_DIAGNOSTIC_MARKER, b"ROOTS6_KSU_NO_SELINUX_HIDE")
        with self.assertRaisesRegex(ValueError, "Nonflashable KernelSU no-SELinux-hide"):
            verify_ksu_inputs(SimpleNamespace(), b"KernelSU\0ROOTS6_KSU_NO_SELINUX_HIDE\0")

    def test_diagnostic_rejection_does_not_depend_on_ksu_mode_or_generic_ksu_string(self):
        with self.assertRaisesRegex(ValueError, "Nonflashable KernelSU no-SELinux-hide"):
            reject_nonflashable_diagnostic(b"ROOTS6_KSU_NO_SELINUX_HIDE\0")
        reject_nonflashable_diagnostic(b"ordinary baseline fixture")

    def test_five_hook_manifest_requires_reboot_and_unmodified_detector(self):
        manifest = HOOK_MANIFEST
        verify_ksu_hook_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "provenance missing"):
            verify_ksu_hook_manifest(manifest.replace(",reboot", ""))
        with self.assertRaisesRegex(ValueError, "provenance missing"):
            verify_ksu_hook_manifest(manifest.replace("=UNCHANGED", "=REPLACED"))
        with self.assertRaisesRegex(ValueError, "incorrectly claims reboot"):
            verify_ksu_hook_manifest(manifest + "NO_OBSOLETE_REBOOT_HOOK=upstream_missing\n")


class RawCallGateTests(unittest.TestCase):
    def setUp(self):
        self.image, self.system_map, self.sites, self.symbols = raw_call_fixture()

    def test_ten_real_backward_bl_calls_pass_and_bind_both_input_hashes(self):
        result = verify_ksu_raw_call_edges(self.image, self.system_map)
        self.assertEqual(result["call_count"], 10)
        self.assertEqual(len({call["caller"] for call in result["calls"]}), 10)
        self.assertEqual(sum(call["hook"] == "ksu_handle_execveat" for call in result["calls"]), 6)
        self.assertEqual(result["image_sha256"], hashlib.sha256(self.image).hexdigest())
        self.assertEqual(result["system_map_sha256"], hashlib.sha256(self.system_map.encode()).hexdigest())
        self.assertFalse(result["runtime_correctness_proven"])

    def test_missing_reboot_call_fails_despite_all_symbols_present(self):
        image = bytearray(self.image)
        struct.pack_into("<I", image, self.sites["SyS_reboot"], 0xD503201F)
        with self.assertRaisesRegex(ValueError, "SyS_reboot.*ksu_handle_sys_reboot.*found 0"):
            verify_ksu_raw_call_edges(bytes(image), self.system_map)

    def test_wrong_and_offset_handler_targets_fail(self):
        for target in (self.symbols["ksu_handle_sys_reboot"] + 4, self.symbols["ksu_handle_execveat"]):
            with self.subTest(target=target):
                image = bytearray(self.image)
                offset = self.sites["SyS_reboot"]
                immediate = (target - self.symbols["_text"] - offset) // 4
                struct.pack_into("<I", image, offset, 0x94000000 | (immediate & 0x03FFFFFF))
                with self.assertRaisesRegex(ValueError, "SyS_reboot.*found 0"):
                    verify_ksu_raw_call_edges(bytes(image), self.system_map)

    def test_plain_branch_is_not_a_bl_call(self):
        image = bytearray(self.image)
        offset = self.sites["SyS_reboot"]
        word = struct.unpack_from("<I", image, offset)[0]
        struct.pack_into("<I", image, offset, word & ~0x80000000)
        with self.assertRaisesRegex(ValueError, "SyS_reboot.*found 0"):
            verify_ksu_raw_call_edges(bytes(image), self.system_map)

    def test_alias_cannot_replace_a_distinct_exec_caller(self):
        system_map = self.system_map.replace(
            f'{self.symbols["do_execveat"]:016x} T do_execveat',
            f'{self.symbols["do_execve"]:016x} T do_execveat')
        with self.assertRaisesRegex(ValueError, "distinct addresses"):
            verify_ksu_raw_call_edges(self.image, system_map)

    def test_duplicate_required_symbol_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate required System.map symbol"):
            verify_ksu_raw_call_edges(self.image, self.system_map + f'{self.symbols["do_execve"]:016x} T do_execve\n')

    def test_map_range_outside_image_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "text range is outside"):
            verify_ksu_raw_call_edges(self.image[:-4], self.system_map)

    def test_extra_reboot_call_is_rejected(self):
        image = bytearray(self.image)
        offset = self.sites["SyS_reboot"] + 4
        immediate = (self.symbols["ksu_handle_sys_reboot"] - self.symbols["_text"] - offset) // 4
        struct.pack_into("<I", image, offset, 0x94000000 | (immediate & 0x03FFFFFF))
        with self.assertRaisesRegex(ValueError, "SyS_reboot.*found 2"):
            verify_ksu_raw_call_edges(bytes(image), self.system_map)


class TracePackageGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.image, self.config = trace_fixture()

    def test_valid_full_trace_and_stock_security_config_pass(self):
        result = verify_ksu_trace(self.manifest, self.image, self.config)
        self.assertEqual(result["REQUIRED_TRACE_MARKERS"], 42)
        self.assertTrue(result["TRACE_CONFIG_GATES_VALID"])
        self.assertFalse(result["MARKER_STRINGS_PROVE_RUNTIME_EXECUTION"])

    def test_missing_linked_trace_marker_fails(self):
        image = self.image.replace((self.manifest["markers"][0] + "\n\0").encode(), b"")
        with self.assertRaisesRegex(ValueError, "diagnostic trace markers"):
            verify_ksu_trace(self.manifest, image, self.config)

    def test_tampered_reduced_manifest_fails(self):
        self.manifest["markers"].pop()
        with self.assertRaisesRegex(ValueError, "refusing a reduced marker set"):
            verify_ksu_trace(self.manifest, self.image, self.config)

    def test_weakened_or_conflicting_config_fails(self):
        for config in (
            self.config.replace("CONFIG_MODULE_SIG_FORCE=y", "# CONFIG_MODULE_SIG_FORCE is not set"),
            self.config.replace("# CONFIG_KSU_DEBUG is not set", "CONFIG_KSU_DEBUG=y"),
            self.config + "CONFIG_KPROBES=y\n",
        ):
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, "stock-security config gates"):
                    verify_ksu_trace(self.manifest, self.image, config)

    def test_ksu_input_gate_checks_raw_edges_and_trace_before_acceptance(self):
        raw_image, system_map, sites, _ = raw_call_fixture()
        image = raw_image + self.image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contents = {"ksu_config": self.config, "system_map": system_map,
                        "baseline_image": "baseline fixture", "ksu_hooks_manifest": HOOK_MANIFEST,
                        "ksu_provenance": f"KSU_UPSTREAM_LEGACY_COMMIT={KSU_UPSTREAM_REVISION}\n",
                        "ksu_trace_manifest": json.dumps(self.manifest)}
            args = SimpleNamespace()
            for name, content in contents.items():
                path = root / name
                path.write_text(content)
                setattr(args, name, path)
            symbols = {"KSU_CONFIG_VALID": True, "KSU_MANUAL_HOOKS_LINKED": True,
                       "KSU_PREINIT_EMBEDDED": True, "KSU_PREINIT_BLOB_BYTES": 17280}
            elf = {"KSU_PREINIT_ELF_LAYOUT_VALID": True, "KSU_PREINIT_ELF_STATIC": True,
                   "KSU_PREINIT_RUNNER_BYTES": 17280, "KSU_PREINIT_RUNNER_SHA256": "a" * 64,
                   "PAGE_CONGRUENCE_VERIFIED": [4096, 65536]}
            with patch("package_cye1_baseline_odintar.KSU_CONFIG_SHA256", hashlib.sha256(args.ksu_config.read_bytes()).hexdigest()), \
                 patch("package_cye1_baseline_odintar.BOOTED_BASELINE_IMAGE_SHA256", hashlib.sha256(args.baseline_image.read_bytes()).hexdigest()), \
                 patch("package_cye1_baseline_odintar.audit_ksu_symbols", return_value=symbols), \
                 patch("package_cye1_baseline_odintar.inspect_ksu_elf", return_value=elf):
                self.assertEqual(verify_ksu_inputs(args, image)["kernelsu_raw_call_edges"]["call_count"], 10)
                no_reboot = bytearray(image)
                struct.pack_into("<I", no_reboot, sites["SyS_reboot"], 0xD503201F)
                with self.assertRaisesRegex(ValueError, "SyS_reboot.*found 0"):
                    verify_ksu_inputs(args, bytes(no_reboot))
                no_marker = image.replace((self.manifest["markers"][0] + "\n\0").encode(), b"")
                with self.assertRaisesRegex(ValueError, "diagnostic trace markers"):
                    verify_ksu_inputs(args, no_marker)


class PinnedToolGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tool = Path(self.tmp.name) / "tool.py"
        self.tool.write_text("# fixture\n")

    def test_exact_commit_and_clean_worktree_pass(self):
        with patch("package_cye1_baseline_odintar.run", side_effect=["pinned\n", ""]) as command:
            pinned_tool(self.tool, "pinned")
        self.assertEqual(command.call_args_list[-1].args[-3:], ("status", "--porcelain=v1", "--untracked-files=all"))

    def test_modified_staged_deleted_or_untracked_tool_sources_fail(self):
        for status in (" M tool.py\n", "M  tool.py\n", " D helper.py\n", "?? helper.py\n"):
            with self.subTest(status=status):
                with patch("package_cye1_baseline_odintar.run", side_effect=["pinned\n", status]):
                    with self.assertRaisesRegex(ValueError, "modified or untracked sources"):
                        pinned_tool(self.tool, "pinned")

    def test_wrong_commit_is_rejected(self):
        with patch("package_cye1_baseline_odintar.run", return_value="other\n"):
            with self.assertRaisesRegex(ValueError, "expected pinned"):
                pinned_tool(self.tool, "pinned")


if __name__ == "__main__":
    unittest.main()
