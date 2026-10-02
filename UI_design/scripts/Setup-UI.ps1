[CmdletBinding()]
param([switch]$UpdateLock)
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
try { $node = Get-UiNode } catch {
    $version = $script:Config.Ui.NodeVersion
    $tools = Join-Path $UiRoot '.tools'
    New-TopicDirectory -Path $tools
    $archiveName = "node-v$version-win-x64.zip"
    $archive = Join-Path $tools $archiveName
    $base = "https://nodejs.org/dist/v$version"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $checksums = (Invoke-WebRequest -UseBasicParsing "$base/SHASUMS256.txt").Content
    $line = @($checksums -split "`n" | Where-Object { $_.Trim().EndsWith($archiveName) })
    if ($line.Count -ne 1) { throw 'Pinned Node archive not found in official checksum index.' }
    $expected = ($line[0].Trim() -split '\s+')[0]
    if (-not (Test-Path -LiteralPath $archive)) { Invoke-WebRequest -UseBasicParsing "$base/$archiveName" -OutFile $archive }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Node download checksum mismatch.' }
    Expand-Archive -LiteralPath $archive -DestinationPath $tools -Force
    $node = Get-UiNode
}
$manifest = @{
    name = 'topic16-research-gallery'; version = '1.0.0'; private = $true; type = 'module'
    dependencies = $script:Config.Ui.Packages; devDependencies = $script:Config.Ui.DevPackages
    engines = @{ node = $script:Config.Ui.NodeVersion }
    scripts = @{
        'spike:build' = 'vite build --config spike/vite.config.ts'
        build = 'tsc --noEmit && vite build'
        dev = 'vite --host 127.0.0.1'
        test = 'vitest run'
        typecheck = 'tsc --noEmit'
        e2e = 'playwright test'
        'check:bundle' = 'node tests/bundle-budget.mjs'
    }
}
Write-Utf8Text -Path (Join-Path $UiRoot 'package.json') -Text ($manifest | ConvertTo-Json -Depth 12)
New-TopicDirectory -Path (Join-Path $UiRoot '.cache')
Write-Utf8Text -Path (Join-Path $UiRoot '.cache\ui-build.json') -Text ($script:Config.Ui | ConvertTo-Json -Depth 12)
if ($UpdateLock -or -not (Test-Path -LiteralPath (Join-Path $UiRoot 'package-lock.json'))) {
    Invoke-UiNpm -Arguments @('install', '--no-audit', '--no-fund')
} else { Invoke-UiNpm -Arguments @('ci', '--no-audit', '--no-fund') }
Write-TopicInfo "UI packages ready using $node. Runtime Python packages were not changed."
