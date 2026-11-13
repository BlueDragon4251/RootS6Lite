# KernelSU Next integration — SM-P613 stock One UI

## Status: blocked pending matching Samsung kernel source

**Do not flash artifacts from this repository.** The stock firmware is `P613XXS8CYE1`, and its kernel reports `4.14.190-perf-28683246-abP613XXS8CYE1`. The community gta4xlve kernel is related hardware, not a verified exact Samsung source match.

The original stock `boot.img` SHA256 was measured as:
`06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`.

## Build gates

1. Obtain Samsung-published kernel sources appropriate for this firmware, preferably via Samsung Open Source Release Center.
2. Record package URL, version, checksum, license, toolchain and build instructions. Do **not** assume newer Lineage sources are ABI-compatible with stock.
3. Produce an unmodified stock baseline kernel; compare modules, DTB/dtbo, flags and kernel version to the original firmware. **Compilation does not imply bootability.**
4. Test the baseline kernel on the device and document successful Android boot, Wi-Fi, touch, S Pen, cameras, charging and SELinux enforcing. Keep recovery/Odin instructions available.
5. Integrate KernelSU Next Legacy from an **immutable tagged or commit-pinned upstream revision**. Current device config has KALLSYMS enabled but KPROBES disabled; manual hooks are likely needed.
6. Review hook changes against this exact 4.14 vendor tree, build, check config (`CONFIG_KSU=y`), test without modules, validate root only after actual device boot.
7. Test ReZygisk + Vector 2.2 and the target application separately; no claim of being ban-free or Play Integrity compatible.

## References
- https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html
- https://github.com/KernelSU-Next/KernelSU-Next
- https://github.com/gta4xlve-dev/android_kernel_samsung_gta4xlve
- https://doc.samsungmobile.com/SM-P613/027830230922/eng.html

## Evidence from previous attempt

- FolkPatch 115404 + kpimg 0.13.9 repacked a 96 MiB Samsung boot image successfully but it caused a bootloop.
- Factory reset did not help.
- Flashing the original stock `boot.img` with Odin restored Android.
- This history makes a verified stock baseline mandatory before any KernelSU modifications.
