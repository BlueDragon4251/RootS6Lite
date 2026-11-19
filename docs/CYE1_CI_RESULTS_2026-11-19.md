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

## Completed follow-up: CYE1 + KernelSU Next (2026-11-19 10:28 UTC)

The specifically opted-in [run 44502580820](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44502580820) on commit `b132aa2d7a3888f078c3d41c17e19c95ae567f7e` **completed successfully**. The actual job log and artifact [14518778090](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44502580820/artifacts/14518778090) were retrieved and inspected; the artifact ZIP SHA256 is `76a7b87c9fedde9ac49aad78283435def441b29ae992b7eb946277caba0ca579`. This is **nonflashable research evidence only**; success does not imply stock boot compatibility.

| Verified in completed CYE1 KSU artifact | Outcome |
| --- | --- |
| Kernel compile / source | Success; official Samsung 2025 P619 base + P613 CYE1 supplement, pinned KSU Next Legacy `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a` |
| CYE1 exported names, CRCs, classes | **12,530/12,530** against the *derived/reconstructed* reference, 0 missing, 0 extra, 0 CRC mismatches, 0 class mismatches |
| Compiled `Module.symvers` | SHA256 `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`; **byte-for-byte identical** to non-rooted CYE1 baseline artifact of run [44500750038](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44500750038) |
| Linked KSU symbols | `System.map` has text (`T`) definitions for `ksu_handle_execveat`, `ksu_handle_faccessat`, `ksu_handle_stat`, `ksu_handle_sys_read`, `ksu_preinit_init`, plus start/end symbols |
| Embedded preinit runner | **17,280-byte AArch64 static ELF** at Image offset 40,258,144; checked directly in artifact Image: ELF magic, SHA256 `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`, and reported 4-KiB/64-KiB PT_LOAD congruence |
| KSU config | `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `CONFIG_KPROBES=n`; `CONFIG_MODVERSIONS=y` and `CONFIG_MODULE_SIG_FORCE=y` remain enabled |
| Generated pre-KSU CYE1 stock-profile config | SHA256 `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208`; **identical** in baseline/KSU artifacts, but complete OEM IKCONFIG provenance was not verified by this CI run |
| Compiled base DTB / SM-P613 EUR DTBO | SHA256 `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816` / `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`; each matches its previously authenticated stock binary |
| Research modules | **10/10** `.ko` signatures present and detached PKCS#7/CMS signatures independently verified against artifact's CI-generated public X.509 certificate using OpenSSL (`-noverify` certificate chain mode). **This does not establish OEM trust.** |
| Image / module release | KSU Image: 48,828,432 bytes, SHA256 `82c39aa5706cc4efc6ee0abc9676d49627dc570fc01901de01b7c7edd1794a6d`; modules report `4.14.190-perf SMP preempt mod_unload modversions aarch64` rather than original `4.14.190-perf-28683246-abP613XXS8CYE1` |
| Samsung DTBO standard libfdt smoke-test | **Fails** with `FDT_ERR_BADOVERLAY` (existing known compatibility blocker); Android libufdt path not yet validated |
| Device boot / stock-module compatibility | **UNTESTED / UNVERIFIED**; `FLASH_ALLOWED=NO` |

The isolated [CYE1 baseline artifact 14518108591](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44500750038/artifacts/14518108591) was also downloaded and examined (ZIP SHA256 `8905e95868dd22eadf5d73ab8c2badfc43373034e5c6666fa9a6a5056119efac`); its compile and full reconstructed export comparison were green. Older [CWL1 KSU control 44500750051](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44500750051) is green but remains **unsuitable as CYE1 ABI evidence** (21 missing exports and 25 different CRCs).

The unchanged source discrepancy is significant: AOSP Clang **10.0.1** is pinned rather than Samsung OEM Clang **10.0.7**, the stock Image differs by **4,096 bytes**, and vendor module certificate compatibility has not been established. The warning for `gsi_write_channel_scratch` (unversioned zero CRC) remains present in both builds. None of these issues was hidden, waived, or patched out.

## Remaining release blockers

1. **Completed:** CYE1 + KernelSU compile, 12,530 reconstructed export CRCs, linked hook symbols, embedded preinit ELF, and CI-module PKCS#7 signature verification. Preserve these gates for subsequent builds.
2. Investigate the full Samsung IKCONFIG, OEM toolchain mismatch, kernel
   build string/vermagic, original module trust, and DTBO overlay loading.
3. Compare boot-image parameters and preserve original ramdisk/DTB/DTBO and
   verified Odin restore files **without building a flash target yet**.
4. Only after stronger validation, consider a supervised *non-rooted*
   baseline physical boot test with explicit rollback; KernelSU on-device
   testing must follow a successful baseline test.

**No experimental artifact is approved for flashing.**

## Later follow-up — current branch baseline, stock trust, controls (2026-11-19)

The branch advanced through `a7532d4` (CYE1 stock release string and
imported stock **public** module certificate), `9fa3d85` (guarded *local*
non-KSU experimental boot packager and offline tests), and `28cbda0`
(documented experimental package hashes). The audits below inspected the
**actual downloaded ZIP archives**, not merely green workflow badges. This
section supersedes the earlier open points on *generated IKCONFIG* and
*baseline module vermagic*, but not the open device/module-trust issues.

| Verification | Observed result |
| --- | --- |
| [New CYE1 baseline run 44507834398](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834398), [artifact 14524431159](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834398/artifacts/14524431159) | **Success**; downloaded ZIP SHA256 `d0c2c08e4335000f4788607bfc42d6d3050084e42d96d167f9933358ceb5070b`. This is the new non-KSU CYE1 source experiment, not an OEM-binary reproduction. |
| New CYE1 exported-symbol ABI | Actual artifact `Module.symvers` SHA256 `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`; 12,530 **unique vmlinux** exports. Artifact's fully reconstructed reference comparison: **12,530/12,530** exact name/CRC/class, zero missing, extra, CRC or class mismatches. This remains a **derived** stock reference, not a direct complete OEM `Module.symvers` capture. |
| Stock `IKCONFIG` and effective build configuration | The `stock-generated.config` SHA256 is `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208`, now pinned as the authentic CYE1 IKCONFIG. Independently diffed artifact configs: exactly **one string setting** changes, from `CONFIG_SYSTEM_TRUSTED_KEYS=""` to `"certs/roots6lite-p613-cye1-oem-public.pem"`. Effective config SHA256 `a0370e63486576da637d933966c32e4a271e471cc0b1fa6fc7bb1604c2488a96`. |
| Original public module certificate | Inspected the compiled Image bytes: OEM-public X.509 DER SHA256 `ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1` is **embedded once**. A certificate's presence does **not** verify that the original firmware's vendor `.ko` files are signed by that key, that the device trusts it, or that all module imports resolve. |
| Kernel and module release | CI reports `4.14.190-perf-28683246-abP613XXS8CYE1`. Independently inspected all 10 signed research module ELF payloads: their `vermagic` contains this exact stock-release prefix. This fixes the previous *release-string mismatch* in the new CYE1 **baseline only**. |
| Research-module PKCS#7 integrity | **10/10** staged CYE1 `.ko` signatures cryptographically verified offline using their artifact's ephemeral CI signer with `openssl cms -verify -binary -noverify`. This is **not** stock OEM-module signature verification and does not weaken signature checking. |
| Image / board-tree binaries | New baseline Image SHA256 `5609cb6faa2a6f07f4a0d0a2205f0d06fe696697cb6efc456d05a6b24d57d600` (48,828,432 bytes); still differs from authenticated stock Image (48,832,528 bytes). DTB SHA256 `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816` and DTBO SHA256 `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12` still match the authenticated stock binaries. Standard libfdt overlay application still fails `FDT_ERR_BADOVERLAY`; Android libufdt path remains untested. |
| [New CWL1 KernelSU Legacy control 44507834525](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834525), [artifact 14523566161](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44507834525/artifacts/14523566161) | **Success**. Downloaded archive SHA256 `cc10f3b631f58635a60f03a96a9e102fe67e3f9f2b7522ba9f47ab02a2629526`; actual `System.map` independently confirms all seven expected KSU/manual-hook/preinit text symbols. Embedded AArch64 ELF 17,280 bytes; SHA256 `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`; 10/10 ephemeral CI-module PKCS#7 signatures verified. **This workflow remains CWL1**, and its release is only `4.14.190-perf`, so it cannot establish CYE1 stock compatibility. |
| [Official CYE1 + KSU research run 44502580820](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44502580820), [artifact 14518778090](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44502580820/artifacts/14518778090) | Previously completed green at pinned Legacy `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`. Its actual artifact was downloaded again; `12,530/12,530` reconstructed export parity, all seven linked KSU symbols, exact embedded AArch64 preinit ELF SHA256 above and **10/10** CI research module signatures were independently rechecked. **This earlier KSU build predates the current baseline-only OEM-public-cert/release modifications**. |
| [New source compatibility audit 44512103461](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44512103461), [artifact 14524372048](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44512103461/artifacts/14524372048) | Audit workflow **success**, but the audited external community source `gta4xlve-dev/android_kernel_samsung_gta4xlve@ef3c0a5` reports `4.14.357-openela`, **not** the actual stock `4.14.190`; it is not validated as a drop-in CYE1 OEM source. |

Additional independent artifact checks: `gsi_write_channel_scratch`
still has CRC `0x00000000` in the actual CYE1 `Module.symvers`.
The verifier and compatibility workflows on the branch head also passed;
their green status does not establish physical-device compatibility.
There was no newly observed CI failure requiring source modification.

**Still blocking flash approval:** no actual boot/bootloader result for this
modified kernel; **no original stock/vendor module set independently checked
for trusted signer, imported symbols and runtime loading**; compiler is AOSP
Clang 10.0.1 rather than OEM 10.0.7; Samsung-specific DTBO loading remains
untested; the OEM signature/AVB boot acceptance is not established.
A separate local experimental TAR is documented in
[`CYE1_BASELINE_BOOT_TEST.md`](CYE1_BASELINE_BOOT_TEST.md), but no flash
package was generated, attached or deployed by this research follow-up.
**FLASH_ALLOWED=NO; no merge to `main`, no CYE1-KernelSU push without the
explicit `[cye1-kernelsu]` commit marker.**
