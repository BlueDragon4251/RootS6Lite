# SM-P613 original-firmware audit (offline, read-only)

The target tablet runs Android 14, firmware `P613XXS8CYE1`, kernel `4.14.190-perf-28683246-abP613XXS8CYE1`. The publicly uploaded Samsung source is **older** (`P613XXU4CWL1`). Matching the kernel major/minor version does not establish compatibility.

## Collect actual stock metadata on Windows — no local compilation

Requires Python 3 only. This script reads local files and writes a JSON report; it never flashes or modifies images, downloads anything, or uploads binaries.

From a checkout of `BlueDragon4251/RootS6Lite`, on PowerShell:

```powershell
py -3 .\scripts\audit_stock_firmware.py `
  --boot "$env:USERPROFILE\Downloads\flashen\boot.img" `
  --recovery "$env:USERPROFILE\Downloads\flashen\recovery.img" `
  --output "$env:USERPROFILE\Downloads\RootS6Lite-stock-audit.json"
```

If an original, decompressed `dtbo.img` belonging to firmware **P613XXS8CYE1** is available, use this variant instead:

```powershell
py -3 .\scripts\audit_stock_firmware.py `
  --boot "$env:USERPROFILE\Downloads\flashen\boot.img" `
  --recovery "$env:USERPROFILE\Downloads\flashen\recovery.img" `
  --dtbo "$env:USERPROFILE\Downloads\flashen\dtbo.img" `
  --output "$env:USERPROFILE\Downloads\RootS6Lite-stock-audit.json"
```

Do not add `--dtbo` when the file is missing. A Samsung `.lz4` image must be decompressed to `.img` first; the tool detects LZ4 frame headers but does not decompress or modify the file.

The schema-2 report includes filenames, sizes, whole-file SHA256 hashes, **per-embedded-FDT SHA256** hashes (for exact binary comparison against the CI DTB and DTBO), standard Android boot header fields, and compatible/model/board-id properties of contained DTBs/DTBO entries. It excludes raw boot contents, ramdisk, partitions, keys, and command lines. Keep the original firmware files local and review the report before sharing.

### Known-good reference hashes

- Stock `boot.img` SHA256: `06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`
- Stock `recovery.img` SHA256: `0132764B3EAE2E6A88606E7D80A3AD77B4FFDE0DC8DACDB644DE425F5511760C`

If the report disagrees, stop and confirm which firmware file was inspected. A stock boot hash match is a provenance check, **not** a compatibility or bootability proof.

### Required comparison

1. Stock boot header format, embedded FDT selection if present, and kernel payload identification.
2. Stock DTBO table entries, board revision selectors and model/compatible properties compared with the compiled Wi-Fi EUR overlay.
3. Kernel module ABI, forced module signing, and symbol CRCs; this script does not yet inspect the entire vendor partition. One CI-built module reports `vermagic=4.14.190-perf SMP preempt mod_unload modversions aarch64`, while the tablet reports `4.14.190-perf-28683246-abP613XXS8CYE1`. This version-suffix difference blocks any assumption that the CI `.ko` files will load against installed stock modules; merely changing `LOCALVERSION` cannot establish ABI compatibility.
4. Resolve differing firmware source revisions, DT warnings, toolchain and CI reproducibility before any controlled baseline boot test.

The experimental CI DTBO overlay application test is **not** proof of stock boot-chain compatibility. No output from the research CI is approved for flashing.

### Initial report received — target firmware stock images (2026-11-13)

The user ran schema-1 stock audit on the unmodified local `boot.img` and `recovery.img` (no separate `dtbo.img` was provided). The report's **whole-file SHA256 values match both known original reference hashes exactly**, and both images are 100,663,296 bytes.

| Reported item | Observed metadata | Research comparison |
| --- | --- | --- |
| Stock `boot.img` | Android boot header version 2, 4,096-byte page, kernel payload 19,080,331 bytes, ramdisk 725,007 bytes | Not yet compared to compiled kernel payload |
| Stock `boot.img` embedded DTB | Offset 19,816,448, 442,711 bytes, `qcom,atoll-ab-idp`, `qcom,board-id=<0x22 0>` | Same size and board identifiers as CI Qualcomm base DTB |
| Stock `recovery.img` embedded Samsung DTBO | Offset 30,273,600, 184,681 bytes, `Samsung GTA4XLVEWIFI EUR PROJECT BRINGUP (board-id,00)`, `dtbo-version=<0>`, `qcom,board-id=<0x22 0>` | Same size, model and board identifiers as CI Samsung EUR overlay DTBO |
| Stock `recovery.img` embedded base DTB | Offset 30,461,952, 442,711 bytes, `qcom,atoll-ab-idp` | Same size and identifiers as CI base DTB |

The original scanner also finds additional 173-byte FDT-formatted records in boot/recovery, without model or compatible strings. Their meaning and boot-chain role are **unclassified**. Do not assume they represent the board's actual DTBO or discard them as noise without validating source bytes.

**Critical distinction:** Matching lengths and hardware IDs are encouraging but **do not prove the binaries match**. The improved schema-2 `audit_stock_firmware.py` (commit `68229ff`) now adds SHA256 of every detected FDT's exact `fdt_total_bytes` span. Re-run the same read-only command using the latest script and compare the reported per-FDT hashes to these CI reference values:

- Qualcomm base DTB: `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816`
- Samsung Wi-Fi EUR overlay DTBO: `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`

If both match, the compiled source-pair device-tree bytes match the respective *embedded* reference FDTs from the submitted stock boot/recovery images; this still does **not** prove installed DTBO partition contents, complete vendor-module ABI equivalence, toolchain parity, or bootability. No flashable output is approved.

### Schema-2 report — exact stock embedded-FDT binary match confirmed

The user supplied a second offline, read-only schema-2 report. It confirms the original whole-file boot/recovery SHA256 references and records these **exact per-FDT hashes**, independently reproduced against downloaded [full CI Run 43373071951](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43373071951) compiled artifacts:

| Source image / offset | FDT size | Reported stock FDT SHA256 | CI reference result |
| --- | ---: | --- | --- |
| `boot.img` / `19816448` | 442,711 | `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816` | **EXACT** base `atoll-ab-idp.dtb` |
| `recovery.img` / `30273600` | 184,681 | `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12` | **EXACT** Samsung `atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo` |
| `recovery.img` / `30461952` | 442,711 | `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816` | **EXACT** base `atoll-ab-idp.dtb` |
| `boot.img` / `20259159` and `recovery.img` / `30904663` | 173 each | `f0358d4d97e41ab9be741c3c974518abca4023b684fd47b6ba7a660d422ab06a` | Identical extra FDT-formatted record in both stock images; **unclassified**, no corresponding CI research artifact |

**Confirmed narrow result:** The two compiled CWL1 device-tree binaries are byte-for-byte the same as the respective FDT blobs embedded in the user's verified original CYE1 boot/recovery images. The earlier OSRC version gap **does not cause drift in these two specific FDT artifacts**. The user-provided report itself is metadata only; no original boot/recovery binaries were uploaded to this project. [Commit 51d5eb7](https://github.com/BlueDragon4251/RootS6Lite/commit/51d5eb7a948f5ffdf636f2eddb1aeae20b7f618c) adds a fast, explicit hash-gated GitHub Actions compatibility check.

The boot-image v2 page geometry is self-consistent: `4096`-byte header + padded kernel payload `19083264` + padded ramdisk `729088` = base DTB offset `19816448`. In recovery, the Samsung FDT begins 64 bytes after the page-aligned end of the reported kernel and ramdisk; this is **consistent with** a 32-byte Android DTBO table header plus one 32-byte entry, but without the actual 64 header bytes it is an inference rather than a verified parsed table.

**Not established:** installed partition contents/selection, compressed stock kernel code parity, Qualcomm original compiler equivalence, Module.symvers and vendor module ABI, module signing enforcement, kernel patch hooks, bootability, KernelSU Next or anything related to Snapchat/Play Integrity. A previously observed research module `vermagic` mismatch remains. `FLASH_ALLOWED=NO`.

### Next read-only gate: boot kernel payload, boot header v2 and embedded IKCONFIG

[Commit 3d85dbe](https://github.com/BlueDragon4251/RootS6Lite/commit/3d85dbea4c381a5819c5b8a3516232d8232e46c6) expands the same offline script to `audit_schema=3`. It reads the **compressed kernel payload** of stock boot/recovery without exporting its bytes, reports payload SHA256, compression signature, and (for gzip) safely bounded decompressed kernel size/hash and ARM64 Image magic. It parses the Android v1/v2 `recovery_dtbo_size`/`recovery_dtbo_offset`/`header_size` and v2 `dtb_size`/`dtb_addr`, computing page-aligned kernel, ramdisk, DTBO and DTB regions. If the recovery image includes a valid Android DTBO table at the v2 header's offset, it reports the table entries/hashes. The tool **never uploads raw partitions, exposes kernel command-line text, exports ramdisk bytes or writes to the device**.

[Commit 2105838](https://github.com/BlueDragon4251/RootS6Lite/commit/2105838f34761fedb39c2452c2f73f4ba4bf3166) additionally parses the kernel's `IKCFG_ST` ... `IKCFG_ED` embedded gzipped Kconfig in a bounded manner (when available). It records only the decompressed config SHA256 and a small allowlisted set of ABI/root-significant flags, e.g. `CONFIG_KPROBES`, `CONFIG_MODVERSIONS`, `CONFIG_MODULE_SIG_FORCE` and `CONFIG_LOCALVERSION`; unrelated config contents are not exported. [13 synthetic tests](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43383214166) passed with [test commit 7855193](https://github.com/BlueDragon4251/RootS6Lite/commit/7855193463166b7efea4ad1873b7e5ad0cd435bb).

Run on Windows PowerShell (same already-verified original files, **no local kernel compilation**):

```powershell
$dir = "$env:USERPROFILE\Downloads\flashen"
Invoke-WebRequest "https://raw.githubusercontent.com/BlueDragon4251/RootS6Lite/agent/kernel-foundation/scripts/audit_stock_firmware.py" -OutFile "$dir\audit_stock_firmware.py"
py -3 "$dir\audit_stock_firmware.py" --boot "$dir\boot.img" --recovery "$dir\recovery.img" --output "$dir\RootS6Lite-stock-kernel-audit-v3.json"
```

Before sharing, the user can review the schema-3 JSON; it contains hashes, generic boot-structure fields, compatible/model/board metadata and selected kernel flags, but not the kernel or ramdisk contents. If the stock payload is gzip, compare its `decompressed_sha256` against the research `Image` SHA256 `12e7a4f340958f269f4760d41c20e2b6311029b92f77f0f63b40c16abc1fbf48` (full Run 43373071951). The research kernel's embedded IKCONFIG plain-text SHA256 is `f13d3cba992e72cf276ffc26b4b2f983ba35d5414f61888cfbdfecdce97e76cf` and corresponds exactly to its generated `.config` artifact. Differences in stock-vs-research kernel binary and/or config are **not necessarily defects** but require investigation and ABI qualification. These checks cannot establish module symbol CRC compatibility or replace an on-device baseline boot test; no research output is flash-approved.

### Actual schema-3 stock kernel results — received 2026-11-13

The uploaded, metadata-only schema-3 report verifies the same original `boot.img` and `recovery.img` whole-file SHA256 values and finds **identical kernel payloads in both images**. The Android v2 header, compressed payload and recovery DTBO table are now substantially characterized:

| Property | Original target stock P613XXS8CYE1 | CI research CWL1/Clang14 baseline |
| --- | --- | --- |
| Android boot header | v2, header size 1,660, page 4,096 | Boot image not yet packaged |
| Boot/recovery kernel payload | gzip, 19,080,331 bytes, SHA256 `1946b2eb0aa710cad781b28a1fddd9464092ecbab45185d31fda1faa2f4d04ef` | Raw uncompressed `Image` produced by CI; gzip packaging not yet stock-equivalent |
| Decompressed ARM64 Image | **48,832,528 bytes**, SHA256 `14defad3fe7854da3cadc43b2c01e96a48a27a4a0e847043c989c45c66fb8228` | **48,826,384 bytes**, SHA256 `12e7a4f340958f269f4760d41c20e2b6311029b92f77f0f63b40c16abc1fbf48` |
| Embedded Linux release | `4.14.190-perf-28683246-abP613XXS8CYE1` | `4.14.190-perf` reported from research modules; no proof of stock release suffix equivalence |
| Embedded decompressed IKCONFIG | **182,359 bytes**, SHA256 `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208` | **181,998 bytes**, SHA256 `f13d3cba992e72cf276ffc26b4b2f983ba35d5414f61888cfbdfecdce97e76cf` |
| Selected 14 root/ABI Kconfig fields | `KPROBES=n`, `MODVERSIONS=y`, `MODULE_SIG_FORCE=y`, `KALLSYMS_ALL=y`, `LOCALVERSION=\"-perf\"` etc. | All **14 selected fields match** stock; full config differs |
| Header DTB region | 442,884 bytes = 442,711-byte Qualcomm base DTB + 173-byte extra FDT-formatted record; SHA256 `60f36c9fca07fb819b34af5f60bc3b2628a74ffd873605a307a7139844d71dc1` | Base DTB alone byte-identical; extra 173-byte record not yet reproduced/identified |
| Recovery DTBO | Valid Android DTBO table, offset `30273536`, **184,745 bytes** = 64-byte header+entry + 184,681-byte Samsung overlay; table v0, one entry ID 0/rev 0, page 4,096 | Samsung DTBO blob **byte-identical**; no standalone CI table/boot package yet |

**Interpretation:** The target firmware's base DTB and Samsung overlay are a perfect binary match to the source-built corresponding FDTs. The **actual kernel and complete Kconfig are not identical**: the stock decompressed kernel is 6,144 bytes larger and has a different SHA256, while the full stock config differs by 361 bytes in reported length. This is not evidence of a specific breaking ABI difference by itself. The selected root/ABI-relevant switches agree, but the complete configuration differences, exported symbol CRCs, kernel build string provenance, vendor modules and signing certificates remain unexamined. The runtime `4.14.190-perf-28683246-abP613XXS8CYE1` release differs from the research module `vermagic`; never just replace a release suffix and claim compatibility.

**Signing gate:** Both stock and research configs indicate `CONFIG_MODULE_SIG_FORCE=y` and `CONFIG_MODULE_SIG_ALL=y`; the earlier CI research `make modules` outputs lacked a signature trailer in the sampled `.ko`. Do not attempt to insert those unsigned modules. A future research flow must validate module signing and trusted public cert with the exact rebuilt kernel (while keeping private keys private); it must not reuse stock signing assumptions.

**Still blocked:** OEM-equivalent toolchain and genuine stock baseline, kernel/module ABI and signing, exact boot packaging with original ramdisk/DTBO header, safe recovery, and controlled on-device stock-baseline test. No CI experiment is approved for flashing; KernelSU Next Legacy integration and apps follow only after the baseline gates.


### Full stock configuration comparison (original CYE1 embedded IKCONFIG, received 2026-11-13)

The user supplied the complete text kernel configuration extracted from the original, whole-file-hash-verified P613XXS8CYE1 stock boot image. The extracted SHA256 is **exactly** the previously audited embedded IKCONFIG SHA256, 1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208. A complete unified diff against the successful CWL1 research build's generated config (SHA256 f13d3cba992e72cf276ffc26b4b2f983ba35d5414f61888cfbdfecdce97e76cf) reveals the following:

- **Stock FIVE enabled:** CONFIG_FIVE=y, plus its Kconfig-selected SHA-1 hash and trusted keyring settings, with default user certificate x509_five_user.der. Research had FIVE disabled.
- **Stock PROCA enabled:** CONFIG_PROCA=y, CONFIG_PROCA_S_OS=y. Research omitted them. Samsung OSRC contains the corresponding Kconfig/implementation and security/samsung/five/x509_five_user.der certificate file.
- **Stock TZIC disabled by dependency:** the research default CONFIG_TZIC=y, CONFIG_TZIC_USE_QSEECOM=y conflicts with PROCA_S_OS=y; Samsung's drivers/security/samsung/tzic/Kconfig declares TZIC depends on !PROCA_S_OS. The stock IKCONFIG omits both.
- Stock also contains a disabled CONFIG_DISABLE_LOCKSCREEN_USB_RESTRICTION line absent from research; this is **not** evidence that the restriction is enabled, but the existence of the setting deserves source-version follow-up.

All other lines of the two complete configs matched in the initial text diff, not merely the earlier 14 allowlisted flags. The stock vs research Image bytes still differ, and a matching Kconfig alone would **not** prove ABI or boot equivalence.

The research compile workflow now explicitly reconciles the CYE1 security configuration: start from official CWL1 Samsung defconfig, preserve its unmodified config in CI evidence, enable FIVE, PROCA and PROCA_S_OS via the Linux kernel scripts/config, run make olddefconfig to resolve Kconfig dependencies, and assert final settings including TZIC disabled. This is a **research build adjustment**; no vendor security safeguards are deliberately removed. New full CI must prove whether the older source successfully compiles with these stock-selected options.

Do not publish the complete original user-extracted config without user review; this documentation records only the named differing flags and verified hashes. No flash permission.


### CYE1 security-profile CI result — run 43386729110 successful

[Full research build 43386729110](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43386729110), commit [1d3b578](https://github.com/BlueDragon4251/RootS6Lite/commit/1d3b578838542a3e0d40ed2fa5f85622cd01478e), **passed**. The actual job logs record CYE1 security profile FIVE=y, PROCA=y, PROCA_S_OS=y, TZIC=n, build exit 0, modules_install exit 0 and 10 signed modules.

The emitted reconciled research config is **182,304 bytes; SHA256 3345e9d95ccc30da221c345f3f25fb974e42d890c2f630bb52fe8be2ef9716df**. A full byte-level diff against the user's original CYE1 IKCONFIG (182,359 bytes) now shows **exactly one line missing**: the explicitly disabled comment "# CONFIG_DISABLE_LOCKSCREEN_USB_RESTRICTION is not set", which is absent from older CWL1 Kconfig. Removing only that comment from the authenticated CYE1 config yields **exactly the same SHA256** as the CI-generated reconciled config. No other Kconfig line differs. This is a narrow, strong **configuration** parity result, not kernel binary/ABI/boot parity.

The new raw research Image remains **48,826,384 bytes** (SHA256 b22e62487910c79d059312ccd9c04c639c3b33df5e7b7952061ab5efaf5acaf3), whereas the original firmware's raw Image was 48,832,528 bytes (SHA256 14defad3fe7854da3cadc43b2c01e96a48a27a4a0e847043c989c45c66fb8228). The reference toolchain and Samsung source code revision still differ. The compilation still logs an unversioned-export warning for gsi_write_channel_scratch, requiring symbol/ABI investigation. Samsung's checked-in Kconfig also emits CR-character and unsupported-choice-default warnings during olddefconfig, to be tracked separately.

[Run 43385818357](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43385818357) separately proved that make modules_install signs all 10 research modules with an ephemeral CI certificate; private key was not uploaded. Archive inspection exposed a duplicate unsigned copy under a modules/build symlink included by the broad upload glob; narrow the artifact glob to kernel subdirectory to keep signed and unsigned module classes separate. This is an artifact-presentation issue, not a signing-stage failure.

**Remaining blocks:** stock/CI ABI and exported-symbol CRC matching, root of module signing trust on target firmware, exact Samsung/Qualcomm compiler, original firmware boot packaging and controlled physical baseline boot. No flash permit.


### Independent cryptographic module-signature verification

The research package from successful run 43386729110 was downloaded and all **ten** installed modules in the */kernel/* staging directory were checked independently using OpenSSL CMS detached PKCS#7 signature verification against the **public X.509 certificate generated in that same build**. Result: 10/10 mathematically valid signatures. This is strictly an experimental-build integrity check, **not** Samsung stock firmware's signing trust or loading/boot compatibility.

The repository's scripts/verify_signed_module_artifact.py independently parses Linux's appended 12-byte module-signature header, extracts the detached PKCS#7 and unsigned module payload, and verifies each using OpenSSL. Run it manually on a downloaded CI artifact ZIP. The dedicated four synthetic framing unit tests cover valid, missing, invalid key type and out-of-bounds signatures. The full cryptographic integration was tested against the real 43386729110 artifact.


### Symbol/version manifest gate — full run 43389560135 successful

[GitHub Actions Run 43389560135](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43389560135), from commit [947bd93](https://github.com/BlueDragon4251/RootS6Lite/commit/947bd932f4d4f3ec6107841aa059808f015b42c0), completed **SUCCESS**. Actual logs: CYE1 config-parity SHA256 gate PASSED, Image+DTB+DTBO+10 modules built, modules_install PASSED and 10 signed modules. Its ZIP artifact (ID 14021961604) was downloaded and inspected. It contains **Module.symvers (692,583 bytes)**, **System.map (6,249,307 bytes)** and **exactly ten signed .ko files under the /kernel/ subtree**. No duplicate raw modules through the build symlink and no signing private key were exported. All ten module signatures independently passed OpenSSL detached PKCS#7 verification against the build's exported public X.509 cert.

The actual research Module.symvers has **12,559 exported symbols**. **Exactly one** has CRC 0x00000000: the exported Qualcomm **gsi_write_channel_scratch**; the related gsi_write_channel_scratch2_reg and scratch3_reg have nonzero CRCs (0xfe7c1eb0 and 0x1909c11c, respectively). The build logs also report that gsi_write_channel_scratch version generation failed. The Samsung source declares it with a packed-union value parameter. This is now a specifically evidenced symbol-version blocker, **not** a harmless warning; no ABI parity should be claimed until the target stock symbol behavior and any consumers are investigated. Do not rewrite the public kernel function signature merely to silence genksyms before confirming stock compatibility.

The CI Image and modules have still **never booted on the actual SM-P613**. Runtime Samsung vendor modules, original firmware public signing trust and source/toolchain binary equivalence remain unknown. A compiled, fully-configured and signed kernel is still **NOT FLASH APPROVED**.
