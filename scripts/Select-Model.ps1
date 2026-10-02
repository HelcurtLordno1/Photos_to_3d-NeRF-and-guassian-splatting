[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ConfigPath,
    [Parameter(Mandatory)][string]$GatePath,
    [Parameter(Mandatory)][string]$CameraPath,
    [string]$OutputPath
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
if (-not $OutputPath) { $OutputPath = Join-Path $ProjectRoot 'reports\model.json' }
Invoke-TopicPython -Arguments @('select-model', '--config', (Resolve-Path -LiteralPath $ConfigPath).Path,
    '--gate', (Resolve-Path -LiteralPath $GatePath).Path, '--camera-path', (Resolve-Path -LiteralPath $CameraPath).Path,
    '--output', [IO.Path]::GetFullPath($OutputPath))
