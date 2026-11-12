[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
# Torch and the CPU selector share this process; avoid loading a second Intel
# OpenMP runtime when the numerical contract tests import them in either order.
$env:MKL_THREADING_LAYER = 'SEQUENTIAL'
$env:PYTHONPATH = (Join-Path $ProjectRoot 'src') + $(if ($env:PYTHONPATH) { ';' + $env:PYTHONPATH } else { '' })
foreach ($file in Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File | Where-Object { $_.Extension -in @('.ps1','.psd1') -and $_.FullName -notmatch '[\\/]third_party[\\/]' }) {
    $tokens=$null; $parseErrors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$parseErrors)
    if ($parseErrors) { throw "PowerShell parse failed: $($file.FullName): $parseErrors" }
}
Invoke-InEnvironment -Command python -Arguments @('-m','unittest','discover','-s',(Join-Path $ProjectRoot 'tests'),'-v') | Out-Null
Write-TopicInfo 'Upgrade CPU contracts and PowerShell parser PASS.'
