[CmdletBinding()]
param([Parameter(Mandatory)][string]$ConfigPath, [switch]$RequireEvaluation)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('audit-run', '--config', (Resolve-Path -LiteralPath $ConfigPath).Path)
if ($RequireEvaluation) { $arguments += '--require-evaluation' }
Invoke-TopicPython -Arguments $arguments
