# SM-P613 P613XXS8CYE1: verified original kernel export ABI comparison

> **Research evidence only. FLASH_ALLOWED=NO.** No physical boot, Samsung
> vendor module installation or KernelSU root test has taken place.

## Evidence and provenance

- Original, unmodified Samsung `boot.img` was supplied by the device owner.
  Its **whole-file SHA256** is
  `06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655`,
  exactly the earlier trusted partition-backup hash.
- The gzip ARM64 `Image` was independently extracted **without extracting the
  ramdisk**. Its size is **48,832,528 bytes**, SHA256
  `14defad3fe7854da3cadc43b2c01e96a48a27a4a0e847043c989c45c66fb8228`,
  matching the previous stock metadata audit.
- Research comparator: actual artifact from [pinned AOSP Clang10 stock-control
  run 43407157828](https://github.com/BlueDragon4251/RootS6Lite/actions/runs/43407157828),
  unmodified Samsung CWL1 OSRC with reconciled CYE1 Kconfig (not KernelSU).
  The reference's `Module.symvers` SHA256 was hard-gated to
  `a76b277bee7a6a8ccd30468b9233401887aea66ee049a39a67901f87dac5cd94`.
- Independent tools: [`extract_verified_stock_kernel.py`](../scripts/extract_verified_stock_kernel.py)
  and [`compare_stock_export_abi.py`](../scripts/compare_stock_export_abi.py),
  with ten passing local synthetic tests, newly added to the source-script
  self-test CI (check its latest run separately).
  **The original stock `boot.img` and Image have not been committed or uploaded
  to this repository or a GitHub Actions runner.**

## How the original CRCs were recovered

The reference `System.map` locates the start/end of both the ordinary and GPL
`__ksymtab` and `__kcrctab` linker sections, plus the `__kstrtab` name sequence.
Its 12,509 built-in symbol names are ordered by 16-byte `__ksymtab` entries
and checked against *both* the 4-byte `__kcrctab` entries and the independently
recorded `Module.symvers` CRC for every name. The first 64 bytes of the reference
CRC table and of its immediately following name-string table each occur **exactly
once** in the original CYE1 Image. Their offset difference directly yields
the stock CRC table count; both stock and reference names are NUL-terminated and
are checked for uniqueness and complete membership.

The stock adds exactly 21 names and removes none, all in the ordinary export
group. This normal/GPL split is corroborated by the **4,919/4,922** GPL CRCs
that still match at the tail of the original table. The names in each export
group are alphabetically sorted, allowing the original stock CRCs to be mapped
by symbol name rather than matched by index alone. The complete derived record
is [CYE1 stock export CRC report](CYE1_STOCK_EXPORT_ABI.json).

| Evidence | Original Samsung CYE1 | CWL1/AOSP10 research baseline |
| --- | ---: | ---: |
| Built-in exported symbols | **12,530** | **12,509** |
| Shared names | **12,509** | **12,509** |
| Shared names with identical export CRC | **12,484** | **12,484** |
| Shared names with different export CRC | **25** | **25** |
| Only on original CYE1 | **21** | 0 |
| GPL export CRCs identical | **4,919 of 4,922** | **4,919 of 4,922** |

The **25 changed CRCs** are concentrated in Samsung USB/OTG notification,
USB-cable/type-C and battery/charging interfaces, including
`usb_notify_dev_register`, `get_otg_notify`, `is_usb_host`, `get_cable_type`
and `sec_bat_set_temp_control_test`. The **21 newer OEM exports** include
`check_usb_restrict_lock_state`, `disconnect_unauthorized_device`,
`usb_check_allowlist_for_lockscreen_enabled_id`, `send_usb_restrict_uevent`,
`get_full_capacity` and `sec_bat_recov_full_capacity`.

Read-only search across the **entire extracted CWL1 Samsung source** found **no source-name match for 19 of the 21 newly exported CYE1 symbols**. The other two (`sec_bat_check_full_capacity` and `sec_bat_recov_full_capacity`) exist only as `static` battery-file functions in the older tree, **not as exported symbols**. In particular, the newer USB lockscreen-restriction APIs are absent. This is a concrete source-version gap, not merely a compiler optimization effect.

These findings establish a **real source/ABI delta** between the authentic
2025 Samsung firmware and the older public OSRC, despite the identical
reconciled Kconfig and byte-identical base DTB/board DTBO. Some new symbols
appear related to lockscreen USB restrictions. Their names suggest changes to
security-sensitive functionality, but their exact runtime semantics have **not
been established** by this CRC audit.

The latest KernelSU Next Legacy research `Module.symvers` is byte-identical
to the same CWL1/AOSP10 control. Thus the KernelSU patches do **not** create
additional export-CRC drift **relative to that older research baseline**;
they also do **not** repair the 25 CYE1 differences or supply the 21 additional
exports. `CONFIG_MODULE_SIG_FORCE=y` remains enabled, but original OEM
certificate trust and the CYE1 vendor module imports are still unavailable.
The research `vermagic` uses `4.14.190-perf` rather than the original
`4.14.190-perf-28683246-abP613XXS8CYE1`; merely copying a release suffix
would not fix ABI or signing differences.

## Original CYE1 firmware module inventory (2026-11-13)

The device owner extracted the **authentic matching P613XXS8CYE1 AP** read-only
on Windows. The AP contains `boot.img.lz4`, `recovery.img.lz4`,
`dtbo.img.lz4`, `super.img.lz4` and other firmware components. The
`super.img.lz4` payload decompressed to Android sparse format (magic
`3aff26ed`) and `simg2img` produced a readable 8.28 GiB raw super image.
`lpdumps` verified four non-A/B named logical partitions in metadata 10.0:
`system`, `vendor`, `product`, `odm`. `lpunpack` successfully
extracted all four; 7-Zip identified readable **Ext** filesystems. Full
7-Zip inventory searches matching `modules|modprobe|\\.ko` found **zero
`.ko` files across all four partitions**, with only a 7-byte
`bin/modprobe` entry in `vendor` and `system/bin/modprobe` in `system`.
This is owner-provided command/output evidence, not CI access to the firmware.
The full AP/partition images are **not uploaded or committed**.

Separately, the original `boot.img` already available to the researcher was
verified **again** against whole-file SHA256
`06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655`.
Its 725,007-byte gzip ramdisk decompresses to a 1,565,952-byte `newc` CPIO
archive (SHA256 `a907080466f4ad5af5d0eb572dea75df346a1c61d474639df2eda42b8178fb58`).
The 9 real entries are `debug_ramdisk`, `dev`, `dpolicy`,
`fstab.default`, `init`, `mnt`, `proc`, `sys`, `verity_key`
(plus the CPIO trailer). **No `.ko`, `modules.load`, or `.rc`
entries** were present in that boot ramdisk. No original firmware binary
was modified by these audits.

**Interpretation:** No separately shipped loadable kernel modules were found
in the inspected normal-boot AP partitions or boot ramdisk. Thus the ten
`.ko` files emitted by the experimental research build are **not evidence
that stock CYE1 loads them**. Conversely, this filesystem-only evidence
cannot prove all kernel functionality is built-in, that no other boot stage
loads a module, or that the research kernel would boot. The prior planned
"OEM vendor module import-CRC gate" is **not applicable to any identified
shipping `.ko`** on these inspected images. The **25 actual kernel export
CRC differences and 21 additional CYE1 exports remain verified source/ABI
mismatches**; they must not be dismissed merely because no `.ko` was found.

## Next gates

1. **Prioritize a matching 2025 Samsung CYE1 source release** and investigate
   security-sensitive USB-restriction, cable/OTG and battery code differences.
   Community kernel forks may be research references, not substitutes for
   independently authenticated firmware-matched OEM sources. The 25 changed
   CRCs and 21 added exports remain unresolved; do not spoof CRC values.
2. Determine whether the kernel's compiled-in drivers and core runtime are
   actually compatible with CYE1 even without shipping `.ko` files; compare
   firmware-matched boot configuration, DTB/DTBO, required subsystems, compiler
   provenance, security interfaces and boot-chain packaging. A green compile
   and lack of external modules are **not a boot test**.
3. Before any controlled unchanged-baseline device test, validate OEM compiler,
   kernel build string, signing and recovery/rollback. Do not create or release
   any experimental flash target prematurely.
4. Only after a baseline device boot succeeds, test KSU Next Legacy, root and
   SELinux on the actual, currently unavailable and unrooted tablet.

**No modified boot image is generated, uploaded, approved or flashed.**
