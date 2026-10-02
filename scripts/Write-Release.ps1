[CmdletBinding()]
param([Parameter(Mandatory)][string]$ModelPath, [Parameter(Mandatory)][string]$OutputPath)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Invoke-TopicPython -Arguments @('release', '--model', (Resolve-Path -LiteralPath $ModelPath).Path,
    '--output', [IO.Path]::GetFullPath($OutputPath))
