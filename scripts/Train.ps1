[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('nerfacto', 'splatfacto')][string]$Method,
    [Parameter(Mandatory)][string]$Dataset,
    [ValidateSet('primary', 'diagnostic', 'repeat')][string]$Protocol = 'primary',
    [ValidateRange(1, 2147483647)][int]$Iterations,
    [int]$Seed,
    [string]$ResultPath,
    [string]$ResumeConfigPath
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('train', '--method', $Method, '--scene', $Dataset, '--protocol', $Protocol)
if ($PSBoundParameters.ContainsKey('Iterations')) { $arguments += @('--iterations', [string]$Iterations) }
if ($PSBoundParameters.ContainsKey('Seed')) { $arguments += @('--seed', [string]$Seed) }
if ($ResultPath) { $arguments += @('--result', [IO.Path]::GetFullPath($ResultPath)) }
if ($ResumeConfigPath) { $arguments += @('--resume-config', (Resolve-Path -LiteralPath $ResumeConfigPath).Path) }
Invoke-TopicPython -Arguments $arguments
