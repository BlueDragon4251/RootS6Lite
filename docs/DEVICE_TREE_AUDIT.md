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

Android `libufdt` source-pair result is documented below; the original `P613XXS8CYE1` boot-chain DTBO comparison is still outstanding. Keep standard `fdtoverlay` as a separate failed diagnostic and `FLASH_ALLOWED=NO`.
### Android libufdt validation — completed on compiled source pair

[Artifact-only CI Run 43373499084](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43373499084) **PASSED** with the exact saved CWL1 base DTB and Samsung Wi-Fi EUR DTBO. The workflow fetches official AOSP `ufdt_apply_overlay` from `kernel/prebuilts/build-tools` and verifies Git blob SHA-1 `2a243bd8eac5c95145b1885e9b009afdf8d5ac2e` before executing it. Outcome:

- Standard `fdtoverlay`: exit 1 / known `FDT_ERR_BADOVERLAY` on ambiguous Samsung DSI child names; retained in logs as diagnostic.
- Android `libufdt`: **exit 0**; merged, non-flashable FDT SHA256 `157aa936a2a27191e62145046259d7a8e828640e2881e15f225e2d82e80cbec6`.
- Merged root compatible: `qcom,atoll-ab-idp qcom,atoll-ab qcom,idp`.
- Artifact explicitly records `STOCK_DTBO_ABI=UNVERIFIED` and `FLASH_ALLOWED=NO`.

This verifies that an Android overlay implementation can merge the **compiled CWL1 source pair**. It is not verification of the bootloader's actual implementation, DTBO partition selection, kernel ABI or the target `P613XXS8CYE1` firmware. Those remain required before any boot test.

### Fresh complete full-build verification — Run 43373071951

[Full stock-source compiler experiment Run 43373071951](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43373071951) completed **successfully** (job `131713143005`, all steps green). The actual build log contains `BUILD_EXIT_CODE=0`, `DTB_COUNT=1`, `DTBO_COUNT=1`, and `MODULE_COUNT=10`. Downloaded artifact `14013642553` contains an ARM64 `Image` (SHA256 `12e7a4f340958f269f4760d41c20e2b6311029b92f77f0f63b40c16abc1fbf48`), the Samsung overlay and Qualcomm base, and ten modules. All **12** DTB/DTBO/module checks passed using the artifact's own saved `sha256sum -c` manifests.

The latest base `atoll-ab-idp.dtb` SHA256 is `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816`; Samsung `atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo` SHA256 is `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`. These are byte-identical to the DTB+DTBO input pair checked by the AOSP-libufdt CI. Applying AOSP `ufdt_apply_overlay` again to the latest artifact yielded the same non-flashable merged FDT SHA256 `157aa936a2a27191e62145046259d7a8e828640e2881e15f225e2d82e80cbec6`. This **does not establish stock firmware compatibility or bootability**.

The full artifact **continues to record** `DTBO_STANDARD_LIBFDT_SMOKE_TEST=FAILED_EXIT_1`, `ANDROID_LIBUFDT_CHECK=PENDING` (the Android verification is a separate successful workflow), `STOCK_DTBO_MATCH=UNVERIFIED`, `FLASH_ALLOWED=NO` and `MODULE_SIGNATURE_TRAILER=ABSENT_IN_FIRST_MODULE`. The latter concerns an unsigned research `.ko` output, not stock module-signature policy verification. The artifact includes the public, auto-generated X.509 certificate fingerprint and DER; **no private signing key** was uploaded.

**Unresolved repeatability:** The latest Image hash differs from earlier full builds even though the generated config, the base DTB, Samsung DTBO and ten module hashes match. The auto-generated public X.509 certificate was found embedded at offset 40,251,136 in two research Images, and its contents differ per run. Do not attribute all Image binary drift to that certificate without further binary-level analysis. This and the missing exact OEM Qualcomm Clang-10 toolchain remain research issues; do not release a flashable image.
