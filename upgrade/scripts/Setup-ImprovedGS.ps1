[CmdletBinding()]
param([switch]$VerifyOnly)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$research = Import-PowerShellDataFile (Join-Path $ProjectRoot 'configs\tea-research.psd1')
$hostRecord = Get-Content -LiteralPath (Join-Path $ArtifactRoot 'logs\host.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$env:TOPIC16_CONDA_EXE = $hostRecord.conda
$source = Join-Path $ThirdPartyRoot 'improved-gs'
if (-not (Test-Path -LiteralPath (Join-Path $source '.git'))) {
    & git clone https://github.com/XiaoBin2001/Improved-GS.git $source
    if ($LASTEXITCODE -ne 0) { throw 'Official Improved-GS clone failed.' }
}
if ((& git -C $source rev-parse HEAD).Trim() -ne $research.ImprovedGsCommit) { throw 'Improved-GS commit differs from declared experiment.' }
if (& git -C $source status --porcelain --untracked-files=no) { throw 'Official Improved-GS source has modifications.' }
$targetEnvironment = Get-CondaEnvironmentPath -Name $research.EnvironmentName
if (-not $targetEnvironment) {
    Invoke-Conda -Arguments @('create','--name',$research.EnvironmentName,'--clone',$research.CloneFrom,'--offline','-y') | Out-Null
    $targetEnvironment = Get-CondaEnvironmentPath -Name $research.EnvironmentName
}
Import-VisualStudioEnvironment
$env:CUDA_HOME = $targetEnvironment
$env:TORCH_CUDA_ARCH_LIST = '8.6'
$env:MAX_JOBS = '4'
$env:DISTUTILS_USE_SDK = '1'
$env:PYTHONUTF8 = '1'
# nvcc/MSVC interpret Unicode source arguments through incompatible code pages.
# Compile through an owned ASCII junction, preserving the clean source bytes.
$hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($source.ToLowerInvariant()))).Replace('-','').Substring(0,16).ToLowerInvariant()
$buildParent = Join-Path ([IO.Path]::GetTempPath()) 'topic16-native-builds'
New-TopicDirectory -Path $buildParent
$buildSource = Join-Path $buildParent $hash
if (-not (Test-Path -LiteralPath $buildSource)) { New-Item -ItemType Junction -Path $buildSource -Target $source | Out-Null }
$junction = Get-Item -LiteralPath $buildSource
if ($junction.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath($junction.Target[0]) -ne [IO.Path]::GetFullPath($source)) { throw 'Build junction target differs from this checkout.' }
# Editable Nerfstudio in the cloned environment remains read-only. Only new
# extension packages are installed, with dependency resolution disabled.
foreach ($extension in @('diff-gaussian-rasterization','simple-knn','fused-ssim') | Where-Object { -not $VerifyOnly }) {
    Invoke-Conda -Arguments @('run','--no-capture-output','-n',$research.EnvironmentName,'python','-m','pip','install',
        '--no-deps','--no-build-isolation',(Join-Path $buildSource ('submodules\' + $extension))) | Out-Null
}
Invoke-Conda -Arguments @('run','--no-capture-output','-n',$research.EnvironmentName,'python','-c',
    'import sys, torch, diff_gaussian_rasterization, simple_knn._C, fused_ssim; print(torch.__version__); assert torch.__version__ == sys.argv[1]', $research.TorchVersion) | Out-Null
Write-TopicInfo 'Improved-GS isolated native extensions installed. GPU numerical and resume checks are still required.'
$ready = @{ status='ready'; commit=$research.ImprovedGsCommit; environment=$research.EnvironmentName; torch=$research.TorchVersion; completed_at=[DateTime]::UtcNow.ToString('o') }
Write-Utf8Text -Path (Join-Path $ArtifactRoot 'logs\improvedgs-setup.json') -Text ($ready | ConvertTo-Json)
