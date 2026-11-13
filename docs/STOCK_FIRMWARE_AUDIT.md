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

The report includes only filenames, sizes, SHA256 hashes, standard Android boot header fields, and compatible/model/board-id properties of contained DTBs/DTBO entries. It excludes raw boot contents, ramdisk, partitions, keys, and command lines. Keep the original firmware files local and review the report before sharing.

### Known-good reference hashes

- Stock `boot.img` SHA256: `06888F51722264EF33F2299E6CCAEFAB9E6E0C7A96D51C5C8A74CFEECD265655`
- Stock `recovery.img` SHA256: `0132764B3EAE2E6A88606E7D80A3AD77B4FFDE0DC8DACDB644DE425F5511760C`

If the report disagrees, stop and confirm which firmware file was inspected. A stock boot hash match is a provenance check, **not** a compatibility or bootability proof.

### Required comparison

1. Stock boot header format, embedded FDT selection if present, and kernel payload identification.
2. Stock DTBO table entries, board revision selectors and model/compatible properties compared with the compiled Wi-Fi EUR overlay.
3. Kernel module ABI, forced module signing, and symbol CRCs; this script does not yet inspect the entire vendor partition.
4. Resolve differing firmware source revisions, DT warnings, toolchain and CI reproducibility before any controlled baseline boot test.

The experimental CI DTBO overlay application test is **not** proof of stock boot-chain compatibility. No output from the research CI is approved for flashing.
