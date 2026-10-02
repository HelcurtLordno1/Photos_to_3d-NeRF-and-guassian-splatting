[CmdletBinding()]
param([Parameter(Mandatory)][string]$ConfigPath, [string]$CameraPath)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('render', '--config', (Resolve-Path -LiteralPath $ConfigPath).Path)
if ($CameraPath) { $arguments += @('--camera-path', (Resolve-Path -LiteralPath $CameraPath).Path) }
Invoke-TopicPython -Arguments $arguments
