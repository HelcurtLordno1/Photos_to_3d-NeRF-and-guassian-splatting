[CmdletBinding()]
param(
    [ValidateSet('Start','Resume','Stop','Status','Attach')][string]$Action = 'Status',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Name = 'topic16-upgrade',
    [string]$Study = 'tea60-v1',
    [ValidateSet('study','full','quality','research')][string]$Task = 'study',
    [string]$SplitPath
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$directory = Join-Path $ArtifactRoot ('logs\sessions\' + $Name)
$statePath = Join-Path $directory 'state.json'
$jobPath = Join-Path $directory 'job.json'
if ($Action -eq 'Attach') {
    & wsl.exe --exec tmux attach-session -t $Name
    if ($LASTEXITCODE -ne 0) { throw 'Tmux attach failed.' }
    return
}
if ($Action -eq 'Status') {
    if (-not (Test-Path -LiteralPath $statePath)) { throw 'Session state does not exist.' }
    Get-Content -LiteralPath $statePath -Raw -Encoding UTF8
    $active = Join-Path $directory 'active-run.json'
    if (Test-Path -LiteralPath $active) { Get-Content -LiteralPath $active -Raw -Encoding UTF8 }
    if (Test-Path -LiteralPath $jobPath) {
        $savedJob = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($savedJob.PSObject.Properties['task'] -and $savedJob.task -eq 'research') {
            $researchState = Join-Path $ArtifactRoot ('jobs\research\' + $savedJob.study + '\state.json')
            if (Test-Path -LiteralPath $researchState) {
                Get-Content -LiteralPath $researchState -Raw -Encoding UTF8 | ConvertFrom-Json |
                    Select-Object study,status,phase,updated_at,error | ConvertTo-Json
            }
            foreach ($method in @('absgs','improvedgs')) {
                $progress = Join-Path $ArtifactRoot ('research\' + $savedJob.study + '\runs\' + $method + '\progress.json')
                if (Test-Path -LiteralPath $progress) { Write-Host $method; Get-Content -LiteralPath $progress -Raw -Encoding UTF8 }
            }
        }
    }
    return
}
if ($Action -eq 'Stop') {
    if (-not (Test-Path -LiteralPath $statePath)) { throw 'Unknown session.' }
    $previous = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($previous.status -notin @('starting','running')) { Write-TopicInfo "Worker already stopped: $($previous.status). Use Status to inspect it."; return }
    Write-Utf8Text -Path (Join-Path $directory 'stop.json') -Text '{"requested":true}'
    Write-TopicInfo 'Checkpoint stop requested. Wait for state=paused before shutdown.'
    return
}
& wsl.exe --exec tmux -V
if ($LASTEXITCODE -ne 0) { throw 'Install tmux in the active WSL distribution before Start.' }
if ($Action -eq 'Start') {
    if (Test-Path -LiteralPath $jobPath) { throw 'Session already exists. Use Resume.' }
    if ($Task -eq 'research') {
        if (-not (Test-Path -LiteralPath (Join-Path $ArtifactRoot ("jobs\research\" + $Study + '\declaration.json')))) { throw 'Run research-plan before starting the research study.' }
    } elseif ($Task -eq 'quality') {
        if (-not (Test-Path -LiteralPath (Join-Path $ArtifactRoot ("jobs\quality\" + $Study + '.json')))) { throw 'Run quality-plan before starting the quality study.' }
    } elseif ($Task -eq 'full') {
        if (-not (Test-Path -LiteralPath (Join-Path $ArtifactRoot ("jobs\campaigns\" + $Study + '.json')))) { throw 'Run full-plan before starting the full campaign.' }
    } elseif (-not $Config.Studies.ContainsKey($Study) -and -not (Test-Path -LiteralPath (Join-Path $ArtifactRoot ("jobs\definitions\" + $Study + '.json')))) { throw 'Unknown study.' }
    New-TopicDirectory -Path $directory
    $job = @{ name=$Name; study=$Study; task=$Task; split_path=$SplitPath; created_at=[DateTime]::UtcNow.ToString('o') }
    Write-Utf8Text -Path $jobPath -Text ($job | ConvertTo-Json)
} else {
    if (-not (Test-Path -LiteralPath $jobPath)) { throw 'No saved job to Resume.' }
    if (Test-Path -LiteralPath $statePath) {
        $previous = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($previous.status -eq 'succeeded') { Write-TopicInfo 'Session completed; inspect Status/Attach.'; return }
        if ($previous.status -in @('starting','running') -and (Get-Process -Id $previous.pid -ErrorAction SilentlyContinue)) {
            throw 'Worker still active. Stop and wait for paused before Resume.'
        }
    }
}
$configuredHost = Join-Path $ArtifactRoot 'logs\host.json'
if (Test-Path -LiteralPath $configuredHost) {
    $hostRecord = Get-Content -LiteralPath $configuredHost -Raw -Encoding UTF8 | ConvertFrom-Json
} else { throw 'Run Setup-Upgrade.ps1 first.' }
Write-Utf8Text -Path (Join-Path $directory 'host.json') -Text ($hostRecord | ConvertTo-Json)
# Native worker owns compute. Tmux only tails its UTF-8 log through a CPU process.
function Quote-Posix([string]$Value) {
    $q = [string][char]39
    return $q + $Value.Replace($q, ($q + [char]34 + $q + [char]34 + $q)) + $q
}
$watch = Join-Path $PSScriptRoot 'Watch-Session.ps1'
$console = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File ' + (Quote-Posix $watch) + ' -Directory ' + (Quote-Posix $directory)
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& wsl.exe --exec tmux has-session -t $Name 2>$null
$exists = $LASTEXITCODE -eq 0
$ErrorActionPreference = $previousPreference
if (-not $exists) {
    & wsl.exe --exec tmux new-session -d -s $Name $console
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start tmux console.' }
}
$stop = Join-Path $directory 'stop.json'
if (Test-Path -LiteralPath $stop) { Remove-Item -LiteralPath $stop }
$worker = Join-Path $PSScriptRoot 'Session-Worker.ps1'
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $worker + '" -Directory "' + $directory + '"'
if ($Action -eq 'Resume') { $arguments += ' -Resume' }
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($admin) { $process = Start-Process powershell.exe -ArgumentList $arguments -WindowStyle Minimized -PassThru }
else { $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -WindowStyle Minimized -PassThru }
Write-TopicInfo "Native worker launched PID=$($process.Id). tmux attach -t $Name"
