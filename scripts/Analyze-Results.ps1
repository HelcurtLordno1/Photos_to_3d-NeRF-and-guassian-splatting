[CmdletBinding()]
param(
    [Parameter(Mandatory)][string[]]$MatrixPaths,
    [string]$OutputDirectory,
    [string]$ReviewPath,
    [ValidateSet('primary', 'diagnostic', 'repeat')][string]$Protocol = 'primary'
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $ProjectRoot 'reports\measured' }
$arguments = @('analyze', '--output', [IO.Path]::GetFullPath($OutputDirectory), '--protocol', $Protocol, '--matrices')
$arguments += @($MatrixPaths | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
if ($ReviewPath) { $arguments += @('--review', (Resolve-Path -LiteralPath $ReviewPath).Path) }
Invoke-TopicPython -Arguments $arguments
