# Experimental CYE1 + KernelSU Next boot image — 2026-11-19

**For SM-P613 P613XXS8CYE1 only. This is NOT a boot-tested or root-tested
KernelSU image.** No actual KernelSU privileges, stock module import, or
manager interoperability have yet been confirmed on-device.

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
