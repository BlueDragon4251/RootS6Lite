# Offline Samsung CYE1 super.img inspection on Windows

This is a **read-only research procedure**. Do not flash or mount any of the
files, do not replace any partition, and do not interpret a successful parser
run as permission to flash an experimental KernelSU Next boot image.

Validated original firmware: `SM-P613`, `P613XXS8CYE1`, Android 14.
The original `boot.img` recovered from the same AP firmware matches SHA256
`06888f51722264ef33f2299e6ccaefab9e6e0c7a96d51c5c8a74cfeecd265655`.

The LZ4-decoded `super.img` is **still an Android sparse image**, not a raw
logical partition filesystem. Its magic begins `3a ff 26 ed`. Simply running
7-Zip on `super.img` or treating it as an ext4 volume is incorrect.

[`scripts/inspect_android_super.py`](../scripts/inspect_android_super.py)
reads the official AOSP sparse format and liblp geometry/metadata with the
Python standard library. It validates header and metadata-table SHA256 digests,
checks partitions/extents against bounds, and reads only the sparse headers and
required metadata when listing. It does **not** expand an 8+ GB raw image,
execute OEM software, or make any changes to the original firmware. An explicit
`--extract-partition` command can copy just one selected logical partition to
a **new** output file, refusing to overwrite pre-existing files.

From Windows CMD in the firmware directory:

```bat
curl.exe -fL "https://raw.githubusercontent.com/BlueDragon4251/RootS6Lite/agent/kernel-foundation/scripts/inspect_android_super.py" -o inspect_android_super.py
py inspect_android_super.py "verify_cye1\super.img"
```

The script should list the logical partitions (`vendor`, `odm`, or
`vendor_dlkm`, depending on the exact firmware). Share the **partition names
and sizes**, not the multi-gigabyte firmware image. Stop and report any
format or checksum error; never bypass the checks.

To extract only the OEM module-bearing partitions of CYE1 once the metadata
checksum and names have been verified (approximately 973 MB + 4.4 MB):

```bat
py inspect_android_super.py "verify_cye1\super.img" --extract-partition vendor --output "verify_cye1\vendor.img"
py inspect_android_super.py "verify_cye1\super.img" --extract-partition odm --output "verify_cye1\odm.img"
```

These commands copy only the listed partitions, produce SHA256 digests, do
not need administrator permissions, and never write to the attached tablet.
If any output or `.partial` file already exists, review it rather than
overwriting it.

**Next research gate:** inspect only the selected vendor module-containing
partitions, correlate each OEM `.ko` file's actual undefined symbols and
`vermagic` against the authenticated CYE1 export manifest, and distinguish
real module loader incompatibilities from unused CRC differences. Samsung
module-signing trust and physical boot safety remain unverified.
