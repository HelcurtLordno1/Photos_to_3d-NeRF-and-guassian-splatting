[CmdletBinding()]
param(
    [ValidateSet('Start','Resume','Stop','Status','Attach')][string]$Action = 'Status',
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Name = 'topic16-full',
    [ValidateSet('research','benchmark','train','inference','runtime','demo')][string]$Task = 'research',
    [string]$CustomScene = 'tea_sets_2',
    [string[]]$Scenes = @('poster'),
    [ValidateSet('primary','diagnostic','repeat')][string]$Protocol = 'primary',
    [int]$Iterations,
    [ValidateSet('nerfacto','splatfacto')][string]$Method = 'nerfacto',
    [string]$Dataset = 'poster',
    [ValidateSet('evaluate','render','export')][string]$Operation = 'evaluate',
    [string]$ConfigPath,
    [string]$CameraPath,
    [string]$ModelPath,
    [string]$ReviewPath
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$directory = Join-Path $ArtifactRoot ('logs\sessions\' + $Name)
$statePath = Join-Path $directory 'state.json'
$jobPath = Join-Path $directory 'job.json'
if ($Action -eq 'Status') {
    if (-not (Test-Path -LiteralPath $statePath)) { throw "No session state exists: $Name" }
    Get-Content -LiteralPath $statePath -Raw -Encoding UTF8
    $active = Join-Path $directory 'active-run.json'
    if (Test-Path -LiteralPath $active) { Get-Content -LiteralPath $active -Raw -Encoding UTF8 }
    return
}
if ($Action -eq 'Stop') {
    if (-not (Test-Path -LiteralPath $statePath)) { throw "Unknown session: $Name" }
    Write-Utf8Text -Path (Join-Path $directory 'stop.json') -Text ('{"requested_at":"' + [DateTime]::UtcNow.ToString('o') + '"}')
    Write-TopicInfo 'Stop requested. Training saves at the next completed iteration; wait for state=paused before resume.'
    return
}
if ($Action -eq 'Attach') {
    & wsl.exe --exec tmux attach-session -t $Name
    if ($LASTEXITCODE -ne 0) { throw 'Tmux attach failed; verify WSL distribution and session name.' }
    return
}
if ($Action -eq 'Start') {
    if (Test-Path -LiteralPath $jobPath) { throw 'Session already exists. Use Resume with the same name, or a new name.' }
    if ($Task -eq 'inference' -and -not $ConfigPath) { throw 'Inference requires an explicit -ConfigPath.' }
    if ($CameraPath -and ($Task -ne 'inference' -or $Operation -ne 'render')) { throw 'CameraPath applies only to inference render.' }
    New-TopicDirectory -Path $directory
    $job = [ordered]@{ name = $Name; task = $Task; custom_scene = $CustomScene; scenes = $Scenes;
        protocol = $Protocol; iterations = $Iterations; method = $Method; dataset = $Dataset;
        operation = $Operation; config = $ConfigPath; camera_path = $CameraPath;
        model = $ModelPath; review = $ReviewPath; created_at = [DateTime]::UtcNow.ToString('o') }
    if ($ConfigPath) { $job.config = (Resolve-Path -LiteralPath $ConfigPath).Path }
    if ($CameraPath) { $job.camera_path = (Resolve-Path -LiteralPath $CameraPath).Path }
    if ($ModelPath) { $job.model = (Resolve-Path -LiteralPath $ModelPath).Path }
    if ($ReviewPath) { $job.review = (Resolve-Path -LiteralPath $ReviewPath).Path }
    Write-Utf8Text -Path $jobPath -Text ($job | ConvertTo-Json -Depth 10)
    Write-Utf8Text -Path (Join-Path $directory 'settings.json') -Text ($Config | ConvertTo-Json -Depth 15)
} else {
    if (-not (Test-Path -LiteralPath $jobPath)) { throw 'Resume needs an existing session with its saved job.' }
    if (Test-Path -LiteralPath $statePath) {
        $previous = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $savedJob = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($previous.status -eq 'succeeded') { Write-TopicInfo 'Session already completed; use Status/Attach to inspect its evidence.'; return }
        if ($ReviewPath) {
            if ($savedJob.task -ne 'research') { throw 'ReviewPath applies only to research sessions.' }
            $savedJob.review = (Resolve-Path -LiteralPath $ReviewPath).Path
            Write-Utf8Text -Path $jobPath -Text ($savedJob | ConvertTo-Json -Depth 10)
        }
        if ($previous.status -in @('starting','running')) {
            $process = Get-Process -Id $previous.pid -ErrorAction SilentlyContinue
            if ($process) { throw 'Worker is still active. Detach/attach to observe it, or Stop and wait for paused.' }
        }
    }
}
$stopPath = Join-Path $directory 'stop.json'
if (Test-Path -LiteralPath $stopPath) { Remove-Item -LiteralPath $stopPath -Force }
Write-Utf8Text -Path (Join-Path $directory 'host.json') -Text (@{ conda = (Get-CondaCommand); cuda_path = $env:CUDA_PATH } | ConvertTo-Json)
# WSL/tmux is the read-only console; CUDA and Conda remain native Windows.
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$linuxRoot = (& wsl.exe --exec wslpath -u $ProjectRoot | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxRoot) { throw 'WSL/wslpath unavailable.' }
$linuxDirectory = (& wsl.exe --exec wslpath -u $directory | Out-String).Trim()
$ErrorActionPreference = 'Continue' # An absent tmux server/session is expected here.
& wsl.exe --exec tmux has-session -t $Name 2>$null
$tmuxExists = $LASTEXITCODE -eq 0
$ErrorActionPreference = 'Stop'
if (-not $tmuxExists) {
    function Quote-Posix([string]$Value) {
        $quote = [string][char]39
        $escape = $quote + [char]34 + $quote + [char]34 + $quote
        return $quote + $Value.Replace($quote, $escape) + $quote
    }
    $console = 'python3 ' + (Quote-Posix "$linuxRoot/src/topic16/cli.py") + ' --root ' + (Quote-Posix $linuxRoot) +
        ' --settings ' + (Quote-Posix "$linuxDirectory/settings.json") + ' session-watch --directory ' + (Quote-Posix $linuxDirectory)
    & wsl.exe --exec tmux new-session -d -s $Name $console
    if ($LASTEXITCODE -ne 0) { throw 'Tmux console could not be created.' }
}
$worker = Join-Path $PSScriptRoot 'Session-Worker.ps1'
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $worker + '" -Directory "' + $directory + '"'
if ($Action -eq 'Resume') { $arguments += ' -Resume' }
$administrator = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($administrator) { $process = Start-Process powershell.exe -WindowStyle Minimized -ArgumentList $arguments -PassThru }
else { $process = Start-Process powershell.exe -Verb RunAs -WindowStyle Minimized -ArgumentList $arguments -PassThru }
Write-TopicInfo "Worker launched PID=$($process.Id); tmux attach -t $Name (WSL), or Manage-Session -Action Attach -Name $Name."
