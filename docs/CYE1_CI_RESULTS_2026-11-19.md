# SM-P613 P613XXS8CYE1 — 2026-11-19 compiled research evidence

> **FLASH_ALLOWED=NO.** This report records observed CI artifacts and a
> reproducible, *derived* OEM export-reference comparison. It does not authorize
> an Odin package or physical testing. All references are to nonflashable
> GitHub Actions research artifacts retained for a limited time.

## Completed controls

| Run | Source/compiler/mode | Outcome | Built-in `Module.symvers` SHA256 |
| --- | --- | --- | --- |
| [44498063613](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44498063613) | Older CWL1, AOSP Clang 10, no KSU | Success | `a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94` |
| [44498062917](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44498062917) | Older CWL1, Clang 14, no KSU | Success | `a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94` |
| [44498063031](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44498063031) | Older CWL1, pinned KSU Next Legacy | Success | `a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94` |
| [44498063616](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44498063616) | **Samsung 2025 P619 base + P613 CYE1 overlay**, AOSP Clang 10, no KSU | **Success** | `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e` |

All four statuses and artifacts were independently read from GitHub, and the
artifacts were downloaded and inspected. The successful CWL1 builds do **not**
substitute for the new CYE1 source. Clang 10 and Clang 14 happening to produce
the same CWL1 export table does not establish OEM toolchain equivalence.

## Full CYE1 export comparison

The CYE1 artifact's existing 46-delta checker reports **46/46** named
Samsung OEM delta exports present with exact CRC and export-class parity.
Its total vmlinux export count is **12,530**, equal to the authenticated stock
Image count. The independent `compare_full_cye1_export_abi.py` was then run
against the artifact's actual `_out/Module.symvers` and the pinned
[`CYE1_RECONSTRUCTED_STOCK_EXPORTS.tsv`](CYE1_RECONSTRUCTED_STOCK_EXPORTS.tsv):

| Derived stock export check | Result |
| --- | ---: |
| Exact name + CRC + class matches | **12,530 / 12,530** |
| Missing stock exports | **0** |
| Extra compiled exports | **0** |
| CRC mismatches | **0** |
| Export-class mismatches | **0** |

The 21 previously missing OEM exports and 25 previously changed CRCs are
therefore resolved by the **new Samsung sources**, without CRC editing or
disabling `CONFIG_MODVERSIONS`. The table is a derived reference: it preserves
the unchanged CWL1 CRCs and applies the 46 authentic CYE1 deltas recovered
from the original stock Image. Its SHA256 and reconstruction procedure are
recorded in [the export report](CYE1_STOCK_EXPORT_ABI.md). It is **not** a
direct full stock `Module.symvers` capture. One reference symbol,
`gsi_write_channel_scratch`, has a zero CRC, a remaining provenance/ABI
investigation item rather than proof of a meaningful nonzero CRC.

## Kernel, DTB, modules, signing

- The CYE1 Image compiled to **48,828,432 bytes** with SHA256
  `70f4c13d64e8d3f4eea1ce9f5fafa1ceb0a48a3869a2161d34370fab994ef753`.
  The authenticated stock Image is **48,832,528 bytes**, SHA256
  `14defad3fe7854da3cadc43b2c01e96a48a27a4a0e847043c989c45c66fb8228`.
  These images are **not identical** (size difference: 4,096 bytes); this
  alone does not identify the cause.
- The compiled Qualcomm base DTB and SM-P613 Wi-Fi EUR DTBO match the
  authenticated original hashes exactly.
- Ten research `.ko` files were installed/signature-appended with a newly
  generated **CI-only certificate**. All ten PKCS#7 signatures were separately
  verified cryptographically with `verify_signed_module_artifact.py`.
  Samsung's original firmware trust in this certificate is **unverified**.
- The standard libfdt overlay application still fails (exit 1). The earlier
  Samsung DSI local-fixup ambiguity is documented separately; this remains a
  compatibility gap, not permission to rewrite official DTS files blindly.
- The compiler is pinned AOSP Clang **10.0.1**, *not* the OEM Qualcomm/Android
  NDK Clang **10.0.7**. The generated CYE1 `.config` hash has not yet been
  authenticated against the original full IKCONFIG. The generated modules use
  `4.14.190-perf` vermagic rather than OEM's full
  `4.14.190-perf-28683246-abP613XXS8CYE1` release string.

## KernelSU distinction

The older CWL1 KernelSU control [run 44498063031](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44498063031)
is green. Its **actual linked** `System.map` contains all four manual-hook
functions and the early preinit symbols. Its embedded **17,280-byte static
AArch64 ELF** satisfies both 4 KiB and 64 KiB PT_LOAD congruence tests. But
that older control still lacks 21 CYE1 exports and differs on 25 CRCs.

The separate **CYE1 + KernelSU Next** research run is
[44502580820](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44502580820),
on commit `b132aa2`. It uses the official 2025 source profile and the pinned
KernelSU Next `legacy` revision `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`.
Its results must be evaluated independently, not inferred from either the
plain CYE1 baseline or the older CWL1-KSU control.

## Remaining release blockers

1. Confirm the complete new **CYE1 + KernelSU** compile, all 12,530 reconstructed
   export CRCs, linked hook symbols, preinit ELF, and module signatures.
2. Investigate the full Samsung IKCONFIG, OEM toolchain mismatch, kernel
   build string/vermagic, original module trust, and DTBO overlay loading.
3. Compare boot-image parameters and preserve original ramdisk/DTB/DTBO and
   verified Odin restore files **without building a flash target yet**.
4. Only after stronger validation, consider a supervised *non-rooted*
   baseline physical boot test with explicit rollback; KernelSU on-device
   testing must follow a successful baseline test.

**No experimental artifact is approved for flashing.**
