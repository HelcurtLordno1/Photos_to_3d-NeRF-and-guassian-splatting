[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$validator = Join-Path $PSScriptRoot '..\scripts\Test-RunManifest.ps1'
$writer = Join-Path $PSScriptRoot '..\scripts\Write-RunManifest.ps1'
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('topic16 space ' + [char]0x00E1 + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null

function Assert-Case {
    param([string]$Name, $Data, [bool]$ExpectedValid)
    $path = Join-Path $fixtureRoot "$Name.json"
    $Data | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8
    $passed = $true
    try { & $validator -Path $path | Out-Null } catch { $passed = $false }
    if ($passed -ne $ExpectedValid) { throw "Case $Name expected valid=$ExpectedValid, got valid=$passed" }
    Write-Host "[ok] $Name"
}

try {
    $base = @{
        schema_version = '1.0'
        run_key = 'garden/nerfacto/20260927T145759000Z'
        scene = 'garden'
        method = 'nerfacto'
        status = 'succeeded'
        started_at = '2026-09-27T14:00:00Z'
        finished_at = '2026-09-27T15:00:00Z'
        provenance = @{ git_commit_sha = 'a1b2c3d'; dataset_split_hash = ('a' * 64) }
        protocol = @{ iterations = 30000; downscale_factor = 2; seed = 42 }
        execution_metrics = @{ wall_time_seconds = 3600 }
        artifacts = @{ config_path = 'artifacts/runs/garden/nerfacto/20260927T145759000Z/config.yml'; checkpoint_dir = 'artifacts/runs/garden/nerfacto/20260927T145759000Z/nerfstudio_models' }
    }
    Assert-Case 'valid-success' $base $true
    $failed = $base.Clone(); $failed.status = 'failed'; $failed.failure_reason = 'CUDA OOM'
    Assert-Case 'valid-failure' $failed $true
    $custom = $base.Clone(); $custom.scene = 'custom:object_v1'; $custom.run_key = 'custom-object_v1/nerfacto/20260927T145759000Z'
    $custom.artifacts = @{ config_path = 'artifacts/runs/custom-object_v1/nerfacto/20260927T145759000Z/config.yml'; checkpoint_dir = 'artifacts/runs/custom-object_v1/nerfacto/20260927T145759000Z/nerfstudio_models' }
    Assert-Case 'valid-custom' $custom $true
    $extra = $base.Clone(); $extra.extra = 'unrecognized'
    Assert-Case 'unknown-key' $extra $false
    $badStatus = $base.Clone(); $badStatus.status = 'failed'; $badStatus.Remove('finished_at')
    Assert-Case 'missing-finish' $badStatus $false
    $mismatch = $base.Clone(); $mismatch.method = 'splatfacto'
    Assert-Case 'wrong-run-key' $mismatch $false
    $badHash = $base.Clone(); $badHash.provenance = @{ git_commit_sha = 'a1b2c3d'; dataset_split_hash = 'not-a-hash' }
    Assert-Case 'bad-split-hash' $badHash $false
    $badTime = $base.Clone(); $badTime.finished_at = '2026-09-27T13:00:00Z'
    Assert-Case 'time-reversed' $badTime $false
    $wrongVersion = $base.Clone(); $wrongVersion.schema_version = '2.0'
    Assert-Case 'wrong-schema-version' $wrongVersion $false
    $missingArtifacts = $base.Clone(); $missingArtifacts.Remove('artifacts')
    Assert-Case 'missing-success-artifacts' $missingArtifacts $false
    $artifactRoot = Join-Path $fixtureRoot 'artifacts'
    & $writer -InputPath (Join-Path $fixtureRoot 'valid-success.json') -ArtifactsDirectory $artifactRoot | Out-Null
    $saved = Join-Path $artifactRoot 'logs\garden\nerfacto\20260927T145759000Z\manifest.json'
    if (-not (Test-Path -LiteralPath $saved)) { throw 'Writer mapped run key to the wrong artifact path.' }
    $duplicateRejected = $false
    try { & $writer -InputPath (Join-Path $fixtureRoot 'valid-success.json') -ArtifactsDirectory $artifactRoot | Out-Null }
    catch { $duplicateRejected = $true }
    if (-not $duplicateRejected) { throw 'Writer overwrote a completed manifest.' }
    Write-Host '[ok] Path mapping with spaces/Unicode and immutable completed run.'
    $running = $base.Clone(); $running.run_key = 'room/nerfacto/20260927T145759000Z'; $running.scene = 'room'
    $running.Remove('finished_at'); $running.Remove('artifacts'); $running.Remove('execution_metrics'); $running.status = 'running'
    Assert-Case 'valid-running' $running $true
    & $writer -InputPath (Join-Path $fixtureRoot 'valid-running.json') -ArtifactsDirectory $artifactRoot | Out-Null
    $terminal = $running.Clone(); $terminal.status = 'failed'; $terminal.failure_reason = 'fixture error'; $terminal.finished_at = '2026-09-27T15:00:00Z'
    Assert-Case 'valid-transition' $terminal $true
    & $writer -InputPath (Join-Path $fixtureRoot 'valid-transition.json') -ArtifactsDirectory $artifactRoot | Out-Null
    $terminalPath = Join-Path $artifactRoot 'logs\room\nerfacto\20260927T145759000Z\manifest.json'
    if ((Get-Content -LiteralPath $terminalPath -Raw | ConvertFrom-Json).status -ne 'failed') {
        throw 'Writer did not atomically replace running with terminal status.'
    }
    Write-Host '[ok] Running-to-failed transition saved.'
    Write-Host '[topic16] Manifest contract tests passed.'
} finally {
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
}
