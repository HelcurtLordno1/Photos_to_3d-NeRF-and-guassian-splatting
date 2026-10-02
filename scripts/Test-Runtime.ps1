[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

if (-not (Get-CondaEnvironmentPath -Name $Config.EnvironmentName)) {
    throw "Conda environment $($Config.EnvironmentName) is missing. Run scripts\Setup-Runtime.ps1 first."
}

Write-TopicInfo 'Validating imports, pinned versions and GPU execution.'
Invoke-TopicPython -Arguments @('runtime-check')
Write-TopicInfo 'Validating the COLMAP executable and its Windows DLL dependencies.'
Invoke-InEnvironment -Command 'colmap' -Arguments @('-h') -Quiet | Out-Null
Write-TopicInfo 'Validating the FFmpeg executable.'
Invoke-InEnvironment -Command 'ffmpeg' -Arguments @('-version') -Quiet | Out-Null
foreach ($entrypoint in @('ns-train', 'ns-eval', 'ns-process-data')) {
    Write-TopicInfo "Validating $entrypoint."
    Invoke-InEnvironment -Command $entrypoint -Arguments @('--help') -Quiet | Out-Null
}
Write-TopicInfo 'Runtime validation passed.'
