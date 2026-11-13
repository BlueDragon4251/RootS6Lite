#!/usr/bin/env python3
"""Extract actionable diagnostics from an experimental Samsung kernel make log.

The earliest reported diagnostic in a parallel make log is a lead, not proof of
the underlying root cause. Preserve the full log for a human investigation.
"""

import argparse
import json
import re
from pathlib import Path


COMPILER_ERROR = re.compile(r"(?:^|\s)(?:fatal\s+)?error:\s|\bundefined reference to\b")
WRAPPER_FATAL = re.compile(r"\berror, forbidden warning:\s")
LINKER_FAILURE = re.compile(
    r"(?:\b(?:ld|ld\.lld|aarch64-linux-gnu-ld):.*\b(?:relocation|linker script|"
    r"dangerous relocation)|\brelocation truncated to fit:|\bdangerous relocation:)",
    re.I,
)
MAKEFILE_FATAL = re.compile(r"^\S[^:\n]*:\d+:\s+\*\*\*\s+")
MAKE_FAILURE = re.compile(r"(?:^|\s)make(?:\[\d+\])?:\s*\*\*|\bError\s+\d+\b")
ENVIRONMENT_FAILURE = re.compile(
    r"\b(?:No space left on device|out of memory|Killed process|Cannot allocate memory|"
    r"command not found|Permission denied|Segmentation fault)\b", re.I
)
WARNING = re.compile(r"(?:^|\s)warning:\s")


def classify(line):
    if WRAPPER_FATAL.search(line):
        return "wrapper_rejected_warning"
    if LINKER_FAILURE.search(line):
        return "linker_error"
    if MAKEFILE_FATAL.search(line):
        return "makefile_fatal"
    if COMPILER_ERROR.search(line):
        return "compiler_or_linker_error"
    if ENVIRONMENT_FAILURE.search(line):
        return "environment_error"
    if MAKE_FAILURE.search(line):
        return "make_failure_or_cascade"
    if WARNING.search(line):
        return "warning"
    return None


def summarize(lines, exit_code, max_items=40):
    findings = []
    counts = {
        "wrapper_rejected_warning": 0,
        "linker_error": 0,
        "makefile_fatal": 0,
        "compiler_or_linker_error": 0,
        "environment_error": 0,
        "make_failure_or_cascade": 0,
        "warning": 0,
    }
    for number, line in enumerate(lines, 1):
        kind = classify(line)
        if kind is None:
            continue
        counts[kind] += 1
        if len(findings) < max_items or kind in (
            "wrapper_rejected_warning", "linker_error", "makefile_fatal", "compiler_or_linker_error", "environment_error"
        ) and sum(f["kind"] == kind for f in findings) < max_items:
            findings.append({"line": number, "kind": kind, "message": line.rstrip()[:1000]})
    significant = [f for f in findings if f["kind"] in (
        "wrapper_rejected_warning", "linker_error", "makefile_fatal", "compiler_or_linker_error", "environment_error"
    )]
    return {
        "exit_code": exit_code,
        "log_lines": len(lines),
        "counts": counts,
        "first_reported_error": significant[0] if significant else None,
        "findings": findings,
        "interpretation": (
            "Parallel make output can interleave failures: the first reported error is "
            "not necessarily the causal failure. Make errors are frequently downstream."
        ),
        "flash_allowed": False,
    }


def render_markdown(result, lines):
    out = [
        "# SM-P613 experimental build diagnostics",
        "",
        f"Exit code: `{result['exit_code']}`; log lines: `{result['log_lines']}`.",
        "**Research only. NOT FLASHABLE.**",
        "",
        result["interpretation"],
        "",
        "## First reported compiler, linker, makefile, wrapper or environment error",
        "",
    ]
    first = result["first_reported_error"]
    if first:
        start = max(0, first["line"] - 6)
        end = min(len(lines), first["line"] + 6)
        out.extend([f"Log line `{first['line']}`:", "", "```text"])
        out.extend(f"{n + 1}: {lines[n].rstrip()}" for n in range(start, end))
        out.append("```")
    else:
        out.append("No directly classified error. Inspect full build.log and exit status.")
    out.extend(["", "## Classified diagnostics", "", "```text"])
    for finding in result["findings"]:
        out.append(f"{finding['line']} [{finding['kind']}] {finding['message']}")
    out.extend(["```", "", "Full, unsuppressed log: `build.log`."])
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    result = summarize(lines, args.exit_code)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(result, lines), encoding="utf-8")
    print("First reported error:", result["first_reported_error"])


if __name__ == "__main__":
    main()
