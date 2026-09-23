[CmdletBinding()]
param([switch]$InstallBuildTools)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
Assert-Command -Name 'winget' | Out-Null

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-TopicInfo 'Installing Git for Windows.'
    & winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Git installation failed.' }
}

try { Get-CondaCommand | Out-Null } catch {
    Write-TopicInfo 'Installing Miniconda.'
    & winget install --id Anaconda.Miniconda3 --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Miniconda installation failed. Reopen PowerShell after installation.' }
}

if ($InstallBuildTools) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Installing or modifying Visual Studio Build Tools requires an elevated Windows PowerShell (Run as administrator).'
    }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $requiredComponents = @(
        'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
        'Microsoft.VisualStudio.Component.VC.v142.x86.x64',
        'Microsoft.VisualStudio.Component.Windows10SDK.19041'
    )
    $hasTools = $false
    if (Test-Path -LiteralPath $vswhere) {
        $hasTools = $true
        foreach ($component in $requiredComponents) {
            if (-not (& $vswhere -latest -products '*' -requires $component -property installationPath)) {
                $hasTools = $false
                break
            }
        }
    }
    if (-not $hasTools) {
        Write-TopicInfo 'Installing the minimal Visual Studio C++ toolchain required by CUDA extensions.'
        # Keep this component list deliberately small. --includeRecommended also pulls
        # Roslyn, test, debugger and ASAN packages that this project never invokes.
        $componentArguments = @(
            '--add', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
            '--add', 'Microsoft.VisualStudio.Component.VC.v142.x86.x64',
            '--add', 'Microsoft.VisualStudio.Component.Windows10SDK.19041'
        )
        $existingPath = if (Test-Path -LiteralPath $vswhere) {
            & $vswhere -latest -products '*' -property installationPath
        }
        if ($existingPath) {
            $installer = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\setup.exe'
            & $installer modify --installPath $existingPath @componentArguments --quiet --norestart
            if ($LASTEXITCODE -ne 0) { throw 'Visual Studio Build Tools modification failed.' }
        } else {
            $override = '--wait --quiet --norestart ' + (($componentArguments | ForEach-Object {
                if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
            }) -join ' ')
            & winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --accept-package-agreements --accept-source-agreements --override $override
            if ($LASTEXITCODE -ne 0) { throw 'Visual Studio Build Tools installation failed.' }
        }
        if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Visual Studio setup returned without installing vswhere.exe.' }
        foreach ($component in $requiredComponents) {
            if (-not (& $vswhere -latest -products '*' -requires $component -property installationPath)) {
                throw "Visual Studio setup returned, but $component is still missing. Check the installer log in `$env:TEMP and rerun after network access is restored."
            }
        }
    }
} else {
    Write-TopicInfo 'Build Tools installation was not requested. Setup-Runtime.ps1 will fail fast if MSVC is missing.'
}

Write-TopicInfo 'Host tools step complete. Reopen PowerShell if a package was newly installed.'
