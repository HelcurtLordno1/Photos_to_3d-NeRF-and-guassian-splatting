[CmdletBinding()]
param([string]$Directory)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
if (-not $Directory) { $Directory = Join-Path $ArtifactRoot ('teacher\qa-launch-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')) }
New-TopicDirectory -Path $Directory
$status = @{ status='running'; pid=$PID; started_at=[DateTime]::UtcNow.ToString('o') }
$statePath = Join-Path $Directory 'state.json'
$log = Join-Path $Directory 'console.log'
try {
    Write-Utf8Text -Path $statePath -Text ($status | ConvertTo-Json)
    & (Join-Path $ProjectRoot 'Invoke-Upgrade.ps1') teacher-qa -Study teacher-room-v1 *>&1 | ForEach-Object {
        [IO.File]::AppendAllText($log, [string]$_ + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    }
    $status.status='passed'
} catch {
    $status.status='failed'; $status.error=$_.Exception.Message
    [IO.File]::AppendAllText($log, [string]$_ + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
} finally {
    $status.finished_at=[DateTime]::UtcNow.ToString('o')
    Write-Utf8Text -Path $statePath -Text ($status | ConvertTo-Json)
}
if ($status.status -ne 'passed') { exit 1 }
