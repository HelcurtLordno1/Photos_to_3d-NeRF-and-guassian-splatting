[CmdletBinding()]
param([ValidateSet('All', 'Audit', 'Figures', 'Package')][string]$Mode = 'All')

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $root 'scripts\lib\Common.ps1')
Assert-WindowsPowerShell

if ($Mode -in @('All', 'Audit')) {
    $venvRoot = Join-Path $PSScriptRoot '.venv'
    $auditPython = Join-Path $venvRoot 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $auditPython)) {
        Invoke-InEnvironment -Command python -Arguments @('-m', 'venv', '--without-pip', $venvRoot) | Out-Null
    }
    $snapshot = Join-Path $PSScriptRoot 'settings.snapshot.json'
    Write-Utf8Text -Path $snapshot -Text ($Config | ConvertTo-Json -Depth 15)
    & $auditPython -I (Join-Path $PSScriptRoot 'audit_artifacts.py') --root $root --settings $snapshot
    if ($LASTEXITCODE -ne 0) { throw 'Isolated artifact audit failed.' }
}
if ($Mode -in @('All', 'Figures')) {
    Invoke-InEnvironment -Command python -Arguments @((Join-Path $PSScriptRoot 'build_figures.py'), '--root', $root) | Out-Null
}
if ($Mode -in @('All', 'Package')) {
    Invoke-InEnvironment -Command python -Arguments @((Join-Path $PSScriptRoot 'build_package.py'), '--root', $root) | Out-Null
}
