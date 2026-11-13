#!/usr/bin/env bash
# Experimental, NOT FLASHABLE. The device stock kernel is P613XXS8CYE1;
# Samsung OSRC P613XXU4CWL1 may be older, and Clang 14 is NOT OEM Clang 10.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(realpath "${1:?kernel source directory}")"
OUT="$(realpath -m "${2:?output directory}")"
EVIDENCE="$(realpath -m "${3:?evidence directory}")"
mkdir -p "$OUT" "$EVIDENCE"
test -f "$SRC/arch/arm64/configs/gta4xlvewifi_eur_open_defconfig"

# Record the as-extracted file hashes so CI-only edits can be audited.
{
  sha256sum "$SRC/scripts/gcc-wrapper.py"
  sha256sum "$SRC/techpack/audio/4.0/dsp/digital-cdc-rsc-mgr.c"
  sha256sum "$SRC/drivers/media/platform/msm/camera/cam_isp/isp_hw_mgr/isp_hw/vfe_hw/vfe_top/cam_vfe_fe_ver1.c"
} > "$EVIDENCE/source-files-before.sha256"

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

# Fix two old-style void() definitions in the temporary extracted source.
# The header prototypes already use void; this keeps the compiler's strict-prototype
# diagnostics enabled for all other files and does not touch the official ZIP.
python3 - "$SRC/techpack/audio/4.0/dsp/digital-cdc-rsc-mgr.c" <<'PY'
import pathlib, sys
p=pathlib.Path(sys.argv[1])
s=p.read_text()
for old,new in [
    ("void digital_cdc_rsc_mgr_init()", "void digital_cdc_rsc_mgr_init(void)"),
    ("void digital_cdc_rsc_mgr_exit()", "void digital_cdc_rsc_mgr_exit(void)"),
]:
    if s.count(old)!=1:
        raise SystemExit("Unexpected stock source for: "+old)
    s=s.replace(old,new)
p.chmod(p.stat().st_mode | 0o200)
p.write_text(s)
PY

# Qualcomm camera code truncates a pointer when passing the CPAS handle.
# Use its first uint32_t element instead, after the 2020 compiler fix by
# Nick Desaulniers. This is a CI-only semantic change, not a stock binary.
# Verify the exact known source pattern, rather than patch arbitrary code.
python3 - "$SRC/drivers/media/platform/msm/camera/cam_isp/isp_hw_mgr/isp_hw/vfe_hw/vfe_top/cam_vfe_fe_ver1.c" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text()
old = "cam_cpas_reg_read((uint32_t)soc_private->cpas_handle,"
new = "cam_cpas_reg_read(soc_private->cpas_handle[0],"
if s.count(old) != 2:
    raise SystemExit(f"Unexpected camera source: expected 2 casts, got {s.count(old)}")
p.chmod(p.stat().st_mode | 0o200)
p.write_text(s.replace(old, new))
PY

{
  sha256sum "$SRC/scripts/gcc-wrapper.py"
  sha256sum "$SRC/techpack/audio/4.0/dsp/digital-cdc-rsc-mgr.c"
  sha256sum "$SRC/drivers/media/platform/msm/camera/cam_isp/isp_hw_mgr/isp_hw/vfe_hw/vfe_top/cam_vfe_fe_ver1.c"
} > "$EVIDENCE/source-files-after.sha256"

export ARCH=arm64
export PYTHON=python3
# Samsung's own build_kernel.sh specifies this Android GCC 4.9 prefix.  The
# workflow obtains an AOSP copy at a pinned commit and verifies its ld.bfd
# SHA256 before invoking this script.  The current Clang 14 frontend remains
# experimental; this restores only the documented Android 4.9 binutils path.
export CROSS_COMPILE="${ANDROID_GCC49_PREFIX:?ANDROID_GCC49_PREFIX must name the verified Android GCC 4.9 aarch64 prefix}"
export CLANG_TRIPLE=aarch64-linux-gnu-
export KBUILD_BUILD_USER=roots6lite-ci
export KBUILD_BUILD_HOST=github-actions
export KBUILD_BUILD_TIMESTAMP="Thu Jan 1 00:00:00 UTC 1970"
export DTC_EXT=/usr/bin/dtc
cd "$SRC"

# Both Ubuntu binutils 2.38 and LLD 14 reject the source's non-PIC ABS32
# MODVERSIONS CRC relocation during its intentional ARM64 -shared link.  The
# Samsung recipe specifies Android GCC 4.9; use its pinned ld.bfd rather than
# changing CONFIG_MODVERSIONS or rewriting the exported-symbol ABI.
test -x "${CROSS_COMPILE}ld"
"${CROSS_COMPILE}ld" --version | grep -F 'GNU ld (binutils-2.27-bd24d23f)' >/dev/null
args=(O="$OUT" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" CLANG_TRIPLE="$CLANG_TRIPLE" REAL_CC=clang-14 DTC_EXT="$DTC_EXT" CONFIG_BUILD_ARM64_DT_OVERLAY=y KCFLAGS="-Wno-unused-but-set-variable -Wno-align-mismatch -Wno-void-pointer-to-int-cast -Wno-pragma-pack -gdwarf-4")
{
  echo "SOURCE_VERSION=4.14.190"
  echo "TEMP_SOURCE_CHANGE=Python2 wrapper, two digital-cdc void prototypes, two camera CPAS pointer-to-handle casts (CI-only); original Samsung archive unchanged"
  echo "SOURCE_FIRMWARE=P613XXU4CWL1"
  echo "DEVICE_FIRMWARE=P613XXS8CYE1"
  echo "COMPILER_EXPERIMENT=clang-14 frontend (NOT OEM Qualcomm clang-10) + verified AOSP Android GCC 4.9 binutils linker"
  echo "LINKER_SELECTION=${CROSS_COMPILE}ld (AOSP Android GCC 4.9 commit 606f80986096476912e04e5c2913685a8f2c3b65; ld.bfd SHA256 2a663de4ce3d702fe3f2a0de48cac366be676f850c2f5732d9cc2e4acb9335e2)"
  echo "COMPILER_FLAGS=-Wno-unused-but-set-variable -Wno-align-mismatch -Wno-void-pointer-to-int-cast -Wno-pragma-pack -gdwarf-4 (diagnostic compatibility only; warnings are not fixes)"
  echo "STOCK_COMPATIBILITY=UNVERIFIED"
  echo "FLASH_ALLOWED=NO"
} > "$EVIDENCE/provenance.txt"

# Observe actual binary/package versions. APT packages are NOT yet version pinned.
{
  echo "RUNNER_IMAGE=${ImageOS:-unknown} ${ImageVersion:-unknown}"
  echo "GITHUB_SHA=${GITHUB_SHA:-unknown}"
  echo "GITHUB_RUN_ID=${GITHUB_RUN_ID:-unknown}"
  echo "SOURCE_ARCHIVE_SHA256=728e592f5ad856773e093a01adebedb06a5ef2554c85813ae275a842eecb13b7"
  echo "TOOLCHAIN_VERSION_PINNED=PARTIAL (Android GCC 4.9 binutils pinned; Clang 14 APT package still not OEM/pinned)"
  clang-14 --version | head -1
  "${CROSS_COMPILE}ld" --version | head -1
  dtc --version
  python3 --version
  dpkg-query -W -f='${Package}=${Version}\n' clang-14 lld-14 llvm-14 gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi 2>/dev/null || true
} > "$EVIDENCE/toolchain-manifest.txt"

echo "=== Generate Samsung config ===" | tee "$EVIDENCE/status.txt"
make "${args[@]}" gta4xlvewifi_eur_open_defconfig 2>&1 | tee "$EVIDENCE/defconfig.log"
cp "$OUT/.config" "$EVIDENCE/stock-generated.config"
sha256sum "$OUT/.config" > "$EVIDENCE/config.sha256"
grep -F 'CONFIG_KALLSYMS=y' "$OUT/.config"
grep -F '# CONFIG_KPROBES is not set' "$OUT/.config"

echo "=== Build Samsung Image, DTBs, and modules (compiler investigation) ===" | tee -a "$EVIDENCE/status.txt"
set +e
make -j2 "${args[@]}" Image dtbs modules 2>&1 | tee "$EVIDENCE/build.log"
code=${PIPESTATUS[0]}
set -e
echo "BUILD_EXIT_CODE=$code" | tee -a "$EVIDENCE/status.txt"
python3 "$SCRIPT_DIR/summarize_samsung_build.py" \
  --log "$EVIDENCE/build.log" --exit-code "$code" \
  --output-json "$EVIDENCE/build-diagnostics.json" \
  --output-md "$EVIDENCE/build-diagnostics.md"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  head -n 100 "$EVIDENCE/build-diagnostics.md" >> "$GITHUB_STEP_SUMMARY"
fi
if (( code != 0 )); then
  tail -n 160 "$EVIDENCE/build.log" > "$EVIDENCE/last-160-build-lines.txt"
  exit "$code"
fi

test -s "$OUT/arch/arm64/boot/Image"
sha256sum "$OUT/arch/arm64/boot/Image" >> "$EVIDENCE/provenance.txt"

# The Samsung Wi-Fi EUR board uses an atoll-ab-idp base DTB plus its own
# GTA4XLVEWIFI revision-00 DTBO. A generic base DTB alone is not sufficient.
BASE_DTB="arch/arm64/boot/dts/qcom/atoll-ab-idp.dtb"
DEVICE_DTBO="arch/arm64/boot/dts/samsung/atoll-sec-gta4xlvewifi-eur-overlay-r00.dtbo"
test -s "$OUT/$BASE_DTB"
test -s "$OUT/$DEVICE_DTBO"

# Image alone omits the device-tree and module compatibility evidence needed
# for later baseline work.  Require both output classes and retain manifests
# of every emitted file rather than treating an Image-only build as complete.
mapfile -t dtbs < <(find "$OUT/arch/arm64/boot/dts" -type f -name '*.dtb' -printf 'arch/arm64/boot/dts/%P\n' | sort)
mapfile -t dtbos < <(find "$OUT/arch/arm64/boot/dts" -type f -name '*.dtbo' -printf 'arch/arm64/boot/dts/%P\n' | sort)
mapfile -t modules < <(cd "$OUT" && find . -type f -name '*.ko' -printf '%P\n' | sort)
(( ${#dtbs[@]} > 0 ))
(( ${#dtbos[@]} > 0 ))
(( ${#modules[@]} > 0 ))
printf '%s\n' "${dtbs[@]}" > "$EVIDENCE/dtb-files.txt"
printf '%s\n' "${dtbos[@]}" > "$EVIDENCE/dtbo-files.txt"
printf '%s\n' "${modules[@]}" > "$EVIDENCE/module-files.txt"
(
  cd "$OUT"
  sha256sum "${dtbs[@]}"
) > "$EVIDENCE/dtb.sha256"
(
  cd "$OUT"
  sha256sum "${dtbos[@]}"
) > "$EVIDENCE/dtbo.sha256"
(
  cd "$OUT"
  sha256sum "${modules[@]}"
) > "$EVIDENCE/modules.sha256"

# Read actual compiled FDT properties; fail if the board overlay or matching
# Qualcomm base is absent/wrong. This is a provenance check, NOT boot proof.
model="$(fdtget -t s "$OUT/$DEVICE_DTBO" / model)"
board_id="$(fdtget -t x "$OUT/$DEVICE_DTBO" / qcom,board-id)"
overlay_compat="$(fdtget -t s "$OUT/$DEVICE_DTBO" / compatible)"
base_compat="$(fdtget -t s "$OUT/$BASE_DTB" / compatible)"
[[ "$model" == *"Samsung GTA4XLVEWIFI EUR PROJECT"* ]]
[[ "$board_id" == "22 0" ]]
[[ "$overlay_compat" == *"qcom,atoll-ab-idp"* ]]
[[ "$base_compat" == *"qcom,atoll-ab-idp"* ]]
{
  echo "BASE_DTB=$BASE_DTB"
  echo "BASE_COMPATIBLE=$base_compat"
  echo "DEVICE_DTBO=$DEVICE_DTBO"
  echo "DEVICE_MODEL=$model"
  echo "DEVICE_COMPATIBLE=$overlay_compat"
  echo "DEVICE_BOARD_ID_HEX=$board_id"
  echo "DTB_DTBO_ABI_MATCH_WITH_STOCK=UNVERIFIED"
  echo "FLASH_ALLOWED=NO"
} > "$EVIDENCE/device-tree-metadata.txt"
printf 'DTB_COUNT=%s\nDTBO_COUNT=%s\nMODULE_COUNT=%s\n' "${#dtbs[@]}" "${#dtbos[@]}" "${#modules[@]}" | tee -a "$EVIDENCE/status.txt"
echo "Image, DTBs, DTBOs and modules compiled, but NEVER FLASH: actual stock DTBO/ABI and physical boot remain unverified." | tee -a "$EVIDENCE/status.txt"
