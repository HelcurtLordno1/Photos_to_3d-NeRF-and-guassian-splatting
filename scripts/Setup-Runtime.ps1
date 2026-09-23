[CmdletBinding()]
param([switch]$RebuildEnvironment)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
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
    "cuda-toolkit=$($Config.CudaToolkitVersion)", "colmap=$($Config.ColmapVersion)", 'ffmpeg', 'ninja'
) | Out-Null

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

Write-TopicInfo 'Validating imports, exact versions and GPU execution.'
$validation = @'
import torch, gsplat, nerfstudio, tinycudann
assert torch.cuda.is_available(), "PyTorch cannot see CUDA"
assert torch.__version__.startswith("2.1.2+cu118"), torch.__version__
assert gsplat.__version__.startswith("1.4.0"), gsplat.__version__
x = torch.ones(1, device="cuda")
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("gpu", torch.cuda.get_device_name(0), "value", x.item())
print("gsplat", gsplat.__version__)
print("nerfstudio", getattr(nerfstudio, "__version__", "1.1.5-source"))
'@
Invoke-InEnvironment -Command 'python' -Arguments @('-c', $validation) | Out-Null
Write-TopicInfo "Runtime is ready. Use conda run -n $($Config.EnvironmentName) <command>, or the project .ps1 wrappers."
