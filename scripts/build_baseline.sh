#!/usr/bin/env bash
# Experimental compiler smoke test, NOT a flashable stock kernel.
set -Eeuo pipefail

SRC="$(realpath "${1:?source directory required}")"
OUT="$(realpath -m "${2:?output directory required}")"
EVIDENCE="$(realpath -m "${3:?evidence directory required}")"
mkdir -p "$OUT" "$EVIDENCE"

[[ -f "$SRC/Makefile" ]] || { echo "No kernel Makefile" >&2; exit 2; }
[[ -f "$SRC/arch/arm64/configs/vendor/atoll-perf_defconfig" ]] || {
  echo "Missing atoll-perf_defconfig" >&2; exit 3;
}
[[ -f "$SRC/arch/arm64/configs/vendor/gta4xlve.config" ]] || {
  echo "Missing gta4xlve.config" >&2; exit 3;
}

cd "$SRC"
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export CROSS_COMPILE_COMPAT=arm-linux-gnueabi-
export CLANG_TRIPLE=aarch64-linux-gnu-
export PATH="/usr/lib/llvm-14/bin:$PATH"
makeargs=(ARCH=arm64 O="$OUT" CC=clang-14 LD=ld.lld-14 AR=llvm-ar-14 NM=llvm-nm-14 OBJCOPY=llvm-objcopy-14 OBJDUMP=llvm-objdump-14 STRIP=llvm-strip-14)

echo "Building candidate baseline with clang-14; this is for compilation RESEARCH only."
make "${makeargs[@]}" vendor/atoll-perf_defconfig
bash scripts/kconfig/merge_config.sh -m -O "$OUT" \
  "$OUT/.config" arch/arm64/configs/vendor/gta4xlve.config
make "${makeargs[@]}" olddefconfig
cp "$OUT/.config" "$EVIDENCE/merged.config"
make -j"$(nproc)" "${makeargs[@]}" Image dtbs 2>&1 | tee "$EVIDENCE/build.log"
test -s "$OUT/arch/arm64/boot/Image"

{
  echo "WARNING: NOT FLASHABLE. Experimental community kernel compilation only."
  echo "Kernel source: $(git rev-parse HEAD)"
  echo "Compiler: $(clang-14 --version | head -1)"
  echo "Image SHA256: $(sha256sum "$OUT/arch/arm64/boot/Image")"
  echo "Stock version: 4.14.190-perf-28683246-abP613XXS8CYE1"
  echo "No Odin tar, boot.img or automatic flash packages have been generated."
} > "$EVIDENCE/BUILD-NOT-FLASHABLE.txt"

if [[ -f "$OUT/arch/arm64/boot/Image.gz" ]]; then
  sha256sum "$OUT/arch/arm64/boot/Image.gz" >> "$EVIDENCE/BUILD-NOT-FLASHABLE.txt"
fi
cat "$EVIDENCE/BUILD-NOT-FLASHABLE.txt"
