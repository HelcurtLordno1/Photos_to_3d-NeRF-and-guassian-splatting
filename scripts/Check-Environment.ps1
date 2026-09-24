[CmdletBinding()]
param([switch]$RequireRuntime)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

$failures = 0
Write-Host "Project: $ProjectRoot"
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

foreach ($name in @('git', 'conda', 'nvidia-smi')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command) {
        Write-Host ('[ok]      {0,-18} {1}' -f $name, $command.Source)
    } else {
        Write-Host ('[missing] {0,-18}' -f $name) -ForegroundColor Red
        $failures++
    }
}

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    & nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader
    if ($LASTEXITCODE -ne 0) { $failures++ }
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path -LiteralPath $vswhere) {
    $vsPath = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $v142Path = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.ComponentGroup.VC.Tools.142.x86.x64 -property installationPath
    if ($vsPath) { Write-Host "[ok]      MSVC build tools   $vsPath" } else { Write-Host '[missing] MSVC C++ workload' -ForegroundColor Yellow }
    if ($v142Path) { Write-Host "[ok]      MSVC v142         $v142Path" } else { Write-Host '[missing] MSVC v142 (14.29) for CUDA 11.8' -ForegroundColor Yellow }
    if ($RequireRuntime -and -not $v142Path) { $failures++ }
} else {
    Write-Host '[missing] Visual Studio Build Tools' -ForegroundColor Yellow
    if ($RequireRuntime) { $failures++ }
}

Write-Host "[info]    free workspace     $(Get-FreeSpaceGiB) GiB"

try {
    $conda = Get-CondaCommand
    & $conda env list
    if ($RequireRuntime) {
        & (Join-Path $PSScriptRoot 'Test-Runtime.ps1')
    }
} catch {
    if ($RequireRuntime) { throw }
    Write-Host "[pending] runtime             $($_.Exception.Message)" -ForegroundColor Yellow
}

if ($failures -gt 0) { throw "$failures required host check(s) failed." }
Write-TopicInfo 'Environment checks completed.'
