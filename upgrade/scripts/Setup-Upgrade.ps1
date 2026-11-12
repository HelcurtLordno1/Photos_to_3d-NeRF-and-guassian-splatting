[CmdletBinding()]
param([string]$CloneFrom, [string]$BaselineRoot, [string]$SharedGpuLock)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
if (-not $BaselineRoot) { $BaselineRoot = (Resolve-Path (Join-Path $ProjectRoot '..')).Path }
$BaselineRoot = (Resolve-Path -LiteralPath $BaselineRoot).Path
if ((Get-FreeSpaceGiB) -lt $Config.MinimumUpgradeFreeGiB) { throw 'Insufficient disk reserve before environment setup.' }
New-TopicDirectory -Path (Join-Path $ProjectRoot 'artifacts\logs')
$hostPath = Join-Path $ProjectRoot 'artifacts\logs\host.json'
if (Test-Path -LiteralPath $hostPath) { throw 'Upgrade is already configured. Existing host/runtime identity is preserved.' }
if (Get-CondaEnvironmentPath -Name $Config.EnvironmentName) { throw 'Target environment already exists without upgrade host provenance; inspect it before setup.' }
if ($CloneFrom) {
    $source = Get-CondaEnvironmentPath -Name $CloneFrom
    if (-not $source) { throw "Clone source environment missing: $CloneFrom" }
    Invoke-Conda -Arguments @('create','-n',$Config.EnvironmentName,'--clone',$source,'-y') | Out-Null
    # The editable upstream checkout stays read-only. Baseline environment packages are untouched.
    $runtimeSource = Join-Path $BaselineRoot 'third_party\nerfstudio'
} else {
    & (Join-Path $PSScriptRoot 'Setup-Runtime.ps1')
    $runtimeSource = Join-Path $ProjectRoot 'third_party\nerfstudio'
}
if (-not $SharedGpuLock) { $SharedGpuLock = Join-Path $BaselineRoot 'artifacts\logs\gpu.lock' }
$record = @{ BaselineRoot = $BaselineRoot; RuntimeSource = $runtimeSource;
    SharedGpuLock = [IO.Path]::GetFullPath($SharedGpuLock); CloneFrom = $CloneFrom;
    conda = (Get-CondaCommand); created_at = [DateTime]::UtcNow.ToString('o') }
Write-Utf8Text -Path $hostPath -Text ($record | ConvertTo-Json)
Write-TopicInfo "Isolated environment $($Config.EnvironmentName) ready. Host provenance: $hostPath"
