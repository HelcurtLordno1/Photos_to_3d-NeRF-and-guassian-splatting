[CmdletBinding()]
param([ValidateSet('runtime', 'research', 'all')][string]$Mode = 'runtime')

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
Assert-Command -Name 'git' | Out-Null

function Get-RepositoryAtCommit {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Commit,
        [switch]$Recursive
    )
    $destination = Join-Path $ThirdPartyRoot $Name
    if ((Test-Path -LiteralPath $destination) -and -not (Test-Path -LiteralPath (Join-Path $destination '.git'))) {
        throw "$destination exists but is not a Git repository; refusing to overwrite it."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $destination '.git'))) {
        New-TopicDirectory -Path $destination
        & git -C $destination init
        & git -C $destination remote add origin $Url
    }
    Write-TopicInfo "Fetching $Name at $Commit"
    & git -C $destination fetch --depth 1 origin $Commit
    if ($LASTEXITCODE -ne 0) { throw "Fetch failed: $Name" }
    & git -C $destination checkout --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "Checkout failed: $Name" }
    if ($Recursive) {
        & git -C $destination submodule update --init --recursive --depth 1
        if ($LASTEXITCODE -ne 0) { throw "Submodule update failed: $Name" }
    }
    $actual = (& git -C $destination rev-parse HEAD).Trim()
    if ($actual -ne $Commit) { throw "Commit mismatch for ${Name}: $actual" }
}

New-TopicDirectory -Path $ThirdPartyRoot
if ($Mode -in @('runtime', 'all')) {
    Get-RepositoryAtCommit -Name 'nerfstudio' -Url 'https://github.com/nerfstudio-project/nerfstudio.git' -Commit $Config.NerfstudioCommit
}
if ($Mode -in @('research', 'all')) {
    Get-RepositoryAtCommit -Name 'nerf' -Url 'https://github.com/bmild/nerf.git' -Commit $Config.NerfReferenceCommit
    Get-RepositoryAtCommit -Name 'multinerf' -Url 'https://github.com/google-research/multinerf.git' -Commit $Config.MultinerfReferenceCommit
    Get-RepositoryAtCommit -Name 'instant-ngp' -Url 'https://github.com/NVlabs/instant-ngp.git' -Commit $Config.InstantNgpReferenceCommit -Recursive
    Get-RepositoryAtCommit -Name 'gaussian-splatting' -Url 'https://github.com/graphdeco-inria/gaussian-splatting.git' -Commit $Config.GaussianSplattingReferenceCommit -Recursive
    Get-RepositoryAtCommit -Name 'gsplat' -Url 'https://github.com/nerfstudio-project/gsplat.git' -Commit $Config.GsplatReferenceCommit
    Get-RepositoryAtCommit -Name 'colmap' -Url 'https://github.com/colmap/colmap.git' -Commit $Config.ColmapReferenceCommit
}
Write-TopicInfo "Repository profile '$Mode' is ready under $ThirdPartyRoot."
