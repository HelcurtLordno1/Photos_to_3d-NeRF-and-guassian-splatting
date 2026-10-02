. (Join-Path $PSScriptRoot 'Common-UI.ps1')
Invoke-UiNpm -Arguments @('run', 'build')
Invoke-UiNpm -Arguments @('run', 'check:bundle')
