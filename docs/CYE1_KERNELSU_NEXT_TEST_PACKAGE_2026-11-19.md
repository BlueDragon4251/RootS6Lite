# Experimental CYE1 + KernelSU Next boot images — 2026-11-19

## Current status — 2026-11-20: KSU5 / trace also FAILED on device

The owner reports **"wieder bootloop mit ksu"** after the KSU5/trace handoff.
This supersedes the previous **device untested** status for that candidate.
Record **physical boot FAILED (owner-reported)**, root **NOT ESTABLISHED**.
Stock Recovery was reachable but ADB reported `unauthorized`; no new crash log
or restart timing was obtained. The owner subsequently reports having flashed
back. Android startup after this particular rollback is not yet confirmed.
The exact failure stage and cause remain unknown; do not invent a kernel panic.

**Do not flash or repackage the KSU5/trace Image again:**

- Image SHA256: `83f2e337b2563b4e0414ec4d59e374f6d345e199b17df43487ebf44cbe986c11`.
- Inner boot.img SHA256: `1785fbfcce0f9a38f7869b23a7a4fda12c61eff077d142aa3d1c3c4828f26a1b`.
- Odin TAR SHA256: `f1437f3471a9ca0017261dfd5917992a7ddc77b07a38fc64ec00774777aa5000`.

The guarded packager now rejects this Image as well as the earlier failed
legacy Image **before reading other provenance or accepting static checks**.
Regression tests cover both exact Image hashes. The kernel itself is not
changed by this incident-recording/denylist commit; no replacement KSU flash
package is being released from it.

The source insertion and five actual linked hook types were already verified.
The repeated failure means the fifth-hook fix was **not sufficient**. It does
not prove that all hook arguments, initialization paths or Samsung interactions
are correct. `KPROBES=n` remains unchanged. Do not disable SELinux, OEM module
signature enforcement or Samsung protection features to manufacture success.

### Evidence preservation and recovery

If the stock Recovery is reachable, enter it once and avoid repeated normal
boot attempts, factory reset, cache wipe or choosing ADB sideload as if it were
a shell. Earlier Samsung Recovery logs show a copy from `/proc/last_kmsg` to
`/cache/recovery/last_kernel` (previously 2,097,136 bytes). This establishes a
candidate path, **not current accessibility or that its contents are fresh**.

- Check `adb devices` once when at a PC. Only a normal `recovery`/`device`
  transport justifies attempting to pull that exact file. `sideload`, an empty
  list, `offline` or `unauthorized` does not provide a normal file-export path.
- If pull is denied or the file is missing, stop. No `adb root`, permission or
  SELinux changes are required or promised. A recovery log viewer, if present,
  may provide photographed evidence; Samsung's available files are unverified.
- No working direct UEFI Fastboot log export is established for this device.
  Its earlier `max-fetch-size` query was unsupported. Do not invent OEM commands.
- Restore the known-booted **baseline rollback TAR** via Odin AP in Download
  Mode if logs cannot be obtained promptly. No factory reset as a first step.
  Keep full matching stock firmware as the fallback. The owner now reports
  flashing back; successful Android startup after this rollback is still open.

Green CI remains valid compilation/static evidence, not a successful boot.
The 42 marker strings in the Image do not tell us which marker executed on the
device; new failed-boot evidence is needed to localize this incident.

### Source-based diagnostic hypothesis, not a diagnosis

The exact pinned [optional SELinux-hide subsystem](https://github.com/KernelSU-Next/KernelSU-Next/blob/e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a/kernel/feature/selinux_hide.c)
starts an asynchronous kernel thread and installs file-operation hooks by
writing through a `vmap(..., PAGE_KERNEL)` alias. Second-stage and post-fs-data
paths also install these hooks. Thus `init.after.ksu_selinux_hide_init` only
records return from thread creation; it does not prove that worker completed.
The existing 42 markers do not individually enclose that asynchronous worker.

This is a concrete, isolated comparison candidate: omit the optional
hide subsystem's thread and installation entry points in an explicitly named
diagnostic profile, **not** SELinux enforcement or Samsung protection checks.
Merely setting its feature boolean false is not equivalent: the setter changes
filtering but does not prevent installation. The separate research branch
`agent/ksu-no-selinux-hide-diag` has now compiled and statically verified that
variant in successful [run 44692312623](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44692312623);
the independent artifact comparisons and remaining limits are recorded in
the [diagnostic report](CYE1_NO_SELINUX_HIDE_DIAGNOSTIC_2026-11-20.md).
It is not an Odin release. The subsystem is **not established as the failure cause**.

Useful actual-log landmarks are `ROOTS6_KSU_TRACE: init.entry`, the paired
`init.before/after.prepare_creds` and `init.before/after.ksu_lsm_hook_init`,
`init.complete`, then the `second_stage.before/after` markers around
`ksu_selinux_hide_handle_second_stage`, `apply_kernelsu_rules`, and
`setup_ksu_cred`. An `after` marker only proves return, not semantic success;
missing markers in incomplete or lost logs do not prove a path was not run.

At incident-recording commit `f2552a943066bb5dc5bf9b857cb77e776bc152f7`,
**154/154 local tests passed**, including **25/25 packager tests**. The later
no-hide diagnostic increases that to **179/179**, including **27/27 packager
tests**, and is confirmed by its own GitHub compile/self-test runs above.
These test rejection and validation logic, not device boot.

## Historical KSU5 / trace preparation — static checks passed before device test

The owner explicitly requested a new private Odin test package while unable to
run PC/device commands. The result is a **new experimental boot/diagnostic
candidate**, not a claim that KernelSU now boots or that the earlier failure's
root cause is fixed. The previously failed image below remains rejected.

### Reverified provenance and source integration

- Kernel build [44605802348](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44605802348),
  source commit `c380056b7f6e4f530ab96c034d8395558fdffb3b`: GitHub confirmed
  `completed/success`, including linked ELF call-edge and trace checks.
- Artifact `14571571487`, ZIP SHA256
  `9dbb8c2e077ff8dd898dd5284e7d31567c9c3ad6af4bfc940d48643ea5fc5ddd`:
  downloaded bytes match GitHub's digest; ZIP integrity checked again.
- KernelSU Next legacy remains pinned to
  `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`. Source insertion, Kbuild/Kconfig
  wiring and the complete non-GKI guide were rechecked. The read-hook ABI is
  taken from this revision, not copied blindly from a different guide version.
- Raw ARM64 Image instructions independently prove ten distinct caller-to-hook
  BL edges: six native/compat exec callers plus faccessat, newfstatat, read and
  reboot. The reboot hook is before the original capability check; that check
  remains present. All 42 diagnostic marker strings are present.
- `CONFIG_KSU=y`, manual hooks enabled, `KPROBES=n`, `KSU_DEBUG=n`.
  Embedded IKCONFIG equals the audited final config. Stock signing, MODVERSIONS,
  SELinux and Samsung RKP/KDP/FIVE/PROCA configuration are retained.

### Packaging gate changes and CI

Packager commit `e13e0767a693c36ee9851269dfb9a6a101982610` adds mandatory
raw-Image BL decoding, the existing complete trace/config validator, and clean
pinned-tool-worktree checks. Missing/offset/wrong reboot calls, aliases, B
instead of BL, duplicate calls, reduced traces and dirty tool sources fail.
The new `--ksu-trace-manifest` input is required for this diagnostic profile.

153/153 local tests passed, including 24 package tests (16 new). GitHub also
confirmed these post-change runs `completed/success`:

- [44620296024](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44620296024):
  pushed-branch Samsung source verifier self-test, including guarded packager.
- [44620312363](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44620312363):
  pull-request self-test.
- [44620296012](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44620296012):
  source compatibility audit.

No kernel source changed during this packaging pass; the Image is exactly the
successful kernel-run artifact above, not an unverified new rebuild.

### Independent binary and package results

- 12,530/12,530 reconstructed export names/CRCs/classes match, including all
  21 previously missing OEM exports. The 46 CYE1 delta entries were rederived
  from the original Image plus authenticated control. Actual Image export CRC
  arrays and names agree with Module.symvers using the linked System.map.
- Module.symvers is byte-identical to the physically booted baseline:
  `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`.
- The OEM public certificate is byte-identical to the stock Image certificate
  and inside the compiled trust list. All ten CI research-module signatures
  were independently verified, with exact stock vermagic. This is not a
  runtime stock-module loading test.
- Original boot no-op repack is byte-exact. The new TAR was generated twice;
  both complete TARs and both reports are byte-identical.
- An independent parser then checked the actual final TAR rather than trusting
  its report: one regular `boot.img`, 100,663,296 bytes, header v2, 4096-byte pages,
  correct SHA1 image ID, exact new gzip kernel, original 725,007-byte ramdisk,
  **complete 442,884-byte DTB region including the additional 173-byte FDT**,
  original commandline and 528-byte Samsung trailer.
- AVB footer/descriptor offsets, salt-plus-image SHA256, sizes and padding were
  independently recalculated. Algorithm is **NONE / unsigned**, not Samsung
  authentication. No `force_feature` or `allow_shell` override is added.
- The rollback TAR is byte-for-byte identical to the previously flashed,
  successfully booted non-KSU baseline, not a newly rebuilt substitute.

| Identity | SHA256 |
| --- | --- |
| New `RootS6Lite_SM-P613_CYE1_KSU5_TRACE_EXPERIMENTAL.tar` (100,669,440 bytes) | `f1437f3471a9ca0017261dfd5917992a7ddc77b07a38fc64ec00774777aa5000` |
| New inner `boot.img` | `1785fbfcce0f9a38f7869b23a7a4fda12c61eff077d142aa3d1c3c4828f26a1b` |
| New uncompressed Image | `83f2e337b2563b4e0414ec4d59e374f6d345e199b17df43487ebf44cbe986c11` |
| `RootS6Lite_SM-P613_CYE1_BASELINE_ROLLBACK.tar` (100,669,440 bytes) | `e98e22019d02e2a21e9f14db8be4466e7e5ab97c7924e49d40a64e380e2a98b3` |
| Rollback inner `boot.img` | `640da30f79fea0deb45bdcdb7e75841a285eb4af55dea149f0f6e8be070e2061` |
| Rollback uncompressed Image | `5609cb6faa2a6f07f4a0d0a2205f0d06fe696697cb6efc456d05a6b24d57d600` |

### Remaining constraints and owner test scope

At preparation time, physical boot, preinit execution, manager handshake, root
authorization and original Samsung module loading were **NOT TESTED**. Physical
boot has since **FAILED**, as recorded above; the other runtime checks remain
unestablished. The
reference is reconstructed, not an original OEM Module.symvers. Clang 10.0.1
is not proven equivalent to OEM Clang 10.0.7. Standard libfdt still reports
`FDT_ERR_BADOVERLAY`; the package retains the original complete DTB and does
not flash a DTBO partition. No CRC or safety check was overridden to claim a pass.

The pinned optional **SULOG** path has a separate argv/logging defect; its
feature defaults to disabled and the stock commandline supplies no override.
Do not enable SULOG or other experimental features/modules in this boot-only
test. This is a later root-functionality blocker, not established evidence for
the earlier early-boot failure.

The private handoff includes the new TAR, unchanged baseline rollback, SHA256
list, JSON validation report and German Odin instructions. AP only; BL/CP/CSC/PIT
empty; Re-Partition/Nand Erase off; no extra vbmeta or bootloader relocking.
Matching full stock firmware remains the fallback. Keep the magnetic cover
away during the test. A failed boot does not justify an immediate factory reset.

Upstream research manifests deliberately retain `FLASH_ALLOWED=NO`; they do
not certify runtime readiness. The explicitly requested local reconstruction
is labelled `UNVERIFIED_EXPERIMENTAL_ONLY`, not a flash-ready release. No OEM
boot binaries, private keys or device logs are committed to this public repo.

## Rejected previous image and incident history

**For SM-P613 P613XXS8CYE1 only. The KSU test image has now been physically tested and FAILED TO BOOT (bootloop). DO NOT FLASH OR REDISTRIBUTE THIS TEST IMAGE.**
No actual KernelSU privileges, stock module import, or manager interoperability
have been confirmed on-device.

## Established evidence

The non-rooted CYE1 baseline [run 44507834398](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834398)
was flashed by the device owner and successfully booted Android 14. Direct
`/proc/version` identifies `roots6lite-ci@github-actions`, AOSP Clang 10.0.1,
the original `4.14.190-perf-28683246-abP613XXS8CYE1` release string, and
GNU ld 2.27. Device-side checks showed SELinux `Enforcing`, Verified Boot
`orange`, and `ro.boot.flash.locked=0`. This is baseline evidence only.

The **separate, root-enabled** CYE1 [run 44569794596](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794596),
commit `4012f415af1d4bd25428d38390b3e63d1e1dd401`, **succeeded**. Actual
artifact 14555926759 has downloaded ZIP SHA256:
`dbcccf9d7b212cd1eaef93ba46ec7935730967ca6bc2e235f65f9853f3d91955`.

- Linked ARM64 Image: 48,828,432 bytes, SHA256
  `b3d551884c1fd95ed5632deac3691bbe343f30a3dfb91833c48c57c12ba418a7`.
- Kernel release matches the booted baseline exactly. The original Samsung
  module-signing public X.509 certificate is embedded exactly once, with
  `CONFIG_MODULE_SIG_FORCE=y` still enabled.
- Baseline `Module.symvers` and KSU `Module.symvers` are **byte-identical**:
  SHA256 `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`.
  The derived stock export comparison found 12,530/12,530 exact symbols,
  CRCs and classes. This still is not a full stock module ABI test.
- Kconfig differs from baseline by the explicit KernelSU options only:
  `CONFIG_KSU=y` and `CONFIG_KSU_MANUAL_HOOK=y`, with `KPROBES=n`. Config
  SHA256 `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416`.
- Pinned KernelSU Next legacy revision:
  `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`.
- The actual `System.map` contains executable `ksu_handle_execveat`,
  `ksu_handle_faccessat`, `ksu_handle_stat` and `ksu_handle_sys_read` hooks.
  The embedded static ARM64 preinit ELF is 17,280 bytes (SHA256
  `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`),
  with valid 4 KiB and 64 KiB page congruence.
- Ten research `.ko` signatures were independently verified cryptographically
  against this CI's public build certificate. This does NOT verify actual
  Samsung stock module loading or OEM trust at runtime.

## Guarded private Odin experiment

The existing local package script now has explicit `--mode kernelsu`, and
refuses packaging unless all of the following succeed: exact original
stock `boot.img` hash, independently pinned KSU `Image` hash, full export
CRC parity and exact symvers SHA, stock Kconfig baseline, exact audited KSU
config, pinned KSU provenance, recorded manual-hook source patches, linked
hook symbols and preinit ELF, embedded OEM public certificate, pinned AOSP
boot tools, and complete boot-image/AVB/TAR roundtrip validation.

The reconstructed Android boot v2 image keeps the original Samsung ramdisk,
DTB, command line and 528-byte `SEANDROIDENFORCE`/`SignerVer02` trailer.
Its AVB `boot` footer is internally consistent but **unsigned** (`NONE`);
the copied Samsung signer is not a valid OEM signature over the new kernel.
The bootloader is unlocked, but **KernelSU bootability is not established**.

Private experimental Odin TAR:
`RootS6Lite_SM-P613_CYE1_KSU_NEXT_LEGACY_EXPERIMENTAL.tar`
(100,669,440 bytes), SHA256:
`e3b1fe96470973ea99a603d657700d039a20fc8aa4b1a79cc876bbf276dd0626`.
Inner `boot.img` SHA256:
`d3a7a5dae7d4137e1bb54930a5ef5efb655e57cd6ca2a453d56cc3d2aa3cdce7`.

**Remain blocked:** physical KSU boot, KernelSU manager/root authorization,
SELinux and Samsung FIVE/PROCA runtime behavior with KSU, complete stock
module trust, and hardware stability. The device owner should complete
baseline hardware tests and retain full matching Odin stock recovery
firmware before any KSU physical experiment. A failed boot may require
Download Mode and a full stock reflash and may risk data loss.

Do not publish OEM boot images or private keys in the public repository.

## Physical-device incident — 2026-11-19

The device owner reported **`bootloop`** immediately after flashing the
experimental KernelSU Next package above. The previously installed CYE1
non-KSU baseline had successfully booted Android 14 on the same device.
This rules out a blanket assertion of physical bootability from green CI,
matching Module.symvers, ELF hook symbols, or successful packaging.

- **Known-failing inner boot.img** SHA256:
  `d3a7a5dae7d4137e1bb54930a5ef5efb655e57cd6ca2a453d56cc3d2aa3cdce7`.
- **Known-failing Odin TAR** SHA256:
  `e3b1fe96470973ea99a603d657700d039a20fc8aa4b1a79cc876bbf276dd0626`.
- Additional device video: unlocked-bootloader warning, **Samsung Galaxy / Secured by Knox** splash, no Android boot animation within the 66-second recording; Android Recovery UI is accessible. This establishes an **early boot hang/failure**, but the recording does not itself prove repeated automatic restarts.
- Kernel panic/pstore, exact restart cycle, and recovery after baseline reflash are **not yet reported**. Do not assert a proven root cause.
- Recommended immediate recovery: reflash the previously booted CYE1 baseline
  Odin AP package, or exact matching original Samsung CYE1 firmware, using
  Download Mode. Do not factory-reset as a substitute for restoring `boot`.
- The running kernel's `CONFIG_KPROBES=n` excludes a broken Kprobe explanation
  for this manual-hook build. Samsung `CONFIG_UH_RKP=y`, `CONFIG_RKP_KDP=y`,
  `CONFIG_FIVE=y`, and `CONFIG_PROCA=y` make KSU credential and SELinux
  interactions legitimate suspects, **not findings**.
- **Stop condition:** No repeat flash of this identical binary. Next test
  must be a separate, specifically instrumented/changed build with source
  diff, exact ABI parity verification and safe rollback. Seek post-crash
  `/sys/fs/pstore` or previous-boot diagnostics if accessible after recovery.

Record physical boot outcome as **FAILED**, while CI build/ABI audit stays
**PASSED**; these results measure different things.


## Verified rollback and magnetic-cover false alarm — 2026-11-19

**Recovery succeeded.** After the early-boot failure of the KSU-enabled
experiment, the owner restored the previously booted **non-KSU CYE1 baseline**
using Odin (PASS). ADB subsequently detected the device; direct on-device
readings showed sys.boot_completed=1, SurfaceFlinger running, the
boot-animation service stopped, and /proc/version again identifying
roots6lite-ci@github-actions, AOSP Clang 10.0.1 and exact CYE1 kernel
release. This is positive evidence of returning to a booted baseline, **not**
of successful KernelSU root.

The first post-restore boot animation was physically visible, followed by a
black screen and an all-black Android screenshot. The owner supplied a private
logcat. Around 19:36:51 the Samsung cover service reported
"updatePowerState : isOpen=false, type=0" and
"PowerManagerService: updateCoverState: closed: true". At 19:36:55 Android
explicitly requested goToSleep because of cover_close, then set the
primary display state to OFF. Later hardware power-key attempts logged
"!@Screen__On : Cancel (coverType: 0)". **The owner confirmed that the
magnetic protective case was responsible**, moved/removed it, and the display
returned with the Android user interface accessible. No display-stack or
baseline-kernel boot regression is established by this incident.

The uploaded full-device logcat and screenshot may contain personal data and
are **not** committed to this public repository. The source-built baseline has
been physically booted again; full Samsung module loading, power-management
stability and all peripheral functions are still not validated.

**The KSU early-boot failure remains unresolved.** It happened with a separate
known-failing inner boot.img SHA256
d3a7a5dae7d4137e1bb54930a5ef5efb655e57cd6ca2a453d56cc3d2aa3cdce7.
No KSU panic/pstore trace has been recovered, and this baseline logcat is
from a *different* (non-KSU) kernel boot, so it cannot identify the KSU crash.
Do not retry the same binary. Investigate pinned legacy/manual-hook early init,
Samsung RKP/KDP/FIVE/PROCA integration and optional preinit separately, using
explicitly isolated changes and independent CI review before another physical
test. Preserve the working baseline Odin recovery package.
