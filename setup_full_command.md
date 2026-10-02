# Runbook native Windows PowerShell

Chạy tại repo bằng PowerShell 5.1+, **Administrator cho mọi GPU command**.
Không activate Conda. Root suy từ
script location, không hard-code ổ D:. Commands có parameter arrays giữ đúng
spaces/Unicode. JSON đọc bằng `-Encoding UTF8` trên PowerShell 5.1.

## 1. Máy mới và máy đã setup

```powershell
Set-Location -LiteralPath 'D:\path\to\Topic_16_CV'  # sửa duy nhất dòng này theo checkout
Set-ExecutionPolicy -Scope Process Bypass
.\Invoke-Topic16.ps1 help
.\scripts\Check-Environment.ps1
```

Host cần Git, Miniconda, NVIDIA driver và MSVC v142/14.29. Nếu thiếu build tools,
chạy installer trong PowerShell elevated; tiếp tục dùng cửa sổ elevated cho GPU:

```powershell
.\scripts\Install-HostTools.ps1 -InstallBuildTools
.\scripts\Setup-Project.ps1
.\scripts\Check-GpuSafety.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
```

Máy đã có runtime không cài lại. Bắt đầu mỗi phiên elevated bằng safety gate:

```powershell
.\scripts\Check-GpuSafety.ps1
.\scripts\Test-Runtime.ps1
.\scripts\Test-Project.ps1
```

Nếu setup cũ cần sửa native DLL tools/finalize:

```powershell
.\scripts\Setup-Runtime.ps1 -RepairNativeTools
.\scripts\Setup-Project.ps1 -FinalizeOnly
```

`-RebuildEnvironment` chỉ dùng khi chủ máy chủ động muốn xóa/tạo lại Conda env;
không cần cho các bước dưới. Registry ở `configs/project.psd1`; requirement snapshot
ở `artifacts/logs/runtime/requirements.txt`, không dùng nó thay installer/CUDA/compiler.

Máy CPU chỉ cần Git/PowerShell/Python 3.10+ cho contract checks:

```powershell
.\scripts\Test-Project.ps1 -PythonExecutable python
```

Không chạy CUDA setup hoặc ký GPU PASS trên CPU. PSScriptAnalyzer optional;
`Test-Project.ps1 -RequireAnalyzer` enforce module khi reviewer đã cài.

## Safety bắt buộc trước mọi GPU stage

Mỗi job tự reapply `nvidia-smi -i 0 -lgc 300,800`; exit khác 0 chặn trước workload.
Query `nvidia-smi -i 0 -q -d POWER,CLOCK,TEMPERATURE` chỉ báo cáo. Policy:
start <65°C; watchdog 2 giây stop ở ≥78°C, ≥80 W, ≥95% VRAM, clock vượt cap hoặc
telemetry thiếu/timeout. Reason ở `artifacts/logs/safety/`; không reset xung/tăng
power limit, không bypass vì idle clock thấp. Xem [GPU safety](docs/protocols/gpu_safety.md).

## 2. Data validation và canonical input

```powershell
.\scripts\Download-Datasets.ps1 -Mode all
.\scripts\Test-Datasets.ps1 -Mode all -WriteManifest
.\scripts\Prepare-Scene.ps1 -Dataset poster
.\scripts\Prepare-Scene.ps1 -Dataset bonsai
```

Downloader resume official archive; verify byte size + pinned SHA-256. Poster raw
226 metadata entries / 100 available images được match thành subset 100. Processed
JSON không BOM; downloader repair BOM cũ có backup, raw không đổi.

Canonical preparation có thể tốn vài phút CPU/disk cho scene lớn: đọc full-resolution
nguồn, common undistort/crop/intrinsics, LANCZOS downscale, sparse points và explicit
split. Train tự gọi bước này; có thể chuẩn bị trước để tách data time khỏi train time.
Valid output reuse/check hashes; data fingerprint độc lập thermal/video/demo policy.
Khác ảnh/pose/data settings hoặc partial bị reject; metadata cũ migrate có backup
khi immutable snapshot và source/output hashes chứng minh tương đương.
Nếu partial/failure, giữ `preparation.json`, logs/data để chẩn đoán; không tự xóa raw.
Windows Open3D dùng ASCII junction trong TEMP; không phải bản dataset thứ hai.

## 3. Diagnostic smoke và full primary

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes poster -Protocol diagnostic -Iterations 100 `
    -MatrixPath .\artifacts\logs\matrices\poster-check.json
```

100 iterations chỉ xác nhận pipeline, không chứng minh full training/densification fit
hay model quality. Full primary smoke:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes poster `
    -MatrixPath .\artifacts\logs\matrices\poster-primary.json
```

Primary default 30k / seed 42 / downscale 2. `-Iterations` hoặc `-Seed` khác primary
bị reject; dùng diagnostic hoặc repeat riêng. Không có arbitrary trailing CLI override.

Chạy trainer riêng và lấy config đúng run:

```powershell
.\scripts\Train.ps1 -Method nerfacto -Dataset poster -ResultPath .\artifacts\logs\run-selection.json
$config = (Get-Content .\artifacts\logs\run-selection.json -Raw -Encoding UTF8 | ConvertFrom-Json).config
.\scripts\Evaluate-Run.ps1 -ConfigPath $config
```

Không lookup latest. Failed run giữ immutable ID/log, không trở thành successful pair.

## 4. Calibration, full matrix, resume

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes bonsai `
    -MatrixPath .\artifacts\logs\matrices\bonsai-primary.json
# Sau khi calibration PASS:
.\scripts\Run-Benchmark.ps1 -Scenes garden,room `
    -MatrixPath .\artifacts\logs\matrices\remaining-primary.json
```

Resume dùng đúng path và cùng scenes/protocol/iterations/seed:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes garden,room `
    -MatrixPath .\artifacts\logs\matrices\remaining-primary.json -Resume
```

Resume reuse config successful; eval chưa hoàn tất retry đúng config. Managed
clean stop restore explicit committed trainer checkpoint trong segment mới, đúng
tổng budget; failure khác giữ attempt để audit. Không chọn latest theo timestamp.
Không chạy hai terminals train/viewer; OS GPU lock reject competing operations.

Lệnh toàn bộ primary research theo thứ tự:

```powershell
.\scripts\Run-Research.ps1
# Copy session directory script vừa in, không tự chọn latest:
$session = 'D:\path\to\Topic_16_CV\artifacts\logs\research\<printed-UTC-ID>'
.\scripts\Run-Research.ps1 -SessionDirectory $session -Resume
```

Để toàn project đạt G-Core, cần custom và human review ở bước 5/7. Session chỉ
đủ official runs sẽ ghi `awaiting-evidence`, không báo project complete.

## 5. Static tea-set video, CPU capture và review

Dữ liệu chính hiện tại: `tea_sets_2.mp4` (camera di chuyển, bộ trà đứng yên),
64,07 s/1.922 frames → 120 PNG lossless → 105 train/15 eval. `video.json` lưu
source/timestamp/index/split/checksum provenance. Các lệnh CPU không cần
Administrator và giữ cùng OS lock với GPU jobs:

```powershell
.\scripts\Extract-Video.ps1 -Video .\data\testing_real_video\tea_sets_2.mp4 -Scene tea_sets_2
.\scripts\Process-Capture.ps1 -Scene tea_sets_2 -CpuOnly `
    -TrainImages .\data\raw\custom\tea_sets_2\train `
    -EvalImages .\data\raw\custom\tea_sets_2\eval
.\scripts\Review-Capture.ps1 -Scene tea_sets_2
```

Extraction/capture thành công được reuse sau kiểm tra hashes. CPU SIFT/matching
và mapper tối đa 4 threads; `--no-gpu` bắt buộc trong CPU path. Sparse output có
nhiều components: chọn một model đủ ≥90% train và **mọi eval**; không nối components
hoặc bỏ eval. Model 1 của tea_sets_2 đã register 105/105 train và 15/15 eval.
Upstream default model 0 chỉ có hai train; đã giữ attempt cũ và refine/convert
model 1 qua pinned SDK. Nếu command đã dừng sau mapping, recovery reuse models:

```powershell
.\scripts\Process-Capture.ps1 -Scene tea_sets_2 -CpuOnly -Recover `
    -TrainImages .\data\raw\custom\tea_sets_2\train `
    -EvalImages .\data\raw\custom\tea_sets_2\eval
```

Visual evidence ở `reports/custom_capture/tea_sets_2/`: `poses.png`,
`projections.png`, `pose_evidence.json`. Sau khi thực sự xem frustums và sparse
projections, ghi đúng người review và nhận xét; approval bind exact split/evidence:

```powershell
.\scripts\Approve-Capture.ps1 -Scene tea_sets_2 `
    -Reviewer 'Tên người thực sự review' -Notes 'Nhận xét thực tế về poses/cloud/projections'
.\scripts\Review-Capture.ps1 -Scene tea_sets_2 -VerifyOnly
```

Scene hiện đã có **agent visual audit** ghi rõ Codex; không giả danh Member 2,
lead hoặc thay independent human research/replay review. Không cần approve lại
để chạy branch hiện tại; reviewer có thể xem evidence trước human acceptance.
Video đầu `tea_sets.mp4` có tay xoay khay, giữ nguyên làm attempt cũ.
Single-video held-out eval là interpolation; temporally adjacent views tương quan.
COLMAP dùng tất cả viewpoints để ước lượng pose, chỉ train pixels đưa vào optimizer.

Chạy nhánh custom riêng sau Administrator safety check:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes 'custom:tea_sets_2' `
    -MatrixPath .\artifacts\logs\matrices\custom-primary.json
```

Hoặc chạy toàn bộ ordered session từ đầu:

```powershell
.\scripts\Run-Research.ps1 -CustomScene tea_sets_2
```

Preflight audit custom chạy trước training. Poster → bonsai → garden/room →
custom; cả hai methods 30k, eval/render/export tuần tự, rồi analysis. Khi còn
human review/replay, session ghi `awaiting-evidence`. Sau actual reviews ở bước 7,
resume đúng session và custom để tiếp tục demo/release:

```powershell
.\scripts\Run-Research.ps1 -SessionDirectory '<exact session path printed earlier>' `
    -Resume -CustomScene tea_sets_2 -ReviewPath .\reports\review.json -DemoMethod splatfacto
```

Khi G-Core PASS, script tạo shared demo path, render hai methods, select explicit
DemoMethod, health check và release trong report session. Method lựa chọn là
preference cho demo; không tự kết luận scientific winner. Script in đường dẫn
model để mở local service bằng `Start-Demo.ps1`.

## 6. Throughput, shared camera path và export

Dùng exact config từ selected matrix/trainer:

```powershell
.\scripts\Render-Run.ps1 -ConfigPath $config
.\scripts\Export-Run.ps1 -ConfigPath $config
```

Renderer mặc định đo held-out cameras, warm-up 3 frames, 3 repeats, CUDA synchronization,
IO không tính FPS. Hai methods phải chạy cùng cameras; archive result path có camera hash.
Tạo deterministic demo path từ frozen evaluation poses, hoặc dùng viewer JSON
đã save ở repo. Demo path có intrinsics/resolution riêng, không thay held-out
metric grid; dùng cùng file cho cả hai methods:

```powershell
.\scripts\Create-CameraPath.ps1 -ConfigPath $config -OutputPath .\reports\camera_path.json
.\scripts\Render-Run.ps1 -ConfigPath $config -CameraPath .\reports\camera_path.json
```

Chạy cùng camera path/resolution cho cả hai configs. Camera JSON dùng
`render_width`, `render_height` (even positive), `camera_path` chứa `camera_to_world`
16 số + `fov`; video FPS default 24 nếu không có field `fps`. Complete render/export
được reuse sau kiểm tra checkpoint/frame/PLY hashes. Partial hoặc tampered output
không overwrite/không PASS: giữ attempt và xử lý recovery/version riêng.

Gaussian export là Gaussian PLY; Nerfacto export là derived point cloud với Open3D
normals. Checkpoint bytes là primary model-size metric; PLY format/size ghi riêng.

## 7. Analysis và G-Core

```powershell
$matrices = @(
    '.\artifacts\logs\matrices\poster-primary.json',
    '.\artifacts\logs\matrices\bonsai-primary.json',
    '.\artifacts\logs\matrices\remaining-primary.json',
    '.\artifacts\logs\matrices\custom-primary.json'
)
.\scripts\Analyze-Results.ps1 -MatrixPaths $matrices -OutputDirectory .\reports\measured
```

Outputs: `results.csv/json/md`, `figures`, `crops.json`, `g-core.json`.
Primary excludes poster. Same-camera crops không tự chứng minh failure hypothesis;
researcher review và giải thích bằng paper/pose/coverage evidence.

Copy `docs/protocols/review.example.json` thành `reports/review.json`; copy
`run_keys` và `settings_hash` từ exact `g-core.json` hiện tại. Review phải endorse
đúng selected runs/registry; ghi approval
chỉ sau independent replay/research review thật và dẫn evidence file paths:

```powershell
.\scripts\Analyze-Results.ps1 -MatrixPaths $matrices `
    -OutputDirectory .\reports\measured -ReviewPath .\reports\review.json
```

Diagnostic/repeat reports là nhánh riêng và G-Core luôn BLOCKED:

```powershell
.\scripts\Analyze-Results.ps1 -MatrixPaths .\artifacts\logs\matrices\poster-check.json `
    -Protocol diagnostic -OutputDirectory .\reports\diagnostic
```

## 8. Model selection, local demo, release

Chỉ khi actual G-Core PASS, video đã render từ cùng camera path:

```powershell
.\scripts\Select-Model.ps1 -ConfigPath $config -GatePath .\reports\measured\g-core.json `
    -CameraPath .\reports\camera_path.json -OutputPath .\reports\model-v1.json
.\scripts\Start-Demo.ps1 -ModelPath .\reports\model-v1.json -HealthOnly
.\scripts\Start-Demo.ps1 -ModelPath .\reports\model-v1.json
```

Mở `http://127.0.0.1:7007`; fixed-camera slider, một request GPU mỗi lần.
Ctrl+C stop. `/health` chỉ ready sau hash/runtime/model/warm-up/determinism checks.
Health check lưu `<model>.health.json`; release cần record này với exact model
hash và completed GPU safety. Nếu mở service, Ctrl+C trước release; chạy lại
`-HealthOnly` khi cần evidence mới. Fallback offline:

```powershell
.\scripts\Start-Demo.ps1 -ModelPath .\reports\model-v1.json -Fallback
.\scripts\Write-Release.ps1 -ModelPath .\reports\model-v1.json -OutputPath .\reports\release-v1.json
```

Không bundle raw/checkpoint lớn vào Git. Transfer exact files listed in release,
verify hashes, setup runtime bằng pins rồi replay trên checkout mới. Gate evidence,
canonical data và model artifacts cần giữ nguyên khi transfer; loader relocate paths
trong bộ nhớ, không sửa config/checkpoint bytes.

## 9. QA và troubleshooting

```powershell
.\scripts\Test-Project.ps1 -RequireRuntime
.\scripts\Test-RunManifest.ps1 -Path '<exact logs/run-key/manifest.json>'
git status --short
git check-ignore .\data\.cache\360_v2.zip
```

| Lỗi | Kiểm tra / xử lý |
|---|---|
| Missing runtime/tool | Check-Environment/Test-Runtime; giữ exact pins, không pip-upgrade tùy tiện |
| UTF-8 BOM | Rerun Download-Datasets smoke repair processed metadata; raw giữ nguyên |
| Unicode Open3D | Junction ASCII tự tạo; nếu TEMP Unicode phải dùng checkout/TEMP ASCII |
| Custom register/pose thấp | Sửa capture/new scene version; không tune model che pose lỗi |
| OOM | Giữ failed attempt; đóng workload khác; protocol mới phải áp dụng cả pair và bảng riêng |
| Matrix exists | Resume exact matrix; không đổi scenes/protocol hoặc overwrite |
| Split/config/model hash mismatch | Giữ evidence, tìm thay đổi input; không cập nhật hash để hợp thức hóa |
| G-Core BLOCKED | Đọc từng check và bổ sung actual custom/full runs/replay/review |
| Analyzer unavailable | Check explicitly skipped; reviewer cài analyzer rồi dùng -RequireAnalyzer |

Research paper/repo downloads optional:

```powershell
.\scripts\Download-Papers.ps1
.\scripts\Download-Repositories.ps1 -Mode research
```

## 10. Tmux, stop và checkpoint resume

Ưu tiên managed session cho lượt dài; xem [session_operations](docs/session_operations.md).

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name topic16-full -Task research -CustomScene tea_sets_2
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
# Ctrl+B, D detach: training vẫn chạy.
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
# Chờ Status=paused rồi:
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
```

WSL: `tmux attach -t topic16-full`. Conda/CUDA luôn ở Windows. Worker tự yêu cầu
elevation khi cần, reapply clock cap từng GPU job; không bypass quyền/telemetry.
Giữ nguyên source/config/runtime/frozen split trong suốt session cần resume.
Inference độc lập dùng `-Task inference -Operation evaluate|render|export -ConfigPath
<exact-config>`; `-CameraPath` chỉ áp dụng render. Eval/render/export partial được
giữ làm failed/paused evidence và chạy lại stage, không cộng partial FPS/metrics.
