param([string]$Url)
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
if (-not $Url) {
    $state = Get-Content -LiteralPath (Join-Path $RepoRoot 'artifacts\ui\server.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $Url = $state.url
}
$health = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 3
if ($health.service -ne 'topic16-ui' -or $health.root -ne $RepoRoot) { throw 'Refusing to stop a different service or checkout.' }
$catalog = Invoke-RestMethod -Uri "$Url/api/catalog" -TimeoutSec 3
Invoke-RestMethod -Uri "$Url/api/shutdown" -Method Post -Headers @{ Origin=$Url; 'X-UI-CSRF'=$catalog.csrf } -ContentType 'application/json' -Body '{}' | Out-Null
Write-Host "Stopping $Url; owned GPU worker will unwind safely."
