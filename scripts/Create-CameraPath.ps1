[CmdletBinding()]
param([Parameter(Mandatory)][string]$ConfigPath, [Parameter(Mandatory)][string]$OutputPath)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Invoke-TopicPython -Arguments @('camera-path', '--config', (Resolve-Path -LiteralPath $ConfigPath).Path,
    '--output', [IO.Path]::GetFullPath($OutputPath))
