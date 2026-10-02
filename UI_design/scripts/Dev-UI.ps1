. (Join-Path $PSScriptRoot 'Common-UI.ps1')
$start = Join-Path $PSScriptRoot 'Start-UI.ps1'
$expectedCatalog = Get-Content -LiteralPath (Join-Path $RepoRoot 'artifacts\ui\catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$existing = @()
foreach ($port in $script:Config.Ui.Port..$script:Config.Ui.MaxPort) {
    try { $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 1; if ($health.service -eq 'topic16-ui') { $existing += $health.pid } } catch {}
}
$job = Start-Job -ArgumentList $start -ScriptBlock { param($start); & $start -NoBrowser }
$oldBackend = $env:TOPIC16_UI_BACKEND
$ownedUrl = $null
try {
    $ready = $false
    for ($i=0; $i -lt 60; $i++) {
        try {
            $state = Get-Content -LiteralPath (Join-Path $RepoRoot 'artifacts\ui\server.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $health = Invoke-RestMethod "$($state.url)/api/health" -TimeoutSec 1
            if ($health.service -eq 'topic16-ui' -and $health.root -eq $RepoRoot -and $health.revision -eq $expectedCatalog.catalog.revision) {
                $env:TOPIC16_UI_BACKEND=$health.url
                if ($health.pid -notin $existing) { $ownedUrl=$health.url }
                $ready=$true; break
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'UI backend did not become ready.' }
    Invoke-UiNpm -Arguments @('run','dev')
} finally {
    $env:TOPIC16_UI_BACKEND=$oldBackend
    if ($ownedUrl) { & (Join-Path $PSScriptRoot 'Stop-UI.ps1') -Url $ownedUrl }
    Stop-Job $job -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
}
