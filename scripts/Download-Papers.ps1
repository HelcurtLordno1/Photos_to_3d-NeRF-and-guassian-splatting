[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

$paperDirectory = Join-Path $ProjectRoot 'docs\research\papers'
New-TopicDirectory -Path $paperDirectory

function Save-Pdf {
    param([string]$FileName, [string]$Url)
    $destination = Join-Path $paperDirectory $FileName
    if (Test-Path -LiteralPath $destination) {
        $stream = [System.IO.File]::OpenRead($destination)
        try {
            $bytes = New-Object byte[] 4
            [void]$stream.Read($bytes, 0, 4)
            if ([Text.Encoding]::ASCII.GetString($bytes) -eq '%PDF') {
                Write-TopicInfo "$FileName already exists; skipping."
                return
            }
        } finally { $stream.Dispose() }
    }
    $partial = "$destination.part"
    Write-TopicInfo "Downloading $FileName"
    & curl.exe --fail --location --retry 4 --output $partial $Url
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $Url" }
    $header = [Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($partial)[0..3])
    if ($header -ne '%PDF') { throw "Downloaded file is not a PDF: $Url" }
    Move-Item -LiteralPath $partial -Destination $destination -Force
}

$papers = @(
    @('01_nerf_eccv2020.pdf', 'https://arxiv.org/pdf/2003.08934'),
    @('02_mipnerf360_cvpr2022.pdf', 'https://arxiv.org/pdf/2111.12077'),
    @('03_instant_ngp_siggraph2022.pdf', 'https://arxiv.org/pdf/2201.05989'),
    @('04_nerfstudio_siggraph2023.pdf', 'https://arxiv.org/pdf/2302.04264'),
    @('05_3d_gaussian_splatting_siggraph2023.pdf', 'https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/3d_gaussian_splatting_low.pdf'),
    @('06_gsplat_jmlr2025.pdf', 'https://jmlr.org/papers/volume26/24-1476/24-1476.pdf'),
    @('07_colmap_cvpr2016.pdf', 'https://openaccess.thecvf.com/content_cvpr_2016/papers/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.pdf')
)
foreach ($paper in $papers) { Save-Pdf -FileName $paper[0] -Url $paper[1] }
Write-TopicInfo "Core papers are ready under $paperDirectory."
