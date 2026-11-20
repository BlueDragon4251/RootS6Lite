#!/usr/bin/env python3
"""Local, opt-in SM-P613 CYE1 boot experiment packager; never runs in CI.

Requires the user's SHA256-pinned stock boot.img and a independently inspected,
CI-built Image. The default baseline mode rejects KernelSU; the explicit
KernelSU mode requires raw-Image call-edge/ELF and diagnostic trace audits,
plus pinned KSU provenance.
Keeps the original ramdisk/DTB and Samsung
SignerVer02 trailer. Replaces the OEM-signed AVB footer with a *self-consistent
but UNSIGNED* hash footer; bootloader acceptance is NOT established.

This is not an official Samsung image and carries no claim of safe booting.
"""
import argparse
from bisect import bisect_right
import gzip
import hashlib
import io
import json
import re
import shlex
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from compare_full_cye1_export_abi import compare as compare_exports
from instrument_kernelsu_boot_trace import verify_linked_trace
from verify_kernelsu_call_edges import SAMSUNG_CYE1_CALLERS
from verify_kernelsu_research_symbols import audit as audit_ksu_symbols
from verify_kernelsu_preinit_elf import inspect as inspect_ksu_elf


STOCK_BOOT_SHA256 = "06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655"
STOCK_CONFIG_SHA256 = "1bb058a8ea9cd72287e2f33fad7745bcc9733c453fbfec7c312352d8cc728208"
STOCK_PUBLIC_CERT_DER_SHA256 = "ff40a362febb34f98dd1f23a41e8ab4cc9ffbcba9152eee68ee2fbbf007d03b1"
PUBLIC_CERT_CONFIG_PATH = "certs/roots6lite-p613-cye1-oem-public.pem"
STOCK_KERNELRELEASE = "4.14.190-perf-28683246-abP613XXS8CYE1"
MKBOOTIMG_COMMIT = "028bdc06ce87ab1ee23204feb5cd5ee406484618"
AVBTOOL_COMMIT = "386fb90492db3bd6bc484a579bcde5b43a2a0292"
PARTITION_SIZE = 100663296
STOCK_DT_BYTES = 442884
STOCK_RAMDISK_BYTES = 725007
BOOTED_BASELINE_IMAGE_SHA256 = "5609cb6faa2a6f07f4a0d0a2205f0d06fe696697cb6efc456d05a6b24d57d600"
STOCK_COMPATIBLE_SYMVERS_SHA256 = "2c8e251d7c1c4c6f617f4f68808f355db3fc90b1126ffc24cd73c734eccb497e"
KSU_CONFIG_SHA256 = "d1261c855df36e575bf12219c6831955f75d76f4706659d9c9245f0dbaf86416"
KSU_UPSTREAM_REVISION = "e5f5ec998de88b9fc43c62cff8f7ae12d3f4800a"
# Owner-reported physical boot failures override all successful static gates.
# Keep both failures: adding tracing/the fifth hook did not establish bootability.
KNOWN_FAILED_KSU_IMAGE_SHA256S = frozenset({
    "b3d551884c1fd95ed5632deac3691bbe343f30a3dfb91833c48c57c12ba418a7",  # 2026-11-19 legacy
    "83f2e337b2563b4e0414ec4d59e374f6d345e199b17df43487ebf44cbe986c11",  # 2026-11-20 KSU5/trace
})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aligned(value: int, page: int) -> int:
    return (value + page - 1) // page * page


def boot_v2_layout(data: bytes) -> dict:
    if len(data) < 1660 or data[:8] != b"ANDROID!":
        raise ValueError("Missing Android boot header")
    kernel_size = struct.unpack_from("<I", data, 8)[0]
    ramdisk_size = struct.unpack_from("<I", data, 16)[0]
    second_size = struct.unpack_from("<I", data, 24)[0]
    page, version = struct.unpack_from("<II", data, 36)
    recovery_size = struct.unpack_from("<I", data, 1632)[0]
    header_size, dtb_size = struct.unpack_from("<II", data, 1644)
    if version != 2 or page != 4096 or header_size != 1660:
        raise ValueError("Expected Samsung Android boot v2, 4096-byte pages")
    pos = page
    offsets = {}
    for name, size in (("kernel", kernel_size), ("ramdisk", ramdisk_size), ("second", second_size), ("recovery", recovery_size), ("dtb", dtb_size)):
        offsets[name] = (pos, pos + size)
        pos = aligned(pos + size, page)
    if offsets["dtb"][1] > len(data):
        raise ValueError("Truncated DTB")
    return {"page": page, "header_size": header_size, "kernel_size": kernel_size,
            "ramdisk_size": ramdisk_size, "dtb_size": dtb_size,
            "payload_end": pos, "offsets": offsets}


def stock_metadata(data: bytes, layout: dict, original_image_size: int) -> bytes:
    start = layout["payload_end"]
    if not start < original_image_size < len(data):
        raise ValueError("Invalid signed stock image boundary")
    tail = data[start:original_image_size]
    if len(tail) != 528 or not tail.startswith(b"SEANDROIDENFORCESignerVer02"):
        raise ValueError("Unexpected CYE1 Samsung signer trailer: do not guess")
    return tail


def run(*args: str) -> str:
    result = subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True)
    return result.stdout


def pinned_tool(script: Path, commit: str) -> None:
    if not script.is_file():
        raise ValueError(f"Missing tool {script}")
    head = run("git", "-C", str(script.parent), "rev-parse", "HEAD").strip()
    if head != commit:
        raise ValueError(f"Tool {script} has commit {head}, expected {commit}")
    dirty = run("git", "-C", str(script.parent), "status", "--porcelain=v1", "--untracked-files=all")
    if dirty.strip():
        raise ValueError(f"Tool {script} has modified or untracked sources; pinned HEAD alone is insufficient")


def parse_avb_info(text: str) -> tuple[int, str]:
    original = re.search(r"^Original image size:\s*(\d+) bytes\s*$", text, re.M)
    salt = re.search(r"^\s*Salt:\s*([a-f0-9]{64})\s*$", text, re.M)
    if not original or not salt or not re.search(r"^\s*Partition Name:\s*boot\s*$", text, re.M):
        raise ValueError("Unexpected stock AVB hash footer layout")
    if not re.search(r"^Algorithm:\s*SHA256_RSA4096\s*$", text, re.M):
        raise ValueError("Unexpected stock AVB signature algorithm")
    return int(original.group(1)), salt.group(1)


def verify_image_payload(candidate: bytes, raw_image: bytes, stock_boot: bytes, avb_original_size: int) -> dict:
    orig = boot_v2_layout(stock_boot)
    new = boot_v2_layout(candidate)
    if candidate[:8] != stock_boot[:8] or new["ramdisk_size"] != orig["ramdisk_size"] or new["dtb_size"] != orig["dtb_size"]:
        raise ValueError("Android header mismatch")
    if new["ramdisk_size"] != STOCK_RAMDISK_BYTES or new["dtb_size"] != STOCK_DT_BYTES:
        raise ValueError("Unrecognized stock ramdisk/DTB sizes")
    for section in ("ramdisk", "dtb"):
        x, y = new["offsets"][section]
        a, b = orig["offsets"][section]
        if candidate[x:y] != stock_boot[a:b]:
            raise ValueError(f"Stock {section} changed")
    start, end = new["offsets"]["kernel"]
    if gzip.decompress(candidate[start:end]) != raw_image:
        raise ValueError("Gzip kernel did not roundtrip")
    trailer = stock_metadata(stock_boot, orig, avb_original_size)
    if candidate[new["payload_end"]:new["payload_end"] + 528] != trailer:
        raise ValueError("Samsung signer block changed")
    # Header, address, command line and OS patch level must be copied through
    # mkbootimg. The kernel size and 32-byte v2 SHA-1 ID are intentionally new.
    old_head = bytearray(stock_boot[:4096])
    new_head = bytearray(candidate[:4096])
    for blob in (old_head, new_head):
        blob[8:12] = b"\0" * 4
        blob[576:608] = b"\0" * 32
    if old_head != new_head:
        raise ValueError("Unapproved Android header modification")
    return {"kernel_gzip_bytes": end - start, "ramdisk_sha256": sha256(candidate[new["offsets"]["ramdisk"][0]:new["offsets"]["ramdisk"][1]]),
            "dtb_sha256": sha256(candidate[new["offsets"]["dtb"][0]:new["offsets"]["dtb"][1]]),
            "samsung_signer_trailer_sha256": sha256(trailer)}


def replace_kernel_arg(unpack_output: str, image: Path) -> list[str]:
    args = shlex.split(unpack_output.strip())
    if args.count("--kernel") != 1 or args.count("--header_version") != 1:
        raise ValueError("Unexpected unpack_bootimg output")
    args[args.index("--kernel") + 1] = str(image)
    return args


def tar_odin(boot: Path, output: Path) -> None:
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo(name="boot.img")
        info.size = boot.stat().st_size
        info.mtime = 0
        info.mode = 0o644
        with boot.open("rb") as source:
            tar.addfile(info, source)


def verify_ksu_hook_manifest(hooks: str) -> None:
    lines = set(hooks.splitlines())
    for line in (
        "KPROBES_REMAIN_DISABLED=YES",
        "HOOKS=execve,execveat,compat_execve,compat_execveat,faccessat,read,newfstatat,reboot",
        "UPSTREAM_REBOOT_HOOK_DETECTOR=UNCHANGED",
    ):
        if line not in lines:
            raise ValueError(f"Manual KernelSU hook provenance missing: {line}")
    if any(line.startswith("NO_OBSOLETE_REBOOT_HOOK=") for line in lines):
        raise ValueError("Obsolete four-hook manifest incorrectly claims reboot callback is missing")


def verify_ksu_raw_call_edges(image: bytes, system_map: str) -> dict:
    """Decode BL words inside distinct, map-bounded Samsung caller functions.

    This is tied to the Image bytes, not an objdump JSON claim. System.map has
    no symbol sizes, so the next distinct text-symbol address bounds each
    function. Aliases at the same address cannot stand in for separate callers.
    An exact handler-entry branch does not establish correct arguments or boot.
    """
    callers = [name for names in SAMSUNG_CYE1_CALLERS.values() for name in names]
    required = {"_text", "_etext", *SAMSUNG_CYE1_CALLERS, *callers}
    symbols = {}
    text_addresses = set()
    for line in system_map.splitlines():
        columns = line.split()
        if len(columns) != 3:
            continue
        address, kind, name = columns
        if kind in ("t", "T"):
            text_addresses.add(int(address, 16))
        if name in required:
            if name in symbols:
                raise ValueError(f"Duplicate required System.map symbol: {name}")
            symbols[name] = (int(address, 16), kind)
    missing = sorted(required - symbols.keys())
    if missing:
        raise ValueError("Raw call audit missing System.map symbols: " + ", ".join(missing))
    base, text_end = symbols["_text"][0], symbols["_etext"][0]
    if base % 4 or text_end % 4 or not 0 < text_end - base <= len(image):
        raise ValueError("System.map text range is outside the raw Image or unaligned")
    for name in required - {"_etext"}:
        address, kind = symbols[name]
        if kind not in ("t", "T") or address % 4 or not base <= address < text_end:
            raise ValueError(f"Required symbol is not aligned Image text: {name}")
    functions = [symbols[name][0] for name in (*callers, *SAMSUNG_CYE1_CALLERS)]
    if len(set(functions)) != len(functions):
        raise ValueError("Required caller/handler functions must have distinct addresses; aliases are not call evidence")
    boundaries = sorted({address for address in text_addresses if base <= address < text_end} | {text_end})
    calls = []
    for hook, expected_callers in SAMSUNG_CYE1_CALLERS.items():
        target = symbols[hook][0]
        for caller in expected_callers:
            start = symbols[caller][0]
            end = boundaries[bisect_right(boundaries, start)]
            if end % 4:
                raise ValueError(f"Unaligned System.map function boundary: {caller}")
            matches = []
            for address in range(start, end, 4):
                word = struct.unpack_from("<I", image, address - base)[0]
                if word & 0xFC000000 != 0x94000000:  # AArch64 BL imm26, not B/BLR.
                    continue
                immediate = word & 0x03FFFFFF
                if immediate & 0x02000000:
                    immediate -= 0x04000000
                if address + immediate * 4 == target:
                    matches.append(address)
            if len(matches) != 1:
                raise ValueError(f"Raw Image requires exactly one BL from {caller} to exact {hook} entry; found {len(matches)}")
            calls.append({"caller": caller, "hook": hook, "address": f"0x{matches[0]:x}",
                          "target": f"0x{target:x}", "caller_start": f"0x{start:x}", "caller_end": f"0x{end:x}"})
    return {"profile": "samsung-cye1-raw-image", "call_count": len(calls), "calls": calls,
            "image_sha256": sha256(image), "system_map_sha256": sha256(system_map.encode()),
            "runtime_correctness_proven": False}


def verify_ksu_trace(manifest: dict, image: bytes, config: str) -> dict:
    trace = verify_linked_trace(manifest, image, config)
    if not trace["LINKED_TRACE_MARKERS_VALID"] or not trace["TRACE_CONFIG_GATES_VALID"]:
        raise ValueError("KernelSU diagnostic trace markers or stock-security config gates failed")
    return trace


def verify_ksu_inputs(args, image: bytes) -> dict:
    image_sha256 = sha256(image)
    if image_sha256 in KNOWN_FAILED_KSU_IMAGE_SHA256S:
        raise ValueError(f"Known failed on-device KernelSU Image {image_sha256}: do not repackage or reflash")
    required = ("ksu_config", "system_map", "baseline_image", "ksu_provenance", "ksu_hooks_manifest", "ksu_trace_manifest")
    if any(getattr(args, field, None) is None for field in required):
        raise ValueError("KernelSU mode requires config, System.map, booted baseline, upstream, hook and trace manifests")
    config = args.ksu_config.read_bytes()
    if sha256(config) != KSU_CONFIG_SHA256:
        raise ValueError("KernelSU effective config differs from CI-audited profile")
    if image.count(b"KernelSU") == 0:
        raise ValueError("KernelSU mode image lacks KernelSU identifiers")
    if sha256(args.baseline_image.read_bytes()) != BOOTED_BASELINE_IMAGE_SHA256:
        raise ValueError("Baseline comparison image differs from physically booted CYE1 Image")
    provenance = args.ksu_provenance.read_text()
    if f"KSU_UPSTREAM_LEGACY_COMMIT={KSU_UPSTREAM_REVISION}" not in provenance:
        raise ValueError("KernelSU Next upstream revision is unverified")
    verify_ksu_hook_manifest(args.ksu_hooks_manifest.read_text())
    system_map = args.system_map.read_text()
    call_edges = verify_ksu_raw_call_edges(image, system_map)
    trace_bytes = args.ksu_trace_manifest.read_bytes()
    trace = verify_ksu_trace(json.loads(trace_bytes), image, config.decode())
    symbols = audit_ksu_symbols(args.ksu_config, args.system_map)
    if not all(symbols[k] for k in ("KSU_CONFIG_VALID", "KSU_MANUAL_HOOKS_LINKED", "KSU_PREINIT_EMBEDDED")):
        raise ValueError("KernelSU configuration, linked hook or preinit symbol audit failed")
    if symbols["KSU_PREINIT_BLOB_BYTES"] != 17280:
        raise ValueError("KernelSU preinit runner size differs from audited pinned upstream")
    elf = inspect_ksu_elf(image, system_map)
    if not elf["KSU_PREINIT_ELF_LAYOUT_VALID"] or not elf["KSU_PREINIT_ELF_STATIC"]:
        raise ValueError("Embedded KernelSU preinit ELF failed independent validation")
    return {
        "kernelsu_upstream_commit": KSU_UPSTREAM_REVISION,
        "kernelsu_manual_hooks_linked": True,
        "kernelsu_raw_call_edges": call_edges,
        "kernelsu_boot_trace": trace,
        "ksu_trace_manifest_sha256": sha256(trace_bytes),
        "kernelsu_preinit_runner_bytes": elf["KSU_PREINIT_RUNNER_BYTES"],
        "kernelsu_preinit_runner_sha256": elf["KSU_PREINIT_RUNNER_SHA256"],
        "kernelsu_preinit_page_congruence": elf["PAGE_CONGRUENCE_VERIFIED"],
        "booted_baseline_image_sha256": BOOTED_BASELINE_IMAGE_SHA256,
        "ksu_config_sha256": sha256(config),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "kernelsu"), default="baseline")
    parser.add_argument("--stock-boot", required=True, type=Path)
    parser.add_argument("--kernel-image", required=True, type=Path)
    parser.add_argument("--expected-kernel-sha256", required=True)
    parser.add_argument("--stock-ikconfig", required=True, type=Path)
    parser.add_argument("--built-config", required=True, type=Path)
    parser.add_argument("--module-symvers", required=True, type=Path)
    parser.add_argument("--abi-manifest", required=True, type=Path)
    parser.add_argument("--abi-reference", required=True, type=Path)
    parser.add_argument("--stock-public-cert", required=True, type=Path)
    parser.add_argument("--ksu-config", type=Path)
    parser.add_argument("--system-map", type=Path)
    parser.add_argument("--baseline-image", type=Path)
    parser.add_argument("--ksu-provenance", type=Path)
    parser.add_argument("--ksu-hooks-manifest", type=Path)
    parser.add_argument("--ksu-trace-manifest", type=Path,
                        help="Required source instrumentation manifest for the current KSU diagnostic profile")
    parser.add_argument("--mkbootimg-directory", required=True, type=Path)
    parser.add_argument("--avbtool-directory", required=True, type=Path)
    parser.add_argument("--output-tar", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    mk = args.mkbootimg_directory / "mkbootimg.py"
    unpack = args.mkbootimg_directory / "unpack_bootimg.py"
    avb = args.avbtool_directory / "avbtool.py"
    pinned_tool(mk, MKBOOTIMG_COMMIT)
    pinned_tool(unpack, MKBOOTIMG_COMMIT)
    pinned_tool(avb, AVBTOOL_COMMIT)
    stock = args.stock_boot.read_bytes()
    if len(stock) != PARTITION_SIZE or sha256(stock) != STOCK_BOOT_SHA256:
        raise ValueError("Stock boot does not match exact P613XXS8CYE1 reference")
    image = args.kernel_image.read_bytes()
    if sha256(image) != args.expected_kernel_sha256.lower() or len(image) < 45000000 or image[56:60] != b"ARMd":
        raise ValueError("Unexpected compiled ARM64 Image (size, PE header, or digest)")
    if STOCK_KERNELRELEASE.encode() not in image:
        raise ValueError("Kernel release string mismatches Samsung stock vermagic")
    if args.mode == "baseline" and b"KernelSU" in image:
        raise ValueError("Baseline Image unexpectedly contains KernelSU string")
    original_config = args.stock_ikconfig.read_bytes()
    if sha256(original_config) != STOCK_CONFIG_SHA256:
        raise ValueError("Original stock IKCONFIG SHA256 mismatch")
    expected_config = original_config.replace(
        b'CONFIG_SYSTEM_TRUSTED_KEYS=""',
        f'CONFIG_SYSTEM_TRUSTED_KEYS="{PUBLIC_CERT_CONFIG_PATH}"'.encode(),
    )
    if expected_config == original_config or args.built_config.read_bytes() != expected_config:
        raise ValueError("Effective CYE1 Kconfig deviates from stock beyond public certificate addition")
    ksu_details = verify_ksu_inputs(args, image) if args.mode == "kernelsu" else {}
    # OpenSSL emits binary DER; subprocess text mode would corrupt it.
    cert = subprocess.run(["openssl", "x509", "-in", str(args.stock_public_cert), "-outform", "DER"],
                          check=True, capture_output=True).stdout
    if sha256(cert) != STOCK_PUBLIC_CERT_DER_SHA256 or image.count(cert) != 1:
        raise ValueError("OEM stock module-signing public certificate not uniquely embedded in compiled Image")
    abi = compare_exports(json.loads(args.abi_manifest.read_text()),
                          args.abi_reference.read_bytes(), args.module_symvers.read_bytes())
    if abi["reconstructed_stock_export_parity"] != "YES" or abi["exact_export_name_crc_class_matches"] != 12530:
        raise ValueError("CYE1 full reconstructed export name/CRC/class mismatch")
    if abi["compiled_symvers_sha256"] != STOCK_COMPATIBLE_SYMVERS_SHA256:
        raise ValueError("Module.symvers changed relative to the physically booted CYE1 baseline")
    avb_info = run(sys.executable, str(avb), "info_image", "--image", str(args.stock_boot))
    original_size, salt = parse_avb_info(avb_info)
    stock_layout = boot_v2_layout(stock)
    tail = stock_metadata(stock, stock_layout, original_size)

    with tempfile.TemporaryDirectory(prefix=f"roots6lite-{args.mode}-") as temp_name:
        temp = Path(temp_name)
        stock_parts = temp / "stock_parts"
        stock_parts.mkdir()
        unpacked = run(sys.executable, str(unpack), "--boot_img", str(args.stock_boot), "--out", str(stock_parts), "--format", "mkbootimg")
        original_args = replace_kernel_arg(unpacked, stock_parts / "kernel")
        noop = temp / "noop.img"
        run(sys.executable, str(mk), *original_args, "-o", str(noop))
        if noop.read_bytes() != stock[:stock_layout["payload_end"]]:
            raise ValueError("AOSP no-op repack does NOT reproduce original Samsung boot payload")

        compressed = temp / "Image.gz"
        compressed.write_bytes(gzip.compress(image, compresslevel=9, mtime=0))
        candidate = temp / "boot.img"
        run(sys.executable, str(mk), *replace_kernel_arg(unpacked, compressed), "-o", str(candidate))
        with candidate.open("ab") as stream:
            stream.write(tail)
        # The OEM private AVB key is unavailable. The only honest test variant
        # for an *unlocked* device is a new, unsigned, internally consistent
        # hash footer. This is not a Samsung-signed image.
        run(sys.executable, str(avb), "add_hash_footer", "--image", str(candidate),
            "--partition_name", "boot", "--partition_size", str(PARTITION_SIZE),
            "--algorithm", "NONE", "--salt", salt)
        if candidate.stat().st_size != PARTITION_SIZE:
            raise ValueError("AVB partition size wrong")
        data = candidate.read_bytes()
        details = verify_image_payload(data, image, stock, original_size)
        unsigned_info = run(sys.executable, str(avb), "info_image", "--image", str(candidate))
        if not re.search(r"^Algorithm:\s*NONE\s*$", unsigned_info, re.M):
            raise ValueError("AVB algorithm is not explicitly unsigned")
        run(sys.executable, str(avb), "verify_image", "--image", str(candidate))
        args.output_tar.parent.mkdir(parents=True, exist_ok=True)
        tar_odin(candidate, args.output_tar)
        with tarfile.open(args.output_tar) as archive:
            names = archive.getnames()
            if names != ["boot.img"] or archive.extractfile("boot.img").read() != data:
                raise ValueError("Odin tar archive roundtrip failed")
        report = {
            "model": "SM-P613", "firmware": "P613XXS8CYE1", "mode": "KERNELSU_NEXT_EXPERIMENT" if args.mode == "kernelsu" else "NONROOT_BASELINE_BOOT_EXPERIMENT",
            "stock_boot_sha256": sha256(stock), "compiled_image_sha256": sha256(image),
            "compiled_image_bytes": len(image), "boot_image_sha256": sha256(data),
            "boot_image_bytes": len(data), "odin_tar_sha256": sha256(args.output_tar.read_bytes()),
            "odin_tar_bytes": args.output_tar.stat().st_size,
            "kernel_release": STOCK_KERNELRELEASE, "avb_algorithm": "NONE (unsigned)",
            "original_samsung_signer_block": "PRESERVED_BYTES_SIGNATURE_NOT_REVALIDATED",
            "physical_boot": "NOT_TESTED", "module_loading": "NOT_TESTED",
            "stock_module_signer_public_cert_sha256": STOCK_PUBLIC_CERT_DER_SHA256,
            "stock_module_signer_public_cert_embedded": True,
            "full_reconstructed_export_matches": abi["exact_export_name_crc_class_matches"],
            "module_symvers_sha256": abi["compiled_symvers_sha256"],
            "stock_config_byte_parity_except_public_cert": True,
            "final_kernel_has_kernelsu_kconfig_additions": args.mode == "kernelsu",
            "root_on_device": "NOT_TESTED" if args.mode == "kernelsu" else "NOT_APPLICABLE",
            "recovery": "USER_MUST_HAVE_MATCHING_STOCK_ODIN_FIRMWARE_AND_DOWNLOAD_MODE",
            "flash_readiness": "UNVERIFIED_EXPERIMENTAL_ONLY", **details, **ksu_details,
        }
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
