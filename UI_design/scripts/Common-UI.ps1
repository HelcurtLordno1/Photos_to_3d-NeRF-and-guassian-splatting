Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$UiRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $UiRoot '..')).Path
. (Join-Path $RepoRoot 'scripts\lib\Common.ps1')
Assert-WindowsPowerShell

# Discover registered Miniconda installs, including nonstandard drives, in a
# fresh/elevated shell. Keep the existing explicit environment override first.
if (-not $env:TOPIC16_CONDA_EXE) {
    foreach ($hive in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore')) {
        foreach ($entry in Get-ChildItem -LiteralPath $hive -ErrorAction SilentlyContinue) {
            $install = Get-ItemProperty -LiteralPath ($entry.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
            if ($install -and $install.PSObject.Properties['(default)']) {
                $registeredConda = Join-Path $install.'(default)' 'Scripts\conda.exe'
                if (Test-Path -LiteralPath $registeredConda) {
                    $env:TOPIC16_CONDA_EXE = $registeredConda
                    break
                }
            }
        }
        if ($env:TOPIC16_CONDA_EXE) { break }
    }
}

function Get-UiNode {
    $pinned = $script:Config.Ui.NodeVersion
    $candidates = @((Join-Path $UiRoot ".tools\node-v$pinned-win-x64\node.exe"))
    $installed = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($installed) { $candidates += $installed.Source }
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) {
            $version = (& $path --version).Trim()
            if ($version -eq "v$pinned") { return $path }
        }
    }
    throw "Pinned Node v$pinned is missing. Run UI_design\scripts\Setup-UI.ps1."
}

function Invoke-UiNode {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $node = Get-UiNode
    $previous = $ErrorActionPreference
    $previousPath = $env:PATH
    try {
        $env:PATH = (Split-Path $node) + ';' + $previousPath
        $ErrorActionPreference = 'Continue'
        & $node @Arguments 2>&1 | ForEach-Object { Write-Host ([string]$_) }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous; $env:PATH = $previousPath }
    if ($code -ne 0) { throw "UI Node command failed ($code)." }
}

function Invoke-UiNpm {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $node = Get-UiNode
    $npm = Join-Path (Split-Path $node) 'node_modules\npm\bin\npm-cli.js'
    if (-not (Test-Path -LiteralPath $npm)) { throw 'npm CLI is missing from the pinned Node installation.' }
    Push-Location -LiteralPath $UiRoot
    try { Invoke-UiNode -Arguments (@($npm) + $Arguments) } finally { Pop-Location }
}

function Invoke-UiPython {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $settingsFile = Join-Path ([IO.Path]::GetTempPath()) ('topic16-ui-' + [guid]::NewGuid().ToString('N') + '.json')
    $oldPythonPath = $env:PYTHONPATH
    try {
        Write-Utf8Text -Path $settingsFile -Text ($script:Config | ConvertTo-Json -Depth 20)
        $env:PYTHONPATH = "$RepoRoot;$RepoRoot\src" + $(if ($oldPythonPath) { ";$oldPythonPath" } else { '' })
        Push-Location -LiteralPath $RepoRoot
        try { Invoke-InEnvironment -Command python -Arguments (@('-m', 'UI_design.backend.cli', '--root', $RepoRoot, '--settings', $settingsFile) + $Arguments) | Out-Null } finally { Pop-Location }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
        Remove-Item -LiteralPath $settingsFile -Force -ErrorAction SilentlyContinue
    }
}
