[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

& (Join-Path $PSScriptRoot 'Check-Environment.ps1')
& (Join-Path $PSScriptRoot 'Download-Repositories.ps1') -Mode runtime
& (Join-Path $PSScriptRoot 'Setup-Runtime.ps1')
& (Join-Path $PSScriptRoot 'Check-Environment.ps1') -RequireRuntime
& (Join-Path $PSScriptRoot 'Download-Datasets.ps1') -Mode all

$requirementsDirectory = Join-Path $ArtifactRoot 'logs\runtime'
New-TopicDirectory -Path $requirementsDirectory
$requirementsPath = Join-Path $requirementsDirectory 'requirements.txt'
$conda = Get-CondaCommand
& $conda run --no-capture-output -n $Config.EnvironmentName python -m pip freeze |
    Set-Content -LiteralPath $requirementsPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'Could not export requirements.txt after setup.' }
Write-TopicInfo "Setup complete. Resolved Python requirements: $requirementsPath"
