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


## Latest post-boot follow-up (2026-11-19 17:12 UTC)

**Newer than the status described above:** the owner has since confirmed physical
Android userland boot of the **non-KernelSU CYE1 baseline** on the SM-P613,
with `getenforce=Enforcing`, AVB `orange`, and bootloader `locked=0`.
This supersedes the prior statement that *no baseline physical boot* had been
observed. The separate **KernelSU kernel remains untested on the device**.

The newer explicit KernelSU research [run 44569794596](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794596)
**completed successfully** with preserved CYE1 reconstructed CRC parity,
linked hooks and preinit, and exact CYE1 release string. Its actual downloaded
artifact, hashes, signing-verification boundaries, new OEM-public-cert gate,
DTB/DTBO status, and remaining blockers are fully documented in
[the 17:12 UTC independent follow-up](CYE1_KSU_FOLLOWUP_2026-11-19_1712UTC.md).
**No KSU flash approval, no main merge, and no OEM module trust proof.**

## Physical KSU bootloop postmortem update — 2026-11-19 18:12 UTC

The physical device has now tested the separate KernelSU-enabled CYE1 image from [run 44569794596](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44569794596). **It bootlooped.** This supersedes earlier statements in this report that this KSU build had not yet been tried. The successful physical boot belongs **only** to the non-KSU baseline. The KSU CI checks (12,530/12,530 reconstructed exports, linked manual hooks, static preinit ELF, release/certificate/CI module signatures) remain reproducible but **do not demonstrate device bootability or root**.

Known-failing TAR SHA256 `e3b1fe96470973ea99a603d657700d039a20fc8aa4b1a79cc876bbf276dd0626`. No panic log, crash phase or confirmed rollback outcome yet; root cause unknown. No same-binary reflashing; retain stock firmware and known-good baseline for recovery. The source verifier [44584798284](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44584798284) and source audit [44584783375](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44584783375) passed after incident documentation; neither rebuilds the KSU kernel. Source audit artifact `14559258252` again rejects `4.14.357-openela` as a stock `4.14.190` replacement. Details and specific stop conditions are in [the physical incident report](CYE1_KERNELSU_NEXT_TEST_PACKAGE_2026-11-19.md#physical-device-incident--2026-11-19) and [new KSU follow-up](CYE1_KSU_FOLLOWUP_2026-11-19_1712UTC.md#physical-ksu-bootloop-postmortem-update--2026-11-19-1812-utc).

**FLASH_ALLOWED=NO for KernelSU; physical boot FAILED; root NOT VERIFIED.** No merge to `main`, no new flash package, no weakening of CRC or signature checks.

## 2026-11-19 19:16 UTC — linked manual-hook call-edge verification (new)

**New independent evidence, NOT a boot fix.** Explicit opt-in [CYE1 + KernelSU Next Legacy research run 44594033300](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/44594033300), branch commit `ca55f788c77fe0f9903f2580fecbb4417565b491`, finished **SUCCESS**. The completed Actions job (ID `135807390570`) passed all configured steps, including new ARM64 `vmlinux` call-edge verification. Actual decoded job logs and the complete artifact **14565352122** were downloaded and inspected. Artifact ZIP SHA256: `547ff42250fccc2be475e66cf2f6b01d79e2388d96f6e3dd2a08bba37f0e61b5`.

- **Source/integration:** pinned KernelSU Next Legacy commit `e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`; `CYE1_MODE=kernelsu` was explicitly selected by the `[cye1-kernelsu]` commit marker. Source/config checks passed. `CONFIG_KSU=y`, `CONFIG_KSU_MANUAL_HOOK=y`, `KPROBES=n`, `MODVERSIONS=y`, `MODULE_SIG_FORCE=y`, `FIVE=y`, `PROCA=y`, and `PROCA_S_OS=y`. Original pre-KSU stock-generated config SHA256 `1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208`; final KSU research config SHA256 `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416`.
- **Real linked call instructions:** inspected artifact `_evidence/ksu-linked-call-edges.json` and completed `objdump` log. **9 actual ARM64 `BL` edges** into all four KernelSU manual handlers: `ksu_handle_execveat` 6 (from `do_execve`, `do_execveat`, `SyS_execve`, `SyS_execveat`, `compat_SyS_execve`, `compat_SyS_execveat`); `ksu_handle_faccessat` 1 (`SyS_faccessat`); `ksu_handle_stat` 1 (`SyS_newfstatat`); `ksu_handle_sys_read` 1 (`SyS_read`). `MISSING_MANUAL_CALL_EDGES=[]`. The separate `System.map` audit also finds all seven expected hook/preinit symbols. This **disproves merely unreferenced hook symbols** but does **not** prove correct hook placement, calling context or safe runtime execution.
- **Export parity:** independently hashed `_out/Module.symvers` SHA256 `2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e`; 12,530 `vmlinux` exports. Artifact full-reference report and completed logs: **12,530/12,530 reconstructed CYE1 name/CRC/class matches, zero missing/extra/CRC/class differences**. This is **reconstructed OEM reference parity**, not a complete original OEM `Module.symvers` or module trust verification. The old `gsi_write_channel_scratch` unversioned-CRC warning persists.
- **Preinit:** linked Image runner offset `40259424`, length `17280` bytes, independently SHA256 `69d4aef4711bbb5517ff28a144ef45f34d645817546602344ee84722d8a6b187`; static AArch64 ELF, valid 4 KiB and 64 KiB segment congruence. `KSU_PREINIT_ELF_LAYOUT_VALID=YES`.
- **Image/release/certificate:** raw `Image` 48,828,432 bytes, SHA256 `eea466eff716dc03deb5fe4f4451283965e52d1e5b735bf4aedff8d38c7a6ed5`, **not stock-image-identical**. Contains `4.14.190-perf-28683246-abP613XXS8CYE1`. The expected **public** Samsung module certificate DER SHA256 `ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1` was independently located **exactly once** in the linked Image.
- **Research modules:** ten staged signed `.ko` files carry the exact CYE1 kernel-release prefix in `vermagic`. Independently parsed their Linux module-signature trailers and verified **10/10** detached CMS/PKCS#7 signatures using their own CI ephemeral public signer with `openssl cms -verify -nointern -certfile ... -noverify -binary` (signature integrity checked, not OEM certificate-chain trust). A one-byte tampering negative test was correctly rejected. No original OEM module trust is established.
- **Device trees:** independently matched stock SHA256: base DTB `e198bad6723d6020442aa7d23c1d361720551735049bbd56ffed75e4fdc83816`; Samsung Wi-Fi EUR DTBO `aa9a690ff42e85281929186513cfe960847f8c63e9d8dfa63ca5c7ae0ef67d12`. Standard libfdt application still fails `FDT_ERR_BADOVERLAY`; Android libufdt/runtime semantics remain separately gated.

**Physical evidence corrected:** after the earlier KSU bootloop, the owner restored the **non-KSU CYE1 baseline** and confirmed Android userland and ADB (`sys.boot_completed=1`, `surfaceflinger=running`). A subsequent black display was explained by the **magnetic protective cover** triggering `cover_close`; removing the cover restored the display. This **is not a successful KSU boot**. The earlier KSU image from run `44569794596` caused a physical bootloop; no panic/root cause or reliable KSU runtime trace has been obtained. Run `44594033300` is a separate research rebuild that **has not** been tested on-device, and its green link checks are not a bootloop repair.

**Stop gates unchanged:** `FLASH_ALLOWED=NO` for KernelSU; no new Odin package or physical flash, no merge to `main`, no CRC fabrication or signature-check weakening. The original OEM-module trust chain, Samsung OEM Clang 10.0.7 parity (current AOSP Clang 10.0.1), early-KSU/Samsung security interactions, and cause of the KSU bootloop remain unresolved.

## 2026-11-19 — correction: required fifth manual hook

The previous `44594033300` call-edge result was accurate for the **four handlers it checked**, but the required set was incomplete. The pinned upstream **does define** `ksu_handle_sys_reboot` in [`kernel/supercall/supercall.c`](https://github.com/KernelSU-Next/KernelSU-Next/blob/e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a/kernel/supercall/supercall.c). The old adapter omitted its `kernel/reboot.c` call and incorrectly replaced the upstream Kbuild detector. Earlier claims that this callback was absent/obsolete are withdrawn.

The repair adds the guide's reboot bridge, preserves native reboot permission and magic checks, restores the unchanged upstream detector, validates the actual five callback signatures, and makes both post-link audits require the fifth handler. The strict `samsung-cye1` disassembly profile additionally checks the specific six exec callers and the four syscall callers (`SyS_faccessat`, `SyS_newfstatat`, `SyS_read`, `SyS_reboot`), rather than accepting an arbitrary non-KSU caller. New regressions reject the old four-hook situation. Packaging rejects the known physically failed Image hash and the old inaccurate hook manifest; no new package is generated.

The unchanged pinned upstream also stages a preinit runner without a demonstrated manual-path caller of `ksu_preinit_handle_execve`. An embedded valid ELF is **not** proof of executed preinit. Samsung hardening interactions and the actual early-boot failure remain unresolved. This source fix is not a claim of repaired device boot or root. New CI and artifact validation must be recorded below once completed; until then **FLASH_ALLOWED=NO**.

The repaired CYE1 research build also enables **logging-only phase tracing** (42 fixed marker literals at 50 source insertion sites). The instrumenter validates all anchors before writes and verifies that removing exactly the inserted `pr_info` lines restores the original source. It marks early init, credential allocation, direct init calls, and the SELinux second-stage callback without changing their order or skipping them. `CONFIG_KSU_DEBUG` remains disabled; its shell-root default must not be enabled just to obtain logs. The linked Image must contain all markers, and configuration gates preserve Kprobes-disabled, MODVERSIONS, SHA512 forced module signing, SELinux, Samsung RKP/KDP/NS, FIVE and PROCA. An `after` marker records return from a direct call, not completion of an asynchronous worker. Logging can affect timing; available persistent/rootless log access has not yet been demonstrated on this tablet.

