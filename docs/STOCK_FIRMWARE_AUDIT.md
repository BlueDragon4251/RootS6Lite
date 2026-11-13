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
