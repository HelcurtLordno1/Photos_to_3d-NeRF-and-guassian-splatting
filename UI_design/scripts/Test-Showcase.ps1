[CmdletBinding()]
param([string]$Directory)
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
if (-not $Directory) { $Directory = Join-Path $RepoRoot ('artifacts\ui\qa\showcase-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')) }
New-Item -ItemType Directory -Path $Directory -Force | Out-Null
$settings = Join-Path $Directory 'settings.json'
$status = @{status='running';pid=$PID;started_at=[DateTime]::UtcNow.ToString('o')}
$state = Join-Path $Directory 'state.json'
$log = Join-Path $Directory 'console.log'
try {
    Write-Utf8Text -Path $state -Text ($status | ConvertTo-Json)
    Write-Utf8Text -Path $settings -Text ($script:Config | ConvertTo-Json -Depth 20)
    $env:MKL_THREADING_LAYER = 'SEQUENTIAL'
    $env:OMP_NUM_THREADS = '4'
    Invoke-UiEnvironment -Command python -Arguments @((Join-Path $UiRoot 'tests\showcase_guard.py'),'--root',$RepoRoot,'--settings',$settings,'--directory',$Directory,'--node',(Get-UiNode)) *>&1 | ForEach-Object {
        [IO.File]::AppendAllText($log, [string]$_ + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    }
    $status.status='passed'
} catch {
    $status.status='failed'; $status.error=$_.Exception.Message
    [IO.File]::AppendAllText($log, [string]$_ + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
} finally {
    $status.finished_at=[DateTime]::UtcNow.ToString('o')
    Write-Utf8Text -Path $state -Text ($status | ConvertTo-Json)
}
if ($status.status -ne 'passed') { exit 1 }
