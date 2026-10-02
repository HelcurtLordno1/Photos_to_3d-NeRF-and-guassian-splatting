Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script:Config = Import-PowerShellDataFile (Join-Path $script:ProjectRoot 'configs\project.psd1')
$script:DataRoot = Join-Path $script:ProjectRoot 'data'
$script:RawDataRoot = Join-Path $script:DataRoot 'raw'
$script:ProcessedDataRoot = Join-Path $script:DataRoot 'processed'
$script:ArtifactRoot = Join-Path $script:ProjectRoot 'artifacts'
$script:ThirdPartyRoot = Join-Path $script:ProjectRoot 'third_party'

function Write-TopicInfo {
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "[topic16] $Message" -ForegroundColor Cyan
}

function Assert-WindowsPowerShell {
    if ($env:OS -ne 'Windows_NT') {
        throw 'Topic 16 runtime scripts must run in native Windows PowerShell, not WSL/Linux.'
    }
}

function Assert-Command {
    param([Parameter(Mandatory)][string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { throw "Missing required command: $Name" }
    return $command
}

function New-TopicDirectory {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8Text {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Text)
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Get-CondaCommand {
    if ($env:TOPIC16_CONDA_EXE -and (Test-Path -LiteralPath $env:TOPIC16_CONDA_EXE)) {
        return $env:TOPIC16_CONDA_EXE
    }
    if ($env:CONDA_EXE -and (Test-Path -LiteralPath $env:CONDA_EXE)) { return $env:CONDA_EXE }
    $command = Get-Command conda.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $command = Get-Command conda -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $candidates = @(
        (Join-Path $env:USERPROFILE 'miniconda3\Scripts\conda.exe'),
        (Join-Path $env:USERPROFILE 'anaconda3\Scripts\conda.exe'),
        'C:\ProgramData\miniconda3\Scripts\conda.exe'
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw 'Conda was not found. Install Miniconda, reopen PowerShell, then rerun.'
}

function Get-CondaEnvironmentPath {
    param([Parameter(Mandatory)][string]$Name)
    $conda = Get-CondaCommand
    $listing = & $conda env list
    if ($LASTEXITCODE -ne 0) { throw 'Could not list Conda environments.' }
    foreach ($line in $listing) {
        if ($line -match ('^\s*' + [regex]::Escape($Name) + '\s+(?:\*\s+)?(.+?)\s*$')) {
            return $matches[1]
        }
    }
    return $null
}

function Invoke-Conda {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$AllowFailure,
        [switch]$Quiet
    )
    $conda = Get-CondaCommand
    $previousPreference = $ErrorActionPreference
    try {
        # Native stderr may contain ordinary progress/warnings. Preserve all
        # output, then decide success from the actual native exit code.
        $ErrorActionPreference = 'Continue'
        if ($Quiet) { & $conda @Arguments 2>&1 | Out-Null }
        else {
            & $conda @Arguments 2>&1 | ForEach-Object {
                $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
                Write-Host $line
            }
        }
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "Conda command failed with exit code ${exitCode}: conda $($Arguments -join ' ')"
    }
    return $exitCode
}

function Invoke-InEnvironment {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter()][string[]]$Arguments = @(),
        [switch]$AllowFailure,
        [switch]$Quiet
    )
    $allArguments = @('run', '--no-capture-output', '-n', $script:Config.EnvironmentName, $Command) + $Arguments
    $exitCode = Invoke-Conda -Arguments $allArguments -AllowFailure:$AllowFailure -Quiet:$Quiet
    return $exitCode
}

function Get-FreeSpaceGiB {
    $root = [System.IO.Path]::GetPathRoot($script:ProjectRoot)
    $drive = [System.IO.DriveInfo]::new($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function ConvertTo-CommandLine {
    param([Parameter(Mandatory)][string[]]$Tokens)
    return (($Tokens | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' ')
}

function Invoke-TopicPython {
    param([Parameter(Mandatory)][string[]]$Arguments)
    Assert-WindowsPowerShell
    $settingsFile = Join-Path ([IO.Path]::GetTempPath()) ('topic16-' + [guid]::NewGuid().ToString('N') + '.json')
    try {
        $script:Config | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $settingsFile -Encoding utf8
        $cli = Join-Path $script:ProjectRoot 'src\topic16\cli.py'
        Invoke-InEnvironment -Command 'python' -Arguments (@($cli, '--root', $script:ProjectRoot, '--settings', $settingsFile) + $Arguments) | Out-Null
    } finally {
        if (Test-Path -LiteralPath $settingsFile) { Remove-Item -LiteralPath $settingsFile -Force }
    }
}

function Import-VisualStudioEnvironment {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) {
        throw 'Visual Studio Build Tools were not found. Run scripts\Install-HostTools.ps1 first.'
    }
    $installationPath = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installationPath) { throw 'MSVC C++ build tools are not installed.' }
    $vcvars = Join-Path $installationPath 'VC\Auxiliary\Build\vcvarsall.bat'
    if (-not (Test-Path -LiteralPath $vcvars)) { throw "Missing vcvarsall.bat: $vcvars" }

    $environmentLines = & cmd.exe /s /c "`"$vcvars`" x64 -vcvars_ver=14.29 >nul 2>&1 && where cl >nul 2>&1 && set"
    if ($LASTEXITCODE -ne 0) {
        throw 'MSVC 14.29 (v142) is unavailable. Run scripts\Install-HostTools.ps1 -InstallBuildTools and confirm the v142 component installed.'
    }
    foreach ($line in $environmentLines) {
        if ($line -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        throw 'Visual Studio environment loaded but cl.exe is unavailable.'
    }
}
