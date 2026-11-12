[CmdletBinding()]
param([Parameter(Mandatory)][string]$Directory, [switch]$Resume)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$Directory = [IO.Path]::GetFullPath($Directory)
$lock = [IO.File]::Open((Join-Path $Directory 'worker.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$job = Get-Content -LiteralPath (Join-Path $Directory 'job.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$hostRecord = Get-Content -LiteralPath (Join-Path $Directory 'host.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$env:TOPIC16_CONDA_EXE = $hostRecord.conda
$env:TOPIC16_SESSION_DIRECTORY = $Directory
$env:PYTHONUTF8 = '1'
$state = @{ status='running'; pid=$PID; name=$job.name; study=$job.study; started_at=[DateTime]::UtcNow.ToString('o') }
$statePath = Join-Path $Directory 'state.json'
$log = Join-Path $Directory 'console.log'
function Write-Log($Value) { [IO.File]::AppendAllText($log, [string]$Value + [Environment]::NewLine, [Text.UTF8Encoding]::new($false)) }
try {
    Set-Location -LiteralPath $ProjectRoot
    Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
    Write-Log "Native Capture Intelligence worker PID=$PID Resume=$Resume"
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw 'GPU worker requires Administrator for the clock safety guard.' }
    $parameters = @{ Study=$job.study; Resume=$Resume }
    if ($job.split_path) { $parameters.SplitPath=$job.split_path }
    $command = 'run'
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'full') { $command = 'full-run' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'quality') { $command = 'quality-run' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'research') { $command = 'research-run' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'confirmation') { $command = 'confirmation-run' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'final') { $command = 'final-run' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'teacher') { $command = 'teacher-run' }
    & (Join-Path $ProjectRoot 'Invoke-Upgrade.ps1') $command @parameters *>&1 | ForEach-Object { Write-Log $_ }
    $state.status = 'succeeded'
    # Publish into the one existing UI cache after successful compute. This
    # independently uses the UI's registered baseline environment, never installs packages.
    $prepare = Join-Path $hostRecord.BaselineRoot 'UI_design\scripts\Prepare-UIAssets.ps1'
    if (Test-Path -LiteralPath $prepare) {
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $prepare *>&1 | ForEach-Object { Write-Log $_ }
            if ($LASTEXITCODE -ne 0) { throw 'Shared catalog preparation failed.' }
            $state.ui_catalog = 'prepared'
            if ($job.PSObject.Properties['task'] -and $job.task -in @('research','confirmation','final','teacher')) {
                # Refresh only this checkout's artifacts-only server. A running
                # inference server or another service is never stopped here.
                $serverPath = Join-Path $hostRecord.BaselineRoot 'artifacts\ui\server.json'
                if (Test-Path -LiteralPath $serverPath) {
                    try {
                        $serverRecord = Get-Content -LiteralPath $serverPath -Raw -Encoding UTF8 | ConvertFrom-Json
                        $health = Invoke-RestMethod -Uri ($serverRecord.url + '/api/health') -TimeoutSec 2
                        if ($health.service -eq 'topic16-ui' -and $health.root -eq $hostRecord.BaselineRoot -and $health.profile -eq 'artifacts') {
                            $stopUi = Join-Path $hostRecord.BaselineRoot 'UI_design\scripts\Stop-UI.ps1'
                            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopUi -Url $serverRecord.url *>&1 | ForEach-Object { Write-Log $_ }
                            if ($LASTEXITCODE -ne 0) { throw 'Owned artifacts UI did not stop.' }
                            $closed = $false
                            for ($i=0; $i -lt 30; $i++) {
                                try { $null = Invoke-RestMethod -Uri ($serverRecord.url + '/api/health') -TimeoutSec 1 }
                                catch { $closed = $true; break }
                                Start-Sleep -Milliseconds 200
                            }
                            if (-not $closed) { throw 'Owned artifacts UI has not closed; manual restart required.' }
                            $startUi = Join-Path $hostRecord.BaselineRoot 'UI_design\scripts\Start-UI.ps1'
                            $uiPort = ([uri]$serverRecord.url).Port
                            $uiArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $startUi + '" -Port ' + $uiPort + ' -Profile artifacts -NoBrowser'
                            $null = Start-Process powershell.exe -ArgumentList $uiArguments -WindowStyle Minimized -PassThru
                            $catalogPath = Join-Path $hostRecord.BaselineRoot 'artifacts\ui\catalog.json'
                            $expectedRevision = (Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json).catalog.revision
                            $refreshed = $false
                            for ($i=0; $i -lt 30; $i++) {
                                try {
                                    $newHealth = Invoke-RestMethod -Uri ($serverRecord.url + '/api/health') -TimeoutSec 1
                                    if ($newHealth.service -eq 'topic16-ui' -and $newHealth.revision -eq $expectedRevision -and $newHealth.profile -eq 'artifacts') { $refreshed = $true; break }
                                } catch {}
                                Start-Sleep -Milliseconds 500
                            }
                            if (-not $refreshed) { throw 'Catalog prepared; UI refresh did not become healthy in time.' }
                            $state.ui_catalog = 'prepared-artifacts-ui-refreshed'
                        }
                    } catch { $state.ui_catalog = 'prepared-restart-ui-if-needed'; Write-Log $_ }
                }
            }
        } catch { $state.ui_catalog = 'needs-prepare'; Write-Log $_ }
    }
    if ($job.PSObject.Properties['task'] -and $job.task -in @('final','teacher')) {
        # CUDA computation has ended. Let the production UI render its models
        # while the guarded browser acceptance runs; this is not timed training.
        $state.status = 'ui-review'
        Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
        $deliveryStudy = $job.study
        if ($job.task -eq 'teacher') { $deliveryStudy = 'final-quality-v1' }
        & (Join-Path $PSScriptRoot 'Complete-FinalUI.ps1') -Study $deliveryStudy *>&1 | ForEach-Object { Write-Log $_ }
        $state.status = 'succeeded'
        $state.ui_catalog = 'all-scenes-browser-verified-and-refreshed'
    }
} catch {
    $state.status = 'failed'
    if (Test-Path -LiteralPath (Join-Path $Directory 'stop.json')) { $state.status = 'paused' }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'teacher') {
        $teacherStatePath = Join-Path $ArtifactRoot ('jobs\teacher\' + $job.study + '\state.json')
        if (Test-Path -LiteralPath $teacherStatePath) {
            $stageState = Get-Content -LiteralPath $teacherStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($stageState.status -eq 'paused') { $state.status = 'paused' }
        }
    }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'final') {
        $finalState = Join-Path $ArtifactRoot ('jobs\final\' + $job.study + '\state.json')
        if (Test-Path -LiteralPath $finalState) {
            $stageState = Get-Content -LiteralPath $finalState -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($stageState.status -eq 'paused') { $state.status = 'paused' }
        }
    }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'confirmation') {
        $confirmationState = Join-Path $ArtifactRoot ('jobs\confirmation\' + $job.study + '\state.json')
        if (Test-Path -LiteralPath $confirmationState) {
            $stageState = Get-Content -LiteralPath $confirmationState -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($stageState.status -eq 'paused') { $state.status = 'paused' }
        }
    }
    if ($job.PSObject.Properties['task'] -and $job.task -eq 'research') {
        $researchState = Join-Path $ArtifactRoot ('jobs\research\' + $job.study + '\state.json')
        if (Test-Path -LiteralPath $researchState) {
            $stageState = Get-Content -LiteralPath $researchState -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($stageState.status -eq 'paused') { $state.status = 'paused' }
        }
    }
    $state.reason = $_.Exception.Message
    Write-Log $_
} finally {
    $state.finished_at = [DateTime]::UtcNow.ToString('o')
    Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
    Write-Log "Worker finished: $($state.status)"
    $lock.Dispose()
}
