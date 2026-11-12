[CmdletBinding()]
param([Parameter(Mandatory)][string]$Study)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$hostRecord = Get-Content -LiteralPath (Join-Path $ArtifactRoot 'logs\host.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$baseline = $hostRecord.BaselineRoot
$prepare = Join-Path $baseline 'UI_design\scripts\Prepare-UIAssets.ps1'
$start = Join-Path $baseline 'UI_design\scripts\Start-UI.ps1'
$stop = Join-Path $baseline 'UI_design\scripts\Stop-UI.ps1'
$serverPath = Join-Path $baseline 'artifacts\ui\server.json'
function Ensure-ArtifactServer {
    $expected = (Get-Content -LiteralPath (Join-Path $baseline 'artifacts\ui\catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json).catalog.revision
    if (Test-Path -LiteralPath $serverPath) {
        $saved = Get-Content -LiteralPath $serverPath -Raw -Encoding UTF8 | ConvertFrom-Json
        try {
            $health = Invoke-RestMethod -Uri ($saved.url + '/api/health') -TimeoutSec 2
            if ($health.service -eq 'topic16-ui' -and $health.root -eq $baseline -and $health.profile -eq 'artifacts') {
                if ($health.revision -eq $expected) { Write-Host ('UI ready: ' + $saved.url); return }
                & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stop -Url $saved.url
                if ($LASTEXITCODE -ne 0) { throw 'Owned artifacts UI shutdown failed.' }
            }
        } catch { Write-Host ('UI discovery: ' + $_.Exception.Message) }
    }
    # An inference server or unrelated listener is never stopped. Auto-port
    # selection publishes its actual endpoint in the existing server registry.
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $start + '" -Profile artifacts -NoBrowser'
    $null = Start-Process powershell.exe -ArgumentList $arguments -WindowStyle Minimized -PassThru
    for ($i=0; $i -lt 60; $i++) {
        if (Test-Path -LiteralPath $serverPath) {
            try {
                $saved = Get-Content -LiteralPath $serverPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $health = Invoke-RestMethod -Uri ($saved.url + '/api/health') -TimeoutSec 1
                if ($health.service -eq 'topic16-ui' -and $health.root -eq $baseline -and $health.profile -eq 'artifacts' -and $health.revision -eq $expected) {
                    Write-Host ('UI ready: ' + $saved.url); return
                }
            } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Computed artifacts retained; final artifacts UI did not become ready.'
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $prepare
if ($LASTEXITCODE -ne 0) { throw 'Final UI catalog preparation failed; computation is retained.' }
Ensure-ArtifactServer
& (Join-Path $ProjectRoot 'Invoke-Upgrade.ps1') final-ui-check -Study $Study
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $prepare
if ($LASTEXITCODE -ne 0) { throw 'Final completion catalog preparation failed.' }
Ensure-ArtifactServer
