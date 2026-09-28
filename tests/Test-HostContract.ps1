[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot '..\scripts\lib\Common.ps1')
Assert-WindowsPowerShell
$oldPath = $env:PATH
$oldUserProfile = $env:USERPROFILE
$oldProgramFiles = ${env:ProgramFiles(x86)}
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('topic16-host-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
try {
    $env:PATH = $fixtureRoot
    $env:USERPROFILE = $fixtureRoot
    $missingConda = $false
    try { Get-CondaCommand | Out-Null }
    catch { $missingConda = $_.Exception.Message -match 'Conda was not found' }
    if (-not $missingConda) { throw 'Missing Conda did not produce the expected error.' }
    Write-Host '[ok] Missing Conda fails clearly.'

    ${env:ProgramFiles(x86)} = $fixtureRoot
    $missingMsvc = $false
    try { Import-VisualStudioEnvironment }
    catch { $missingMsvc = $_.Exception.Message -match 'Visual Studio Build Tools were not found' }
    if (-not $missingMsvc) { throw 'Missing MSVC did not produce the expected error.' }
    Write-Host '[ok] Missing MSVC fails clearly.'
} finally {
    $env:PATH = $oldPath
    $env:USERPROFILE = $oldUserProfile
    ${env:ProgramFiles(x86)} = $oldProgramFiles
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
}
