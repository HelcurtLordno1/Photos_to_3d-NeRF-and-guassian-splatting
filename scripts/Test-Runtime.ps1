[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

if (-not (Get-CondaEnvironmentPath -Name $Config.EnvironmentName)) {
    throw "Conda environment $($Config.EnvironmentName) is missing. Run scripts\Setup-Runtime.ps1 first."
}

# Conda on Windows cannot wrap a python -c argument containing newlines.
$validation = @(
    'import torch, gsplat, nerfstudio, tinycudann'
    'assert torch.cuda.is_available(), "PyTorch cannot see CUDA"'
    "assert torch.__version__ == '$($Config.TorchVersion)', torch.__version__"
    "assert gsplat.__version__ == '$($Config.GsplatVersion)', gsplat.__version__"
    'x = torch.ones(1, device="cuda")'
    'print("torch", torch.__version__, "cuda", torch.version.cuda)'
    'print("gpu", torch.cuda.get_device_name(0), "value", x.item())'
    'print("gsplat", gsplat.__version__)'
    'print("nerfstudio", getattr(nerfstudio, "__version__", "source"))'
) -join '; '

Write-TopicInfo 'Validating imports, pinned versions and GPU execution.'
Invoke-InEnvironment -Command 'python' -Arguments @('-c', $validation) | Out-Null
Write-TopicInfo 'Validating the COLMAP executable and its Windows DLL dependencies.'
Invoke-InEnvironment -Command 'colmap' -Arguments @('-h') -Quiet | Out-Null
Write-TopicInfo 'Validating the FFmpeg executable.'
Invoke-InEnvironment -Command 'ffmpeg' -Arguments @('-version') -Quiet | Out-Null
foreach ($entrypoint in @('ns-train', 'ns-eval', 'ns-process-data')) {
    Write-TopicInfo "Validating $entrypoint."
    Invoke-InEnvironment -Command $entrypoint -Arguments @('--help') -Quiet | Out-Null
}
Write-TopicInfo 'Runtime validation passed.'
