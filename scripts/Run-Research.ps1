[CmdletBinding()]
param(
    [string]$SessionDirectory,
    [switch]$Resume,
    [ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$CustomScene,
    [string]$ReviewPath,
    [ValidateSet('nerfacto', 'splatfacto')][string]$DemoMethod = 'splatfacto'
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
if (-not $SessionDirectory) {
    if ($Resume) { throw '-Resume requires the explicit -SessionDirectory from the previous attempt.' }
    $SessionDirectory = Join-Path $ArtifactRoot ('logs\research\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
}
$session = [IO.Path]::GetFullPath($SessionDirectory)
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $ArtifactRoot 'logs\research')).TrimEnd('\') + '\'
if (-not $session.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Research session must be under artifacts/logs/research.' }
New-TopicDirectory -Path $session
$statePath = Join-Path $session 'session.json'
if ((Test-Path -LiteralPath $statePath) -and -not $Resume) { throw 'Session already exists; use -Resume.' }
if ($Resume -and -not (Test-Path -LiteralPath $statePath)) { throw 'Session does not exist for resume.' }
if ($Resume) {
    $previous = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($previous.custom_scene -ne $CustomScene) { throw 'Resume requires the same custom scene selection.' }
}
$state = [ordered]@{ schema_version = '1.0'; status = 'running'; custom_scene = $CustomScene; started_at = [DateTime]::UtcNow.ToString('o') }
Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
Write-TopicInfo "Research session: $session"
try {
    if ($CustomScene) { & (Join-Path $PSScriptRoot 'Review-Capture.ps1') -Scene $CustomScene -VerifyOnly }
    & (Join-Path $PSScriptRoot 'Check-GpuSafety.ps1')
    & (Join-Path $PSScriptRoot 'Test-Project.ps1') -RequireRuntime
    & (Join-Path $PSScriptRoot 'Test-Datasets.ps1') -Mode all -WriteManifest
    $matrices = @()
    foreach ($stage in @(
        @{ name = 'poster'; scenes = @('poster') },
        @{ name = 'calibration'; scenes = @('bonsai') },
        @{ name = 'benchmark'; scenes = @('garden', 'room') }
    )) {
        $matrix = Join-Path $ArtifactRoot ('logs\matrices\' + (Split-Path $session -Leaf) + '-' + $stage.name + '.json')
        & (Join-Path $PSScriptRoot 'Run-Benchmark.ps1') -Scenes $stage.scenes -MatrixPath $matrix -Resume:(Test-Path -LiteralPath $matrix)
        $matrices += $matrix
    }
    if ($CustomScene) {
        $matrix = Join-Path $ArtifactRoot ('logs\matrices\' + (Split-Path $session -Leaf) + '-custom.json')
        & (Join-Path $PSScriptRoot 'Run-Benchmark.ps1') -Scenes @("custom:$CustomScene") -MatrixPath $matrix -Resume:(Test-Path -LiteralPath $matrix)
        $matrices += $matrix
    }
    # Measurement/export stages use configs returned by the selected matrices.
    # Existing complete artifacts are reused, never selected by modification time.
    foreach ($matrix in $matrices) {
        $record = Get-Content -LiteralPath $matrix -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($scene in $record.scenes) {
            $pair = $record.pairs.PSObject.Properties[$scene].Value
            foreach ($method in @('nerfacto', 'splatfacto')) {
                $relativeConfig = $pair.runs.PSObject.Properties[$method].Value
                $configPath = Join-Path $ProjectRoot $relativeConfig
                & (Join-Path $PSScriptRoot 'Render-Run.ps1') -ConfigPath $configPath
                & (Join-Path $PSScriptRoot 'Export-Run.ps1') -ConfigPath $configPath
            }
        }
    }
    $report = Join-Path $ProjectRoot ('reports\' + (Split-Path $session -Leaf))
    $analysisArguments = @{ MatrixPaths = $matrices; OutputDirectory = $report }
    if ($ReviewPath) { $analysisArguments.ReviewPath = $ReviewPath }
    & (Join-Path $PSScriptRoot 'Analyze-Results.ps1') @analysisArguments
    $gate = Get-Content -LiteralPath (Join-Path $report 'g-core.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $state.status = if ($gate.status -eq 'PASS') { 'succeeded' } else { 'awaiting-evidence' }
    $state.report = $report
    if ($gate.status -eq 'PASS') {
        # A reproducible demo selection is an explicit preference, not a claim
        # that one method wins the scientific comparison.
        $custom = Get-Content -LiteralPath $matrices[-1] -Raw -Encoding UTF8 | ConvertFrom-Json
        $pair = $custom.pairs.PSObject.Properties["custom:$CustomScene"].Value
        $demoRoot = Join-Path $report ('demo-' + $DemoMethod)
        New-TopicDirectory -Path $demoRoot
        $cameraPath = Join-Path $demoRoot 'camera_path.json'
        $selectedConfig = Join-Path $ProjectRoot $pair.runs.PSObject.Properties[$DemoMethod].Value
        & (Join-Path $PSScriptRoot 'Create-CameraPath.ps1') -ConfigPath $selectedConfig -OutputPath $cameraPath
        foreach ($method in @('nerfacto', 'splatfacto')) {
            & (Join-Path $PSScriptRoot 'Render-Run.ps1') -ConfigPath (Join-Path $ProjectRoot $pair.runs.PSObject.Properties[$method].Value) -CameraPath $cameraPath
        }
        $modelPath = Join-Path $demoRoot 'model.json'
        if (-not (Test-Path -LiteralPath $modelPath)) {
            & (Join-Path $PSScriptRoot 'Select-Model.ps1') -ConfigPath $selectedConfig -GatePath (Join-Path $report 'g-core.json') -CameraPath $cameraPath -OutputPath $modelPath
        }
        & (Join-Path $PSScriptRoot 'Start-Demo.ps1') -ModelPath $modelPath -HealthOnly
        $releasePath = Join-Path $demoRoot 'release.json'
        if (-not (Test-Path -LiteralPath $releasePath)) {
            & (Join-Path $PSScriptRoot 'Write-Release.ps1') -ModelPath $modelPath -OutputPath $releasePath
        }
        $state.demo_model = $modelPath
        $state.release = $releasePath
        Write-TopicInfo "Demo health/release completed. Start-Demo.ps1 -ModelPath '$modelPath' starts the local service."
    }
    Write-TopicInfo "Research jobs completed; G-Core=$($gate.status)."
} catch {
    $state.status = if ($env:TOPIC16_SESSION_DIRECTORY -and (Test-Path -LiteralPath (Join-Path $env:TOPIC16_SESSION_DIRECTORY 'stop.json'))) { 'paused' } else { 'failed' }
    $state.failure_reason = $_.Exception.Message
    throw
} finally {
    $state.finished_at = [DateTime]::UtcNow.ToString('o')
    Write-Utf8Text -Path $statePath -Text ($state | ConvertTo-Json)
}
