# Upload an UNMODIFIED official Samsung OSRC source package as GitHub Release asset.
# Execute locally on Windows. gh CLI must be installed and authenticated.
$ErrorActionPreference = 'Stop'
$repo = 'BlueDragon4251/RootS6Lite'
$tag = 'source-P613XXU4CWL1'
$source = Join-Path $HOME 'Downloads\flashen\SM-P613_EUR_14_Opensource.zip'
$expected = '728E592F5AD856773E093A01ADEBEDB06A5EF2554C85813AE275A842EECB13B7'
if (-not (Test-Path -LiteralPath $source)) { throw "Source archive not found: $source" }
$actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw "SHA256 mismatch! Expected $expected but got $actual" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI missing. Install it with: winget install --id GitHub.cli -e'
}
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI not authenticated. Run: gh auth login' }
gh release view $tag --repo $repo *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Release exists; upload asset if not already present..."
    gh release upload $tag $source --repo $repo
} else {
    gh release create $tag $source --repo $repo --title "Samsung SM-P613 Android 14 official sources CWL1" --notes "Samsung OSRC package, kernel 4.14.190; source-only, NOT FLASHABLE."
}
if ($LASTEXITCODE -ne 0) { throw 'GitHub upload failed' }
Write-Host 'Source upload completed. Run workflow: Official Samsung OSRC source audit (NOT FLASHABLE).'
