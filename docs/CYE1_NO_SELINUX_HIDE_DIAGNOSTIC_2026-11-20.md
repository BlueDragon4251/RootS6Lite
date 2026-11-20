# CYE1 optional SELinux-hide isolation — 2026-11-20

## Status and purpose

Compile and static verification passed. The original CI artifact remains
research-only and contains no Odin package. Following the owner's explicit
request to test, a separate, exact-artifact local Odin **boot-test package**
has been prepared as documented below. **The owner now reports a successful
Android boot with the no-hide candidate. Root and runtime module compatibility
remain unverified; the precise earlier bootloop cause is not established.** This branch
starts from `f2552a943066bb5dc5bf9b857cb77e776bc152f7`, which records both
owner-reported KSU boot failures and rejects both failed Image hashes. The
non-KSU baseline previously booted. After the latest KSU5 failure the owner
reported flashing back; the later no-hide Android-start confirmation is
recorded separately below and does not retroactively identify that rollback.

The current incident has no authenticated KSU crash trace. Stock Recovery ADB
was `unauthorized`. An unavailable log does not identify a panic, failed hook
or Samsung protection rejection. This is a controlled source comparison,
not an established diagnosis or fix.

## Exact change

KernelSU Next remains pinned to
`e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`. Its optional hide subsystem installs
file-operation hooks via a writable `vmap` alias and starts a background thread.
The feature toggle merely changes a boolean; disabling that toggle does not
prevent installation. The existing post-init trace marker does not prove the
asynchronous worker completed.

Only `kernel/feature/selinux_hide.c` is replaced in the transient upstream tree.
The original 15,691 bytes must have SHA256
`9dfb9d24ad6dc6032a2f6a8d9a672a9a2a988d3cfcb0bfea8867a59084928706`.
Four entry points remain: init emits a fixed diagnostic warning, and exit,
second-stage and post-fs-data do nothing. No hide feature handler, worker,
fake status page or file-operation patching remains in that implementation.
The unchanged feature dispatcher reports the absent handler as unsupported.

The two former internal helpers `ksu_selinux_hide_add_type` and
`ksu_selinux_hide_add_rule` have no external callers at this pin and are removed
with the implementation. `sepol_expected_argc` belongs to the SELinux policy
code, not this implementation, and remains unchanged.

## Invariants and gates

- Explicit workflow mode `kernelsu-no-selinux-hide`; normal `baseline` and
  `kernelsu` modes remain available. There is no duplicate build workflow.
- Preparation requires the exact commit, clean checkout and original source
  hash before the ordinary integration and logging-only trace patches run.
- No Kconfig, Kbuild, primary manual hook, preinit, policy or credential change
  is made by the no-hide preparer. Ordinary existing Samsung compatibility
  shims and the 42 trace markers still apply unchanged afterward.
- `KPROBES=n`, manual hooks, SELinux, MODVERSIONS, forced module signatures,
  RKP/KDP, FIVE and PROCA retain the existing KSU research configuration. Its
  complete final config hash must remain
  `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416`.
- Existing 12,530-export comparison, OEM certificate, linked main-hook call
  edges and embedded preinit ELF checks also run for this mode.
- A separate source/linked-code report verifies actual source and binary
  evidence. The embedded IKCONFIG must match the same complete config hash;
  vmlinux disassembly of the retained stubs must match raw Image bytes. Only
  empty returns or the exact init warning to `printk` are accepted. A manifest
  alone is not accepted as proof of omission.
- `ROOTS6_KSU_NO_SELINUX_HIDE` identifies this Image. Ordinary `baseline` and
  `kernelsu` packaging modes reject it even if ordinary KSU static checks pass.
  The later, owner-requested test profile below is separately opt-in and pinned
  to this exact Image, map and original reports; no generic bypass is added.

The trace patch's `POLICY_OR_HOOK_FLOW_CHANGED=false` describes that script's
logging-only insertion, **not the whole diagnostic profile**. This profile
intentionally changes optional hide behavior and records it separately.

## Results

GitHub confirmed [run 44692312623](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44692312623)
and job `136140778745` **completed/success** for source commit
`ded27cc8a2c2fa4bba09c0a115a0a2983c8be589`, completed on 20 November 2026 at
08:18:54 CET (07:18:54 UTC). Every workflow step ran successfully, including
the no-hide source preparation, actual compile, normal KSU checks, separate
linked no-hide verification and artifact upload. The PR self-test
[44692345505](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44692345505)
also completed successfully. Changes remain in [draft PR #3](https://github.com/BlueDragon4251/RootS6Lite/pull/3),
targeting the development branch rather than `main`.

**179/179 tests passed locally and in the compile workflow**, including 23
diagnostic gate tests and 27 packager tests. Independent read-only code review
found no blocker for research compilation. These tests are not device tests.

Artifact `14609577333`,
`SM-P613-CYE1-kernelsu-no-selinux-hide-AOSP10-RESEARCH-NOT-FLASHABLE`, was
downloaded after completion. The actual 27,906,665-byte ZIP matches GitHub's
published SHA256 and passes ZIP integrity checking. It contains no Odin TAR.

| Artifact identity | SHA256 |
| --- | --- |
| Downloaded ZIP | `0791193107d2684c8afaaa851d00525abd1066a590dcb484cc7902b085d9c444` |
| Actual raw Image (48,828,432 bytes) | `8765677928ad2011b1b714a17e347956f85d359130b5e73126286bbdfe9a876d` |
| Actual System.map | `a21563875c433e8b6d34a469eabf7591e77bbb0e50657c862014d1a4227ca940` |
| Actual Module.symvers, unchanged | `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e` |
| Final and embedded config, unchanged | `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416` |
| Replacement hide source | `72cf9fd7557a3fc87dae186df2c8171a4b8ed20243dae6b6e2f0e7a75c419959` |

### Actual binary evidence

- The source and linked reports both identify the diagnostic mode and remain
  `FLASH_ALLOWED=NO`, `ROOT_FUNCTIONALITY=UNVERIFIED`. Embedded IKCONFIG has
  182,608 bytes and the exact expected complete config hash.
- The retained init stub is 28 bytes. An independent decode of the downloaded
  Image, separate from CI's objdump check, confirms only a balanced frame,
  constant-address setup, one direct `BL` to actual `printk` and return. Its
  argument points to the exact diagnostic warning literal. Exit, second-stage
  and post-fs-data are each exactly one four-byte ARM64 `RET` instruction.
- The former optional hide worker, helpers and feature state are absent;
  `sepol_expected_argc` is still present. The five primary hook types and all
  ten expected linked calls pass the ordinary gates; all 42 trace markers
  remain. Manual-hook and trace-source manifests are byteidentical to the
  previous KSU5 build.
- Independent raw-Image decoding additionally confirms all ten main-hook
  call addresses, ARM64 opcodes and handler targets are unchanged from KSU5.
  The exact set of 42 null-terminated trace literals is unchanged. Separately
  decompressed IKCONFIG is byteidentical to the supplied final config, not
  merely accepted from a JSON report.
- Export comparison passes 46/46 authenticated delta references and
  12,530/12,530 reconstructed name/CRC/class entries, without missing or extra
  exports. Module.symvers is byteidentical to the failed KSU5 build and the
  previously booted baseline's recorded hash. This is **not** a directly
  captured OEM Module.symvers or a full runtime OEM-module ABI test.
  All 21 previously missing OEM exports are present within the confirmed
  46-entry delta set; no CRC adjustment or acceptance bypass was used.
- Embedded preinit remains 17,280 bytes, SHA256
  `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`.
  Both 4 KiB and 64 KiB ELF page-layout checks pass.
- All ten new research-module signatures were independently verified with
  OpenSSL CMS using only the new public CI certificate (`-nointern`). Every
  signature uses SHA512/RSA. Negative controls reject the previous CI signer
  and a modified payload. All module payloads remain byteidentical to the
  previous KSU5 build and corresponding new `_out` modules; only the CMS
  signature ranges changed.
- Every module retains exact CYE1 vermagic. The real built-in 2,681-byte trust
  list contains the unchanged 1,357-byte OEM certificate and the new 1,324-byte
  public CI certificate, each once. New CI certificate SHA256 is
  `a57e5e8399215533af11e69db4324cc0872dc96f4e1e235fa832c287476739d5`;
  OEM SHA256 remains `ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1`.
- At the research stage, the guarded packager was tested against the **actual
  new Image bytes** and rejected them as the nonflashable no-hide diagnostic,
  not just against a synthetic sentinel fixture. No TAR was created at that
  stage. Those ordinary-mode rejections remain in effect after addition of the
  owner-requested, exact-artifact test profile below.

### Limits and comparison controls

The intended source change is isolated, but this is **not a strictly
single-variable, bit-for-bit build-environment experiment**. GitHub's hosted
Ubuntu 22 runner changed from `20261111.360.2` to `20261116.365.1`; host packages
remain unpinned. The recorded compiler/linker pins are unchanged, but AOSP
Clang 10.0.1 is still not the original OEM Clang 10.0.7. Each clean build also
generates a new signing key/certificate, so Image and signed-module hashes
are expected to differ even outside the optional-hide code. No private key
is included in the artifact.

The standard libfdt DTBO merge smoke-test **still fails with
`FDT_ERR_BADOVERLAY` / exit 1**. The existing workflow records that separately
as blocked rather than failing compilation. DTB and DTBO bytes are unchanged
from the prior artifact; this does not resolve the overlay-application issue
or validate a replacement boot image. The full original 442,884-byte boot DTB
region is not reconstructed or packaged by this research run.

The independently compared DTB is 442,711 bytes, SHA256
`e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816`;
the device DTBO is 184,681 bytes, SHA256
`aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`.
The build log records 16 warnings and no compiler/linker fatal error; warnings
are not represented as a warning-free build.

Compilation, static isolation and the above comparisons passed. At the research
and packaging stages, physical boot, root authorization and actual Samsung
OEM-module loading were untested. The later owner report below confirms the
first Android start, not the remaining runtime checks. There is still no fresh
KSU failure log. The successful comparison supports the optional-hide
hypothesis but does not establish the exact fault or eliminate other build
differences. SELinux enforcement and Samsung safeguards must not be disabled
to force a result.

## Separate owner-requested Odin boot test

After reviewing the research result, the owner explicitly asked whether this
variant could be tested. The local packager now provides the distinct mode
`kernelsu-no-hide-test`, requiring all of the following:

- `--accept-experimental-no-hide-test` plus new, separate TAR/report paths.
- The exact Image and System.map hashes in the table above, and the unchanged
  original source/linked JSON reports from run `44692312623`.
- Source report SHA256
  `5937d3014e69cf11ba155cf27ada87e172a6cfd0c2cfe19ff7c53406314658fa`
  and linked report SHA256
  `fcd1490aa962ee579aff64c8e355ae67af303fbc9f0fa9f83d85e13141be14d4`.
- Actual embedded IKCONFIG agreement, all existing config/provenance gates,
  ten raw linked call edges, 42 trace markers, preinit ELF validation,
  12,530 reconstructed export matches, OEM certificate and stock boot checks.
- Clean, exact AOSP tool commits: mkbootimg
  `028bdc06ce87ab1ee23204feb5cd5ee406484618` and avbtool
  `386fb90492db3bd6bc484a579bcde5b43a2a0292`.

Both known physically failed Image hashes are rejected before any mode or
acceptance flag can be considered. Ordinary modes still reject this diagnostic
Image, including when the new acceptance flag is present. The research JSON
reports are not rewritten: `FLASH_ALLOWED=NO` and the original diagnostic
warning remain intact. They are compilation/isolation evidence, not runtime
release certificates. Only the separate local package report records scope
`OWNER_REQUESTED_EXPERIMENTAL_BOOT_TEST`, with readiness
`UNVERIFIED_EXPERIMENTAL_ONLY` and, at its creation time, physical boot/root/module
loading `NOT_TESTED`. These original reports are immutable build-time evidence;
later device results belong to the separate runtime record below.

**191/191 local tests pass, including 39 packager tests.** Independent read-only
review and a separate full-suite run found no blocker in the narrowed profile.
Negative tests cover missing/changed inputs, false acknowledgement, both failed
Images in every mode, and continued mandatory ordinary validation gates.
GitHub confirms the post-change self-test
[44697341083](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44697341083)
and job `136157146931` **completed/success** for packaging commit
`22f5242c297f80af7f5cba51cc0eed3d41c66c70`, including the guarded packager step.
This workflow runs the selected source/boot/package self-tests, not the entire
191-test local suite, and is not a new kernel compile.

The new TAR and JSON report were each generated twice from the original stock
boot and the already-compiled Image. Both complete TARs and both reports are
byte-identical. **No kernel source or kernel binary changed during packaging.**
The original stock boot is verified against SHA256
`06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655`.

| Local test-package identity | SHA256 |
| --- | --- |
| `RootS6Lite_SM-P613_CYE1_KSU_NOHIDE_BOOT_TEST.tar` (100,669,440 bytes) | `d449365f3f78c8014aaaeccfc0ed78bf25b4af1c8216018334845719a1aeb31c` |
| New inner `boot.img` (100,663,296 bytes) | `aa149f0386146ae7714909075f39161d15c689338be2daaa75340c652e47627a` |
| `RootS6Lite_NOHIDE_package_report.json` | `a1583d492e3b67fb2273c2f34b67c0acbadf580c2390a80b2777ab18c96b8a62` |
| Unchanged, previously booted `RootS6Lite_SM-P613_CYE1_BASELINE_ROLLBACK.tar` | `e98e22019d02e2a21e9f14db8be4466e7e5ab97c7924e49d40a64e380e2a98b3` |

The package contains only `boot.img`; Android boot header v2, 4096-byte pages,
stock commandline, original 725,007-byte ramdisk and **full 442,884-byte stock
DTB region** are retained. This includes the additional 173-byte FDT, not just
the shorter compiled base DTB. No DTBO partition is replaced, and the unresolved
libfdt overlay smoke-test is not represented as passing. Stock ramdisk SHA256
is `bcd59bb1748dbf0e1c341fd9c7c20c8790636aaded2d7397ae7b09aa8313bb45`;
full stock DTB SHA256 is
`60f36c9fca07fb819b34af5f60bc3b2628a74ffd873605a307a7139844d71dc1`.

The existing 528-byte Samsung signer trailer is preserved, **not re-signed**.
AVB is internally consistent but algorithm **NONE / unsigned**. Verification
of that hash footer is not OEM authentication or proof that a Samsung device
will accept or boot the Image. The rollback TAR matches the previously booted
baseline byte-for-byte; it is not a new rebuild.

An independent parser subsequently read the actual final TAR/boot bytes, not
just the package report. It confirms one regular USTAR entry, the exact Image
after gzip integrity checking, and the complete 4096-byte stock header page
except the necessary kernel-size and recalculated image-ID fields. The v2
SHA1 ID was independently recomputed as
`e9c3a75a845b146ad7e5ac938b300ecf5d3c5379`. Ramdisk, full DTB, original 528-byte
trailer, load addresses, commandline and recovery fields are byte-exact.
All payload and AVB padding is zero-filled as expected.

The independent AVB parse confirms a 20,058,640-byte hashed payload,
20,062,208-byte vbmeta offset, 512-byte vbmeta, one 200-byte `boot` hash
descriptor, zero-byte authentication block and a footer at 100,663,232.
Recalculated SHA256 of original salt plus payload is
`e1f33980d19ed3627a25982597ac34728e56533a587a8bf93bb315bf10d20789`,
matching the descriptor. The pinned `avbtool verify_image` independently exits
0. These are unsigned structure/integrity checks, not Samsung authentication.
The rollback was separately parsed and its embedded baseline Image rehashed
to `5609cb6faa2a6f07f4a0d0a2205f0d06fe696697cb6efc456d05a6b24d57d600`.

Owner test scope: SM-P613 / P613XXS8CYE1 only; Odin AP only, other fields empty,
no PIT/Re-Partition/Nand Erase, no added vbmeta image and no bootloader relock.
Keep a matching full stock firmware and working Download Mode available.
Remove the magnetic cover. First assess Android startup and ADB only; do not
enable SULOG, extra KSU features or modules during this isolation test. If it
loops again, preserve available evidence once and restore the known baseline
without treating a factory reset as the first remedy. Recovery `unauthorized`
is still not a working log-export path. OEM boot binaries and private keys are
not committed to the public repository.

## Device result — first no-hide Android boot, 2026-11-20

After receiving the exact no-hide boot-test package above, the owner reports:

> es hat gebootet und bin in android drinnen mit ksu nohide

Record **first physical Android boot PASS (owner-reported)** for this no-hide
test. The report associates the run with the handed-off candidate; no new
device-side image hash, console capture or full runtime log was supplied.
Do not describe this as an independently measured on-device binary identity.
The candidate remains Image SHA256
`8765677928ad2011b1b714a17e347956f85d359130b5e73126286bbdfe9a876d`,
boot SHA256 `aa149f0386146ae7714909075f39161d15c689338be2daaa75340c652e47627a`,
and TAR SHA256 `d449365f3f78c8014aaaeccfc0ed78bf25b4af1c8216018334845719a1aeb31c`.

| Runtime question | Current evidence |
| --- | --- |
| Android starts with the no-hide candidate | PASS, owner-reported first boot |
| KernelSU Next manager recognizes the kernel | CONFIRMED by later owner screenshot; basic recognition succeeds, UAPI 5/6 mismatch remains |
| An explicitly authorized app obtains UID 0 | NOT YET VERIFIED |
| Live SELinux enforcing state on this boot | Manager displays enforcing; not yet independently measured with getenforce |
| OEM-module loading and Wi-Fi/Bluetooth/audio/suspend behavior | NOT YET VALIDATED |
| Repeat-boot reliability and longer-term stability | NOT YET VALIDATED |

This is a meaningful runtime improvement over both earlier failed KSU
candidates. It strengthens the optional-hide isolation hypothesis, but the
hosted-runner and generated-certificate differences above prevent a strict
single-variable causal claim. A successful boot also does not prove every
manual hook, manager API, permission path or feature works correctly.

Freeze the successful candidate while collecting the next evidence. Do not
flash another variant, reintroduce hide, enable SULOG, change enforcement or
install modules for this first verification. The next low-impact step is to
open the KernelSU Next manager and record its main status, reported kernel
version and installed manager version. A manager status alone is not a UID 0
authorization test. Follow with a controlled, explicitly authorized root
check only after manager compatibility and recognition have been confirmed.

The two earlier failed Image hashes remain rejected, the PR stays draft and
the normal packaging gates remain unchanged. No kernel source, Image, TAR,
original CI manifest or historical package report is changed by recording
this user observation.

## Follow-up: manager recognition confirmed, UAPI mismatch identified

The owner supplied the complete manager screen after the successful no-hide
boot. It displays `Arbeitet`, `BUILT-IN (LEGACY)`, kernel
`v3.4.0-legacy (33327-6)`, `Manual`, manager `v3.4.2 (33355-5)`, and the exact
warning that manager API 5 is below kernel API 6. The Android kernel release
matches CYE1. This is positive evidence of basic manager/kernel recognition,
not an independent UID-0 authorization test or complete manager compatibility.

The screenshot displays SELinux `Erzwingung`, but the manager implementation
also returns that label when the enforce file cannot be read. Record the UI
observation without upgrading it to an independent `getenforce` measurement.
`Seccomp: Disabled` is read through `prctl(PR_GET_SECCOMP)` in the manager's
calling context, not a global kernel setting; the actual build still has
`CONFIG_SECCOMP=y` and `CONFIG_SECCOMP_FILTER=y`.

An official, signed UAPI-6 development APK was cryptographically validated,
but its versionCode **33554 is lower than the installed stable manager's
33355**. Consequently it is **not** an eligible ordinary in-place update.
The earlier in-place-update recommendation was corrected in
[the manager validation report](CYE1_MANAGER_UAPI6_VALIDATION_2026-11-20.md).
**Do not uninstall the current manager, attempt a forced downgrade or flash
another kernel to resolve this UI warning.** Preserve the first successful
no-hide boot and seek a newer officially signed UAPI-6 APK with a compatible
versionCode before any manager update. Root, OEM-module loading and stability
remain separate pending checks. Both failed KSU Images remain blocked.
