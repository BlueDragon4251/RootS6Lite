# SM-P613 official Samsung kernel source and CI status

**Research only; no output is approved for flashing.** Target tablet: Samsung Galaxy Tab S6 Lite 2022 Wi-Fi `SM-P613`, Android 14 `P613XXS8CYE1`. Its reported stock kernel is `4.14.190-perf-28683246-abP613XXS8CYE1`.

## Verified Samsung source

The Samsung Open Source Release Center package `SM-P613_EUR_14_Opensource.zip` is uploaded as the [source-P613XXU4CWL1 GitHub Release](https://github.com/BlueDragon4251/RootS6Lite/releases/tag/source-P613XXU4CWL1). CI downloads this asset, checks its SHA256 and extracts it into an ephemeral runner directory.

- ZIP size: **233,492,856 bytes**; SHA256 `728e592f5ad856773e093a01adebedb06a5ef2554c85813ae275a842eecb13b7`
- `Kernel.tar.gz`: SHA256 `4ef99eebc13604a8dc9d9037901f912fefe1f0ed0dff116e6baa176e4221a1b7`
- ZIP members: `Kernel.tar.gz`, `Platform.tar.gz`, `README_Kernel.txt`, `README_Platform.txt`
- Source kernel Makefile: `4.14.190`; defconfig: `gta4xlvewifi_eur_open_defconfig`
- `CONFIG_KALLSYMS=y`, `CONFIG_KALLSYMS_ALL=y`, `CONFIG_KPROBES=n`
- [Source/Kconfig audit Run 43292547560](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43292547560): **PASS**.

**Important mismatch:** the source revision `P613XXU4CWL1` is older than device firmware `P613XXS8CYE1`. A matching Linux `4.14.190` number is **not** proof of compatible vendor patches, DTB/dtbo, modules, KMI/ABI or boot image format.

## Toolchain status

Samsung's `build_kernel.sh` expects Qualcomm `llvm-arm-toolchain-ship/10.0/bin/clang` and Android `aarch64-linux-android-4.9` GCC. Neither is bundled in the official ZIP.

The current research workflow uses Ubuntu 22.04 packages `clang-14`, `lld-14`, `llvm-14`, `gcc-aarch64-linux-gnu`, `gcc-arm-linux-gnueabi`. **This is not the OEM toolchain. Its APT package versions are not pinned.** Build evidence captures the runner identity, Git commit, installed binary/package versions, generated `.config` SHA256, and exact compile flags in `_evidence/toolchain-manifest.txt`, `_evidence/config.sha256` and `_evidence/provenance.txt`.

Current `KCFLAGS` include experimental warning suppressions for Clang 14 (`-Wno-unused-but-set-variable`, `-Wno-align-mismatch`, `-Wno-void-pointer-to-int-cast`, `-Wno-pragma-pack`). These are **unresolved compatibility issues, not production fixes**. The original Samsung compiler must be reproduced or each warning's semantics reviewed.

## Experimental builds and failure diagnosis

Run the [Samsung baseline compile workflow](https://github.com/BlueDragon4251/RootS6Lite/actions/workflows/samsung-baseline-compile.yml) on `agent/kernel-foundation`. It is automatically triggered by changes to its workflow/script/parser.

- [Run 43297732140](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43297732140): stopped at two `-Wstrict-prototypes` compiler errors in `digital-cdc-rsc-mgr.c`; `-Wpragma-pack` in `kperfmon.c` was also rejected by Samsung's wrapper.
- [Run 43302556605](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43302556605): stopped at `cam_vfe_fe_ver1.c:399` because of a pointer-to-`uint32_t` cast, rejected as `error, forbidden warning`. The cascading `make Error 1/2` messages are not the root cause.
- [Run 43304295357](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43304295357): enhanced diagnostics/toolchain evidence, outcome to be inspected.
- [Run 43305303644](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43305303644): experimental CI-only camera-cast fix, outcome to be inspected.

To compile under Clang 14, the CI script **modifies the extracted source copy**, not the release archive:
1. Converts Samsung's Python 2 `gcc-wrapper.py` to Python 3.
2. Normalizes two old-style C function definitions in `digital-cdc-rsc-mgr.c`.
3. Replaces two pointer-to-integer casts in `cam_vfe_fe_ver1.c` with the first handle value (an independently documented upstream compiler fix).

The script asserts expected source patterns and records before/after SHA256 hashes in `_evidence/source-files-before.sha256` and `_evidence/source-files-after.sha256`. This is **not** an unmodified baseline binary. The parser `scripts/summarize_samsung_build.py` extracts the first reported compiler/wrapper/environment error, separates downstream `make` failures, and saves JSON/Markdown diagnostics, while keeping the complete `build.log`. Parallel logs may interleave errors; investigate context rather than blindly fixing the first text match.

Build artifacts are explicitly named `SM-P613-COMPILER-EXPERIMENT-NOT-FLASHABLE`. They contain `_evidence/`, the generated `.config` and raw `Image` only if successfully built. No `boot.img` or Odin archive is created.

## Required gates before a flashable build

1. Produce and checksum an experimental raw `Image` to establish compiler progress.
2. Locate and pin the matching original Qualcomm Clang 10 / Android GCC 4.9 toolchain; compile a truly unmodified official-source baseline.
3. Identify sources/patches matching `P613XXS8CYE1` and compare the device DTB/dtbo, stock boot payload, module version symbols and ABI.
4. Confirm a technically validated stock-compatible boot image and preserve the known-good original `boot.img` (SHA256 `06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`), Odin recovery instructions, and an authorized physical boot test.
5. Only after a successful baseline boot: integrate a pinned KernelSU Next Legacy revision appropriate for `CONFIG_KPROBES=n`; test root and SELinux enforcing, then ReZygisk/Vector/PurrfectSnap independently.

FolkPatch/KernelPatch previously caused a bootloop, including after a factory reset; restoring the original boot image through Odin recovered the tablet. **Never flash compiler-experiment artifacts.** Track progress in [Issue #2](https://github.com/BlueDragon4251/RootS6Lite/issues/2).
