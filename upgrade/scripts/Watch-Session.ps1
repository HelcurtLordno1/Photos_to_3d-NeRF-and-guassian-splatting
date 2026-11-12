param([Parameter(Mandatory)][string]$Directory)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$log = Join-Path $Directory 'console.log'
$offset = 0L
Write-Host 'Capture Intelligence console. Ctrl+B D detaches; use Manage-Session Stop to checkpoint.'
while ($true) {
    if (Test-Path -LiteralPath $log) {
        $stream = [IO.File]::Open($log, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            [void]$stream.Seek($offset, [IO.SeekOrigin]::Begin)
            $reader = [IO.StreamReader]::new($stream, [Text.UTF8Encoding]::new($false))
            $content = $reader.ReadToEnd()
            $offset = $stream.Position
            if ($content) { [Console]::Write($content) }
        } finally { $stream.Dispose() }
    }
    Start-Sleep -Seconds 1
}
