[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Path,
    [string]$SchemaPath = (Join-Path $PSScriptRoot '..\configs\run_manifest_schema.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
$schema = Get-Content -LiteralPath $SchemaPath -Raw -Encoding UTF8 | ConvertFrom-Json
$issues = New-Object 'System.Collections.Generic.List[string]'

function Test-Node {
    param($Value, $Rule, [string]$Location)
    if ($null -eq $Value) { $issues.Add("$Location is null"); return }
    if ($Rule.PSObject.Properties['type']) {
        $validType = switch ($Rule.type) {
            'object'  { $Value -is [pscustomobject] }
            'string'  { $Value -is [string] }
            'integer' { $Value -is [int] -or $Value -is [long] -or $Value -is [bigint] }
            'number'  { $Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal] }
            default   { throw "Unsupported schema type: $($Rule.type)" }
        }
        if (-not $validType) { $issues.Add("$Location has wrong type; expected $($Rule.type)"); return }
    }
    if ($Rule.PSObject.Properties['const'] -and $Value -cne $Rule.const) {
        $issues.Add("$Location must equal $($Rule.const)")
    }
    if ($Rule.PSObject.Properties['enum'] -and $Value -cnotin @($Rule.enum)) {
        $issues.Add("$Location is not an allowed value")
    }
    if ($Value -is [string]) {
        if ($Rule.PSObject.Properties['minLength'] -and $Value.Length -lt $Rule.minLength) {
            $issues.Add("$Location is too short")
        }
        if ($Rule.PSObject.Properties['pattern'] -and $Value -cnotmatch $Rule.pattern) {
            $issues.Add("$Location does not match its pattern")
        }
        if ($Rule.PSObject.Properties['format'] -and $Rule.format -eq 'date-time') {
            $parsed = [DateTimeOffset]::MinValue
            $utcSyntax = $Value -cmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$'
            if (-not $utcSyntax -or -not [DateTimeOffset]::TryParse($Value, [ref]$parsed)) {
                $issues.Add("$Location must be an ISO-8601 UTC timestamp")
            }
        }
    }
    if ($Rule.PSObject.Properties['minimum'] -and $Value -lt $Rule.minimum) {
        $issues.Add("$Location is below minimum $($Rule.minimum)")
    }
    if ($Value -is [pscustomobject]) {
        $propertyRules = $Rule.properties
        if ($Rule.PSObject.Properties['required']) {
            foreach ($name in @($Rule.required)) {
                if (-not $Value.PSObject.Properties[$name]) { $issues.Add("$Location.$name is required") }
            }
        }
        foreach ($property in $Value.PSObject.Properties) {
            $childRule = $propertyRules.PSObject.Properties[$property.Name]
            if (-not $childRule) {
                if ($Rule.additionalProperties -eq $false) { $issues.Add("$Location.$($property.Name) is not allowed") }
            } else {
                Test-Node -Value $property.Value -Rule $childRule.Value -Location "$Location.$($property.Name)"
            }
        }
    }
}

Test-Node -Value $manifest -Rule $schema -Location 'manifest'
if ($manifest -is [pscustomobject]) {
    $status = $manifest.PSObject.Properties['status']
    if ($status) {
        foreach ($condition in @($schema.allOf)) {
            if ($status.Value -eq $condition.if.properties.status.const) {
                foreach ($name in @($condition.then.required)) {
                    if (-not $manifest.PSObject.Properties[$name]) { $issues.Add("manifest.$name is required for $($status.Value) runs") }
                }
            }
        }
    }
    $scene = $manifest.PSObject.Properties['scene']
    $method = $manifest.PSObject.Properties['method']
    $key = $manifest.PSObject.Properties['run_key']
    if ($scene -and $method -and $key) {
        $folder = ([string]$scene.Value).Replace(':', '-')
        if (-not ([string]$key.Value).StartsWith("$folder/$($method.Value)/", [StringComparison]::Ordinal)) {
            $issues.Add('manifest.run_key must match scene and method')
        }
        $artifacts = $manifest.PSObject.Properties['artifacts']
        if ($artifacts -and $artifacts.Value -is [pscustomobject]) {
            $prefix = 'artifacts/runs/' + [string]$key.Value
            $configPath = $artifacts.Value.PSObject.Properties['config_path']
            $checkpointPath = $artifacts.Value.PSObject.Properties['checkpoint_dir']
            if ($configPath -and $configPath.Value -cne "$prefix/config.yml") {
                $issues.Add('manifest.artifacts.config_path does not match run_key')
            }
            if ($checkpointPath -and $checkpointPath.Value -cne "$prefix/nerfstudio_models") {
                $issues.Add('manifest.artifacts.checkpoint_dir does not match run_key')
            }
        }
    }
    $started = $manifest.PSObject.Properties['started_at']
    $finished = $manifest.PSObject.Properties['finished_at']
    if ($started -and $finished) {
        $startTime = [DateTimeOffset]::MinValue
        $finishTime = [DateTimeOffset]::MinValue
        if ([DateTimeOffset]::TryParse([string]$started.Value, [ref]$startTime) -and
            [DateTimeOffset]::TryParse([string]$finished.Value, [ref]$finishTime) -and
            $finishTime -lt $startTime) {
            $issues.Add('manifest.finished_at precedes started_at')
        }
    }
}
if ($issues.Count -gt 0) { throw ($issues -join [Environment]::NewLine) }
Write-Host "[topic16] Run manifest valid: $Path"
