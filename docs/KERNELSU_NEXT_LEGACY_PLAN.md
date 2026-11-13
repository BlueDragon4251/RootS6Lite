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


## Independent offline integration experiment — 2026-11-13 (not a boot test)

The physical baseline gate above is **still not satisfied**. To make progress while the tablet is unavailable, a separate [opt-in Legacy CI workflow](../.github/workflows/samsung-kernelsu-next-legacy-compile.yml) and [strict source adapter](../scripts/integrate_kernelsu_next_research.py) were prepared without changing stock source ZIP, baseline build behavior, Android, or the tablet. The independent experimental [run 43405563445](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43405563445) was started; its actual build result must be checked separately.

The integration first **generates and SHA256-verifies the exact CYE1 stock .config without KSU**, then adds upstream `Kconfig/Kbuild` and applies precisely anchored manual hooks only in the temporary runner tree, re-runs `olddefconfig` and confirms `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `CONFIG_KPROBES=n`, stock FIVE/PROCA, forced module signing and SELinux. Every modified source file receives a before/after SHA256 record. The pinned Git upstream SHA is verified before use; no floating install script, new repository, release, flashed boot image or privileged on-device operation.

**Important upstream-versus-doc API drift:** The official website's sample `ksu_handle_sys_read(fd, &buf, &count)` does not match the actually pinned `legacy` source at `e5f5ec9`, which defines `void ksu_handle_sys_read(unsigned int fd)`. The sample also references `ksu_handle_sys_reboot`, which is absent at that commit. Therefore, the experimental adapter uses verified upstream ABI in `fs/read_write.c`, **does not invent a reboot callback**, and keeps all compatibility assumptions explicitly unverified. It also passes a **real addressable `int` variable** for the `AT_FDCWD` exec hook, instead of the website example's unsafe integer-to-pointer cast. Native and compat `execve`/`execveat` codepaths are considered; formal function/ABI correctness and runtime tests remain open.

Even if the new KSU experiment compiles, **stock ABI equality, bootability, KSU root behavior and Samsung boot-chain compatibility are NOT proven**. Do not merge the PR or distribute an Odin-flashable image on the strength of the CI run.


### Actual Legacy CI failure analysis and targeted source shims

- [First KSU CI 43405563445](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43405563445): `BUILD_EXIT_CODE=2`. The pinned upstream's `kernel/Kbuild:221` **aborted before compilation** because it only looked for `ksu_handle_sys_reboot` in `kernel/reboot.c`, although the same pinned upstream lacks that callback. [Commit 56e460d](https://github.com/BlueDragon4251/RootS6Lite/commit/56e460d92e804a577e0fab03c3963a5b43ce2626) replaces that stale Kbuild detector **only in the CI checkout** with checks for all four actual source hook files. No fake reboot callback or silent `HAVE_KSU_HOOK=0` override.
- [Second KSU CI 43406135320](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43406135320): the corrected manual hook detector passed, but the build stopped on a real Samsung GCC-wrapper-rejected `-Wdeclaration-after-statement` warning in `fs/read_write.c`. [Commit 9d4e656](https://github.com/BlueDragon4251/RootS6Lite/commit/9d4e656e585606620bbf1b5d830f3de7efa5c5c5) moves the hook after existing local C90 declarations. Warning policy remains unchanged.
- [Third KSU CI 43406752433](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43406752433): first true compiler error in the pinned upstream's **automatic legacy `can_umount` backport**: `fs/namespace.c:2286:15` dereferenced `mnt->mnt.mnt_flags` as a value. On this Samsung kernel, `CONFIG_RKP_NS_PROT` makes `struct mount::mnt` a **pointer**, so the expression is invalid. [Commit 242e6cb](https://github.com/BlueDragon4251/RootS6Lite/commit/242e6cba03a040bd05ff3578e0ba6d6c5c43749b) changes the temporary upstream backport to `path->mnt->mnt_flags`, reading the same underlying `vfsmount` security flag regardless of the Samsung-specific mount representation. `MNT_LOCKED` security semantics are retained. [Fourth KSU CI 43407327486](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407327486) was launched; its outcome must be verified in actual job logs.

Other pinned upstream legacy backports **automatically modify** `fs/namespace.c`, `fs/internal.h`, `include/linux/seccomp.h`, and several `security/selinux` sources during make. These are real changes to the ephemeral kernel source that require source review and boot-time validation, especially for stock Samsung FIVE/PROCA/RKP/SELinux. The Kbuild has also reported `preinit disabled` because staged kernel UAPI headers were absent; assess whether the fallback init integration suffices before making any root-functionality claims.

The stock baseline workflow, source archive, module signature enforcement and no-flash gate are untouched by these opt-in research changes.


### First complete linked KernelSU Next Legacy research build (2026-11-13)

[Run 43407327486](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407327486) completed **SUCCESS**; actual job logs show `BUILD_EXIT_CODE=0`, one base DTB, one SM-P613 DTBO, ten signed modules and an uploaded **RESEARCH-NOT-FLASHABLE** artifact (ID `14028569861`). Both built DT tree files match the verified CYE1 references byte for byte; the Image **does not** match the Samsung stock Image. The build used pinned KernelSU Next Legacy upstream `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a` and pinned AOSP Clang10, not Samsung Qualcomm OEM Clang10. **Compilation alone does not prove that KSU root works.**

The compiler output also reports `gsi_write_channel_scratch` without an export CRC and the upstream Kbuild explicitly reported `preinit disabled` because the kernel UAPI header staging directory was missing. These are **open compatibility/functionality questions**, not harmless warnings. The actual 4 manual-hook functions had been checked at the source/configuration level, but a post-link `System.map` audit is needed to distinguish compiled-in functions from merely present source.

[Commit 7ffd225](https://github.com/BlueDragon4251/RootS6Lite/commit/7ffd225caa72ebb9b0a338b7558b5cc8ae3ef7ef) now stages kernel UAPI headers with Samsung's own `headers_install` target **only in the opt-in research build**, requires the preinit header sentinel and runs a new linked-symbol/configuration audit after `Image` linking. The new [linked-symbol verifier](../scripts/verify_kernelsu_research_symbols.py) and [four offline unit tests](../scripts/test_verify_kernelsu_research_symbols.py) were added in commits `96ae27e` and `d8e2ba4`; all four unit tests pass locally. The updated KSU [run 43410832253](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43410832253) must be assessed from real logs and artifacts before this new check is considered validated in CI. The unchanged-stock Clang10 and Clang14 controls [43407157828](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407157828) and [43407157745](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407157745) both succeeded after the diagnostic-parser restoration.

**Still blocked:** OEM toolchain equality, stock vendor-module ABI and signing trust, Samsung 2025 CYE1 source/build congruence, Android boot/SELinux/security hooks, verified preinit behavior, and on-device root. Tablet unavailable and unrooted. `FLASH_ALLOWED=NO`; no Odin image is released.


### Independent full KSU artifact audit and export-CRC mismatch

Downloaded the actual [43407327486 artifact](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407327486): ZIP SHA256 `4b5596d064e61d6773dc8b540fbc2ea21b75331bfe70def31134ef11731f2479`; Image SHA256 `cdd664f21ea69ac3ac5bd7cb3acfc162ea45c6c48ee881844621dbf6629b1718` (48,828,432 bytes, **not** stock-equal). The real `_out/System.map` includes **linked executable-text symbols** `ksu_handle_execveat`, `ksu_handle_faccessat`, `ksu_handle_stat`, and `ksu_handle_sys_read`. KSU config confirms built-in manual hooks with Kprobes disabled and existing FIVE/PROCA/SELinux/module-signing enforcement. This establishes binary linkage, not functioning privilege escalation or root.

A reproducible symbol-name/CRC join of this KSU `Module.symvers` against the pinned AOSP10 stock control yields **12,559 common exported symbols, 8,271 changed CRCs** (65.86%). There are no dropped symbol names among those 12,559. The earlier AOSP10 stock artifact `43395956545` has a **byte-identical** `Module.symvers` to the later green stock control `43407157828`, so baseline drift does not explain this large difference. **This is a blocking module-ABI finding until impact on real CYE1 OEM modules is established.** A likely major driver is upstream Kbuild's automatic addition of `atomic_t filter_count` to `struct seccomp`, indirectly affecting `task_struct` and many exported type CRCs; this is a source-based hypothesis, not yet a proven single cause. The upstream `kernel/policy/app_profile.c` explicitly references `current->seccomp.filter_count`; removing that field without redesigning its semantics is not a safe shortcut.

The artifact also proves the old build's preinit runner symbols are absent, as expected from `preinit disabled`. The next CI run adds header staging, and the [enhanced six-test symbol verifier](../scripts/verify_kernelsu_research_symbols.py) now requires linked `ksu_preinit_init`, runner start/end and nonzero embedded runner size. These checks remain a necessary but insufficient offline gate; **do not bypass them to get a green CI badge**. The OEM kernel module signatures and stock ABI are not known from this research build.


### Preinit-enabled full kernel and embedded ELF inspection (2026-11-13)

[Run 43412971174](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43412971174) completed **SUCCESS** after the pinned-upstream-only Samsung 4.14 time64 UAPI compatibility shim in [`fa20424`](https://github.com/BlueDragon4251/RootS6Lite/commit/fa20424863460c6274fafcd49903c48fa17e4f04). Real job logs: `BUILD_EXIT_CODE=0`, `preinit enabled`, `KSU_MANUAL_HOOKS_LINKED=YES`, `KSU_PREINIT_EMBEDDED=YES`, `KSU_RESEARCH_CONFIG_VALID=YES`; exact CYE1 base-DTB/board-DTBO parity and ten independently signed research modules. The automated symbol report says the embedded runner occupies **17,280 bytes**, not an empty placeholder. Artifact ID `14031702155`; downloaded ZIP SHA256 `618c5ee5537a496546952475fdac8dfd3ac0a177890e1759f79d07823dc58d56`.

The older Android GCC4.9 BFD linker printed `-z noseparate-code ignored`. To investigate the *actual effect* without executing anything on the tablet, the runner bytes were extracted **from the final linked Image** using `System.map` symbols `_text`, `ksu_preinit_runner_start` and `ksu_preinit_runner_end`. Extraction offset was 40,258,144 bytes; the runner SHA256 is `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`. It is a stripped, statically linked AArch64 ELF64 executable; its two `PT_LOAD` segments are both 65,536-byte aligned with matching `p_offset % page_size == p_vaddr % page_size` for both 4,096 and 65,536 bytes. The entry point belongs to executable `PT_LOAD`; there are no dynamic/interpreter segments and the GNU stack is nonexecutable. This **answers the observed file-layout warning for this artifact**, but does *not* prove Android will launch the preinit runner successfully or that Root works.

A reusable [embedded-runner ELF verifier](../scripts/verify_kernelsu_preinit_elf.py) and [four passing offline verifier tests](../scripts/test_verify_kernelsu_preinit_elf.py) were added in `938569b` and `c266242`; automated CI integration of this second-level verifier is pending. **No flash approval; the large export CRC divergence documented above remains an explicit ABI blocker.**


### Export-CRC regression eliminated without weakening Samsung seccomp (2026-11-13)

**Independent A/B result:** [Run 43415010034](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43415010034), commit [`0eb5e5e`](https://github.com/BlueDragon4251/RootS6Lite/commit/0eb5e5e047eab752a08a6be347fd605157e2af56), completed **SUCCESS**. Downloaded KSU artifact ZIP SHA256 `826c3d3ff6868cd534476594c49bcf1eca6bd781ec1c73dd18bbcade8bfebc69`; raw Image SHA256 `4da0c2f0974c5d23b8b74fb3ffeee73493691eb59690037c2c42c96a3a6ffbdf` (48,828,432 bytes; *not* stock-equal). Actual logs confirm `BUILD_EXIT_CODE=0`, linked manual hooks, nonempty Preinit runner, exact stock-reference DTB+DTBO and ten signed research modules.

**Module.symvers comparison with the same pinned AOSP10 CYE1-config stock research control**: 12,559 common exports; **0 changed CRCs**. The complete `Module.symvers` files are byte-for-byte equal (SHA256 `a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94`). Without this patch, the KSU builds with or without Preinit both changed exactly **8,271 CRCs**. Therefore, the unconditionally inserted upstream `seccomp.filter_count` field **was the cause of the observed research-control CRC cascade**. Upstream 4.14 KSU's own `disable_seccomp()` implementation uses the already available `put_seccomp_filter()` path; the `filter_count` access is guarded behind a **newer** codepath not selected on this Samsung 4.14 kernel. The CI-only Kbuild shim now conditions that extra backport on the absence of `put_seccomp_filter()`, consistent with upstream's existing optional-release test. It does *not* alter Samsung's original seccomp field layout, `CONFIG_SECCOMP`, kernel security policy, or stock-build mode.

The actual resulting binary also independently passes [embedded ELF layout validation](../scripts/verify_kernelsu_preinit_elf.py): 17,280 bytes, identical runner SHA256 `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`, static ARM64 ELF with two correctly congruent 4K/64K `PT_LOAD` segments. The [KSU-only workflow CI gate in `e82be65`](https://github.com/BlueDragon4251/RootS6Lite/commit/e82be65cb7a974507b12bf9f0aef1e5d9b1bf5c1) now automatically validates the embedded ELF, forbids reintroducing `filter_count`, requires the **pinned stock-research** `Module.symvers` hash, and runs all ten locally passing verifier unit tests. The new [full CI run 43417308976](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43417308976) must be checked before the additional gate is marked green.

**Scope limit:** This establishes **research AOSP10 baseline** export-CRC parity, not equality with the *original proprietary Samsung CYE1 kernel* or original stock vendor modules. Samsung OEM module-signing certificate trust, original module CRCs, kernel Image binary mismatch, 2025 firmware compatibility, bootchain and device root are unverified. `FLASH_ALLOWED=NO` and PR stays Draft.


### OEM compiler provenance check — 2026-11-13

The authentic Samsung `README_Kernel.txt` recipe calls for the old Qualcomm `toolchain/llvm-arm-toolchain-ship/10.0/bin/clang` rather than generic upstream `clang`. Qualcomm's [official Snapdragon LLVM Compiler page](https://www.qualcomm.com/developer/software/snapdragon-llvm-compiler) presents a **login-to-download** route; it does not demonstrate that the exact Samsung-era `llvm-arm-toolchain-ship/10.0` release, revision, or cryptographic digest is available for an unattended, reproducible GitHub Actions build. Qualcomm's [2026 CPULLVM announcement](https://www.qualcomm.com/developer/blog/2026/04/announcing-an-open-source-llvm-toolchain-for-snapdragon-cpus-mcus) describes a new open-source LLVM 22-era family, **not a drop-in replacement for the historical proprietary Qualcomm Clang 10**. Do not invent an OEM toolchain SHA or obtain unsigned executables from arbitrary mirrors.

**Compiler gate remains open**. The pinned official **AOSP Clang 10** CI control proves a reproducible comparison and internal 12,559-export CRC reference, but not original CYE1 OEM ABI, exact `vermagic`, image equality, or boot compatibility. The research kernel and its ten newly signed modules cannot inherit trust from Samsung's inaccessible OEM signing key. `FLASH_ALLOWED=NO`.


### Remaining warnings classified from actual full KSU log

Read the complete successful [KSU A/B run 43415010034](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43415010034) job log, **not just its green status**. The log has 84 `warning:`/`WARNING:`-matched lines; many are repeated in separate Kconfig passes. The following distinct root causes remain tracked:

- `drivers/ccic/Kconfig` and `drivers/Kconfig`: unsupported source characters (likely original CR characters, needs byte-level verification), repeated; do not silently drop Kconfig content.
- `drivers/samsung/debug/Kconfig`: conflicting `SEC_DEBUG` tristate/boolean definition and unsupported choice-value defaults; Samsung source Kconfig semantics require investigation.
- Host `scripts/extract-cert.c`/`sign-file.c`: OpenSSL 3 deprecated `ENGINE_*`/`ERR_get_error_line` calls on Ubuntu 22.04; these are host-tool API compatibility warnings, not evidence that module signatures are accepted on the tablet.
- Host `security/samsung/defex_lsm/pack_rules.c:444`: `strncpy` possible truncation of an 8,126-character input into the fixed 4,096-byte integrity field; exact DEFEX rule format/expected maximum must be proven before changing the rule packer.
- `MODPOST`: `gsi_write_channel_scratch` version generation failed twice and remains the sole zero-CRC exported symbol in research controls. OEM behavior is unknown.
- Legacy Android GCC4.9 linker: `-z noseparate-code ignored` for the preinit runner. The extracted real runner passed static AArch64 ELF, entry, `PT_LOAD` 4K/64K congruence and non-executable-stack checks; runtime execution remains unverified.
- Node `punycode` and `url.parse()` deprecations arise in GitHub's artifact-upload action runtime; classify separately from kernel compilation.

No warning above is designated harmless or silently suppressed. All are either an explicit source/platform compatibility item, host-tool issue or a runtime gate. `FLASH_ALLOWED=NO`.
