[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
# Run in Administrator PowerShell. Every GPU task independently repeats this gate.
Invoke-TopicPython -Arguments @('safety-check')
