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
