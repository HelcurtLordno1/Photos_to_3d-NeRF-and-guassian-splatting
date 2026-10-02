[CmdletBinding()]
param([Parameter(Mandatory)][string]$Directory, [switch]$Resume)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$Directory = [IO.Path]::GetFullPath($Directory)
$job = Get-Content -LiteralPath (Join-Path $Directory 'job.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$hostSettings = Get-Content -LiteralPath (Join-Path $Directory 'host.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$env:TOPIC16_CONDA_EXE = $hostSettings.conda
if ($hostSettings.cuda_path) { $env:CUDA_PATH = $hostSettings.cuda_path }
$statePath = Join-Path $Directory 'state.json'
$logPath = Join-Path $Directory 'console.log'
$state = [ordered]@{ name = $job.name; status = 'running'; pid = $PID; started_at = [DateTime]::UtcNow.ToString('o'); task = $job.task }
$env:TOPIC16_SESSION_DIRECTORY = $Directory
Set-Location -LiteralPath $ProjectRoot
# Exclusive OS handle prevents two launches from owning one session state.
$workerLock = [IO.File]::Open((Join-Path $Directory 'worker.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
function Write-SessionLog($Value) {
    $text = [string]$Value
    [IO.File]::AppendAllText($logPath, $text + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}
Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
try {
    $administrator = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $administrator) { throw 'Worker requires Administrator; no workload started.' }
    $saved = Get-Content -LiteralPath (Join-Path $Directory 'settings.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if (($saved | ConvertTo-Json -Depth 15 -Compress) -cne (($Config | ConvertTo-Json -Depth 15 | ConvertFrom-Json) | ConvertTo-Json -Depth 15 -Compress)) {
        throw 'Session registry changed. Preserve the session and use the exact recorded registry to resume.'
    }
    Write-SessionLog "[$([DateTime]::UtcNow.ToString('o'))] $($job.task) worker PID=$PID Administrator=$administrator Resume=$Resume"
    & {
        switch ($job.task) {
            'research' {
                $parameters = @{ SessionDirectory = (Join-Path $ArtifactRoot ('logs\research\' + $job.name)); CustomScene = $job.custom_scene }
                if ($Resume) { $parameters.Resume = $true }
                if ($job.review) { $parameters.ReviewPath = $job.review }
                & (Join-Path $PSScriptRoot 'Run-Research.ps1') @parameters
            }
            'benchmark' {
                $parameters = @{ Scenes = @($job.scenes); MatrixPath = (Join-Path $ArtifactRoot ('logs\matrices\' + $job.name + '.json')); Protocol = $job.protocol }
                if ($Resume) { $parameters.Resume = $true }
                if ($job.iterations -gt 0) { $parameters.Iterations = $job.iterations }
                & (Join-Path $PSScriptRoot 'Run-Benchmark.ps1') @parameters
            }
            'train' {
                $parameters = @{ Method = $job.method; Dataset = $job.dataset; Protocol = $job.protocol; ResultPath = (Join-Path $Directory 'result.json') }
                if ($job.iterations -gt 0) { $parameters.Iterations = $job.iterations }
                $active = Join-Path $Directory 'active-run.json'
                if ($Resume -and (Test-Path -LiteralPath $active)) {
                    $record = Get-Content -LiteralPath $active -Raw -Encoding UTF8 | ConvertFrom-Json
                    if (Test-Path -LiteralPath (Join-Path $ProjectRoot $record.resume_record)) { $parameters.ResumeConfigPath = Join-Path $ProjectRoot $record.config }
                }
                & (Join-Path $PSScriptRoot 'Train.ps1') @parameters
            }
            'inference' {
                $parameters = @{ ConfigPath = $job.config }
                switch ($job.operation) {
                    'evaluate' { & (Join-Path $PSScriptRoot 'Evaluate-Run.ps1') @parameters }
                    'render' {
                        if ($job.camera_path) { $parameters.CameraPath = $job.camera_path }
                        & (Join-Path $PSScriptRoot 'Render-Run.ps1') @parameters
                    }
                    'export' { & (Join-Path $PSScriptRoot 'Export-Run.ps1') @parameters }
                    default { throw 'Unknown inference operation in saved job.' }
                }
            }
            'runtime' { & (Join-Path $PSScriptRoot 'Test-Runtime.ps1') }
            'demo' { & (Join-Path $PSScriptRoot 'Start-Demo.ps1') -ModelPath $job.model }
        }
    } *>&1 | ForEach-Object { Write-SessionLog $_ }
    $state.status = 'succeeded'
    if ($job.task -eq 'research') {
        $research = Get-Content -LiteralPath (Join-Path $ArtifactRoot ('logs\research\' + $job.name + '\session.json')) -Raw -Encoding UTF8 | ConvertFrom-Json
        $state.status = $research.status
    }
} catch {
    $state.status = if (Test-Path -LiteralPath (Join-Path $Directory 'stop.json')) { 'paused' } else { 'failed' }
    $state.reason = $_.Exception.Message
    Write-SessionLog $_
} finally {
    $state.finished_at = [DateTime]::UtcNow.ToString('o')
    Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
    Write-SessionLog "Worker finished: $($state.status)"
    $workerLock.Dispose()
}
