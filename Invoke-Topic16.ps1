[CmdletBinding()]
param(
    [Parameter(Position = 0)][ValidateSet('help', 'check', 'gpu-safety', 'qa', 'research', 'host-tools', 'repos', 'setup', 'setup-all', 'papers', 'data-smoke', 'data-benchmark', 'data-all', 'train-smoke', 'benchmark', 'ui-setup', 'ui-prepare', 'ui-build', 'ui', 'ui-test', 'ui-dev', 'ui-stop')]
    [string]$Task = 'help'
)

$scripts = Join-Path $PSScriptRoot 'scripts'
$uiScripts = Join-Path $PSScriptRoot 'UI_design\scripts'
switch ($Task) {
    'help' {
        @'
Topic 16 PowerShell tasks
  GPU commands require Windows PowerShell Administrator; clock cap 300-800 MHz is reapplied per job.
  .\Invoke-Topic16.ps1 check           Host/GPU/disk preflight
  .\Invoke-Topic16.ps1 gpu-safety      Apply clock cap and verify conservative safety thresholds
  .\Invoke-Topic16.ps1 qa              PowerShell parser and CPU contract tests
  .\Invoke-Topic16.ps1 research        Ordered full primary research session
  .\Invoke-Topic16.ps1 host-tools      Install Git/Miniconda checks (MSVC: call script with -InstallBuildTools)
  .\Invoke-Topic16.ps1 repos           Fetch pinned Nerfstudio source
  .\Invoke-Topic16.ps1 setup           Create and validate the native Windows CUDA runtime
  .\Invoke-Topic16.ps1 setup-all       Download data, install runtime and export requirements
  .\Invoke-Topic16.ps1 papers          Download seven core papers
  .\Invoke-Topic16.ps1 data-smoke      Download Nerfstudio poster
  .\Invoke-Topic16.ps1 data-benchmark  Download/extract garden, bonsai, room
  .\Invoke-Topic16.ps1 data-all        Download smoke and benchmark data
  .\Invoke-Topic16.ps1 train-smoke     Train both methods on poster
  .\Invoke-Topic16.ps1 benchmark       Train/evaluate the paired 3-scene matrix
  .\Invoke-Topic16.ps1 ui-setup        Install isolated UI packages from registry pins
  .\Invoke-Topic16.ps1 ui-prepare      Validate completed pairs and prepare UI catalog
  .\Invoke-Topic16.ps1 ui-build        Build the production UI
  .\Invoke-Topic16.ps1 ui              Open Spatial Studio (no training)
  .\Invoke-Topic16.ps1 ui-test         UI typecheck and CPU contracts
  .\Invoke-Topic16.ps1 ui-dev          Vite hot reload with the local artifact API
  .\Invoke-Topic16.ps1 ui-stop         Stop the matching local UI safely
'@
    }
    'check' { & (Join-Path $scripts 'Check-Environment.ps1') }
    'gpu-safety' { & (Join-Path $scripts 'Check-GpuSafety.ps1') }
    'qa' { & (Join-Path $scripts 'Test-Project.ps1') }
    'research' { & (Join-Path $scripts 'Run-Research.ps1') }
    'host-tools' { & (Join-Path $scripts 'Install-HostTools.ps1') }
    'repos' { & (Join-Path $scripts 'Download-Repositories.ps1') -Mode runtime }
    'setup' { & (Join-Path $scripts 'Setup-Runtime.ps1') }
    'setup-all' { & (Join-Path $scripts 'Setup-Project.ps1') }
    'papers' { & (Join-Path $scripts 'Download-Papers.ps1') }
    'data-smoke' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode smoke }
    'data-benchmark' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode benchmark }
    'data-all' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode all }
    'train-smoke' {
        & (Join-Path $scripts 'Run-Benchmark.ps1') -Scenes @('poster')
    }
    'benchmark' { & (Join-Path $scripts 'Run-Benchmark.ps1') }
    'ui-setup' { & (Join-Path $uiScripts 'Setup-UI.ps1') }
    'ui-prepare' { & (Join-Path $uiScripts 'Prepare-UIAssets.ps1') }
    'ui-build' { & (Join-Path $uiScripts 'Build-UI.ps1') }
    'ui' { & (Join-Path $uiScripts 'Start-UI.ps1') }
    'ui-test' { & (Join-Path $uiScripts 'Test-UI.ps1') }
    'ui-dev' { & (Join-Path $uiScripts 'Dev-UI.ps1') }
    'ui-stop' { & (Join-Path $uiScripts 'Stop-UI.ps1') }
}
