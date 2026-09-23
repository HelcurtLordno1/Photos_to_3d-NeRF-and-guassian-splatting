[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('nerfacto', 'splatfacto')][string]$Method,
    [Parameter(Mandatory)][string]$Dataset,
    [Parameter(ValueFromRemainingArguments)][string[]]$ExtraArguments
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

$evalMode = 'interval'
switch -Regex ($Dataset) {
    '^poster$' {
        $dataDirectory = Join-Path $ProcessedDataRoot 'nerfstudio\poster'
        $parser = 'nerfstudio-data'
    }
    '^(garden|bonsai|room)$' {
        $dataDirectory = Join-Path $RawDataRoot "mipnerf360\$Dataset"
        $parser = 'colmap'
    }
    '^custom:(.+)$' {
        $scene = $Matches[1]
        if ($scene -notmatch '^[a-z0-9][a-z0-9_-]*$') { throw 'Custom scene name is invalid.' }
        $dataDirectory = Join-Path $ProcessedDataRoot "custom\$scene"
        $parser = 'nerfstudio-data'
        $transform = Join-Path $dataDirectory 'transforms.json'
        if (-not (Test-Path -LiteralPath $transform) -or -not (Select-String -LiteralPath $transform -Pattern 'frame_eval_' -Quiet)) {
            throw 'Custom scene requires a processed transforms.json with held-out evaluation frames.'
        }
        $evalMode = 'filename'
    }
    default { throw 'Dataset must be poster, garden, bonsai, room, or custom:<name>.' }
}

if (-not (Test-Path -LiteralPath $dataDirectory -PathType Container)) { throw "Dataset is missing: $dataDirectory" }
if ($parser -eq 'nerfstudio-data' -and -not (Test-Path -LiteralPath (Join-Path $dataDirectory 'transforms.json'))) {
    throw "Missing transforms.json in $dataDirectory"
}
if ($parser -eq 'colmap' -and -not (Test-Path -LiteralPath (Join-Path $dataDirectory 'sparse\0'))) {
    throw "Missing COLMAP sparse\0 in $dataDirectory"
}
$imagesDirectory = if ($Config.DownscaleFactor -eq 1) { 'images' } else { "images_$($Config.DownscaleFactor)" }
if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory $imagesDirectory))) {
    throw "Missing $imagesDirectory in $dataDirectory"
}

$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$runName = $Dataset.Replace(':', '-')
$runDirectory = Join-Path $ArtifactRoot "runs\$runName\$Method\$runId"
$logDirectory = Join-Path $ArtifactRoot "logs\$runName\$Method\$runId"
if (Test-Path -LiteralPath $runDirectory) { throw "Run directory already exists: $runDirectory" }
New-TopicDirectory -Path $runDirectory
New-TopicDirectory -Path $logDirectory

$monitor = $null
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $monitorScript = Join-Path $PSScriptRoot 'Monitor-Gpu.ps1'
    $monitor = Start-Process powershell.exe -ArgumentList @(
        '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$monitorScript`"",
        '-Output', "`"$(Join-Path $logDirectory 'gpu.csv')`"", '-IntervalSeconds', $Config.GpuSampleSeconds
    ) -PassThru -WindowStyle Hidden
}

try {
    @(
        "method=$Method", "dataset=$Dataset", "data_dir=$dataDirectory",
        "iterations=$($Config.TrainIterations)", "downscale=$($Config.DownscaleFactor)",
        "eval_mode=$evalMode", "seed=$($Config.RandomSeed)"
    ) | Set-Content -LiteralPath (Join-Path $logDirectory 'run.env') -Encoding utf8
    & git -C $ProjectRoot status --short -- . 2>$null | Set-Content -LiteralPath (Join-Path $logDirectory 'git-status.txt') -Encoding utf8
    & nvidia-smi -q 2>$null | Set-Content -LiteralPath (Join-Path $logDirectory 'nvidia-smi.txt') -Encoding utf8

    $arguments = @(
        'run', '--no-capture-output', '-n', $Config.EnvironmentName, 'ns-train', $Method,
        '--output-dir', (Join-Path $ArtifactRoot 'runs'), '--experiment-name', $runName, '--timestamp', $runId,
        '--max-num-iterations', [string]$Config.TrainIterations,
        '--machine.seed', [string]$Config.RandomSeed, '--vis', 'tensorboard'
    )
    if ($ExtraArguments) { $arguments += $ExtraArguments }
    $arguments += @(
        $parser, '--data', $dataDirectory, '--downscale-factor', [string]$Config.DownscaleFactor,
        '--eval-mode', $evalMode
    )
    if ($parser -eq 'colmap') { $arguments += @('--colmap-path', 'sparse/0') }
    if ($evalMode -eq 'interval') { $arguments += @('--eval-interval', [string]$Config.EvalInterval) }
    $commandLine = ConvertTo-CommandLine -Tokens (@('conda') + $arguments)
    $commandLine | Set-Content -LiteralPath (Join-Path $logDirectory 'command.txt') -Encoding utf8
    Write-TopicInfo "Run directory: $runDirectory"
    Write-Host $commandLine

    $start = [DateTime]::UtcNow
    $conda = Get-CondaCommand
    & $conda @arguments 2>&1 | Tee-Object -FilePath (Join-Path $logDirectory 'train.log')
    $status = $LASTEXITCODE
    $end = [DateTime]::UtcNow
    @(
        "start_utc=$($start.ToString('o'))", "end_utc=$($end.ToString('o'))",
        "elapsed_seconds=$([int]($end - $start).TotalSeconds)", "exit_code=$status"
    ) | Set-Content -LiteralPath (Join-Path $logDirectory 'timing.env') -Encoding utf8
    if ($status -ne 0) { throw "Training failed with exit code $status; see $logDirectory\train.log" }
    if (-not (Test-Path -LiteralPath (Join-Path $runDirectory 'config.yml'))) {
        throw "Training exited successfully but config.yml is missing: $runDirectory"
    }
    $checkpoints = @(Get-ChildItem -LiteralPath (Join-Path $runDirectory 'nerfstudio_models') -Filter '*.ckpt' -File -ErrorAction SilentlyContinue)
    if ($checkpoints.Count -eq 0) { throw "Training exited successfully but no checkpoint exists: $runDirectory" }
} finally {
    if ($monitor -and -not $monitor.HasExited) { Stop-Process -Id $monitor.Id -Force -ErrorAction SilentlyContinue }
}
Write-TopicInfo "Training complete. Evaluate $runDirectory\config.yml with scripts\Evaluate-Run.ps1."
