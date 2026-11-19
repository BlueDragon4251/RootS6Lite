"""Regression coverage for the pinned five-hook Samsung research adapter.

Fixtures model the source anchors, not a compiled Samsung kernel. The real
Samsung archive and pinned upstream are exercised separately by research CI.
"""

from pathlib import Path
import tempfile
import unittest

from integrate_kernelsu_next_research import (
    integrate,
    make_patches,
    replace_exact,
    verify_pinned_upstream,
)


REBOOT_SOURCE = """/* Native reboot entry point. */
SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,
		void __user *, arg)
{
	struct pid_namespace *pid_ns = task_active_pid_ns(current);
	char buffer[256];
	int ret = 0;

	/* We only trust the superuser with rebooting the system. */
	if (!ns_capable(pid_ns->user_ns, CAP_SYS_BOOT))
		return -EPERM;

	if (magic1 != LINUX_REBOOT_MAGIC1 || magic2 != LINUX_REBOOT_MAGIC2)
		return -EINVAL;

	mutex_lock(&system_transition_mutex);
	kernel_restart(NULL);
	mutex_unlock(&system_transition_mutex);
	return ret;
}
"""

UPSTREAM_REBOOT = (
    "int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd,\n"
    "\t\t\t  void __user **arg)\n{\n\treturn 0;\n}\n"
)
UPSTREAM_DETECTOR = (
    'HAVE_KSU_HOOK := $(shell grep -q "ksu_handle_sys_reboot" '
    '$(srctree)/kernel/reboot.c && echo 0 || echo 1)'
)

SOURCE_FIXTURES = {
    "arch/arm64/configs/gta4xlvewifi_eur_open_defconfig": "CONFIG_MODULE_SIG_FORCE=y\n",
    "drivers/Makefile": "obj-y += base/\n",
    "drivers/Kconfig": 'source "drivers/base/Kconfig"\n',
    "include/uapi/linux/time.h": "/* Legacy UAPI has no time64 definitions. */\n",
    "kernel/reboot.c": REBOOT_SOURCE,
    "fs/exec.c": """int do_execve(struct filename *filename,
	const char __user *const __user *__argv,
	const char __user *const __user *__envp)
{
	struct user_arg_ptr argv = { .ptr.native = __argv };
	struct user_arg_ptr envp = { .ptr.native = __envp };
	return do_execveat_common(AT_FDCWD, filename, argv, envp, 0);
}
int do_execveat(int fd, struct filename *filename,
	struct user_arg_ptr argv, struct user_arg_ptr envp, int flags)
{
	return do_execveat_common(fd, filename, argv, envp, flags);
}
static int compat_do_execve(struct filename *filename,
	struct user_arg_ptr argv, struct user_arg_ptr envp)
{
	return do_execveat_common(AT_FDCWD, filename, argv, envp, 0);
}
static int compat_do_execveat(int fd, struct filename *filename,
	struct user_arg_ptr argv, struct user_arg_ptr envp, int flags)
{
	return do_execveat_common(fd, filename, argv, envp, flags);
}
""",
    "fs/open.c": """SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)
{
	unsigned int lookup_flags = LOOKUP_FOLLOW;

	if (mode & ~S_IRWXO)
		return -EINVAL;
}
""",
    "fs/read_write.c": """SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)
{
	struct fd f = fdget_pos(fd);
	ssize_t ret = -EBADF;
	if (f.file)
		ret = vfs_read(f.file, buf, count, NULL);
	return ret;
}
""",
    "fs/stat.c": """SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,
		struct stat __user *, statbuf, int, flag)
{
	struct kstat stat;
	int error;

	error = vfs_fstatat(dfd, filename, &stat, flag);
	return error;
}
""",
}

UPSTREAM_FIXTURES = {
    "kernel/Kconfig": "config KSU_MANUAL_HOOK\n\tdefault y if !KPROBES\n",
    "kernel/core/init.c": (
        "int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv,\n"
        "\tvoid *envp, int *flags) { return 0; }\n"
    ),
    "kernel/feature/sucompat.c": (
        "int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
        "\tint *mode, int *flags) { return 0; }\n"
        "int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags)\n"
        "{ return 0; }\n"
    ),
    "kernel/runtime/ksud_integration.c": "void ksu_handle_sys_read(unsigned int fd) {}\n",
    "kernel/supercall/supercall.c": UPSTREAM_REBOOT,
    "kernel/preinit/runner/nolibc/time.h": "#include <linux/time.h>\n\nstatic __inline__\nint fixture(void) {}\n",
    "kernel/Kbuild": (
        UPSTREAM_DETECTOR + "\n"
        "if (mnt->mnt.mnt_flags & MNT_LOCKED)\n"
        'ifneq ($(shell grep -q "atomic_t filter_count;" $(srctree)/include/linux/seccomp.h; echo $$?),0)\n'
        "$(srctree)/include/linux/seccomp.h)\nendif\n\n# security/selinux backports\n"
    ),
}


def apply_reboot_patches(text):
    for old, new, count in make_patches()["kernel/reboot.c"]:
        text = replace_exact(text, old, new, count, "kernel/reboot.c")
    return text


class RebootPatchTests(unittest.TestCase):
    def test_hook_runs_after_declarations_before_native_permission_check(self):
        patched = apply_reboot_patches(REBOOT_SOURCE)
        call = "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);"
        self.assertEqual(patched.count(call), 1)
        self.assertLess(patched.index("int ret = 0;"), patched.index(call))
        self.assertLess(patched.index(call), patched.index("if (!ns_capable"))
        self.assertIn("void __user **arg);", patched)

    def test_native_reboot_body_is_unchanged_except_for_guarded_hook(self):
        patched = apply_reboot_patches(REBOOT_SOURCE)
        declaration = (
            "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
            "extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd,\n"
            "                                 void __user **arg);\n"
            "#endif\n"
        )
        hook = (
            "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
            "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
            "#endif\n\n"
        )
        self.assertEqual(patched.replace(declaration, "").replace(hook, ""), REBOOT_SOURCE)
        self.assertLess(patched.index("return -EPERM;"), patched.index("LINUX_REBOOT_MAGIC1"))
        self.assertLess(patched.index("return -EINVAL;"), patched.index("kernel_restart(NULL)"))

    def test_missing_permission_anchor_is_rejected(self):
        altered = REBOOT_SOURCE.replace("CAP_SYS_BOOT", "OTHER_CAPABILITY")
        with self.assertRaisesRegex(ValueError, "expected 1 exact anchors, got 0"):
            apply_reboot_patches(altered)

    def test_duplicate_reboot_function_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected 1 exact anchors, got 2"):
            apply_reboot_patches(REBOOT_SOURCE + REBOOT_SOURCE)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.upstream = self.root / "upstream"
        self.manifest = self.root / "manifest.txt"
        for root, fixtures in ((self.source, SOURCE_FIXTURES), (self.upstream, UPSTREAM_FIXTURES)):
            for relative, body in fixtures.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file() and not path.is_symlink()
        }

    def assert_unchanged_on_failure(self, message):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, message):
            integrate(self.source, self.upstream, self.manifest)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.source / "drivers/kernelsu").exists())
        self.assertFalse(self.manifest.exists())

    def test_pinned_reboot_signature_is_accepted(self):
        verify_pinned_upstream(self.upstream)

    def test_missing_pinned_reboot_callback_is_rejected_before_mutation(self):
        (self.upstream / "kernel/supercall/supercall.c").write_text("/* no callback */\n")
        self.assert_unchanged_on_failure("Pinned upstream ABI changed: kernel/supercall/supercall.c")

    def test_wrong_reboot_pointer_depth_is_rejected(self):
        (self.upstream / "kernel/supercall/supercall.c").write_text(
            UPSTREAM_REBOOT.replace("void __user **arg", "void __user *arg")
        )
        self.assert_unchanged_on_failure("Pinned upstream ABI changed")

    def test_full_integration_includes_fifth_hook_and_preserves_detector(self):
        integrate(self.source, self.upstream, self.manifest)
        self.assertEqual((self.source / "kernel/reboot.c").read_text(), apply_reboot_patches(REBOOT_SOURCE))
        kbuild = (self.upstream / "kernel/Kbuild").read_text()
        self.assertEqual(kbuild.count(UPSTREAM_DETECTOR), 1)
        self.assertNotIn('HAVE_KSU_HOOK := $(shell grep -q "ksu_handle_execveat"', kbuild)
        self.assertIn("if (path->mnt->mnt_flags & MNT_LOCKED)", kbuild)
        self.assertIn('grep -wq "put_seccomp_filter"', kbuild)
        self.assertIn("struct __kernel_timespec", (self.upstream / "kernel/preinit/runner/nolibc/time.h").read_text())
        self.assertEqual((self.source / "drivers/kernelsu").resolve(), self.upstream / "kernel")
        self.assertEqual((self.source / "arch/arm64/configs/gta4xlvewifi_eur_open_defconfig").read_text(), SOURCE_FIXTURES["arch/arm64/configs/gta4xlvewifi_eur_open_defconfig"])
        manifest = self.manifest.read_text()
        self.assertIn("kernel/reboot.c BEFORE=", manifest)
        self.assertIn("newfstatat,reboot", manifest)
        self.assertIn("UPSTREAM_REBOOT_HOOK_DETECTOR=UNCHANGED", manifest)
        self.assertIn("FLASH_ALLOWED=NO", manifest)
        self.assertNotIn("upstream_missing", manifest)
        self.assertNotIn("CI_HOOK_DETECTOR_FIX", manifest)

    def test_missing_reboot_anchor_leaves_all_earlier_files_untouched(self):
        (self.source / "kernel/reboot.c").write_text(REBOOT_SOURCE.replace("CAP_SYS_BOOT", "OTHER"))
        self.assert_unchanged_on_failure("kernel/reboot.c: expected 1 exact anchors, got 0")

    def test_duplicate_reboot_anchor_leaves_all_files_untouched(self):
        (self.source / "kernel/reboot.c").write_text(REBOOT_SOURCE * 2)
        self.assert_unchanged_on_failure("kernel/reboot.c: expected 1 exact anchors, got 2")

    def test_preexisting_hook_without_config_guard_is_rejected(self):
        (self.source / "kernel/reboot.c").write_text(
            REBOOT_SOURCE.replace("int ret = 0;", "int ret = 0;\n\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);")
        )
        self.assert_unchanged_on_failure("Manual hook already present: kernel/reboot.c")

    def test_changed_upstream_hook_detector_is_rejected(self):
        kbuild = self.upstream / "kernel/Kbuild"
        kbuild.write_text(kbuild.read_text().replace("ksu_handle_sys_reboot", "obsolete_hook"))
        self.assert_unchanged_on_failure("Pinned upstream Kbuild manual reboot-hook detector changed")

    def test_late_uapi_failure_does_not_partially_patch_sources(self):
        (self.source / "include/uapi/linux/time_types.h").write_text("/* unexpected newer UAPI */\n")
        self.assert_unchanged_on_failure("Unexpected modern time_types.h")

    def test_repeated_integration_is_rejected_without_further_changes(self):
        integrate(self.source, self.upstream, self.manifest)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Manual hook already present"):
            integrate(self.source, self.upstream, self.manifest)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
