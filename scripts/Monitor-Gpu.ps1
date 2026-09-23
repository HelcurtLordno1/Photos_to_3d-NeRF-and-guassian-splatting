[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Output,
    [int]$IntervalSeconds = 10
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
Assert-Command -Name 'nvidia-smi' | Out-Null
New-TopicDirectory -Path (Split-Path $Output -Parent)
& nvidia-smi --query-gpu=timestamp,index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv --loop=$IntervalSeconds | Out-File -LiteralPath $Output -Encoding utf8
