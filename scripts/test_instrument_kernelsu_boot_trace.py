"""Logging-only source and linked marker gates; no device boot claims."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from instrument_kernelsu_boot_trace import (
    INIT_PATH,
    RUNTIME_PATH,
    instrument_sources,
    instrument_tree,
    marker_counts,
    verify_linked_trace,
)


# Independent, reduced fixtures keep the pinned call order/indentation and
# both init branches, including statements that must never be removed.
INIT_SOURCE = """bool allow_shell = false;
int __init kernelsu_init(void)
{
	ksu_late_loaded = false;
    ksu_cred = prepare_creds();
    if (!ksu_cred) {
        return -ENOSYS;
    }
	ksu_feature_init();
	ksu_sulog_init();
	ksu_adb_root_init();
	ksu_shell_su_adb_only_init();
	ksu_feature_apply_forced();
	ksu_lsm_hook_init();
	ksu_selinux_hide_init();
	ksu_supercalls_init();
	ksu_app_profile_init();
	if (ksu_late_loaded) {
		apply_kernelsu_rules();
		cache_sid();
		setup_ksu_cred();
		escape_to_root_for_init();
		ksu_allowlist_init();
		ksu_load_allow_list();
		ksu_syscall_hook_manager_init();
		ksu_throne_tracker_init();
		ksu_observer_init();
		ksu_file_wrapper_init();
		if (!getenforce()) {
			setenforce(true);
		}
	} else {
		ksu_syscall_hook_manager_init();
		ksu_allowlist_init();
		ksu_throne_tracker_init();
		ksu_ksud_init();
		ksu_preinit_init();
		ksu_file_wrapper_init();
	}
	return 0;
}

void __exit kernelsu_exit(void)
{
	ksu_syscall_hook_manager_exit();
}
"""
RUNTIME_SOURCE = """/* Calls outside the selected callback must not be instrumented. */
static void unrelated(void) { apply_kernelsu_rules(); }
static void ksu_initialize_selinux_tw_func(struct callback_head *cb)
{
	ksu_selinux_hide_handle_second_stage();
	apply_kernelsu_rules();
	ksu_feature_apply_forced();
	cache_sid();
	setup_ksu_cred();
	kfree(cb);
}
static void another(void) { setup_ksu_cred(); }
"""
CONFIG_SOURCE = """CONFIG_KSU=y
CONFIG_KSU_MANUAL_HOOK=y
# CONFIG_KSU_DEBUG is not set
# CONFIG_KPROBES is not set
CONFIG_MODVERSIONS=y
CONFIG_MODULE_SIG=y
CONFIG_MODULE_SIG_FORCE=y
CONFIG_MODULE_SIG_SHA512=y
CONFIG_SECURITY_SELINUX=y
CONFIG_UH_RKP=y
CONFIG_RKP_KDP=y
CONFIG_RKP_NS_PROT=y
CONFIG_FIVE=y
CONFIG_PROCA=y
CONFIG_PROCA_S_OS=y
"""


def original_sources():
    return {INIT_PATH: INIT_SOURCE, RUNTIME_PATH: RUNTIME_SOURCE}


class TraceSourceTests(unittest.TestCase):
    def test_only_literal_logging_lines_are_added(self):
        sources = original_sources()
        edited = instrument_sources(sources)
        for path, body in edited.items():
            stripped = "".join(line for line in body.splitlines(keepends=True)
                               if not line.lstrip().startswith('pr_info("ROOTS6_KSU_TRACE: '))
            self.assertEqual(stripped, sources[path])
        self.assertEqual(len(marker_counts()), 42)
        self.assertNotIn("%", "\n".join(marker_counts()))

    def test_entry_completion_and_call_order_are_preserved(self):
        edited = instrument_sources(original_sources())
        init = edited[INIT_PATH]
        self.assertLess(init.index("init.entry"), init.index("ksu_cred = prepare_creds();"))
        self.assertLess(init.index("init.after.prepare_creds"), init.index("if (!ksu_cred)"))
        self.assertLess(init.index("init.after.ksu_preinit_init"), init.index("init.complete"))
        self.assertLess(init.index("init.complete"), init.index("\treturn 0;"))
        self.assertEqual(init.count("ROOTS6_KSU_TRACE: init.before.ksu_allowlist_init"), 2)
        self.assertEqual(init.count("ROOTS6_KSU_TRACE: init.after.ksu_file_wrapper_init"), 2)
        runtime = edited[RUNTIME_PATH]
        self.assertLess(runtime.index("second_stage.before.apply_kernelsu_rules"), runtime.index("\tapply_kernelsu_rules();"))
        self.assertLess(runtime.index("\tsetup_ksu_cred();"), runtime.index("second_stage.after.setup_ksu_cred"))
        self.assertIn("static void unrelated(void) { apply_kernelsu_rules(); }", runtime)

    def test_missing_init_call_is_rejected(self):
        sources = original_sources()
        sources[INIT_PATH] = INIT_SOURCE.replace("\tksu_lsm_hook_init();\n", "")
        with self.assertRaisesRegex(ValueError, "ksu_lsm_hook_init: expected 1 anchors, got 0"):
            instrument_sources(sources)

    def test_duplicate_init_call_is_rejected(self):
        sources = original_sources()
        sources[INIT_PATH] += "\n\tksu_lsm_hook_init();\n"
        with self.assertRaisesRegex(ValueError, "ksu_lsm_hook_init: expected 1 anchors, got 2"):
            instrument_sources(sources)

    def test_changed_second_stage_call_order_is_rejected(self):
        sources = original_sources()
        sources[RUNTIME_PATH] = RUNTIME_SOURCE.replace(
            "\tksu_feature_apply_forced();\n\tcache_sid();", "\tcache_sid();\n\tksu_feature_apply_forced();")
        with self.assertRaisesRegex(ValueError, "ksu_initialize_selinux_tw_func: expected 1 anchors, got 0"):
            instrument_sources(sources)

    def test_second_instrumentation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Boot trace already present"):
            instrument_sources(instrument_sources(original_sources()))


class TraceTreeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.upstream = self.root / "upstream"
        self.manifest = self.root / "trace.json"
        for path, body in original_sources().items():
            target = self.upstream / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)

    def instrument(self):
        return instrument_tree(self.upstream, self.manifest)

    def test_manifest_records_source_hashes_and_all_markers(self):
        report = self.instrument()
        self.assertEqual(report, json.loads(self.manifest.read_text()))
        self.assertEqual(report["FLASH_ALLOWED"], "NO")
        self.assertFalse(report["POLICY_OR_HOOK_FLOW_CHANGED"])
        for path, original in original_sources().items():
            self.assertEqual(report["sources"][path]["before_sha256"], hashlib.sha256(original.encode()).hexdigest())
            self.assertEqual(report["sources"][path]["after_sha256"], hashlib.sha256((self.upstream / path).read_bytes()).hexdigest())
        self.assertEqual(len(report["markers"]), 42)

    def test_later_file_error_leaves_both_source_files_unchanged(self):
        path = self.upstream / RUNTIME_PATH
        path.write_text(path.read_text().replace("\tkfree(cb);", "\tkfree(other);"))
        before = {p: (self.upstream / p).read_bytes() for p in original_sources()}
        with self.assertRaisesRegex(ValueError, "ksu_initialize_selinux_tw_func"):
            self.instrument()
        self.assertEqual(before, {p: (self.upstream / p).read_bytes() for p in original_sources()})
        self.assertFalse(self.manifest.exists())

    def test_refuses_to_overwrite_an_existing_manifest(self):
        self.manifest.write_text("existing")
        with self.assertRaisesRegex(ValueError, "Manifest must be a new file"):
            self.instrument()
        self.assertEqual(self.manifest.read_text(), "existing")
        self.assertEqual((self.upstream / INIT_PATH).read_text(), INIT_SOURCE)

    def test_linked_marker_and_config_verification_passes(self):
        manifest = self.instrument()
        image = b"header" + b"".join((marker + "\n\0").encode() for marker in manifest["markers"])
        result = verify_linked_trace(manifest, image, CONFIG_SOURCE)
        self.assertTrue(result["LINKED_TRACE_MARKERS_VALID"])
        self.assertTrue(result["TRACE_CONFIG_GATES_VALID"])
        self.assertFalse(result["MARKER_STRINGS_PROVE_RUNTIME_EXECUTION"])
        self.assertEqual(result["FLASH_ALLOWED"], "NO")

    def test_one_missing_linked_marker_fails(self):
        manifest = self.instrument()
        image = b"".join((marker + "\n\0").encode() for marker in manifest["markers"][1:])
        result = verify_linked_trace(manifest, image, CONFIG_SOURCE)
        self.assertFalse(result["LINKED_TRACE_MARKERS_VALID"])
        self.assertEqual(result["MISSING_TRACE_MARKERS"], manifest["markers"][:1])

    def test_debug_enable_or_stock_security_disable_fails(self):
        manifest = self.instrument()
        for bad_config in (
            CONFIG_SOURCE.replace("# CONFIG_KSU_DEBUG is not set", "CONFIG_KSU_DEBUG=y"),
            CONFIG_SOURCE.replace("CONFIG_MODULE_SIG_FORCE=y", "# CONFIG_MODULE_SIG_FORCE is not set"),
            CONFIG_SOURCE.replace("CONFIG_RKP_KDP=y", "# CONFIG_RKP_KDP is not set"),
        ):
            with self.subTest(config=bad_config):
                result = verify_linked_trace(manifest, b"", bad_config)
                self.assertFalse(result["TRACE_CONFIG_GATES_VALID"])

    def test_conflicting_or_duplicate_config_values_fail(self):
        manifest = self.instrument()
        for extra in ("CONFIG_KSU_DEBUG=y\n", "CONFIG_KSU=y\n"):
            with self.subTest(extra=extra):
                self.assertFalse(verify_linked_trace(manifest, b"", CONFIG_SOURCE + extra)["TRACE_CONFIG_GATES_VALID"])

    def test_reduced_manifest_marker_set_is_rejected(self):
        manifest = self.instrument()
        manifest["markers"].pop()
        with self.assertRaisesRegex(ValueError, "refusing a reduced marker set"):
            verify_linked_trace(manifest, b"", CONFIG_SOURCE)

    def test_source_hashes_are_required_and_well_formed(self):
        manifest = self.instrument()
        for bad in ("", "1" * 63, "g" * 64, None):
            with self.subTest(hash=bad):
                modified = json.loads(json.dumps(manifest))
                modified["sources"][INIT_PATH]["before_sha256"] = bad
                with self.assertRaisesRegex(ValueError, "Invalid trace source hashes"):
                    verify_linked_trace(modified, b"", CONFIG_SOURCE)

    def test_unexpected_source_inventory_is_rejected(self):
        manifest = self.instrument()
        manifest["sources"].pop(RUNTIME_PATH)
        with self.assertRaisesRegex(ValueError, "Unexpected trace manifest source inventory"):
            verify_linked_trace(manifest, b"", CONFIG_SOURCE)


if __name__ == "__main__":
    unittest.main()
