# Replay có bằng chứng: cách thực hiện khi chỉ có một máy

## Replay nghĩa là gì?

Có ba mức khác nhau:

| Mức | Thực sự làm gì | Chứng minh được gì |
|---|---|---|
| Artifact replay | Python sạch đọc checkpoint/hash và tính lại bảng từ metrics cũ | Integrity và reproducible analysis, không train/inference |
| Clean-environment GPU replay, cùng máy | Source riêng, Conda mới cài từ pin, tải/prepare data lại, train/eval mới | Tái lập workflow trên cùng phần cứng trong environment mới |
| Independent clean-machine GPU replay | Người khác/máy Windows khác làm cùng quy trình | Thêm độc lập khỏi máy đang dùng; scope/hardware phải ghi rõ |

Đã thực hiện mức 1: venv không có third-party distributions, `python -I`, bản sao
validator, 10 runs audited, results khớp chính xác. Evidence: artifact-audit.json.
Không có inference hoặc train mới ở lượt này. Hai mức sau **chưa chạy**.

User hiện chỉ có một máy. Mức 2 có thể thực hiện trên máy này khi muốn kiểm tra
setup/train/eval từ đầu; không cần xóa Conda/model cũ. Nhưng tiêu chí hiện hành
ở `Modular_construct.md` ghi “Independent clean-machine replay có reviewer, notes
và evidence files”. Vì thế không tự thay mức 3 bằng mức 1 hoặc 2 rồi báo PASS.
Nếu hội đồng/chủ protocol chấp nhận phạm vi cùng máy, quyết định thay phạm vi đó
cần được ghi rõ và review; không thay định nghĩa ngầm để vượt gate.

## Snapshot chuẩn bị sẵn

`replay-source.zip` chứa source/scripts/config/tests/docs đang dùng, bao gồm các
file chưa commit mà Git HEAD đơn lẻ có thể không chứa. `replay-source-manifest.json`
ghi SHA-256 từng file và archive. Nó không chứa data/model, credentials, môi trường
Conda hay cache; cần cài mới runtime và acquire dataset để là replay thực sự.
Source ZIP huấn luyện gốc nằm trong từng `artifacts/logs/<run_key>/source.zip`,
đã được audit với provenance. Source adapter hiện tại có compatibility fix inventory;
không gọi snapshot mới là đúng bytes của source huấn luyện cũ.

## A. Chỉ kiểm tra lại evidence hiện tại, không train

Mở native Windows PowerShell tại repo hiện tại:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$env:TOPIC16_CONDA_EXE = (Get-Content -LiteralPath `
    '.\artifacts\logs\sessions\topic16-full\host.json' -Raw -Encoding UTF8 | ConvertFrom-Json).conda
.\reports\topic16-full\review\Build-Evidence.ps1 -Mode Audit
# CPU tạo lại per-view diagnostics/crops/charts từ PNG cũ, cũng không inference:
.\reports\topic16-full\review\Build-Evidence.ps1 -Mode Figures
# Publish lại HTML, source bundle và checksum index sau khi evidence thay đổi:
.\reports\topic16-full\review\Build-Evidence.ps1 -Mode Package
```

Audit chủ động fail nếu venv có package ngoài standard library, nếu identity/hash
đổi hoặc bảng recompute khác. Không dùng file status PASS cũ thay cho lần chạy mới.
Sau khi regenerate evidence, checksum index/endorsement cũ phải được kiểm tra và
review lại nếu nội dung đổi; không đè evidence đã ký mà vẫn giữ chữ ký cũ.

## B. Chuẩn bị root riêng cho clean-environment replay

Các commands sau **chưa được chạy**, vì đây là scope GPU replay mới. Cần native
Windows PowerShell Administrator cho GPU guard. Chờ session hiện tại không có
GPU worker; chạy tuần tự. Máy khác cần cài Git, Conda và MSVC v142 bằng host runbook
trước. Cùng máy có thể dùng Conda executable đã lưu để tạo **environment khác**.

```powershell
$ErrorActionPreference = 'Stop'
Set-ExecutionPolicy -Scope Process Bypass
$originRoot = (Get-Location).Path  # đang ở repo có evidence gốc
$bundle = Join-Path $originRoot 'reports\topic16-full\review\replay-source.zip'
$manifestPath = Join-Path $originRoot 'reports\topic16-full\review\replay-source-manifest.json'
$expected = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected.archive_sha256) {
    throw 'Replay source archive checksum mismatch.'
}
$env:TOPIC16_CONDA_EXE = (Get-Content -LiteralPath `
    (Join-Path $originRoot 'artifacts\logs\sessions\topic16-full\host.json') `
    -Raw -Encoding UTF8 | ConvertFrom-Json).conda
$replayTag = Get-Date -Format 'yyyyMMdd-HHmmss'
$replayRoot = Join-Path 'D:\' ('Topic16CleanReplay-' + $replayTag)
if (Test-Path -LiteralPath $replayRoot) { throw 'Use a new empty replay directory.' }
Expand-Archive -LiteralPath $bundle -DestinationPath $replayRoot
# Verify extracted source bytes before editing the environment name.
foreach ($item in $expected.files) {
    $path = Join-Path $replayRoot $item.path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) {
        throw "Extracted source mismatch: $($item.path)"
    }
}
Set-Location -LiteralPath $replayRoot
$registry = Join-Path $replayRoot 'configs\project.psd1'
$registryText = [IO.File]::ReadAllText($registry)
$replayEnvironment = 'topic16-replay-' + $replayTag
$registryText = $registryText.Replace("EnvironmentName = 'topic16-ns115'", "EnvironmentName = '$replayEnvironment'")
[IO.File]::WriteAllText($registry, $registryText, [Text.UTF8Encoding]::new($false))
# Snapshot commit identifies replay files; this is not the original Git history.
git init
if ($LASTEXITCODE -ne 0) { throw 'git init failed' }
git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
git -c user.name='Topic16 replay snapshot' -c user.email='replay@local.invalid' commit -m 'Record clean replay source snapshot'
if ($LASTEXITCODE -ne 0) { throw 'git snapshot failed' }
New-Item -ItemType Directory -Path '.\artifacts\logs\replay' -Force | Out-Null
Start-Transcript -Path '.\artifacts\logs\replay\setup-and-training.log'
.\scripts\Check-Environment.ps1
.\scripts\Download-Repositories.ps1 -Mode runtime
.\scripts\Setup-Runtime.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Test-Project.ps1 -RequireRuntime
.\scripts\Download-Datasets.ps1 -Mode smoke
.\scripts\Prepare-Scene.ps1 -Dataset poster
.\scripts\Check-GpuSafety.ps1
.\scripts\Run-Benchmark.ps1 -Scenes poster `
    -MatrixPath '.\artifacts\logs\matrices\replay-poster-primary.json' -Protocol primary
```

Không dùng `conda clone`, không copy environment cũ, không dùng `-RebuildEnvironment`
trên environment gốc, không copy checkpoint/canonical input để giả fresh train/data.
EnvironmentName là delta vận hành duy nhất của registry; pin/protocol giữ nguyên.
Registry hash replay vì vậy khác baseline, cần ghi rõ trong comparison notes.
Setup script khóa engine versions nhưng có dependency transitive được resolver chọn;
freeze và so với snapshot baseline để ghi dependency drift, không hứa byte-identical
dependencies hoặc checkpoint. Máy khác có thể có driver/runtime khác cần review.

## C. Eval/render/export đúng các configs mới và ghi evidence

`Run-Benchmark` đã thực hiện train/eval. Dùng configs trả về trong matrix mới;
không chọn model “latest” của repo gốc:

```powershell
$matrix = Get-Content -LiteralPath '.\artifacts\logs\matrices\replay-poster-primary.json' -Raw -Encoding UTF8 | ConvertFrom-Json
if ($matrix.status -ne 'succeeded') { throw 'Replay matrix incomplete.' }
foreach ($method in @('nerfacto', 'splatfacto')) {
    $exactConfig = Join-Path $replayRoot $matrix.pairs.poster.runs.$method
    .\scripts\Evaluate-Run.ps1 -ConfigPath $exactConfig
    .\scripts\Render-Run.ps1 -ConfigPath $exactConfig
    .\scripts\Export-Run.ps1 -ConfigPath $exactConfig
}
.\scripts\Analyze-Results.ps1 `
    -MatrixPaths '.\artifacts\logs\matrices\replay-poster-primary.json' `
    -OutputDirectory '.\reports\replay-poster-primary'
Stop-Transcript
```

Poster-only primary analysis vẫn BLOCKED do thiếu cả matrix nghiên cứu; đó không
phải failure của replay. Poster ở primary results được bỏ khỏi bảng chính, nên số
poster nằm trong exact `artifacts/metrics/<new_run_key>/metrics.json`. Pair validator
và matrix chứng minh shared cameras/GT. Đây là **scoped workflow replay**, không
reproduce toàn bộ bốn bảng kết quả. Reviewer ghi rõ scope, không endorse chất lượng
garden/room/custom chỉ từ poster. Full reproduction cần runs mới tương ứng cho
bonsai/garden/room/custom; giữ tách reports, không nhập replay run vào baseline.

Evidence giao về repo gốc: source manifest/hash, trước/sau registry delta, hostname/
OS/GPU/driver, người chạy và timestamp, setup transcript, runtime freeze, dataset
validation/preparation/split, exact matrix/config/final checkpoints hoặc hashes kèm
file giao nhận, evaluation/GT/pred hashes, render/export records và safety logs.
Lưu source artifacts vào một folder replay riêng, không đè paths baseline. Nếu hồ sơ
tham chiếu files chưa copy về repo gốc, endorsement của G-Core sẽ không resolve được;
cần giao toàn bộ evidence mà reviewer cần, không chỉ status JSON.

Tiêu chí review: setup hoàn tất không có bypass; pin/delta được giải thích; actual
fresh training đạt target, evaluation finite và same-camera paired contract PASS;
render/export actual PASS; so số mới với số baseline và ghi sai khác; reviewer xác
nhận phạm vi thực sự đã kiểm chứng. Không yêu cầu checkpoint byte-identical vì CUDA/
optimizer có thể không bitwise deterministic. Không tự đặt tolerance sau khi thấy số
để hợp thức hóa kết quả; nếu cần ngưỡng tái lập, chủ protocol chọn trước lần replay.

## Thời gian và dữ liệu cũ

Hai jobs poster baseline đã có số đo trong manifests; thời gian GPU replay sẽ thay
đổi theo setup/download/cache/nhiệt máy. Toàn bộ 8 jobs chính từng dùng khoảng 510,52
phút training active, chưa kể poster, eval/render/export và cài environment. Không
hứa “30 phút xong hết”. Artifact audit chỉ mất thời gian đọc/hash files, không cần
train. Model/metrics/exports cũ được giữ nguyên để dùng về sau.
