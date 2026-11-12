#!/usr/bin/env bash
# Experimental, NOT FLASHABLE. The device stock kernel is P613XXS8CYE1;
# Samsung OSRC P613XXU4CWL1 may be older, and Clang 14 is NOT OEM Clang 10.
set -Eeuo pipefail
SRC="$(realpath "${1:?kernel source directory}")"
OUT="$(realpath -m "${2:?output directory}")"
EVIDENCE="$(realpath -m "${3:?evidence directory}")"
mkdir -p "$OUT" "$EVIDENCE"
test -f "$SRC/arch/arm64/configs/gta4xlvewifi_eur_open_defconfig"

# Samsung ships a Python 2-only gcc-wrapper. Convert it in the ephemeral
# extracted tree for exploratory GitHub CI; never modify the official ZIP.
python3 - "$SRC/scripts/gcc-wrapper.py" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.chmod(p.stat().st_mode | 0o200)  # Samsung tar marks this file read-only
s = p.read_text()
if "print >> sys.stderr" in s:
    from lib2to3.refactor import RefactoringTool, get_fixers_from_package
    tool = RefactoringTool(get_fixers_from_package("lib2to3.fixes"))
    s = str(tool.refactor_string(s, str(p)))
    s = s.replace("subprocess.Popen(args, stderr=subprocess.PIPE)", 
                  "subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines=True)")
    p.write_text(s.replace("#! /usr/bin/env python2", "#! /usr/bin/env python3"))
PY

export ARCH=arm64
export PYTHON=python3
export CROSS_COMPILE=aarch64-linux-gnu-
export CLANG_TRIPLE=aarch64-linux-gnu-
export KBUILD_BUILD_USER=roots6lite-ci
export KBUILD_BUILD_HOST=github-actions
export DTC_EXT=/usr/bin/dtc
cd "$SRC"

args=(O="$OUT" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" CLANG_TRIPLE="$CLANG_TRIPLE" REAL_CC=clang-14 DTC_EXT="$DTC_EXT" CONFIG_BUILD_ARM64_DT_OVERLAY=y KCFLAGS="-Wno-unused-but-set-variable -Wno-align-mismatch -Wno-void-pointer-to-int-cast -gdwarf-4")
{
  echo "SOURCE_VERSION=4.14.190"
  echo "SOURCE_FIRMWARE=P613XXU4CWL1"
  echo "DEVICE_FIRMWARE=P613XXS8CYE1"
  echo "COMPILER_EXPERIMENT=clang-14 (NOT OEM Qualcomm clang-10)"
  echo "COMPILER_FLAGS=-Wno-unused-but-set-variable -Wno-align-mismatch -Wno-void-pointer-to-int-cast -gdwarf-4 (diagnostic compatibility only; warnings are not fixes)"
  echo "STOCK_COMPATIBILITY=UNVERIFIED"
  echo "FLASH_ALLOWED=NO"
} > "$EVIDENCE/provenance.txt"

echo "=== Generate Samsung config ===" | tee "$EVIDENCE/status.txt"
make "${args[@]}" gta4xlvewifi_eur_open_defconfig 2>&1 | tee "$EVIDENCE/defconfig.log"
cp "$OUT/.config" "$EVIDENCE/stock-generated.config"
grep -F 'CONFIG_KALLSYMS=y' "$OUT/.config"
grep -F '# CONFIG_KPROBES is not set' "$OUT/.config"

echo "=== Build Samsung kernel Image (compiler investigation) ===" | tee -a "$EVIDENCE/status.txt"
set +e
make -j2 "${args[@]}" Image 2>&1 | tee "$EVIDENCE/build.log"
code=${PIPESTATUS[0]}
set -e
echo "BUILD_EXIT_CODE=$code" | tee -a "$EVIDENCE/status.txt"
if (( code != 0 )); then
  tail -n 160 "$EVIDENCE/build.log" > "$EVIDENCE/last-160-build-lines.txt"
  exit "$code"
fi

test -s "$OUT/arch/arm64/boot/Image"
sha256sum "$OUT/arch/arm64/boot/Image" >> "$EVIDENCE/provenance.txt"
echo "Kernel Image compiled, but NEVER FLASH this artifact: stock ABI/DTB, exact toolchain and physical boot are unverified." | tee -a "$EVIDENCE/status.txt"
