# KernelSU Next Legacy for SM-P613 — integration gate plan

> **Research only. FLASH_ALLOWED=NO.** No stock-equivalent bootable
> kernel has yet been demonstrated on the physical tablet. The target device
> currently runs the restored, unrooted Samsung boot partition and is not
> available for on-device tests.

## Verified target and immutable baseline

- Wi-Fi SM-P613, Android 14, P613XXS8CYE1, Linux
  `4.14.190-perf-28683246-abP613XXS8CYE1`.
- Original boot SHA256
  `06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`
  (verify against the original local file before packaging).
- Samsung public OSRC P613XXU4CWL1 is **older** than target firmware. A
  research compile does not establish binary, module ABI or boot compatibility.
- Authenticated CYE1 IKCONFIG comparison: all configuration lines can be
  recreated from the older OSRC except one absent, explicitly disabled
  USB-lockscreen Kconfig comment. Critically preserve
  `CONFIG_FIVE=y`, `CONFIG_PROCA=y`, `CONFIG_PROCA_S_OS=y`,
  `CONFIG_TZIC=n`, `CONFIG_KPROBES=n`, `CONFIG_MODULE_SIG_FORCE=y`.
- The research base DTB and board overlay have matched the corresponding
  original blobs **byte for byte**; the raw kernel Image has **not**.
- Research modules are CI-key-signed, but there is no evidence that the
  stock firmware trusts that signing certificate. `Module.symvers` currently
  contains one unknown/zero CRC for `gsi_write_channel_scratch`.

## Pinned upstream integration research

KernelSU Next's official non-GKI guide:
https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html

The upstream **legacy** branch was read at commit
`e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a` (2026-11-09).
Its `kernel/Kconfig` defines:

- `CONFIG_KSU` (root system; must be enabled to compile).
- `CONFIG_KSU_MANUAL_HOOK`, which defaults to `y` when KPROBES is
  disabled and KernelSU is built into the kernel.
- Other dynamic hook modes should not be enabled on this stock
  `CONFIG_KPROBES=n` 4.14 device.

The user's KernelSU Next Manager version 3.4.2 is **not evidence**
that the generic `v3.4.2` upstream release tag is appropriate for
legacy 4.14. Verify manager/kernel protocol compatibility and pin the
**legacy** integration commit before the first experimental root build.
Do not run an unpinned `curl | bash` integration in CI.

The Samsung CWL1 OSRC has candidate hook sites:

| File | Existing symbol | OSRC source location |
| --- | --- | --- |
| `fs/exec.c` | `do_execve`, `compat_do_execve` | around lines 2017, 2038 |
| `fs/open.c` | `SYSCALL_DEFINE3(faccessat)` | around line 366 |
| `fs/read_write.c` | `SYSCALL_DEFINE3(read)` | around line 600 |
| `fs/stat.c` | `SYSCALL_DEFINE4(newfstatat)` | around line 358 |
| `kernel/reboot.c` | `SYSCALL_DEFINE4(reboot)` | around line 285 |

These are inspection anchors, **not yet validated hooks**. Check actual
KernelSU Next legacy callback signatures against the pinned source before
patching. Some online diff examples are version-specific; blindly applying
them could introduce pointer bugs or bootloops.

## Gated execution order

1. Complete pinned AOSP Android 11 Clang r370808 10.0.1 comparison CI
   against successful experimental Clang 14 baseline. Neither is Samsung's
   proprietary Qualcomm Clang 10; preserve compiler-specific diagnostics.
2. Compare Image/DTB/DTBO sizes and hashes, CYE1 config, modpost warnings,
   `Module.symvers`, module `vermagic`, signature trust and any available
   ABI evidence. Resolve stock mismatch before marking a baseline image
   bootable.
3. Once technically validated, prepare a **separate controlled baseline
   test** packaging plan, retaining the original known-good `boot.img`
   and Odin rollback instructions. No automatic flashing.
4. After a supervised stock-baseline boot succeeds, add a pinned
   KernelSU Next **legacy/manual-hook** research workflow and run full
   compile, config, ABI and static checks. Keep `SELinux=Enforcing`,
   Samsung security settings and all signed-module protections.
5. Perform root and non-root behavior, boot stability, SELinux and
   app/module checks on the actual device, then consider ReZygisk,
   Vector 2.2 and PurrfectSnap. Do not claim Snapchat safety or Play
   Integrity without an actual test.

**Current stop condition for device actions:** tablet unavailable and
stock-baseline boot not verified. CI/research/documentation can progress
without a device and without existing root.
