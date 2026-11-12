[CmdletBinding()]
param([switch]$RebuildEnvironment, [switch]$RepairNativeTools)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
if ($RebuildEnvironment -and $RepairNativeTools) {
    throw 'Choose either -RebuildEnvironment or -RepairNativeTools, not both.'
}
Assert-Command -Name 'git' | Out-Null
Assert-Command -Name 'nvidia-smi' | Out-Null
Import-VisualStudioEnvironment

if (-not (Test-Path -LiteralPath (Join-Path $ThirdPartyRoot 'nerfstudio\.git'))) {
    & (Join-Path $PSScriptRoot 'Download-Repositories.ps1') -Mode runtime
}
$runtimeRoot = Join-Path $ThirdPartyRoot 'nerfstudio'
$actualCommit = (& git -C $runtimeRoot rev-parse HEAD).Trim()
if ($actualCommit -ne $Config.NerfstudioCommit) {
    throw "Nerfstudio is at $actualCommit; expected $($Config.NerfstudioCommit)."
}

$environmentExists = Get-CondaEnvironmentPath -Name $Config.EnvironmentName
if ($RepairNativeTools -and -not $environmentExists) {
    throw "Cannot repair missing Conda environment $($Config.EnvironmentName). Run scripts\Setup-Runtime.ps1 without -RepairNativeTools."
}
if ($RebuildEnvironment -and $environmentExists) {
    Write-TopicInfo "Removing Conda environment $($Config.EnvironmentName)."
    Invoke-Conda -Arguments @('env', 'remove', '-n', $Config.EnvironmentName, '-y') | Out-Null
    $environmentExists = $null
}
if (-not $environmentExists) {
    Write-TopicInfo "Creating Conda environment $($Config.EnvironmentName)."
    Invoke-Conda -Arguments @('create', '-n', $Config.EnvironmentName, '-y', "python=$($Config.PythonVersion)", 'pip<25', 'setuptools<82', 'numpy<2') | Out-Null
    $environmentExists = Get-CondaEnvironmentPath -Name $Config.EnvironmentName
}

Write-TopicInfo 'Installing the CUDA compiler toolkit, COLMAP, FFmpeg and Ninja into the isolated environment.'
Invoke-Conda -Arguments @(
    'install', '-n', $Config.EnvironmentName, '-y',
    '-c', $Config.CudaToolkitChannel, '-c', 'conda-forge',
    "cuda-toolkit=$($Config.CudaToolkitVersion)", "colmap=$($Config.ColmapVersion)",
    "ffmpeg=$($Config.FfmpegVersion)", 'ninja',
    "conda-forge::libglib=$($Config.LibglibVersion)", "libintl=$($Config.LibintlVersion)"
) | Out-Null

# Some mixed-channel Windows transactions unlink an overlapping intl-8.dll
# while replacing defaults' libglib. Restore the pinned conda-forge DLL if the
# package metadata exists but the file disappeared.
$intlDll = Join-Path $environmentExists 'Library\bin\intl-8.dll'
if (-not (Test-Path -LiteralPath $intlDll)) {
    Write-TopicInfo 'Restoring the missing libintl DLL after Conda package replacement.'
    Invoke-Conda -Arguments @(
        'install', '-n', $Config.EnvironmentName, '-y', '--force-reinstall', '--no-deps',
        '-c', 'conda-forge', "libintl=$($Config.LibintlVersion)"
    ) | Out-Null
}

# The conda-forge Windows COLMAP 3.9.1 GPU build imports mpir.dll but omits
# mpir from its dependency metadata. Installing it with normal resolution would
# downgrade NumPy and replace unrelated CUDA/runtime packages; only this DLL
# package is needed alongside the existing GMP package.
$mpirDll = Join-Path $environmentExists 'Library\bin\mpir.dll'
if (-not (Test-Path -LiteralPath $mpirDll)) {
    Write-TopicInfo 'Installing the missing Windows COLMAP mpir.dll runtime without changing other packages.'
    Invoke-Conda -Arguments @(
        'install', '-n', $Config.EnvironmentName, '-y', '--no-deps',
        '-c', 'conda-forge', "mpir=$($Config.ColmapMpirVersion)"
    ) | Out-Null
}

Write-TopicInfo 'Checking the pinned FFmpeg executable.'
Invoke-InEnvironment -Command 'ffmpeg' -Arguments @('-version') -Quiet | Out-Null

if ($RepairNativeTools) {
    & (Join-Path $PSScriptRoot 'Test-Runtime.ps1')
    return
}

Write-TopicInfo 'Installing pinned PyTorch CUDA wheels.'
Invoke-InEnvironment -Command 'python' -Arguments @(
    '-m', 'pip', 'install',
    "torch==$($Config.TorchVersion)", "torchvision==$($Config.TorchvisionVersion)",
    '--extra-index-url', $Config.TorchIndexUrl
) | Out-Null

Invoke-InEnvironment -Command 'python' -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip<25', 'setuptools<82', 'wheel', 'numpy<2') | Out-Null
Write-TopicInfo 'Installing the matching precompiled Windows gsplat wheel before Nerfstudio dependency resolution.'
Invoke-InEnvironment -Command 'python' -Arguments @(
    '-m', 'pip', 'install', '--no-deps', '--only-binary=:all:',
    "gsplat==$($Config.GsplatVersion)", '--index-url', $Config.GsplatIndexUrl
) | Out-Null

Write-TopicInfo 'Installing Nerfstudio from the verified source snapshot.'
Invoke-InEnvironment -Command 'python' -Arguments @('-m', 'pip', 'install', '-e', $runtimeRoot) | Out-Null

$env:TCNN_CUDA_ARCHITECTURES = '86'
$env:TORCH_CUDA_ARCH_LIST = '8.6'
$environmentPath = $environmentExists
if (-not $environmentPath) { throw 'Could not resolve the Conda environment path after creation.' }
$env:CUDA_HOME = $environmentPath

Write-TopicInfo 'Building the pinned tiny-cuda-nn torch bindings for compute capability 8.6.'
$tcnnUrl = "git+https://github.com/NVlabs/tiny-cuda-nn.git@$($Config.TinyCudaNnCommit)#subdirectory=bindings/torch"
Invoke-InEnvironment -Command 'python' -Arguments @('-m', 'pip', 'install', '--no-build-isolation', $tcnnUrl) | Out-Null

& (Join-Path $PSScriptRoot 'Test-Runtime.ps1')
Write-TopicInfo "Runtime is ready. Use conda run -n $($Config.EnvironmentName) <command>, or the project .ps1 wrappers."
