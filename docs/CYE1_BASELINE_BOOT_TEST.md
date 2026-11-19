# SM-P613 CYE1 first-boot baseline experiment (NO KernelSU)

This is a **user-authorized experimental physical boot test**, not a release,
stock-equivalent official image, or proof of safety. Only the device owner with
an unlocked bootloader and a proven Odin stock-firmware recovery path should
consider this test. A failed flash may do more than loop: it can fail the
bootloader's format checks, leave data inaccessible, or require a full reflash.

## Independent offline gates

The package generator (`scripts/package_cye1_baseline_odintar.py`):

1. Requires the exact original 100,663,296-byte P613XXS8CYE1 `boot.img`
   (SHA256 `06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655`).
2. Requires a SHA256-identified compiled 64-bit ARM `Image` with the exact
   stock `4.14.190-perf-28683246-abP613XXS8CYE1` release string and **no
   KernelSU**. It refuses the previous `4.14.190-perf` research output.
3. Requires authentic CYE1 IKCONFIG; the effective build config may differ
   from it **only** by adding the original kernel's publicly extracted module
   signing certificate to `CONFIG_SYSTEM_TRUSTED_KEYS`. The DER certificate
   (SHA256 `ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1`)
   must appear exactly once in the linked `Image`. This does not prove that
   stock OEM `.ko` files will load on the tablet.
4. Requires **12,530/12,530** compiled symbol names, CRCs and export classes
   to agree with the **reconstructed** stock reference, not a direct Samsung
   `Module.symvers` dump. The extra module import/signature/runtime checks
   remain unverified.
5. Requires pinned AOSP Android 14 `mkbootimg` and `avbtool` source commits;
   the no-change repack of the stock Android v2 payload must be byte-exact.
6. Uses the freshly compressed research kernel; retains the stock ramdisk,
   DTB, v2 boot parameters, command line and all 528 bytes of the Samsung
   `SEANDROIDENFORCE`/`SignerVer02` trailer. **The copied Samsung signature
   does not authenticate the new payload.**
7. Replaces the old RSA-signed AVB footer with a valid self-consistent **AVB
   `NONE` (unsigned)** boot hash footer for the same 100,663,296-byte partition.
   It verifies the image with pinned `avbtool verify_image`. This only makes
   sense on an **unlocked** device (`orange` state); bootloader acceptance and
   Samsung enforcement beyond AOSP remain untested.
8. Packs a single `boot.img` entry into an uncompressed Odin TAR and verifies
   full archive roundtrip. No proprietary stock image is committed or uploaded
   into the public GitHub repository.

The research kernel still uses AOSP Clang 10.0.1 rather than Samsung's
original Clang 10.0.7. The DTBO overlay apply issue and true stock module
dependencies remain open. Even all green offline gates cannot prove a boot.

## Device owner's controlled test (only after a reviewed TAR exists)

- Verify the tablet is **SM-P613 / P613XXS8CYE1**, unlocked (orange), and has
  sufficient charge. Back up important data; flashing/recovery may erase it.
- Keep the **matching complete stock firmware** and Odin on the PC, with a
  working USB cable and Download Mode. Do not rely on fastboot (unavailable).
- Confirm the provided TAR SHA256 independently. In Odin, use **AP only** for
  this boot-only TAR. Never enable `Re-Partition`, provide a PIT, or add an
  unrelated `BL`/`CP`/`CSC` during the experiment.
- Start the flash only if prepared to return to Download Mode and restore the
  exact official firmware. Give first boot several minutes, but note any
  repeated Samsung logo or error text. Photograph bootloader errors. Do not
  factory-reset reflexively; it does not repair an invalid boot kernel.
- If it fails to start, return to Download Mode, use the authentic P613XXS8CYE1
  Odin firmware package, and restore the stock partitions. A stock reflash
  can alter or wipe userdata depending on selected CSC and state.
- If it boots, check `uname -r`, `getprop ro.boot.verifiedbootstate`, SELinux,
  Wi-Fi, Bluetooth, audio, cameras, charging, standby, and any `dmesg`/logcat
  module-signature errors accessible without root. Do **not** test KernelSU
  yet. Record the first boot outcome before adding another variable.

This guide documents the test protocol. It is **not** an instruction to flash
an unverified CI artifact. The final TAR and hashes must be supplied only
after the post-change GitHub Actions build and archive checks are complete.

## Observed package preparation, 2026-11-19

- CYE1 research compile [GitHub Actions 44507834398](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834398)
  finished **successfully**, with all compilation and ABI-comparison steps
  green. Artifact 14524431159 ZIP SHA256:
  `d0c2c08e4335000f4788607bfc42d6d3050084e42d96d167f9933358ceb5070b`.
- Rebuilt `Image` SHA256:
  `5609cb6faa2a6f07f4a0d0a2205f0d06fe696697cb6efc456d05a6b24d57d600`
  (48,828,432 bytes). Stock-reconstructed `Module.symvers` full export
  comparison **12,530/12,530 exact**, symvers SHA256:
  `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`.
- The pristine CI config matches authentic stock IKCONFIG byte-for-byte
  (SHA256 `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208`).
  The compiled effective config differs in exactly **one string option**:
  `CONFIG_SYSTEM_TRUSTED_KEYS` points to the stock public signing cert;
  verified effective-config SHA256:
  `a0370e63486576da637d933966c32e4a271e471cc0b1fa6fc7bb1604c2488a96`.
- The package script completed every integrity check, including the embedded
  public X.509 certificate, gzip decompression roundtrip, exact stock
  ramdisk/DTB bytes, header metadata, Samsung 528-byte signer block, 100 MB
  partition footprint, unsigned AVB hash verification, and USTAR readback.
- Actual new `boot.img` SHA256:
  `640da30f79fea0deb45bdcdb7e75841a285eb4af55dea149f0f6e8be070e2061`.
  Generated TAR `RootS6Lite_SM-P613_CYE1_BASELINE_EXPERIMENTAL.tar`,
  **100,669,440 bytes**, SHA256:
  `e98e22019d02e2a21e9f14db8be4466e7e5ab97c7924e49d40a64e380e2a98b3`.
- The TAR and machine-readable package report were handed to the device owner
  privately, **not uploaded to GitHub**. The original `boot.img` and OEM
  private signing key are absent from the repository.

**Still unverified:** bootloader acceptance of the unsigned AVB footer and
stale OEM signer bytes; physical boot, OEM module loading, Wi-Fi and other
devices, Samsung compiler binary equivalence, and rooted KernelSU behavior.
The pending next result is the owner's first-boot outcome. A successful
package *generation* is not a successful device boot.

## First physical boot observation — 2026-11-19

The device owner reported flashing the privately provided experimental baseline
Odin TAR to the **SM-P613 P613XXS8CYE1** and returning successfully to the
Android system. This is the first **observed physical boot** of our isolated
CYE1 source-built baseline.

The owner supplied direct ADB evidence:

```text
Linux version 4.14.190-perf-28683246-abP613XXS8CYE1 (roots6lite-ci@github-actions) (Android (6051079 based on r370808) clang version 10.0.1 (https://android.googlesource.com/toolchain/llvm-project b9738d6d99f614c8bf7a3e7c769659b313b88244), GNU ld (binutils-2.27-bd24d23f) 2.27.0.20170315) #1 SMP PREEMPT Thu Jan 1 00:00:00 UTC 1970
```

The unique `roots6lite-ci@github-actions` build identity and Clang 10.0.1
identify our rebuilt kernel, not Samsung's original OEM binary. Therefore
the bootloader accepted the experimental boot-image packaging sufficiently to
start the modified kernel and reach Android userland. This **overrides the
earlier unverified physical-boot/bootloader gate for this one device test only**.

**Not yet tested or confirmed:** SELinux and verified-boot readings after
flash, Samsung stock module loading and signatures, Wi-Fi/Bluetooth/audio/
camera/charging, stability, suspend/resume, and any KernelSU Next/root
behavior. No KernelSU was included in the baseline TAR. The owner was asked
to run the remaining ADB commands as one quoted `adb shell` invocation
because multiple pasted Windows CMD lines did not execute as intended.
