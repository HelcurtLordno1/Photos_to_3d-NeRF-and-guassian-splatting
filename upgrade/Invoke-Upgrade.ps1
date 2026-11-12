[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('inventory','verify','audit','plan','run','publish','repair-study','preflight','full-plan','full-run','historical-common','quality-plan','quality-run','quality-audit','quality-measure','research-plan','research-run','confirmation-plan','confirmation-run','final-plan','final-run','final-ui-check')][string]$Command = 'plan',
    [string]$Study = 'tea60-v1',
    [string]$Scene = 'tea_sets_2',
    [string]$BaselineRoot,
    [string]$SplitPath,
    [switch]$Resume,
    [switch]$FullHash
)
. (Join-Path $PSScriptRoot 'scripts\lib\Common.ps1')
$arguments = @($Command, '--study', $Study, '--scene', $Scene)
if ($BaselineRoot) { $arguments += @('--baseline-root', (Resolve-Path -LiteralPath $BaselineRoot).Path) }
if ($SplitPath) { $arguments += @('--split-path', (Resolve-Path -LiteralPath $SplitPath).Path) }
if ($Resume) { $arguments += '--resume' }
if ($FullHash) { $arguments += '--full-hash' }
Invoke-TopicPython -Arguments $arguments -QualityProfile:($Command -in @('quality-plan','quality-run','quality-audit','quality-measure')) -ResearchProfile:($Command -in @('research-plan','research-run')) -ConfirmationProfile:($Command -in @('confirmation-plan','confirmation-run')) -FinalProfile:($Command -in @('final-plan','final-run','final-ui-check'))
