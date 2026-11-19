#!/usr/bin/env python3
"""Add logging-only boot phase markers to the pinned temporary KSU checkout.

The caller must verify the upstream git revision before invoking this script.
No hook is skipped, no policy is changed, and CONFIG_KSU_DEBUG is not enabled.
Logging can change timing; neither marker strings nor green CI prove bootability.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


UPSTREAM_PIN = "e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a"
PREFIX = "ROOTS6_KSU_TRACE: "
INIT_PATH = "kernel/core/init.c"
RUNTIME_PATH = "kernel/runtime/ksud_integration.c"
INIT_CALLS = (
    ("ksu_feature_init", "\t", 1),
    ("ksu_sulog_init", "\t", 1),
    ("ksu_adb_root_init", "\t", 1),
    ("ksu_shell_su_adb_only_init", "\t", 1),
    ("ksu_feature_apply_forced", "\t", 1),
    ("ksu_lsm_hook_init", "\t", 1),
    ("ksu_selinux_hide_init", "\t", 1),
    ("ksu_supercalls_init", "\t", 1),
    ("ksu_app_profile_init", "\t", 1),
    ("ksu_syscall_hook_manager_init", "\t\t", 2),
    ("ksu_allowlist_init", "\t\t", 2),
    ("ksu_throne_tracker_init", "\t\t", 2),
    ("ksu_ksud_init", "\t\t", 1),
    ("ksu_preinit_init", "\t\t", 1),
    ("ksu_file_wrapper_init", "\t\t", 2),
)
SECOND_STAGE_BLOCK = """static void ksu_initialize_selinux_tw_func(struct callback_head *cb)
{
	ksu_selinux_hide_handle_second_stage();
	apply_kernelsu_rules();
	ksu_feature_apply_forced();
	cache_sid();
	setup_ksu_cred();
	kfree(cb);
}
"""
SECOND_STAGE_CALLS = (
    "ksu_selinux_hide_handle_second_stage",
    "apply_kernelsu_rules",
    "setup_ksu_cred",
)
REQUIRED_CONFIG = (
    "CONFIG_KSU=y",
    "CONFIG_KSU_MANUAL_HOOK=y",
    "# CONFIG_KSU_DEBUG is not set",
    "# CONFIG_KPROBES is not set",
    "CONFIG_MODVERSIONS=y",
    "CONFIG_MODULE_SIG=y",
    "CONFIG_MODULE_SIG_FORCE=y",
    "CONFIG_MODULE_SIG_SHA512=y",
    "CONFIG_SECURITY_SELINUX=y",
    "CONFIG_UH_RKP=y",
    "CONFIG_RKP_KDP=y",
    "CONFIG_RKP_NS_PROT=y",
    "CONFIG_FIVE=y",
    "CONFIG_PROCA=y",
    "CONFIG_PROCA_S_OS=y",
)
TRACE_LINE = re.compile(r'^[ \t]*pr_info\("ROOTS6_KSU_TRACE: [a-z0-9_.]+\\n"\);\n', re.M)


def replace_exact(text, old, new, count, label):
    found = text.count(old)
    if found != count:
        raise ValueError(f"{label}: expected {count} anchors, got {found}")
    return text.replace(old, new)


def trace_line(phase, indent="\t"):
    return f'{indent}pr_info("{PREFIX}{phase}\\n");\n'


def marker_counts():
    counts = {PREFIX + phase: 1 for phase in (
        "init.entry", "init.complete", "init.before.prepare_creds", "init.after.prepare_creds",
        "second_stage.entry", "second_stage.complete",
    )}
    for function, _, count in INIT_CALLS:
        for phase in ("before", "after"):
            counts[PREFIX + f"init.{phase}.{function}"] = count
    for function in SECOND_STAGE_CALLS:
        for phase in ("before", "after"):
            counts[PREFIX + f"second_stage.{phase}.{function}"] = 1
    return counts


def instrument_sources(sources):
    """Return validated edits; removing only inserted logging lines is lossless."""
    if set(sources) != {INIT_PATH, RUNTIME_PATH}:
        raise ValueError("Exactly the two pinned KSU source files are required")
    if any(PREFIX in body for body in sources.values()):
        raise ValueError("Boot trace already present")
    init = sources[INIT_PATH]
    init = replace_exact(init, "int __init kernelsu_init(void)\n{\n",
                         "int __init kernelsu_init(void)\n{\n" + trace_line("init.entry"),
                         1, "kernelsu_init entry")
    init = replace_exact(init, "\treturn 0;\n}\n\nvoid __exit kernelsu_exit(void)\n",
                         trace_line("init.complete") + "\treturn 0;\n}\n\nvoid __exit kernelsu_exit(void)\n",
                         1, "kernelsu_init completion")
    credentials = "    ksu_cred = prepare_creds();\n"
    init = replace_exact(init, "\n" + credentials,
                         "\n" + trace_line("init.before.prepare_creds", "    ") + credentials
                         + trace_line("init.after.prepare_creds", "    "), 1, "prepare_creds")
    for function, indent, count in INIT_CALLS:
        call = f"{indent}{function}();\n"
        init = replace_exact(init, "\n" + call,
                             "\n" + trace_line(f"init.before.{function}", indent) + call
                             + trace_line(f"init.after.{function}", indent), count, function)

    block = SECOND_STAGE_BLOCK.replace("{\n", "{\n" + trace_line("second_stage.entry"), 1)
    for function in SECOND_STAGE_CALLS:
        call = f"\t{function}();\n"
        block = replace_exact(block, call, trace_line(f"second_stage.before.{function}")
                              + call + trace_line(f"second_stage.after.{function}"), 1, function)
    block = replace_exact(block, "\tkfree(cb);\n}\n", "\tkfree(cb);\n"
                          + trace_line("second_stage.complete") + "}\n", 1, "second stage completion")
    runtime = replace_exact(sources[RUNTIME_PATH], SECOND_STAGE_BLOCK, block, 1,
                            "ksu_initialize_selinux_tw_func")
    edits = {INIT_PATH: init, RUNTIME_PATH: runtime}
    for path, body in edits.items():
        if TRACE_LINE.sub("", body) != sources[path]:
            raise ValueError(f"Non-logging change detected: {path}")
    combined = "\n".join(edits.values())
    for marker, count in marker_counts().items():
        if combined.count(marker + "\\n") != count:
            raise ValueError(f"Unexpected marker count: {marker}")
    return edits


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def instrument_tree(upstream, manifest):
    if manifest.exists() or not manifest.parent.is_dir():
        raise ValueError("Manifest must be a new file in an existing directory")
    sources = {path: (upstream / path).read_text() for path in (INIT_PATH, RUNTIME_PATH)}
    edits = instrument_sources(sources)
    report = {
        "schema_version": 1,
        "expected_upstream_commit": UPSTREAM_PIN,
        "mode": "logging-only",
        "FLASH_ALLOWED": "NO",
        "POLICY_OR_HOOK_FLOW_CHANGED": False,
        "CONFIG_KSU_DEBUG_ENABLED_BY_THIS_SCRIPT": False,
        "sources": {path: {"before_sha256": digest(sources[path]), "after_sha256": digest(body)}
                    for path, body in edits.items()},
        "markers": sorted(marker_counts()),
        "source_marker_counts": marker_counts(),
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
    }
    # Every source/anchor/marker check has succeeded before the first write.
    for path, body in edits.items():
        target = upstream / path
        target.chmod(target.stat().st_mode | 0o200)
        target.write_text(body)
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def verify_linked_trace(manifest, image, config):
    if (manifest.get("schema_version") != 1
            or manifest.get("expected_upstream_commit") != UPSTREAM_PIN
            or manifest.get("mode") != "logging-only"
            or manifest.get("FLASH_ALLOWED") != "NO"
            or manifest.get("POLICY_OR_HOOK_FLOW_CHANGED") is not False
            or manifest.get("CONFIG_KSU_DEBUG_ENABLED_BY_THIS_SCRIPT") is not False
            or manifest.get("markers") != sorted(marker_counts())
            or manifest.get("source_marker_counts") != marker_counts()):
        raise ValueError("Unexpected trace manifest; refusing a reduced marker set")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or set(sources) != {INIT_PATH, RUNTIME_PATH}:
        raise ValueError("Unexpected trace manifest source inventory")
    for path, hashes in sources.items():
        if (not isinstance(hashes, dict) or set(hashes) != {"before_sha256", "after_sha256"}
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in hashes.values())
                or hashes["before_sha256"] == hashes["after_sha256"]):
            raise ValueError(f"Invalid trace source hashes: {path}")
    missing = [marker for marker in sorted(marker_counts()) if (marker + "\n\0").encode() not in image]
    settings = {}
    for line in config.splitlines():
        match = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=.*|# (CONFIG_[A-Z0-9_]+) is not set", line)
        if match:
            settings.setdefault(match.group(1) or match.group(2), []).append(line)
    invalid_config = []
    for line in REQUIRED_CONFIG:
        symbol = re.search(r"CONFIG_[A-Z0-9_]+", line).group()
        if settings.get(symbol) != [line]:
            invalid_config.append(line)
    return {
        "FLASH_ALLOWED": "NO",
        "LINKED_TRACE_MARKERS_VALID": not missing,
        "REQUIRED_TRACE_MARKERS": len(marker_counts()),
        "MISSING_TRACE_MARKERS": missing,
        "TRACE_CONFIG_GATES_VALID": not invalid_config,
        "MISSING_OR_CONFLICTING_CONFIG": invalid_config,
        "MARKER_STRINGS_PROVE_RUNTIME_EXECUTION": False,
        "DEVICE_BOOT_TEST": "NOT_PERFORMED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    apply = commands.add_parser("apply", help="Instrument the temporary pinned upstream checkout")
    apply.add_argument("--upstream", type=Path, required=True)
    apply.add_argument("--manifest", type=Path, required=True)
    verify = commands.add_parser("verify", help="Check linked marker literals and required config gates")
    verify.add_argument("--image", type=Path, required=True)
    verify.add_argument("--config", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "apply":
        instrument_tree(args.upstream.resolve(), args.manifest.resolve())
        print("ROOTS6_KSU_BOOT_TRACE=LOGGING_ONLY_SOURCE_PATCHED")
    else:
        result = verify_linked_trace(json.loads(args.manifest.read_text()),
                                     args.image.read_bytes(), args.config.read_text())
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"LINKED_TRACE_MARKERS_VALID={result['LINKED_TRACE_MARKERS_VALID']}")
        print(f"TRACE_CONFIG_GATES_VALID={result['TRACE_CONFIG_GATES_VALID']}")
        if not result["LINKED_TRACE_MARKERS_VALID"] or not result["TRACE_CONFIG_GATES_VALID"]:
            parser.exit(1, "Boot trace linked-image/configuration validation failed\n")
    print("FLASH_ALLOWED=NO")


if __name__ == "__main__":
    main()
