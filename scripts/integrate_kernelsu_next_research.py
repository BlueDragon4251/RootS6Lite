#!/usr/bin/env python3
"""Strict, opt-in KernelSU Next legacy/manual-hook integration for CI research.

Applies only to a temporary extracted Samsung OSRC source tree. This script
must never touch the archived Samsung ZIP or produce a flashable boot image.
"""

import argparse
import hashlib
import os
from pathlib import Path


def replace_exact(text: str, old: str, new: str, count: int, label: str) -> str:
    actual = text.count(old)
    if actual != count:
        raise ValueError(f"{label}: expected {count} exact anchors, got {actual}")
    return text.replace(old, new)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_pinned_upstream(upstream: Path) -> None:
    required = {
        "kernel/Kconfig": [
            "config KSU_MANUAL_HOOK",
            "default y if !KPROBES",
        ],
        "kernel/core/init.c": [
            "int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv,",
        ],
        "kernel/feature/sucompat.c": [
            "int ksu_handle_faccessat(int *dfd, const char __user **filename_user,",
            "int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags)",
        ],
        "kernel/runtime/ksud_integration.c": [
            "void ksu_handle_sys_read(unsigned int fd)",
        ],
    }
    for name, needles in required.items():
        body = (upstream / name).read_text()
        for needle in needles:
            if needle not in body:
                raise ValueError(f"Pinned upstream ABI changed: {name}: {needle}")
    # Some online integration guides show an old 3-argument sys_read ABI and a
    # reboot callback; neither exists at the selected upstream legacy commit.
    # Do not link against obsolete, missing functions just to follow a guide.


def make_patches() -> dict[str, list[tuple[str, str, int]]]:
    exec_prototype = (
        "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
        "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
        "                                void *argv, void *envp, int *flags);\n"
        "#endif\n\n"
    )
    return {
        "fs/exec.c": [
            (
                "int do_execve(struct filename *filename,\n",
                exec_prototype + "int do_execve(struct filename *filename,\n",
                1,
            ),
            (
                "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);",
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "\t{\n"
                "\t\tint ksu_fd = AT_FDCWD;\n"
                "\t\tint ksu_flags = 0;\n"
                "\t\tksu_handle_execveat(&ksu_fd, &filename, &argv, &envp, &ksu_flags);\n"
                "\t\treturn do_execveat_common(ksu_fd, filename, argv, envp, ksu_flags);\n"
                "\t}\n"
                "#else\n"
                "\treturn do_execveat_common(AT_FDCWD, filename, argv, envp, 0);\n"
                "#endif",
                2,
            ),
            (
                "\treturn do_execveat_common(fd, filename, argv, envp, flags);",
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
                "#endif\n"
                "\treturn do_execveat_common(fd, filename, argv, envp, flags);",
                2,
            ),
        ],
        "fs/open.c": [
            (
                "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n\tif (mode & ~S_IRWXO)",
                "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n"
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n"
                "#endif\n\n\tif (mode & ~S_IRWXO)",
                1,
            ),
            (
                "SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)",
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
                "                               int *mode, int *flags);\n"
                "#endif\n"
                "SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)",
                1,
            ),
        ],
        "fs/read_write.c": [
            (
                "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n"
                "{\n\tstruct fd f = fdget_pos(fd);\n\tssize_t ret = -EBADF;\n",
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "extern void ksu_handle_sys_read(unsigned int fd);\n"
                "#endif\n"
                "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n{\n"
                "\tstruct fd f = fdget_pos(fd);\n\tssize_t ret = -EBADF;\n"
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "\tksu_handle_sys_read(fd);\n"
                "#endif\n",
                1,
            ),
        ],
        "fs/stat.c": [
            (
                "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "extern int ksu_handle_stat(int *dfd, const char __user **filename_user,\n"
                "                           int *flags);\n"
                "#endif\n"
                "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
                1,
            ),
            (
                "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,\n"
                "\t\tstruct stat __user *, statbuf, int, flag)\n"
                "{\n\tstruct kstat stat;\n\tint error;\n\n"
                "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
                "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,\n"
                "\t\tstruct stat __user *, statbuf, int, flag)\n"
                "{\n\tstruct kstat stat;\n\tint error;\n\n"
                "#ifdef CONFIG_KSU_MANUAL_HOOK\n"
                "\tksu_handle_stat(&dfd, &filename, &flag);\n"
                "#endif\n"
                "\terror = vfs_fstatat(dfd, filename, &stat, flag);",
                1,
            ),
        ],
    }


def integrate(source: Path, upstream: Path, manifest: Path) -> None:
    if not (source / "arch/arm64/configs/gta4xlvewifi_eur_open_defconfig").is_file():
        raise ValueError("Wrong source directory: Samsung SM-P613 defconfig missing")
    verify_pinned_upstream(upstream)

    edits: dict[Path, bytes] = {}
    for relative, patches in make_patches().items():
        target = source / relative
        text = target.read_text()
        if "ksu_handle_execveat" in text or "CONFIG_KSU_MANUAL_HOOK" in text:
            raise ValueError(f"Manual hook already present: {relative}")
        for old, new, count in patches:
            text = replace_exact(text, old, new, count, relative)
        edits[target] = text.encode()

    makefile = source / "drivers/Makefile"
    kconfig = source / "drivers/Kconfig"
    makefile_text = makefile.read_text()
    kconfig_text = kconfig.read_text()
    if "obj-$(CONFIG_KSU)" in makefile_text or 'source "drivers/kernelsu/Kconfig"' in kconfig_text:
        raise ValueError("KernelSU driver configuration already inserted")
    edits[makefile] = (makefile_text.rstrip("\n") + "\nobj-$(CONFIG_KSU) += kernelsu/\n").encode()
    edits[kconfig] = (kconfig_text.rstrip("\n") + '\nsource "drivers/kernelsu/Kconfig"\n').encode()

    link = source / "drivers/kernelsu"
    if link.exists() or link.is_symlink():
        raise ValueError("drivers/kernelsu already exists")
    link_target = upstream / "kernel"
    if not (link_target / "Kbuild").is_file():
        raise ValueError("Pinned upstream kernel/Kbuild missing")

    # The pinned upstream Kbuild detects manual hooks solely by grepping for
    # `ksu_handle_sys_reboot` in kernel/reboot.c. However, the same pinned
    # upstream revision does not define that callback anymore. Preserve the
    # stop-on-missing-hooks gate by checking the *actual* four verified hook
    # sites instead. This is an explicitly recorded CI-only Kbuild adaptation,
    # never a fabricated reboot hook, silent bypass, or change to Samsung ZIP.
    kbuild = link_target / "Kbuild"
    kbuild_original = kbuild.read_bytes()
    kbuild_old = (
        'HAVE_KSU_HOOK := $(shell grep -q "ksu_handle_sys_reboot" '
        '$(srctree)/kernel/reboot.c && echo 0 || echo 1)'
    )
    kbuild_new = (
        'HAVE_KSU_HOOK := $(shell grep -q "ksu_handle_execveat" '
        '$(srctree)/fs/exec.c && '
        'grep -q "ksu_handle_faccessat" $(srctree)/fs/open.c && '
        'grep -q "ksu_handle_sys_read" $(srctree)/fs/read_write.c && '
        'grep -q "ksu_handle_stat" $(srctree)/fs/stat.c && echo 0 || echo 1)'
    )
    kbuild_patched = replace_exact(
        kbuild_original.decode(), kbuild_old, kbuild_new, 1, "upstream/kernel/Kbuild"
    ).encode()

    # All anchor checks complete: only now mutate ephemeral extracted files.
    records = ["RESEARCH_ONLY=YES", "FLASH_ALLOWED=NO", "KPROBES_REMAIN_DISABLED=YES"]
    for path, new_content in edits.items():
        original = path.read_bytes()
        path.chmod(path.stat().st_mode | 0o200)
        path.write_bytes(new_content)
        records.append(f"{path.relative_to(source)} BEFORE={sha256(original)} AFTER={sha256(new_content)}")
    kbuild.chmod(kbuild.stat().st_mode | 0o200)
    kbuild.write_bytes(kbuild_patched)
    records.append(
        "upstream/kernel/Kbuild CI_HOOK_DETECTOR_FIX "
        f"BEFORE={sha256(kbuild_original)} AFTER={sha256(kbuild_patched)}"
    )
    link.symlink_to(link_target.resolve(), target_is_directory=True)
    records.append(f"drivers/kernelsu SYMLINK={os.readlink(link)}")
    records.append("HOOKS=execve,execveat,compat_execve,compat_execveat,faccessat,read,newfstatat")
    records.append("NO_OBSOLETE_REBOOT_HOOK=upstream_missing")
    manifest.write_text("\n".join(records) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    integrate(args.source.resolve(), args.upstream.resolve(), args.manifest.resolve())
    print("KSU_LEGACY_SOURCE_PATCH=COMPLETE_RESEARCH_ONLY")


if __name__ == "__main__":
    main()
