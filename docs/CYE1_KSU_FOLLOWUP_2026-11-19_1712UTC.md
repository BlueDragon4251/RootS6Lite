# CYE1 KernelSU Next follow-up — 19 November 2026, 17:12 UTC

**Status:** Nonflashable research build succeeded. This report is based on the actual GitHub job log, downloaded archive and independently inspected kernel/map/config/module bytes.

## New result

- [GitHub Actions 44569794596](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794596): **success**, SHA `4012f415af1d4bd25428d38390b3e63d1e1dd401`. The branch push used the explicit `[cye1-kernelsu]` marker and the pinned KernelSU Next Legacy SHA `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`. New linked-image verification for the exact stock release and embedded OEM public certificate passed.
- [Artifact 14555926759](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794596/artifacts/14555926759): downloaded archive SHA256 `dbcccf9d7b212cd1eaef93ba46ec7935730967ca6bc2e235f65f9853f3d91955`; independently calculated SHA256 matches GitHub artifact digest.
- Additional source-audit [44569794493](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794493) and source verifier [44569809197](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569809197) both succeeded on the same commit.

## Artifact verification

| Evidence | Observed result |
| --- | --- |
| CYE1 exported symbols | 12,530 distinct `vmlinux` exports counted directly in `Module.symvers`; its SHA256 `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e` matches prior CYE1 baseline. Checker: **12,530/12,530** exact names, CRCs and classes against the **derived/reconstructed** OEM reference, 0 missing, 0 extra, 0 CRC or class mismatches; not a directly captured full stock `Module.symvers`. |
| Known unversioned export | `gsi_write_channel_scratch` remains CRC `0x00000000` with compiler warning; not hidden or patched. |
| Linked KernelSU hooks | Direct `System.map` verification confirms text (`T`) definitions of `ksu_handle_execveat`, `ksu_handle_faccessat`, `ksu_handle_stat`, `ksu_handle_sys_read`, `ksu_preinit_init`, `ksu_preinit_runner_start`, `ksu_preinit_runner_end`. |
| Embedded preinit runner | Extracted at `Image` file offset **40,259,424**, length **17,280 bytes**, SHA256 `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`. The ELF is AArch64 (e_machine=183), and both PT_LOAD alignments are congruent for 4 KiB and 64 KiB pages. |
| Kernel image and release | `Image` size 48,828,432 bytes, SHA256 `b3d551884c1fd95ed5632deac3691bbe343f30a3dfb91833c48c57c12ba418a7`. Contains exact `4.14.190-perf-28683246-abP613XXS8CYE1`; differs from original stock Image (48,832,528 bytes). |
| Embedded stock OEM public certificate | Independently located exactly one DER certificate (ASN.1 1357 bytes) inside compiled `Image`, SHA256 `ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1`. This is a **public** certificate, not the original OEM private key nor proof of actual OEM module trust. |
| Config: pristine vs KSU final | Authenticated pre-build stock config SHA256 `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208`. Pre-KSU effective config SHA256 `a0370e63486576da637d933966c32e4a271e471cc0b1fa6fc7bb1604c2488a96` includes OEM public key path. **Final KSU config** `ksu-legacy-research.config` SHA256 `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416`, with `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `CONFIG_MODVERSIONS=y`, `CONFIG_MODULE_SIG_FORCE=y`, and Kprobes disabled. Do not mistake the pre-KSU config hash for final KSU config. |
| Signed research modules | **10/10** appended PKCS#7/CMS signatures independently verified with OpenSSL against the archive's **ephemeral CI signing certificate** as an explicitly selected validation trust anchor; a tampered-content negative test failed as expected. Every signed `.ko` has exact stock-release `vermagic` prefix `4.14.190-perf-28683246-abP613XXS8CYE1`. OEM stock modules were *not* signed by this CI key and have not been validated. |
| DTB / DTBO | Compiled Qualcomm base DTB SHA256 `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816` and SM-P613 EUR Wi-Fi DTBO SHA256 `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`; both match authenticated stock reference hashes. |

## Physical device distinction (newly supplied owner evidence)

The owner reported successful Android 14 userland boot on the **SM-P613/P613XXS8CYE1** after flashing the earlier **non-KSU baseline** experimental TAR. Actual `adb shell cat /proc/version` output includes `roots6lite-ci@github-actions`, full stock CYE1 release string and AOSP Clang 10.0.1. Runtime `getenforce` is **Enforcing**, `ro.boot.verifiedbootstate` **orange** and `ro.boot.flash.locked` **0**. See [CYE1 baseline boot test](CYE1_BASELINE_BOOT_TEST.md) for complete evidence. This **supersedes older claims in the primary CI report that no baseline physical boot had occurred**. It does *not* establish that the newly built **KSU** kernel boots or provides working root.

## Outstanding gates

The standard libfdt DTBO overlay apply check still fails with `FDT_ERR_BADOVERLAY`; Android-specific runtime overlay handling has not been independently validated. The compiler is pinned **AOSP Clang 10.0.1**, not OEM **Clang 10.0.7**. The original stock/vendor `.ko` set has not been comprehensively checked for true trusted signers, import/modversion satisfaction or runtime module loading. Wi-Fi, Bluetooth, audio, cameras, suspend/resume and charging on this custom baseline are not fully reported. No KernelSU device test has occurred. An ephemeral CI module signature is **not** OEM module trust.

**FLASH_ALLOWED=NO for KernelSU.** No merge to `main`, no flashable package, no fake CRC values, no weakened signature checks. The non-KSU baseline's physical boot must not be extrapolated to the changed KSU image.

## Physical KSU bootloop postmortem update — 2026-11-19 18:12 UTC

**This section supersedes the statements above saying no KernelSU physical test has occurred.** The SM-P613 owner reported a **BOOTLOOP** after flashing the *separate KernelSU-enabled* CYE1 Odin experiment. This is now documented as a **failed physical boot**, despite the successful build, derived ABI parity (12,530/12,530), linked manual hooks and preinit ELF, OEM public certificate embedding and offline packaging checks. The previously booted **non-KSU** CYE1 baseline remains the only positive physical boot evidence. No bootloop phase, kernel panic/pstore log, or successful recovery result has yet been supplied; **the actual cause is unknown**. Samsung RKP/KDP/FIVE/PROCA interactions are hypotheses, not proven diagnoses.

Known-failing KSU test TAR SHA256: `e3b1fe96470973ea99a603d657700d039a20fc8aa4b1a79cc876bbf276dd0626`; inner boot.img SHA256: `d3a7a5dae7d4137e1bb54930a5ef5efb655e57cd6ca2a453d56cc3d2aa3cdce7`. **Do not repeat-flash these binaries.** Restore the known-good baseline or exact matching Samsung stock firmware in Download Mode before further investigation. No factory reset is a substitute for restoring a bad boot kernel. See [physical incident and recovery notes](CYE1_KERNELSU_NEXT_TEST_PACKAGE_2026-11-19.md#physical-device-incident--2026-11-19).

New repository checks after the incident: [source verifier 44584798284](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44584798284) and [source compatibility audit 44584783375](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44584783375), both **success** on documentation commit `8c5768a`. They are not additional KSU bootability evidence. Actual artifact `14559258252` was downloaded and inspected (ZIP SHA256 `614a510d24fef2d60f433db0df690a0777bc6a10a3ff16111c201f967f2baf8c`); it still reports community source `4.14.357-openela` versus stock `4.14.190`, `kernel_version_exact_match=false`, `flash_safe=false`.

**Gate: KSU physical boot FAILED, root NOT ESTABLISHED, no repeat flash, no additional KSU package or push, no merge to main.** A distinct changed/instrumented research image would need independent review, and device-side crash evidence is needed before a confident diagnosis.
