[CmdletBinding()]
param(
    [Parameter(Position = 0)][ValidateSet('help', 'check', 'host-tools', 'repos', 'setup', 'setup-all', 'papers', 'data-smoke', 'data-benchmark', 'data-all', 'train-smoke', 'benchmark')]
    [string]$Task = 'help'
)

$scripts = Join-Path $PSScriptRoot 'scripts'
switch ($Task) {
    'help' {
        @'
Topic 16 PowerShell tasks
  .\Invoke-Topic16.ps1 check           Host/GPU/disk preflight
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
'@
    }
    'check' { & (Join-Path $scripts 'Check-Environment.ps1') }
    'host-tools' { & (Join-Path $scripts 'Install-HostTools.ps1') }
    'repos' { & (Join-Path $scripts 'Download-Repositories.ps1') -Mode runtime }
    'setup' { & (Join-Path $scripts 'Setup-Runtime.ps1') }
    'setup-all' { & (Join-Path $scripts 'Setup-Project.ps1') }
    'papers' { & (Join-Path $scripts 'Download-Papers.ps1') }
    'data-smoke' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode smoke }
    'data-benchmark' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode benchmark }
    'data-all' { & (Join-Path $scripts 'Download-Datasets.ps1') -Mode all }
    'train-smoke' {
        & (Join-Path $scripts 'Train.ps1') -Method nerfacto -Dataset poster
        & (Join-Path $scripts 'Train.ps1') -Method splatfacto -Dataset poster
    }
    'benchmark' { & (Join-Path $scripts 'Run-Benchmark.ps1') }
}
