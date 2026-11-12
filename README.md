# RootS6Lite — Samsung SM-P613 KernelSU Next

Experimental research and reproducible GitHub Actions workflows for the **Samsung Galaxy Tab S6 Lite 2022 Wi-Fi (SM-P613)** on **P613XXS8CYE1**, Android 14.

> **NO FLASHABLE BUILDS HAVE BEEN VALIDATED. DO NOT FLASH WORKFLOW ARTIFACTS.** Prior attempt to patch the stock boot image with FolkPatch 115404 / KernelPatch 0.13.9 bootlooped. Flashing the original boot image restored Android. A successful GitHub build does **not** establish boot compatibility.

### Device reference

- Product: SM-P613 / gta4xlvewifixx (2022, Qualcomm)
- Samsung build: `P613XXS8CYE1`
- Running stock kernel: `4.14.190-perf-28683246-abP613XXS8CYE1`
- Architecture: arm64
- Stock boot partition: 100663296 bytes; Android boot header v2 observed during patch attempt
- Kernel configuration from device: `CONFIG_KALLSYMS=y`, `CONFIG_KALLSYMS_ALL=y`, `# CONFIG_KPROBES is not set`
- Original boot SHA256: `06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`
- Recovery verified unchanged: `0132764B3EAE2E6A88606E7D80A3AD77B4FFDE0DC8DACDB644DE425F5511760C`

### Critical source mismatch

The community kernel `gta4xlve-dev/android_kernel_samsung_gta4xlve` is **not** confirmed to match stock firmware:
- `lineage-24.0`: Linux **4.14.357-openela**
- `lineage-20.0`: Linux **4.14.320**
- target Samsung stock: Linux **4.14.190-perf**

Community builds are for **research only** and must not be repacked into an Odin image for stock One UI. A **stock-compatible source release, matching toolchain, defconfig, device tree, and successful baseline boot test** are prerequisites for a KernelSU Next boot image.

### Project gates

1. Identify the correct Samsung source package and compiler/defconfig.
2. Build a **non-rooted baseline** and check provenance, kernel version, and hashes.
3. Manually test baseline boot, hardware functionality, and rescue via Odin.
4. Integrate KernelSU Next Legacy, build, test and document.
5. Only after real-device verification, package a clearly versioned Odin image.

[Samsung update info](https://doc.samsungmobile.com/SM-P613/027830230922/eng.html) · [KernelSU Next non-GKI integration](https://kernelsu-next.github.io/webpage/pages/how-to-integrate-for-non-gki.html) · [Community kernel](https://github.com/gta4xlve-dev/android_kernel_samsung_gta4xlve)

The repository intentionally contains **no untested flashable boot image**.
