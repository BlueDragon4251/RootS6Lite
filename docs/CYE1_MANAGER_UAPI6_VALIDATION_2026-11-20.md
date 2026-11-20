# CYE1 no-hide: official UAPI-6 manager validation — 2026-11-20

## Device evidence and scope

The owner confirms Android starts with the previously handed-off no-hide
kernel. The subsequent screenshot shows `Arbeitet`, `BUILT-IN (LEGACY)`,
kernel `v3.4.0-legacy (33327-6)`, hook mode `Manual`, and installed manager
`v3.4.2 (33355-5)`. Its warning identifies **kernel UAPI 6 versus manager UAPI 5**.
These numbers describe the kernel/manager interface, not a request for an app
named version 6. Basic recognition succeeds; full manager compatibility and
an explicit UID-0 authorization test remain outstanding.

The successful kernel, all Odin TARs, original build reports and kernel trust
rules are unchanged. No new kernel compile or device installation was performed
while preparing this manager handoff. This is a verified official development
APK candidate, **not a new stable upstream release or a confirmed device root
result**.

## Exact official candidate

- APK: `KernelSU_Next_v3.4.2-199-gaa235b99_33554-release.apk`.
- Actual size: **17,885,467 bytes**.
- APK SHA256: `1807088573c9e6e2c42b253f750a5eab88c7e2d20c2aba9b6fbae6c7a8eb2e95`.
- Official [Build Manager CI run 43999580687](https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/43999580687):
  `completed/success`, push to `dev` at
  `aa235b99574b5b349cdb4980bcb98fd58e6abb28`.
- Exact normal [manager artifact 14324476358](https://github.com/KernelSU-Next/KernelSU-Next/actions/runs/43999580687/artifacts/14324476358),
  not `manager-spoofed`. GitHub records it as unexpired at verification time.
- Downloaded ZIP: 16,653,148 bytes; its actual SHA256 matches GitHub's published
  digest `b19587fc004a8718dcc0bb887dd372734478990c561dbe63ed66cf242eb794b1`.
- The [pinned workflow](https://github.com/KernelSU-Next/KernelSU-Next/blob/aa235b99574b5b349cdb4980bcb98fd58e6abb28/.github/workflows/build-manager-ci.yml)
  uses the official signing secrets and uploads normal managers from dev/tags,
  not ordinary pull-request builds. Actual cryptographic verification below
  is required in addition to this workflow description.

Commit attribution comes from official CI/run/artifact metadata and the
officially signed APK. This was **not independently reproduced from source**.
The APK-internal VCS metadata says `NO_SUPPORTED_VCS_FOUND`, so it is not used
as a second source-commit attestation. No content was patched or re-signed.

## Actual APK checks

The main agent repeated the independent read-only APK audit against the actual
handoff bytes. Google `apksig` 8.13.1 validated them specifically for Android
14 / API 34. ZIP integrity also passes.

| Property | Verified result |
| --- | --- |
| Package ID | `com.rifsxd.ksunext` |
| Manifest versionName | `v3.4.2-199-gaa235b99` |
| Manifest versionCode | `33554` |
| Minimum / target SDK | 26 / 36 |
| Android-14 cryptographic verification | PASS, no errors or warnings |
| APK signature scheme | Valid V2; V3 and V3.1 absent |
| Signing-block entries | Only V2 `0x7109871a` and padding `0x42726577` |
| Signer certificate | One 998-byte DER certificate |
| Signer certificate SHA256 | `79e590113c4c4c0c222978e413a5faa801666957b1212a328e46c00c69821bf7` |
| Actual ARM64 native manager UAPI | **6** |

The signing certificate matches the unmodified legacy kernel's exact expected
size `0x3e6` and hash, as recorded twice in the actual no-hide build log and in
the [pinned Kbuild](https://github.com/KernelSU-Next/KernelSU-Next/blob/e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a/kernel/Kbuild).
Its signing-block layout is compatible with the pinned
[APK verifier](https://github.com/KernelSU-Next/KernelSU-Next/blob/e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a/kernel/manager/apk_sign.c).
No debug-manager allowance, custom certificate, package spoof or kernel trust
override is required.

The official [v3.4.2 release APK](https://github.com/KernelSU-Next/KernelSU-Next/releases/download/v3.4.2/KernelSU_Next_v3.4.2_33355-release.apk)
was separately downloaded and cryptographically verified. Its APK SHA256 is
`774a5511f7034a4930e881114e202319cbdc34c5aaaa5c7c6b6d2902364e4c58`.
Both packages have the same package ID and **byte-identical signer certificate**,
but the versionCode goes **down from 33355 (installed stable) to 33554
(candidate)**. This is a **one-step downgrade**, not an update. Ordinary Android
package installation is expected to reject an in-place downgrade, even with the
same signing certificate. Therefore **do not hand off or attempt the 33554 APK
as a normal in-place update**. No installation failure has been observed on the
device; this blocker follows from the independently audited manifest versions.
Do not uninstall the existing manager, bypass downgrade safeguards, or use
`adb install -d` to force this candidate. A normal update requires an official,
correctly signed UAPI-6 manager with an acceptable versionCode (preferably
higher than 33355), whose manifest, signature, UAPI and side effects are
validated independently before installation.

The ARM64 JNI symbol `Java_com_rifsxd_ksunext_Natives_getManagerUAPIVersion`
is eight bytes at virtual address/file offset `0x14ec` in the real
`lib/arm64-v8a/libkernelsu.so`. Its instructions are
`528000c0 d65f03c0` (`MOV W0,#6; RET`). The relevant ELF LOAD mapping was checked;
the value is not inferred solely from the filename or source header.

## Interface comparison

The exact [manager dev UAPI](https://github.com/KernelSU-Next/KernelSU-Next/tree/aa235b99574b5b349cdb4980bcb98fd58e6abb28/uapi)
was compared with the [legacy kernel UAPI](https://github.com/KernelSU-Next/KernelSU-Next/tree/e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a/uapi).
`app_profile.h`, `feature.h`, `ksu.h` and `sulog.h` are byteidentical.
`supercall.h` and `selinux.h` differ only by equivalent `static const` versus
`#define` declarations needed for the older kernel compiler. GET_INFO,
GET/SET_APP_PROFILE, feature structures, IOCTL numbers and flags agree.

UAPI 6 includes actual additions: `KSU_IOCTL_LOOKUP_SYMBOLS`,
`KSU_GET_INFO_FLAG_PREINIT` and awareness of possible preinit/modules.rc paths
under `/metadata/vold/ksu`. Simply changing the API number in the old manager
would hide real implementation differences; this handoff does not do that.

## Opening the updated manager has userspace side effects

This is **not a purely read-only status check**. At the exact candidate commit:

1. [MainActivity](https://github.com/KernelSU-Next/KernelSU-Next/blob/aa235b99574b5b349cdb4980bcb98fd58e6abb28/manager/app/src/main/java/com/rifsxd/ksunext/ui/MainActivity.kt)
   calls `install()` when the app is recognized as manager.
2. [KsuCli](https://github.com/KernelSU-Next/KernelSU-Next/blob/aa235b99574b5b349cdb4980bcb98fd58e6abb28/manager/app/src/main/java/com/rifsxd/ksunext/ui/util/KsuCli.kt)
   invokes bundled `ksud install --libadbroot ...`.
3. [utils::install](https://github.com/KernelSU-Next/KernelSU-Next/blob/aa235b99574b5b349cdb4980bcb98fd58e6abb28/userspace/ksud/src/utils.rs)
   can replace `/data/adb/ksud`, set its SELinux label, install ordinary helper
   programs and symlinks under `/data/adb/ksu/bin/`, and copy
   `/data/adb/ksu/lib/libadbroot.so`.
4. [Asset extraction](https://github.com/KernelSU-Next/KernelSU-Next/blob/aa235b99574b5b349cdb4980bcb98fd58e6abb28/userspace/ksud/src/assets.rs)
   explicitly skips `ksuinit`, `waitsys` and `*.ko`.

That automatic install call chain does not flash boot/DTBO/vbmeta, invoke
boot-patching, synchronize preinit under `/metadata/vold`, or enable
SULOG/hide/ADB-root features. Copying libadbroot is not enabling ADB-root.
Existing user feature settings and later boot-time behavior cannot be certified
without device evidence. Do not enable any additional feature or module during
this recognition test, and do not select a kernel install/patch/uninstall menu.

## Screenshot interpretation and next device check

The existing manager's `Arbeitet` proves recognition/version-query success,
not a separately observed UID-0 grant. Full-featured manager operation requires
recognition, equal UAPI versions and successful root availability.

The screenshot's SELinux `Erzwingung` is only a manager-reported status: its
[SELinux checker](https://github.com/KernelSU-Next/KernelSU-Next/blob/4c706b5938665866ebe16944a481a7b91e3396af/manager/app/src/main/java/com/rifsxd/ksunext/ui/util/SELinuxChecker.kt)
also chooses enforcing when the file is unreadable. The displayed
`Seccomp: Disabled` comes from `prctl(PR_GET_SECCOMP)` in the manager's own
calling context; it is not evidence that global kernel seccomp is disabled.
The actual config retains `CONFIG_SECCOMP=y` and `CONFIG_SECCOMP_FILTER=y`.
No protection should be disabled to remove either display.

User handoff: **do not install the audited 33554 UAPI-6 candidate over the
installed 33355 manager**; its lower versionCode blocks the ordinary update.
Keep the booting no-hide kernel and installed manager unchanged. No Odin flash,
manager uninstall, forced APK downgrade, extra modules or feature toggles.
Once an official UAPI-6 APK with a compatible versionCode and the expected
signer is independently validated, test its in-place update and check for a
new manager UAPI-6 status without changing the kernel. A controlled, explicitly
authorized UID-0 test follows separately. Root and updated-manager operation
remain **NOT TESTED**.
