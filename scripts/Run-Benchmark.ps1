[CmdletBinding()]
param(
    [string[]]$Scenes = @('garden', 'bonsai', 'room'),
    [switch]$SkipTraining,
    [switch]$SkipEvaluation
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
foreach ($scene in $Scenes) {
    if ($scene -notin @('garden', 'bonsai', 'room')) { throw "Unsupported benchmark scene: $scene" }
    foreach ($method in @('nerfacto', 'splatfacto')) {
        if (-not $SkipTraining) {
            & (Join-Path $PSScriptRoot 'Train.ps1') -Method $method -Dataset $scene
        }
        if (-not $SkipEvaluation) {
            $runRoot = Join-Path $ArtifactRoot "runs\$scene\$method"
            $config = Get-ChildItem -LiteralPath $runRoot -Filter config.yml -File -Recurse | Sort-Object FullName | Select-Object -Last 1
            if (-not $config) { throw "No config.yml found for $scene/$method" }
            & (Join-Path $PSScriptRoot 'Evaluate-Run.ps1') -ConfigPath $config.FullName
        }
    }
}
Write-TopicInfo 'Requested paired benchmark matrix completed.'
