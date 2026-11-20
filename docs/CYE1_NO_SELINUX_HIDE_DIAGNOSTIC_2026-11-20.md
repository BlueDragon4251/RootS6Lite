# CYE1 optional SELinux-hide isolation — 2026-11-20

## Status and purpose

Research only: **no Odin package; no physical boot or root claim**. This branch
starts from `f2552a943066bb5dc5bf9b857cb77e776bc152f7`, which records both
owner-reported KSU boot failures and rejects both failed Image hashes. The
non-KSU baseline previously booted. The owner has now flashed back again;
Android startup after this specific rollback is not yet confirmed.

The current incident has no authenticated KSU crash trace. Stock Recovery ADB
was `unauthorized`. An unavailable log does not identify a panic, failed hook
or Samsung protection rejection. This is a controlled source comparison,
not an established diagnosis or fix.

## Exact change

KernelSU Next remains pinned to
`e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a`. Its optional hide subsystem installs
file-operation hooks via a writable `vmap` alias and starts a background thread.
The feature toggle merely changes a boolean; disabling that toggle does not
prevent installation. The existing post-init trace marker does not prove the
asynchronous worker completed.

Only `kernel/feature/selinux_hide.c` is replaced in the transient upstream tree.
The original 15,691 bytes must have SHA256
`9dfb9d24ad6dc6032a2f6a8d9a672a9a2a988d3cfcb0bfea8867a59084928706`.
Four entry points remain: init emits a fixed diagnostic warning, and exit,
second-stage and post-fs-data do nothing. No hide feature handler, worker,
fake status page or file-operation patching remains in that implementation.
The unchanged feature dispatcher reports the absent handler as unsupported.

The two former internal helpers `ksu_selinux_hide_add_type` and
`ksu_selinux_hide_add_rule` have no external callers at this pin and are removed
with the implementation. `sepol_expected_argc` belongs to the SELinux policy
code, not this implementation, and remains unchanged.

## Invariants and gates

- Explicit workflow mode `kernelsu-no-selinux-hide`; normal `baseline` and
  `kernelsu` modes remain available. There is no duplicate build workflow.
- Preparation requires the exact commit, clean checkout and original source
  hash before the ordinary integration and logging-only trace patches run.
- No Kconfig, Kbuild, primary manual hook, preinit, policy or credential change
  is made by the no-hide preparer. Ordinary existing Samsung compatibility
  shims and the 42 trace markers still apply unchanged afterward.
- `KPROBES=n`, manual hooks, SELinux, MODVERSIONS, forced module signatures,
  RKP/KDP, FIVE and PROCA retain the existing KSU research configuration. Its
  complete final config hash must remain
  `d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416`.
- Existing 12,530-export comparison, OEM certificate, linked main-hook call
  edges and embedded preinit ELF checks also run for this mode.
- A separate source/linked-code report verifies actual source and binary
  evidence. The embedded IKCONFIG must match the same complete config hash;
  vmlinux disassembly of the retained stubs must match raw Image bytes. Only
  empty returns or the exact init warning to `printk` are accepted. A manifest
  alone is not accepted as proof of omission.
- `ROOTS6_KSU_NO_SELINUX_HIDE` identifies this Image. The guarded packager
  explicitly rejects it even if all ordinary KSU static checks pass.

The trace patch's `POLICY_OR_HOOK_FLOW_CHANGED=false` describes that script's
logging-only insertion, **not the whole diagnostic profile**. This profile
intentionally changes optional hide behavior and records it separately.

## Results

At initial commit preparation, the new compile and linked-code verification
are pending. No green build, successful boot, root authorization or on-device
module loading is claimed. Actual run IDs, hashes, test counts and any failures
will be appended after GitHub confirms them.

Local preparation checks: **179/179 tests passed**, including 23 diagnostic
gate tests and 27 packager tests. Workflow YAML parsed successfully. These are
offline synthetic/regression checks, not a kernel compile or a device test.

A successful static build would establish a reproducible isolated variant.
It would not show whether the omitted subsystem caused the device failure;
that still requires fresh device evidence or a separately approved controlled
boot test. SELinux enforcement and Samsung safeguards must not be disabled
to force a result.
