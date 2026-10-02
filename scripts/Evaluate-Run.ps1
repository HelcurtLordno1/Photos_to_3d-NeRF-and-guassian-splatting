[CmdletBinding()]
param([Parameter(Mandatory)][string]$ConfigPath)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Invoke-TopicPython -Arguments @('evaluate', '--config', (Resolve-Path -LiteralPath $ConfigPath).Path)
