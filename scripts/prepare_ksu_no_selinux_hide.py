#!/usr/bin/env python3
"""Non-flashable, one-file diagnostic isolation of the optional hide feature.

Apply BEFORE the normal legacy integration and bounded trace instrumentation.
This does not disable SELinux, Samsung protections, KSU policy or main hooks.
The normal five-hook, 42-trace, ABI and preinit-ELF audits remain mandatory.
"""

import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from instrument_kernelsu_boot_trace import REQUIRED_CONFIG
from audit_stock_firmware import embedded_ikconfig_metadata


UPSTREAM_PIN = "e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a"
SOURCE_PATH = "kernel/feature/selinux_hide.c"
SOURCE_SHA256 = "9dfb9d24ad6dc6032a2f6a8d9a672a9a2a988d3cfcb0bfea8867a59084928706"
CONFIG_SHA256 = "d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416"
MODE = "kernelsu-no-selinux-hide"
SENTINEL = "ROOTS6_KSU_NO_SELINUX_HIDE"
WARNING = SENTINEL + ": optional hide implementation absent; RESEARCH_ONLY; NEVER_FLASH"
APIS = (
    "ksu_selinux_hide_init", "ksu_selinux_hide_exit",
    "ksu_selinux_hide_handle_second_stage", "ksu_selinux_hide_handle_post_fs_data",
)
EXIT_API = "ksu_selinux_hide_exit"
INIT_API = "ksu_selinux_hide_init"
STUB_SOURCE = ('''/* RootS6Lite isolated diagnostic only. NEVER FLASH.
 * Only the optional hide implementation is absent; no security policy changes.
 */
#include <linux/init.h>
#include <linux/printk.h>
#include "feature/selinux_hide.h"

void __init ksu_selinux_hide_init(void)
{
\tpr_warn("''' + WARNING + '''\\n");
}

void __exit ksu_selinux_hide_exit(void)
{
}

void ksu_selinux_hide_handle_second_stage(void)
{
}

void ksu_selinux_hide_handle_post_fs_data(void)
{
}
''').encode()
# These are EXISTING edits performed separately by the normal integration and
# trace scripts. This diagnostic script neither applies nor approves them.
EXTERNAL_BUILD_EDITS = {
    "kernel/Kbuild", "kernel/preinit/runner/nolibc/time.h",
    "kernel/core/init.c", "kernel/runtime/ksud_integration.c",
}
REMOVED_SYMBOLS = {
    "ksu_selinux_hide_add_type", "ksu_selinux_hide_add_rule", "ksu_rcu_replace",
    "ksu_should_hide_context", "ksu_is_dirty_access_query", "ksu_fix_access_response",
    "ksu_patch_fops_slot", "ksu_resolve_fops", "ksu_sel_write", "ksu_proc_pid_attr_write",
    "ksu_hook_proc_attr_write", "ksu_hook_transaction_write", "ksu_get_real_status_page",
    "ksu_prepare_fake_status_page", "ksu_status_open", "ksu_hook_status_open",
    "selinux_hide_get", "selinux_hide_set", "ksu_selinux_hide_init_thread",
    "ksu_selinux_hide_enabled", "ksu_hide_type_list", "ksu_hide_rule_list",
    "ksu_hide_list_mutex", "ksu_dirty_rules", "orig_sel_write", "g_sel_context_fops",
    "orig_proc_pid_attr_write", "g_proc_attr_fops", "ksu_fake_status_page",
    "orig_status_open", "g_status_fops", "selinux_hide_handler",
}
NOP, RET = 0xD503201F, 0xD65F03C0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(*args):
    return subprocess.run([str(arg) for arg in args], check=True, capture_output=True,
                          text=True, timeout=60).stdout


def git(root, *args):
    return run("git", "-C", root, *args)


def expected_manifest(complete):
    return {
        "schema_version": 1, "mode": MODE, "expected_upstream_commit": UPSTREAM_PIN,
        "RESEARCH_ONLY": "YES", "FLASH_ALLOWED": "NO", "CONFIG_UNCHANGED": True,
        "OPTIONAL_HIDE_BEHAVIOR_CHANGED": True, "ROOT_FUNCTIONALITY": "UNVERIFIED",
        "source": SOURCE_PATH, "before_sha256": SOURCE_SHA256,
        "after_sha256": digest(STUB_SOURCE), "api_entry_points": list(APIS),
        "sentinel": SENTINEL, "expected_final_config_sha256": CONFIG_SHA256,
        "APPLY_COMPLETE": complete, "DEVICE_BOOT_TEST": "NOT_PERFORMED",
    }


def check_pin(root):
    if git(root, "rev-parse", "HEAD").strip() != UPSTREAM_PIN:
        raise ValueError("Unexpected KernelSU upstream revision")


def apply_to_tree(root, manifest):
    root, manifest = root.resolve(), manifest.resolve()
    if manifest.exists() or not manifest.parent.is_dir() or manifest.is_relative_to(root):
        raise ValueError("Manifest must be new, outside the upstream checkout, in an existing directory")
    check_pin(root)
    if git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("Diagnostic apply requires a clean upstream checkout before integration/trace")
    source = root / SOURCE_PATH
    if source.is_symlink() or source.resolve() != source or digest(source.read_bytes()) != SOURCE_SHA256:
        raise ValueError("Pinned optional-hide source hash/path differs or diagnostic was already applied")
    # Reserve and record the planned operation before changing the one source.
    # An interrupted/failed apply leaves APPLY_COMPLETE=false and cannot verify.
    with manifest.open("x", encoding="utf-8") as stream:
        json.dump(expected_manifest(False), stream, indent=2, sort_keys=True)
        stream.write("\n")
    source.write_bytes(STUB_SOURCE)
    if source.read_bytes() != STUB_SOURCE or set(git(root, "diff", "--name-only", "HEAD").splitlines()) != {SOURCE_PATH}:
        raise ValueError("Unexpected changes while applying the one-file diagnostic")
    result = expected_manifest(True)
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def verify_source(root, manifest):
    check_pin(root)
    if json.loads(manifest.read_bytes()) != expected_manifest(True):
        raise ValueError("Unexpected or incomplete no-hide manifest")
    source = root / SOURCE_PATH
    if source.is_symlink() or source.resolve() != source or source.read_bytes() != STUB_SOURCE:
        raise ValueError("Diagnostic stub source is not the exact one-file replacement")
    changed = set(git(root, "diff", "--name-only", "HEAD").splitlines())
    if SOURCE_PATH not in changed or changed - {SOURCE_PATH} - EXTERNAL_BUILD_EDITS:
        raise ValueError("Unexpected source/config/policy edits outside diagnostic and existing integration/trace paths")
    return sorted(changed & EXTERNAL_BUILD_EDITS)


def verify_config(config):
    if digest(config) != CONFIG_SHA256:
        raise ValueError("Final config hash differs from the audited unchanged KSU profile")
    settings = {}
    for line in config.decode().splitlines():
        match = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=.*|# (CONFIG_[A-Z0-9_]+) is not set", line)
        if match:
            settings.setdefault(match.group(1) or match.group(2), []).append(line)
    for line in (*REQUIRED_CONFIG, "CONFIG_KALLSYMS=y", "CONFIG_KALLSYMS_ALL=y"):
        symbol = re.search(r"CONFIG_[A-Z0-9_]+", line).group()
        if settings.get(symbol) != [line]:
            raise ValueError("Missing/conflicting security or symbol config gate: " + symbol)


def verify_embedded_config(image):
    if image.count(b"IKCFG_ST") != 1 or image.count(b"IKCFG_ED") != 1:
        raise ValueError("Image must contain exactly one embedded IKCONFIG marker pair")
    config = embedded_ikconfig_metadata(image)
    if config.get("status") != "found" or config.get("sha256") != CONFIG_SHA256:
        raise ValueError("Embedded Image config does not match the audited final config hash")
    return config


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def verify_warn_words(words, start, printk, image, base):
    """Accept only constant-address setup, an optional standard 16-byte frame,
    and exactly one direct printk call/tail call. No loads/stores except the
    balanced x29/x30 frame; no other branch, hook, thread or registration call.
    Unexpected compiler output fails closed rather than broadening the gate.
    """
    pointer = None
    address_kind = None
    added = frame = framed = called = finished = False
    for index, word in enumerate(words):
        pc = start + index * 4
        if word == NOP:
            continue
        if finished:
            raise ValueError("Instructions remain after diagnostic init return/tail call")
        if word == 0xA9BF7BFD and not (frame or framed or called):  # stp x29,x30,[sp,#-16]!
            frame = framed = True
        elif word == 0x910003FD and frame and not called:  # mov x29,sp
            pass
        elif word == 0xA8C17BFD and frame and called:  # ldp x29,x30,[sp],#16
            frame = False
        elif word & 0x9F00001F in (0x10000000, 0x90000000) and address_kind is None and not called:
            immediate = signed(((word >> 5) & 0x7FFFF) << 2 | ((word >> 29) & 3), 21)
            address_kind = "adrp" if word & 0x80000000 else "adr"
            pointer = (pc & ~0xFFF) + (immediate << 12) if address_kind == "adrp" else pc + immediate
        elif word & 0xFFC003FF == 0x91000000 and address_kind == "adrp" and not (added or called):
            pointer += (word >> 10) & 0xFFF  # add x0,x0,#imm12
            added = True
        elif word & 0xFC000000 in (0x14000000, 0x94000000) and not called:
            target = pc + signed(word & 0x03FFFFFF, 26) * 4
            literal = b"\x014" + WARNING.encode() + b"\n\0"
            offset = -1 if pointer is None else pointer - base
            if target != printk or offset < 0 or image[offset:offset + len(literal)] != literal:
                raise ValueError("Diagnostic init must call exact printk with the exact warning literal")
            called = True
            if word & 0x80000000:  # BL: preserve/restore LR around the call.
                if not frame:
                    raise ValueError("Unexpected unframed diagnostic printk call")
            else:
                if frame:
                    raise ValueError("Diagnostic tail call leaves a live frame")
                finished = True
        elif word == RET and called and not frame:
            finished = True
        else:
            raise ValueError(f"Unexpected diagnostic init instruction 0x{word:08x}")
    if not (called and finished) or frame:
        raise ValueError("Incomplete diagnostic init logging-only body")


def verify_linked(image, system_map, disassemble):
    if len(image) < 64 or image[56:60] != b"ARMd":
        raise ValueError("Expected raw ARM64 Image")
    marker = WARNING.encode() + b"\n\0"
    if image.count(marker) != 1 or b"selinux_hide: " in image:
        raise ValueError("Missing/duplicate diagnostic marker or retained optional-hide log strings")
    symbols, text_addresses = {}, set()
    needed = {"_text", "printk", *APIS}
    for line in system_map.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        address, kind, name = fields
        if name.split(".")[0] in REMOVED_SYMBOLS:
            raise ValueError("Optional hide implementation symbol remains: " + name)
        if kind in ("t", "T"):
            text_addresses.add(int(address, 16))
        if name in needed:
            if name in symbols or kind not in ("t", "T"):
                raise ValueError("Duplicate/non-text required symbol: " + name)
            symbols[name] = int(address, 16)
    if needed - {EXIT_API} - symbols.keys():
        raise ValueError("Required diagnostic stub/printk/Image-base symbol is missing")
    base = symbols["_text"]
    boundaries = sorted({address for address in text_addresses if base <= address < base + len(image)} | {base + len(image)})
    bodies = {}
    for name in APIS:
        if name not in symbols:  # Built-in __exit text is legitimately discarded.
            bodies[name] = {"state": "ABSENT_BUILTIN_EXIT_SECTION"}
            continue
        start = symbols[name]
        if start % 4 or not base <= start < base + len(image):
            raise ValueError("Stub is outside/aligned incorrectly in Image: " + name)
        end = boundaries[bisect_right(boundaries, start)]
        if end % 4 or not 0 < end - start <= 96:
            raise ValueError("Unexpected diagnostic stub extent: " + name)
        instructions = []
        for line in disassemble(start, end).splitlines():
            match = re.match(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+\S", line)
            if match:
                instructions.append((int(match.group(1), 16), int(match.group(2), 16)))
        expected = [(address, struct.unpack_from("<I", image, address - base)[0])
                    for address in range(start, end, 4)]
        if instructions != expected:
            raise ValueError("vmlinux disassembly does not exactly match raw Image stub bytes: " + name)
        words = [word for _, word in expected]
        if name == INIT_API:
            verify_warn_words(words, start, symbols["printk"], image, base)
        elif words[0] != RET or any(word != NOP for word in words[1:]):
            raise ValueError("Diagnostic no-op stub contains more than RET and padding: " + name)
        bodies[name] = {"state": "VERIFIED", "address": f"0x{start:x}", "bytes": end - start,
                        "image_bytes_sha256": digest(image[start - base:end - base])}
    return bodies


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("apply", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--upstream-root", required=True, type=Path)
        command.add_argument("--manifest", required=True, type=Path)
    verify = commands.choices["verify"]
    for name in ("config", "image", "system-map", "vmlinux", "objdump", "report"):
        verify.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.command == "apply":
        apply_to_tree(args.upstream_root, args.manifest)
        print("NO_SELINUX_HIDE_SOURCE_PREPARED=YES\nRESEARCH_ONLY=YES\nFLASH_ALLOWED=NO")
        return
    if args.report.exists() or not args.report.parent.is_dir():
        parser.error("Report must be a new file in an existing directory")
    result = {"mode": MODE, "RESEARCH_ONLY": "YES", "FLASH_ALLOWED": "NO",
              "NO_SELINUX_HIDE_VERIFIED": False, "DEVICE_BOOT_TEST": "NOT_PERFORMED",
              "ROOT_FUNCTIONALITY": "UNVERIFIED"}
    try:
        later_edits = verify_source(args.upstream_root.resolve(), args.manifest)
        config = args.config.read_bytes()
        verify_config(config)
        image, system_map = args.image.read_bytes(), args.system_map.read_bytes()
        embedded_config = verify_embedded_config(image)
        bodies = verify_linked(image, system_map.decode(), lambda start, end: run(
            args.objdump, "-d", f"--start-address=0x{start:x}", f"--stop-address=0x{end:x}", args.vmlinux))
        result.update({"NO_SELINUX_HIDE_VERIFIED": True, "CONFIG_UNCHANGED": True,
                       "OPTIONAL_HIDE_BEHAVIOR_CHANGED": True,
                       "source_sha256": digest(STUB_SOURCE), "config_sha256": digest(config),
                       "EMBEDDED_CONFIG_MATCH": True, "embedded_config": embedded_config,
                       "image_sha256": digest(image), "system_map_sha256": digest(system_map),
                       "vmlinux_sha256": file_digest(args.vmlinux), "objdump_sha256": file_digest(args.objdump),
                       "stub_bodies": bodies, "external_build_edits_require_separate_audits": later_edits,
                       "OPTIONAL_HIDE_IMPLEMENTATION_ABSENT": True,
                       "RUNTIME_CORRECTNESS_PROVEN": False})
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["NO_SELINUX_HIDE_VERIFIED"]:
        parser.exit(1, "No-hide diagnostic verification failed; NEVER FLASH\n")


if __name__ == "__main__":
    main()
