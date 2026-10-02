[CmdletBinding()]
param([switch]$RequireRuntime, [switch]$RequireAnalyzer, [string]$PythonExecutable)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$files = @(Get-ChildItem -LiteralPath $PSScriptRoot -Recurse -Filter '*.ps1' -File)
$files += @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'tests') -Filter '*.ps1' -File)
$files += Get-Item -LiteralPath (Join-Path $ProjectRoot 'Invoke-Topic16.ps1')
foreach ($file in $files) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors)
    if ($errors) { $errors | Out-Host; throw "PowerShell syntax failed: $($file.FullName)" }
}
Write-TopicInfo "Parsed $($files.Count) PowerShell files."
$analyzer = Get-Command Invoke-ScriptAnalyzer -ErrorAction SilentlyContinue
if ($analyzer) {
    $issues = @($files | ForEach-Object { Invoke-ScriptAnalyzer -Path $_.FullName -Severity Error })
    if ($issues.Count) { $issues | Out-Host; throw 'PSScriptAnalyzer error check failed.' }
} elseif ($RequireAnalyzer) { throw 'PSScriptAnalyzer unavailable; install it explicitly then rerun.' }
else { Write-TopicInfo 'PSScriptAnalyzer unavailable; check skipped (use -RequireAnalyzer to enforce).' }
foreach ($test in 'Test-HostContract.ps1', 'Test-ManifestContract.ps1', 'Test-DatasetContract.ps1') {
    & (Join-Path $ProjectRoot "tests\$test")
}
$pythonArguments = @('-m', 'unittest', 'discover', '-s', (Join-Path $ProjectRoot 'tests'), '-p', 'test_*.py', '-v')
if ($PythonExecutable) {
    # unittest writes ordinary progress to stderr. Windows PowerShell must decide
    # success from the process exit code, rather than treat that progress as fatal.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $PythonExecutable @pythonArguments 2>&1 | ForEach-Object {
            $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { [string]$_ }
            Write-Host $line
        }
        $pythonExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($pythonExitCode -ne 0) { throw 'Python contract tests failed.' }
} else {
    Invoke-InEnvironment -Command python -Arguments $pythonArguments | Out-Null
}
if ($RequireRuntime) { & (Join-Path $PSScriptRoot 'Check-Environment.ps1') -RequireRuntime }
Write-TopicInfo 'Project CPU checks PASS; GPU/capture gates require their own real evidence.'
