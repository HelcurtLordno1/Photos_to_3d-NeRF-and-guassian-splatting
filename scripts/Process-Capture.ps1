[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Scene,
    [Parameter(Mandatory)][string]$TrainImages,
    [Parameter(Mandatory)][string]$EvalImages,
    [switch]$CpuOnly,
    [switch]$Recover
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('capture', '--scene', $Scene,
    '--train', (Resolve-Path -LiteralPath $TrainImages).Path,
    '--eval', (Resolve-Path -LiteralPath $EvalImages).Path)
if ($CpuOnly) { $arguments += '--cpu-only' }
if ($Recover) { $arguments += '--recover' }
Invoke-TopicPython -Arguments $arguments
