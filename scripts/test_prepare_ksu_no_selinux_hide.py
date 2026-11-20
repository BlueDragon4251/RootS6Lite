"""Pinned, non-flashable diagnostic gates without Samsung binaries or a build."""

import json
import gzip
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import prepare_ksu_no_selinux_hide as diagnostic


ORIGINAL = b"pinned upstream fixture\n"
CONFIG = ("\n".join(diagnostic.REQUIRED_CONFIG) +
          "\nCONFIG_KALLSYMS=y\nCONFIG_KALLSYMS_ALL=y\n").encode()


def image_fixture(framed=False):
    base = 0xFFFFFF8008080000
    image = bytearray(struct.pack("<I", diagnostic.NOP) * 256)
    image[56:60] = b"ARMd"
    literal = b"\x014" + diagnostic.WARNING.encode() + b"\n\0"
    image[0x300:0x300 + len(literal)] = literal
    prefix = [0xA9BF7BFD, 0x910003FD] if framed else []
    words = prefix + [0x90000000, 0x91000000 | (0x300 << 10)]  # adrp/add x0.
    branch_pc = base + 0x100 + len(words) * 4
    words.append((0x94000000 if framed else 0x14000000) | (((base + 0x80 - branch_pc) // 4) & 0x03FFFFFF))
    if framed:
        words += [0xA8C17BFD, diagnostic.RET]
    for index, word in enumerate(words):
        struct.pack_into("<I", image, 0x100 + index * 4, word)
    for offset in (0x140, 0x180):
        struct.pack_into("<I", image, offset, diagnostic.RET)
    symbols = [(0, "_text"), (0x80, "printk"), (0x100, diagnostic.INIT_API),
               (0x140, "ksu_selinux_hide_handle_second_stage"),
               (0x180, "ksu_selinux_hide_handle_post_fs_data"), (0x1C0, "following_function")]
    system_map = "".join(f"{base + offset:016x} T {name}\n" for offset, name in symbols)
    frozen = bytes(image)
    def disassemble(start, end):
        return "\n".join(f"{address:016x}: {struct.unpack_from('<I', frozen, address - base)[0]:08x} fixture"
                         for address in range(start, end, 4))
    return frozen, system_map, disassemble


class SourceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "upstream"
        self.source = self.root / diagnostic.SOURCE_PATH
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(ORIGINAL)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.head = diagnostic.UPSTREAM_PIN
        self.status = ""
        self.changed = diagnostic.SOURCE_PATH + "\n"
        def git(_root, *args):
            return {"rev-parse": self.head, "status": self.status, "diff": self.changed}[args[0]]
        self.addCleanup(patch.stopall)
        patch("prepare_ksu_no_selinux_hide.git", side_effect=git).start()
        patch("prepare_ksu_no_selinux_hide.SOURCE_SHA256", diagnostic.digest(ORIGINAL)).start()

    def test_exact_one_file_replacement_and_manifest(self):
        guard = self.root / "untouched-policy.c"
        guard.write_bytes(b"unchanged policy fixture")
        result = diagnostic.apply_to_tree(self.root, self.manifest)
        self.assertEqual(self.source.read_bytes(), diagnostic.STUB_SOURCE)
        self.assertEqual(guard.read_bytes(), b"unchanged policy fixture")
        self.assertEqual(result, json.loads(self.manifest.read_bytes()))
        self.assertEqual(result["FLASH_ALLOWED"], "NO")
        self.assertEqual(result["RESEARCH_ONLY"], "YES")
        self.assertTrue(result["CONFIG_UNCHANGED"])
        self.assertTrue(result["OPTIONAL_HIDE_BEHAVIOR_CHANGED"])
        self.assertEqual(result["ROOT_FUNCTIONALITY"], "UNVERIFIED")
        self.assertEqual(len(result["api_entry_points"]), 4)
        self.assertEqual(diagnostic.verify_source(self.root, self.manifest), [])

    def test_wrong_revision_is_rejected_before_writes(self):
        self.head = "0" * 40
        with self.assertRaisesRegex(ValueError, "upstream revision"):
            diagnostic.apply_to_tree(self.root, self.manifest)
        self.assertEqual(self.source.read_bytes(), ORIGINAL)
        self.assertFalse(self.manifest.exists())

    def test_wrong_source_hash_is_rejected_before_writes(self):
        self.source.write_bytes(ORIGINAL + b"drift")
        with self.assertRaisesRegex(ValueError, "source hash/path"):
            diagnostic.apply_to_tree(self.root, self.manifest)
        self.assertFalse(self.manifest.exists())

    def test_dirty_checkout_is_rejected_before_writes(self):
        for status in (" M kernel/Kconfig\n", "?? injected.c\n"):
            with self.subTest(status=status):
                self.status = status
                with self.assertRaisesRegex(ValueError, "clean upstream checkout"):
                    diagnostic.apply_to_tree(self.root, self.manifest)
                self.assertEqual(self.source.read_bytes(), ORIGINAL)
                self.assertFalse(self.manifest.exists())

    def test_existing_or_in_checkout_manifest_is_rejected(self):
        self.manifest.write_text("keep")
        for manifest in (self.manifest, self.root / "new.json"):
            with self.subTest(manifest=manifest):
                with self.assertRaisesRegex(ValueError, "Manifest must be new"):
                    diagnostic.apply_to_tree(self.root, manifest)
        self.assertEqual(self.source.read_bytes(), ORIGINAL)
        self.assertEqual(self.manifest.read_text(), "keep")

    def test_patched_twice_is_rejected(self):
        diagnostic.apply_to_tree(self.root, self.manifest)
        with self.assertRaisesRegex(ValueError, "already applied"):
            diagnostic.apply_to_tree(self.root, self.manifest.with_name("second.json"))
        self.assertFalse(self.manifest.with_name("second.json").exists())

    def test_later_expected_integration_edits_are_recorded(self):
        diagnostic.apply_to_tree(self.root, self.manifest)
        self.changed += "\n".join(sorted(diagnostic.EXTERNAL_BUILD_EDITS))
        self.assertEqual(diagnostic.verify_source(self.root, self.manifest), sorted(diagnostic.EXTERNAL_BUILD_EDITS))

    def test_unexpected_policy_or_config_edit_is_rejected(self):
        diagnostic.apply_to_tree(self.root, self.manifest)
        self.changed += "kernel/selinux/selinux.c\n"
        with self.assertRaisesRegex(ValueError, "outside diagnostic"):
            diagnostic.verify_source(self.root, self.manifest)

    def test_tampered_stub_source_is_rejected(self):
        diagnostic.apply_to_tree(self.root, self.manifest)
        self.source.write_bytes(diagnostic.STUB_SOURCE + b"/* drift */\n")
        with self.assertRaisesRegex(ValueError, "exact one-file replacement"):
            diagnostic.verify_source(self.root, self.manifest)

    def test_incomplete_manifest_cannot_assert_success(self):
        diagnostic.apply_to_tree(self.root, self.manifest)
        self.manifest.write_text(json.dumps(diagnostic.expected_manifest(False)))
        with self.assertRaisesRegex(ValueError, "incomplete no-hide manifest"):
            diagnostic.verify_source(self.root, self.manifest)


class ConfigIsolationTests(unittest.TestCase):
    def test_exact_hash_and_security_gates_pass(self):
        with patch("prepare_ksu_no_selinux_hide.CONFIG_SHA256", diagnostic.digest(CONFIG)):
            diagnostic.verify_config(CONFIG)

    def test_any_config_hash_drift_fails(self):
        with patch("prepare_ksu_no_selinux_hide.CONFIG_SHA256", diagnostic.digest(CONFIG)):
            with self.assertRaisesRegex(ValueError, "Final config hash differs"):
                diagnostic.verify_config(CONFIG + b"# drift\n")

    def test_security_conflict_or_missing_kallsyms_all_fails(self):
        for config in (CONFIG + b"CONFIG_KPROBES=y\n", CONFIG.replace(b"CONFIG_KALLSYMS_ALL=y\n", b""),
                       CONFIG.replace(b"CONFIG_MODULE_SIG_FORCE=y", b"# CONFIG_MODULE_SIG_FORCE is not set")):
            with self.subTest(config=config):
                with patch("prepare_ksu_no_selinux_hide.CONFIG_SHA256", diagnostic.digest(config)):
                    with self.assertRaisesRegex(ValueError, "security or symbol config gate"):
                        diagnostic.verify_config(config)

    def test_embedded_gzip_config_must_match_actual_final_hash(self):
        image = b"Image" + b"IKCFG_ST" + gzip.compress(CONFIG, mtime=0) + b"IKCFG_ED"
        with patch("prepare_ksu_no_selinux_hide.CONFIG_SHA256", diagnostic.digest(CONFIG)):
            self.assertEqual(diagnostic.verify_embedded_config(image)["sha256"], diagnostic.digest(CONFIG))
            changed = b"IKCFG_ST" + gzip.compress(CONFIG + b"# drift\n", mtime=0) + b"IKCFG_ED"
            with self.assertRaisesRegex(ValueError, "Embedded Image config does not match"):
                diagnostic.verify_embedded_config(changed)

    def test_absent_duplicate_or_corrupt_embedded_config_fails(self):
        for image in (b"Image", b"IKCFG_STIKCFG_STIKCFG_ED", b"IKCFG_STnot-gzipIKCFG_ED"):
            with self.subTest(image=image):
                with self.assertRaisesRegex(ValueError, "IKCONFIG marker pair|Embedded Image config"):
                    diagnostic.verify_embedded_config(image)


class LinkedIsolationTests(unittest.TestCase):
    def test_exact_logging_tail_call_and_noop_bodies_pass(self):
        result = diagnostic.verify_linked(*image_fixture())
        self.assertEqual(result[diagnostic.INIT_API]["state"], "VERIFIED")
        self.assertEqual(result[diagnostic.EXIT_API]["state"], "ABSENT_BUILTIN_EXIT_SECTION")

    def test_exact_framed_bl_and_return_pass(self):
        result = diagnostic.verify_linked(*image_fixture(framed=True))
        self.assertEqual(result[diagnostic.INIT_API]["state"], "VERIFIED")

    def test_missing_marker_fails(self):
        image, system_map, disassemble = image_fixture()
        image = image.replace(diagnostic.SENTINEL.encode(), b"X" * len(diagnostic.SENTINEL))
        with self.assertRaisesRegex(ValueError, "diagnostic marker"):
            diagnostic.verify_linked(image, system_map, disassemble)

    def test_removed_implementation_symbol_or_old_logs_fail(self):
        image, system_map, disassemble = image_fixture()
        with self.assertRaisesRegex(ValueError, "implementation symbol remains"):
            diagnostic.verify_linked(image, system_map + "ffffff8008080020 t ksu_patch_fops_slot.isra.0\n", disassemble)
        with self.assertRaisesRegex(ValueError, "retained optional-hide log strings"):
            diagnostic.verify_linked(image + b"selinux_hide: enabled=1\0", system_map, disassemble)

    def test_image_and_vmlinux_instruction_mismatch_fails(self):
        image, system_map, disassemble = image_fixture()
        changed = bytearray(image)
        struct.pack_into("<I", changed, 0x140, diagnostic.NOP)
        with self.assertRaisesRegex(ValueError, "does not exactly match raw Image"):
            diagnostic.verify_linked(bytes(changed), system_map, disassemble)

    def test_non_logging_init_call_or_handler_offset_fails(self):
        image, system_map, _ = image_fixture()
        base, start = 0xFFFFFF8008080000, 0xFFFFFF8008080100
        for target in (base + 0x140, base + 0x84):
            words = [0x90000000, 0x91000000 | (0x300 << 10),
                     0x14000000 | (((target - (start + 8)) // 4) & 0x03FFFFFF)]
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "exact printk"):
                    diagnostic.verify_warn_words(words, start, base + 0x80, image, base)

    def test_wrong_warning_pointer_and_unknown_instrumentation_fail(self):
        image, _, _ = image_fixture()
        base, start = 0xFFFFFF8008080000, 0xFFFFFF8008080100
        branch = 0x14000000 | (((base + 0x80 - start - 8) // 4) & 0x03FFFFFF)
        with self.assertRaisesRegex(ValueError, "exact warning literal"):
            diagnostic.verify_warn_words([0x90000000, 0x91000000, branch], start, base + 0x80, image, base)
        with self.assertRaisesRegex(ValueError, "Unexpected diagnostic init instruction"):
            diagnostic.verify_warn_words([0xD63F0000], start, base + 0x80, image, base)  # BLR x0.

    def test_main_source_does_not_alter_policy_or_retain_internal_helpers(self):
        text = diagnostic.STUB_SOURCE.decode()
        self.assertEqual(text.count("pr_warn("), 1)
        for name in diagnostic.REMOVED_SYMBOLS:
            self.assertNotIn(name, text)
        for operation in ("setenforce", "apply_kernelsu_rules", "kthread", "vmap(", "ksu_register_feature_handler"):
            self.assertNotIn(operation, text)


if __name__ == "__main__":
    unittest.main()
