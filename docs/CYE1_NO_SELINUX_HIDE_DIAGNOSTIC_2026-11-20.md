# CYE1 optional SELinux-hide isolation — 2026-11-20

## Status and purpose

Compile and static verification passed; research only: **no Odin package; no
physical boot or root claim**. This branch
starts from `f2552a943066bb5dc5bf9b857cb77e776bc152f7`, which records both
owner-reported KSU boot failures and rejects both failed Image hashes. The
non-KSU baseline previously booted. The owner has now flashed back again;
Android startup after this specific rollback is not yet confirmed.

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
- `ROOTS6_KSU_NO_SELINUX_HIDE` identifies this Image. The guarded packager
  explicitly rejects it even if all ordinary KSU static checks pass.

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
- The guarded packager was tested against the **actual new Image bytes** and
  rejected them as the nonflashable no-hide diagnostic, not just against a
  synthetic sentinel fixture. No output TAR was created.

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

Compilation, static isolation and the above comparisons passed. **Physical
boot, root authorization and actual Samsung OEM-module loading remain
untested for this variant.** There is still no fresh KSU failure log. No
evidence yet establishes optional SELinux-hide as the bootloop cause; the
successful no-hide compile does not establish a fix. SELinux enforcement and
Samsung safeguards must not be disabled to force a result.
