param([switch]$Browser, [string]$Url = 'http://127.0.0.1:7016')
. (Join-Path $PSScriptRoot 'Common-UI.ps1')
Invoke-UiNpm -Arguments @('run','typecheck')
Invoke-UiNpm -Arguments @('test')
$env:PYTHONPATH = "$RepoRoot;$RepoRoot\src"
foreach ($file in Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1') {
    $tokens=$null; $errors=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
    if ($errors) { throw "PowerShell parser failed: $($file.FullName)" }
}
Invoke-InEnvironment -Command python -Arguments @('-m','unittest','discover','-s',(Join-Path $UiRoot 'tests'),'-p','test_*.py') | Out-Null
if ($Browser) { Invoke-UiNode -Arguments @((Join-Path $UiRoot 'tests\browser.mjs'),$Url) }
