param([string]$ExtraMatrix)
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
$arguments = @('prepare')
if ($ExtraMatrix) { $arguments += @('--extra-matrix', $ExtraMatrix) }
Invoke-UiPython -Arguments $arguments
