# SM-P613 Samsung Device Tree / DTBO audit (research only)

Updated 2026-11-13. **No device-tree output in this project is approved for flashing.**

## Source and kernel configuration

Official Samsung OSRC ZIP: `SM-P613_EUR_14_Opensource.zip`, release `source-P613XXU4CWL1`, SHA256 `728e592f5ad856773e093a01adebedb06a5ef2554c85813ae275a842eecb13b7`.

The `gta4xlvewifi_eur_open_defconfig` generates `CONFIG_SEC_GTA4XLVEWIFI_EUR_OPEN=y`, `CONFIG_ARCH_ATOLL=y`, and `CONFIG_OF=y`.

Samsung's `arch/arm64/boot/dts/samsung/Makefile` maps:

- Device overlay: `atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo`
- Overlay source: `atoll-sec-gta4xlvewifi-eur-overlay-r00.dts`
- Base DTB: `../qcom/atoll-ab-idp.dtb` (`SEC_ATOLL_BASE_DTB`)

The Samsung overlay source declares `model = "Samsung GTA4XLVEWIFI EUR PROJECT BRINGUP (board-id,00)"`, `compatible = "qcom,atoll-ab-idp", "qcom,atoll-ab", "qcom,idp"`, `qcom,board-id = <34 0>`, and `dtbo-version = <0>`. These are **source facts, not confirmation of the device's installed boot-chain DTBO**.

## Findings from successful experimental compile

[GitHub Actions Run 43316540672](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43316540672) compiled:
- ARM64 `Image` (48,826,384 bytes; SHA256 `19ca8df5f1d2abfe3496f6d3219841a41d675c4d757c3837ef441e23b1187e57`)
- One base `atoll-ab-idp.dtb` (442,711 bytes)
- Ten ARM64 `.ko` modules (`vermagic=4.14.190-perf SMP preempt mod_unload modversions aarch64` observed in `rdbg.ko`)
- **Also compiled** the device-specific `atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo` according to the full CI `build.log` (`DTC` entry), but the artifact upload and manifests retained only `*.dtb`, not `*.dtbo`.

Therefore the generic-looking `atoll-ab-idp.dtb` is the expected base in this source recipe. **The missing item in the saved evidence is the corresponding Samsung DTBO**, not necessarily a wrong base DTB.

The compiler also emitted many device-tree and reverse-overlay warnings (e.g. reg-format, GPIO, clocks, cooling-device references). Some may be artifacts of unresolved overlay phandles during reverse rendering, but they have **not been individually verified or waived**. Keep full logs and investigate before claiming board compatibility.

## New CI evidence gates

The research CI now requires both the base `atoll-ab-idp.dtb` and the specific Samsung `atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo`, collects all `*.dtbo` outputs, and saves:

- `_evidence/dtbo-files.txt`
- `_evidence/dtbo.sha256`
- `_evidence/device-tree-metadata.txt`

The metadata gate reads the compiled FDT with `fdtget` and validates the expected Samsung model text, the overlay board-id `0x22 0x0` (decimal 34 and 0), and compatible `qcom,atoll-ab-idp` base and overlay identifiers.

[Run 43366096008](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43366096008) **passed** the new checks. Its downloaded artifact contains the 442,711-byte Qualcomm base DTB, 184,681-byte Samsung Wi-Fi EUR overlay, and ten modules. All 12 individual DTB/DTBO/module SHA256 checks passed when rechecked against the unpacked artifact. The overlay reports the expected model and board ID `<34 0>` (`0x22 0`). This still does **not** establish that the DTB/DTBO matches running firmware `P613XXS8CYE1`.

The same full build log contains **881 DTC warning lines**: `avoid_default_addr_size` (228), `unit_address_vs_reg` (175), `graph_port` (158), `reg_format` (114), and other groups. These are not suppressed or declared harmless; a separate actual base+overlay merge test is required to distinguish standalone-overlay parse warnings from problems in the resulting tree.

## Unfinished stock-compatibility checks

1. Inspect verified original firmware `P613XXS8CYE1` boot/dtbo payloads and their actual FDT properties, version/revision selectors and hashes.
2. Compare the base and overlay against the compiled CWL1 files and identify vendor changes since CWL1.
3. Review all device-tree warnings and test the overlay with its base where technically supported.
4. Compare kernel `vermagic`, exported symbols / modversion CRCs, module dependencies, and actual stock module inventory. Ten compiled `.ko` files do **not** imply the stock vendor partition contains exactly ten loadable modules.
5. Establish the exact Qualcomm-Clang-10/Android-GCC-4.9 build and a genuinely unmodified baseline. Current Clang 14 / Android GCC 4.9 **binutils** build uses CI-only source compatibility edits.
6. Only after technical validation, perform a controlled physical boot test with verified original `boot.img` recovery available.

No Odin package or flash-ready image should be generated from these research outputs.

## Standard libfdt merge diagnostic — 2026-11-13

[Full compile Run 43368653577](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43368653577) finished `make Image dtbs modules` with `BUILD_EXIT_CODE=0`, but the new **post-build** `fdtoverlay` smoke test rejected the compiled Samsung overlay with `FDT_ERR_BADOVERLAY`. This is not a compiler error and not a physical-boot result.

[Artifact-only audit Run 43372773879](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43372773879) and [instrumented libfdt 1.6.1 Run 43372601554](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43372601554) narrowed the failure to `overlay_update_local_references` in libfdt. [Run 43372773879](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43372773879) pinpointed the missing property lookup (libfdt `LOCAL_BADOVERLAY_LINE=250`, `tree_node=13856`, `fixup_node=158648`).

Read-only parsing of the saved binary FDT structure maps these offsets to:
- libfdt-selected tree node: `/fragment@6/__overlay__/qcom,dsi-display@0`, with `label`, `qcom,dsi-*` and `phandle`, but **no** `pinctrl-0`.
- local fixup node: `/__local_fixups__/fragment@6/__overlay__/qcom,dsi-display`, whose properties include `pinctrl-0`, `pinctrl-1` and `qcom,dsi-display-list`.
- The Samsung overlay contains **seven siblings**: `qcom,dsi-display@0` through `@5`, plus `qcom,dsi-display` without a unit address.

The standard libfdt child-name lookup for `qcom,dsi-display` can select the first `qcom,dsi-display@0` sibling when applying local fixups. This explains the observed `FDT_ERR_BADOVERLAY` without implying that the Android/Qualcomm bootloader uses identical overlay semantics. All 161 external overlay fixup label names resolved against the compiled base's `__symbols__`; no missing fragment targets were found. **Do not silently change Samsung's FDT source or claim stock compatibility.**

Next: compare the overlay using Android's `libufdt` implementation and with the original `P613XXS8CYE1` boot-chain DTBO. Treat standard `fdtoverlay` as a separate diagnostic; preserve its failure record and mark `FLASH_ALLOWED=NO`.