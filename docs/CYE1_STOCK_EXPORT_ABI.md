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

## Next gates

1. Compare all original CYE1 vendor/system `.ko` import CRCs with the recovered
   OEM export mapping, and determine whether those 25 changed or 21 new symbols
   are consumed by modules necessary to boot. Do **not** claim compatibility
   if a module's signature chain or exact module contents are unknown.
2. Investigate the Samsung 2025 USB-restriction and battery interface changes
   and locate an authentic matching source package if Samsung provides one.
3. Validate OEM compiler, kernel build string, module signing and Android
   boot-chain packaging before any controlled unchanged-baseline boot attempt.
4. Only after stock-baseline boot succeeds, test KSU Next Legacy/root/SELinux
   on the actual, currently unavailable and unrooted tablet.

**No modified boot image is generated, uploaded, approved or flashed.**
