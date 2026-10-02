param([int]$Port = 0, [switch]$NoBrowser, [ValidateSet('auto','artifacts','inference')][string]$Profile = 'auto')
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
if (-not (Test-Path -LiteralPath (Join-Path $UiRoot 'dist\index.html'))) { throw 'Build UI first: UI_design\scripts\Build-UI.ps1' }
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'artifacts\ui\catalog.json'))) { throw 'Prepare assets first: UI_design\scripts\Prepare-UIAssets.ps1' }
$ports = if ($Port) { @($Port) } else { $script:Config.Ui.Port..$script:Config.Ui.MaxPort }
$localCatalog = Get-Content -LiteralPath (Join-Path $RepoRoot 'artifacts\ui\catalog.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($candidate in $ports) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$candidate/api/health" -TimeoutSec 2
        if ($health.service -eq 'topic16-ui' -and $health.root -eq $RepoRoot -and $health.revision -eq $localCatalog.catalog.revision -and ($Profile -eq 'auto' -or $Profile -eq $health.profile)) {
            Write-Host "UI is running at $($health.url)"
            if (-not $NoBrowser) { Start-Process $health.url }
            return
        }
    } catch {}
}
# Open after the server publishes its actual port, never guess the URL.
if (-not $NoBrowser) {
    $state = Join-Path $RepoRoot 'artifacts\ui\server.json'
    Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
    Start-Job -ArgumentList $state -ScriptBlock {
        param($state)
        for ($i = 0; $i -lt 120; $i++) {
            if (Test-Path -LiteralPath $state) {
                $server = Get-Content -LiteralPath $state -Raw | ConvertFrom-Json
                Start-Process $server.url; break
            }
            Start-Sleep -Milliseconds 500
        }
    } | Out-Null
}
$arguments = @('serve','--profile',$Profile)
if ($Port) { $arguments += @('--port', [string]$Port) }
Invoke-UiPython -Arguments $arguments
