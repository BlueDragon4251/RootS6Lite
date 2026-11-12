# SM-P613 official Samsung source — confirmed

Uploaded and inspected Samsung Open Source Release Center package: SM-P613_EUR_14_Opensource.zip, version P613XXU4CWL1 (Android 14).

## Verified evidence

- ZIP: 233,492,856 bytes; SHA256 **728e592f5ad856773e093a01adebedb06a5ef2554c85813ae275a842eecb13b7**
- Kernel.tar.gz SHA256 **4ef99eebc13604a8dc9d9037901f912fefe1f0ed0dff116e6baa176e4221a1b7**
- Contents: Kernel.tar.gz, Platform.tar.gz, README_Kernel.txt, README_Platform.txt
- Kernel Makefile: **4.14.190** (matches the base version of running firmware P613XXS8CYE1, but not guaranteed to match Samsung's patches)
- Samsung defconfig: **gta4xlvewifi_eur_open_defconfig**
- KALLSYMS and KALLSYMS_ALL: enabled; KPROBES: **disabled**
- Samsung build_kernel.sh requires **Qualcomm Clang 10.0** (llvm-arm-toolchain-ship) and **Android aarch64-linux-android GCC 4.9**, neither of which is bundled.
- Local configuration-generation test on the extracted real source: **PASS**. Full kernel compilation: **NOT YET RUN**.
- This is older **P613XXU4CWL1** source; the user's **P613XXS8CYE1** device may have newer kernel changes. Thus no rooted or stock boot compatibility has been verified.

## Enable official-source CI

Because the GitHub connector can write repository text but cannot upload the 223 MB ZIP as a binary GitHub Release asset, the source archive is **not uploaded to the GitHub repository**. To enable the workflow, use the repository's Releases UI and create a release tagged **source-P613XXU4CWL1** with exact asset name **SM-P613_EUR_14_Opensource.zip**.

From the Windows computer where the archive is already downloaded, alternatively use GitHub CLI (after signing in):

~~~powershell
$repo = "BlueDragon4251/RootS6Lite"
$source = "$HOME\Downloads\flashen\SM-P613_EUR_14_Opensource.zip"
Get-FileHash $source -Algorithm SHA256
gh release create source-P613XXU4CWL1 $source --repo $repo --title "Samsung SM-P613 Android 14 OSRC source" --notes "Unmodified Samsung open-source kernel release. Research only; no flashable binaries."
~~~

Only proceed if the SHA256 agrees with the hash above. The repository is public, so release assets will also be public. Then use **Actions -> Official Samsung OSRC source audit -> Run workflow**. The workflow extracts the authentic kernel and generates the stock configuration. It **does not make an Odin tar**.

## Next steps

Find the matching Qualcomm toolchain, compile stock baseline from this source, check the device-tree/ABI compatibility with firmware P613XXS8CYE1, and test real-device boot while retaining original Odin recovery. Only then integrate KernelSU Next Legacy hooks with CONFIG_KPROBES=n.
