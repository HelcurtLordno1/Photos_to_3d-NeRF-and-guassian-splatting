[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Output,
    [ValidateRange(1, 3600)][int]$IntervalSeconds = 10,
    [string]$StopFile,
    [string]$ReadyFile
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
Assert-Command -Name 'nvidia-smi' | Out-Null
New-TopicDirectory -Path (Split-Path ([IO.Path]::GetFullPath($Output)) -Parent)
if (Test-Path -LiteralPath $Output) { throw "GPU log already exists: $Output" }
$columns = @('timestamp', 'index', 'name', 'utilization.gpu', 'memory.used', 'memory.total', 'temperature.gpu', 'power.draw')
do {
    # One short query per sample. There is no native --loop process to orphan.
    $lines = @(& nvidia-smi --id=0 --query-gpu=timestamp,index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) { throw 'nvidia-smi failed to return one GPU sample.' }
    $row = $lines[0] | ConvertFrom-Csv -Header $columns
    if (-not $row.'memory.used' -or $row.index.Trim() -ne '0') { throw 'Invalid GPU sample.' }
    $number = 0.0
    if (-not [double]::TryParse($row.'memory.used'.Trim(), [Globalization.NumberStyles]::Float,
        [Globalization.CultureInfo]::InvariantCulture, [ref]$number) -or $number -lt 0 -or
        [double]::IsNaN($number) -or [double]::IsInfinity($number)) { throw 'Invalid GPU memory sample.' }
    $row | Export-Csv -LiteralPath $Output -NoTypeInformation -Encoding UTF8 -Append
    if ($ReadyFile -and -not (Test-Path -LiteralPath $ReadyFile)) { [IO.File]::WriteAllText($ReadyFile, 'ready') }
    if (-not $StopFile) { Start-Sleep -Seconds $IntervalSeconds; continue }
    $deadline = [DateTime]::UtcNow.AddSeconds($IntervalSeconds)
    while (-not (Test-Path -LiteralPath $StopFile) -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
    }
} while (-not $StopFile -or -not (Test-Path -LiteralPath $StopFile))
