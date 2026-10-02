# Setup và vận hành đầy đủ · Native Windows PowerShell

Runbook này đối chiếu với scripts hiện tại, [session operations](docs/session_operations.md), [setup snapshot](docs/setup_status_2026-09-23.md), [kiến trúc project](README.md#4-kiến-trúc-từ-input-đến-kết-quả-có-bằng-chứng), [bản đồ code](README.md#6-cấu-trúc-project-và-điểm-vào-code) và [Spatial Studio](UI_design/README.md). Dùng để cài máy mới, chạy pipeline nghiên cứu và mở UI; không xem các lệnh sửa lỗi/pause/release là một chuỗi phải chạy hết.

**Máy đã hoàn tất experiments: bắt đầu ở [mục 2](#2-máy-đã-setup-mở-ui-trước), không training lại. Máy mới: mục 1 → 3 → 4 → 5.** Mục 6–10 là lựa chọn vận hành/QA/nghiệm thu khi cần. Tài liệu setup ngày 2026-09-23 là snapshot lịch sử; trạng thái hiện tại 2026-10-02 là đủ 10/10 train/eval và toàn bộ render/export, research session `awaiting-evidence`.

## Quy ước trước khi copy lệnh

- Dùng **native Windows PowerShell 5.1**, tại **root repo**, không dùng Bash/WSL cho CUDA pipeline. Không cần activate Conda.
- **Run as administrator** khi setup build tools, chạy `Check-GpuSafety`, train/eval/render/export hoặc UI inference. Capture CPU, build UI và artifacts-only UI không cần quyền GPU.
- Chạy **từng block theo thứ tự**, đọc kết quả trước block tiếp theo. Stop/Resume, artifacts/inference, direct/managed và primary/diagnostic là các lựa chọn riêng.
- Giữ nguyên một PowerShell session cho các block chia sẻ biến; mở shell mới thì đặt lại thư mục, execution policy và biến cần dùng. Không có dấu `PS>` hay placeholder `<...>` trong commands thực thi bên dưới.
- JSON đọc bằng `-Raw -Encoding UTF8`; dùng `-LiteralPath` cho đường dẫn có spaces/tiếng Việt. Scripts suy root từ `$PSScriptRoot`.
- `configs/project.psd1` là nguồn pins. Snapshot `artifacts/logs/runtime/requirements.txt` không phải portable pip installer; UI dùng registry + `UI_design/package-lock.json`.
- Một GPU operation tại một thời điểm. Đóng các workload CUDA khác; không mở viewer/inference trong timed benchmark. Failed/partial artifacts được giữ để audit, không xóa để làm lệnh “chạy sạch”.

## 1. Máy mới: clone → host tools → full environment

### 1.1. Prerequisites

Baseline đã kiểm chứng: Windows x64, RTX A4500 Laptop 16 GB / compute capability 8.6, NVIDIA driver và `nvidia-smi`, Git, Miniconda, MSVC v142/14.29 và Windows SDK. `Setup-Runtime.ps1` hiện build tiny-cuda-nn cho **86**; đổi GPU cần xác nhận lại compiler/build và protocol, không chỉ tăng/giảm batch một phương pháp.

Cần Internet cho upstream/dependencies/datasets. Archive official Mip-NeRF 360 là **12.535.427.936 bytes**; tối thiểu 20 GiB free của downloader chưa bao gồm mọi environment, extracted data, canonical copies, checkpoint/PLY và logs. Chuẩn bị thêm dung lượng theo workload và giữ archive để reuse.

Driver NVIDIA không được installer project cài. `winget` phải hoạt động để cài host tools. Trình duyệt UI cần WebGL2. WSL/tmux chỉ cần cho **managed sessions ở mục 6**, không cần cho quickstart trực tiếp.

### 1.2. Clone và cài host tools

Mở Windows PowerShell Administrator. Folder mặc định dưới đây dùng được ngay; nếu đổi vị trí thì dùng cùng vị trí ở mục 1.3.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = 'Stop'

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Git installation failed.' }
    throw 'Git installed. Reopen Administrator PowerShell and run this block again.'
}

$checkoutRoot = 'C:\CVProjects\Topic_16_CV'
if (Test-Path -LiteralPath $checkoutRoot) { throw 'Checkout already exists. Use the existing checkout instead of cloning over it.' }
New-Item -ItemType Directory -Path (Split-Path $checkoutRoot) -Force | Out-Null
git clone --branch main https://github.com/HelcurtLordno1/Photos_to_3d-NeRF-and-guassian-splatting.git $checkoutRoot
if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
Set-Location -LiteralPath $checkoutRoot
.\scripts\Install-HostTools.ps1 -InstallBuildTools
```

Nếu block vừa cài Git, nó dừng có chủ đích để bạn mở shell mới và chạy lại. Sau `Install-HostTools`, cũng **mở lại Administrator PowerShell** để nhận PATH/installer changes. Build tools installer chọn đủ C++ v142 và SDK cần thiết; không thay bằng MSVC mới nhất rồi mặc định CUDA 11.8 tương thích.

Clone chỉ có files Git đang track. Recipe UI yêu cầu checkout có `UI_design\scripts\Setup-UI.ps1`; nếu revision lấy về chưa có UI, nhận đúng source revision từ chủ dự án trước khi tiếp tục. Không tự pull/update một session đang training để thêm UI.

### 1.3. Cài environment, official data và UI dependencies

```powershell
Set-Location -LiteralPath 'C:\CVProjects\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = 'Stop'

.\scripts\Check-Environment.ps1
.\scripts\Setup-Project.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Test-Project.ps1 -RequireRuntime
.\scripts\Test-Datasets.ps1 -Mode all -WriteManifest
.\UI_design\scripts\Setup-UI.ps1
```

| Lệnh | Công việc | Thành phẩm cần thấy |
|---|---|---|
| `Check-Environment.ps1` | Kiểm Git, Conda, driver/GPU, build tools, storage | Required host checks hoàn tất |
| `Setup-Project.ps1` | Download upstream → Setup-Runtime → runtime check → all datasets → freeze | Env `topic16-ns115`, source/data đúng pins, requirements snapshot |
| `Check-Environment.ps1 -RequireRuntime` | CUDA/import/native CLI validation qua Test-Runtime | Runtime checks PASS |
| `Test-Project.ps1 -RequireRuntime` | Parser, core contract/negative fixtures và runtime | QA PASS; analyzer optional được báo riêng |
| `Test-Datasets.ps1 -Mode all -WriteManifest` | Kiểm official images, poses, counts, hashes | Dataset manifest hợp lệ |
| `Setup-UI.ps1` | Node đúng pin + official SHA verification + npm lockfile install | UI dependencies sẵn sàng; chưa tạo scene catalog |

**Vì sao không có một lệnh `pip install -r requirements.txt` cho cả project?** Có cả Conda native DLLs, CUDA toolkit, PyTorch wheels theo index, gsplat wheels, tiny-cuda-nn build bằng MSVC và Nerfstudio editable checkout. Snapshot freeze hiện có local build URLs; không thể biến thành installer portable chỉ bằng đổi tên file. `Setup-Project.ps1` là entrypoint thực hiện đúng các bước đó và xuất `artifacts/logs/runtime/requirements.txt` để audit. `Setup-UI.ps1` xử lý frontend riêng, không thêm Python packages vào environment đã train.

Không chạy `Setup-Runtime.ps1 -RebuildEnvironment` trên happy path: tùy chọn này **xóa/tạo lại Conda environment**. Repair/finalize có điều kiện ở mục 10.

### 1.4. Nếu Conda cài ở vị trí không nằm trong PATH

Core scripts tìm override, PATH và các vị trí cài thông dụng. Với vị trí khác, nhập **đường dẫn thật tới `Scripts\conda.exe`** một lần trong shell hiện tại:

```powershell
$condaExecutable = Read-Host 'Full path to Scripts\conda.exe in your Miniconda installation'
if (-not (Test-Path -LiteralPath $condaExecutable -PathType Leaf)) { throw 'Conda executable not found.' }
$env:TOPIC16_CONDA_EXE = (Resolve-Path -LiteralPath $condaExecutable).Path
.\scripts\Check-Environment.ps1 -RequireRuntime
```

Với máy chưa setup runtime, bỏ `-RequireRuntime` ở lần kiểm tra đầu rồi quay lại mục 1.3. Không hard-code đường dẫn Conda của laptop này cho máy khác. UI launcher còn dò registered Python installs trên Windows, nhưng core setup không được giả định đã có UI helper nạp sẵn.

## 2. Máy đã setup: mở UI trước

### 2.1. Đi vào checkout và mở thành phẩm

Nếu terminal đã ở root repo, chỉ cần `Invoke-Topic16.ps1 ui`. Nếu mở terminal mới ở nơi khác, block này hỏi checkout path thật:

```powershell
$existingCheckout = Read-Host 'Full path to your existing Topic_16_CV checkout'
Set-Location -LiteralPath $existingCheckout
Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = 'Stop'

# Reuse the Conda location recorded by an existing managed session, if present.
$hostRecord = '.\artifacts\logs\sessions\topic16-full\host.json'
if (Test-Path -LiteralPath $hostRecord) {
    $sessionHost = Get-Content -LiteralPath $hostRecord -Raw -Encoding UTF8 | ConvertFrom-Json
    if (Test-Path -LiteralPath $sessionHost.conda -PathType Leaf) {
        $env:TOPIC16_CONDA_EXE = $sessionHost.conda
    }
}
.\Invoke-Topic16.ps1 ui
```

Profile `auto` bật inference khi server được chạy Administrator, còn lại dùng artifacts. Nếu reuse một server artifacts đang chạy, lệnh auto không tự nâng quyền server đó; chọn profile rõ ràng như mục 2.3 để đổi mode.

### 2.2. UI chưa build hoặc cần cập nhật catalog/build

Cần có đầy đủ exact matrices, evaluation, throughput và exports của research trước prepare; clone code/report alone chưa đủ.

```powershell
.\UI_design\scripts\Prepare-UIAssets.ps1
.\UI_design\scripts\Build-UI.ps1
.\UI_design\scripts\Start-UI.ps1 -Profile artifacts
```

`Prepare-UIAssets` kiểm hashes/contracts rồi tạo cover thật, error images và allowlist tại `artifacts/ui/catalog.json`. Nó **không train và không sửa checkpoint gốc**. `Build-UI` kiểm TypeScript và bundle budget rồi tạo `UI_design/dist`.

### 2.3. Chọn profile, URL và dừng

| Profile | Quyền / capability |
|---|---|
| `artifacts` | Xem gallery/exports/GT/saved predictions/metrics/diagram; không mở CUDA worker |
| `inference` | Administrator, CUDA runtime và GPU guard; render chính xác tại camera mới |
| `auto` | Inference nếu elevated; artifacts nếu không. Có thể reuse service phù hợp đã mở |

**Chọn một** trong hai lệnh sau, không chạy hai servers chỉ để đổi profile:

```powershell
.\UI_design\scripts\Start-UI.ps1 -Profile artifacts
```

```powershell
.\UI_design\scripts\Start-UI.ps1 -Profile inference
```

Server ưu tiên `http://127.0.0.1:7016`, fallback tới 7020. `-Port 7018` yêu cầu đúng cổng 7018; `-NoBrowser` không tự mở tab. Đọc URL thực ở một terminal khác:

```powershell
$uiState = Get-Content -LiteralPath '.\artifacts\ui\server.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$uiState.url
```

Giữ terminal chạy server. Khi muốn dừng/đổi profile, chạy ở **terminal PowerShell khác tại root**:

```powershell
.\UI_design\scripts\Stop-UI.ps1
```

Stop chỉ nhắm service cùng checkout và owned worker. Sau đó Start lại với profile mong muốn. Bookmarks thuộc browser origin; backup JSON trước khi đổi port.

**Viewport:** N là point-cloud proxy; S là full Gaussian export qua Spark. Saved eval images và Render ảnh model mới là kết quả checkpoint thật. Camera N/S dùng chung frozen model frame; không fit lại từng model. Chọn Song song/N/S, orbit/zoom/pan, camera sync, gallery speed và presets trong giao diện. Inference N/S chạy tuần tự, không chạy song song CUDA. Xem [UI README](UI_design/README.md) cho thao tác đầy đủ.

## 3. Dữ liệu trước full research

### 3.1. Official data / canonical input

Nếu mục 1.3 đã PASS thì downloader không cần chạy lại để mở UI. Trên máy cần bổ sung/kiểm data:

```powershell
.\scripts\Download-Datasets.ps1 -Mode all
.\scripts\Test-Datasets.ps1 -Mode all -WriteManifest
```

Archive/source có pinned SHA/bytes/revision. Poster giữ 100 matched images từ 226 metadata entries; Garden 185, Bonsai 292, Room 311. Valid downloads được reuse. Không xóa `data/.cache/360_v2.zip` để “làm sạch”.

Train tự prepare canonical; có thể làm trước để tách data time khỏi train:

```powershell
.\scripts\Prepare-Scene.ps1 -Dataset poster
.\scripts\Prepare-Scene.ps1 -Dataset bonsai
.\scripts\Prepare-Scene.ps1 -Dataset garden
.\scripts\Prepare-Scene.ps1 -Dataset room
```

Canonical dùng chung undistort/crop/intrinsics, sparse points, LANCZOS downscale và explicit train/val/test lists. Source raw không sửa. Preparation/hash mismatch không được chữa bằng sửa hash thủ công. Open3D Windows dùng ASCII junction trong TEMP trỏ vào repo, không copy một dataset khác.

### 3.2. Custom `tea_sets_2`: nguồn → frames → COLMAP → figures

Để tái lập đúng cảnh đã công bố, lấy video gốc từ chủ dự án. SHA-256 nằm trong block; file này không có URL downloader và không nằm trong Git. Thiếu nguồn thì dừng nhánh custom, không lấy video khác làm cùng identity.

```powershell
$videoTarget = '.\data\testing_real_video\tea_sets_2.mp4'
if (-not (Test-Path -LiteralPath $videoTarget -PathType Leaf)) {
    $sourceVideo = Read-Host 'Full path to the original tea_sets_2.mp4'
    if (-not (Test-Path -LiteralPath $sourceVideo -PathType Leaf)) { throw 'Source video not found.' }
    New-Item -ItemType Directory -Path (Split-Path $videoTarget) -Force | Out-Null
    Copy-Item -LiteralPath $sourceVideo -Destination $videoTarget
}
$expectedVideoHash = 'dda518b9a383dc97f88d53d60ee6c972e5cb13c12e1f9d9ac770a4d7335b5c9d'
if ((Get-FileHash -LiteralPath $videoTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedVideoHash) {
    throw 'Video differs from the original dataset. Use the original video, or define a separate custom scene/protocol.'
}

.\scripts\Extract-Video.ps1 -Video $videoTarget -Scene tea_sets_2
.\scripts\Process-Capture.ps1 -Scene tea_sets_2 -CpuOnly `
    -TrainImages '.\data\raw\custom\tea_sets_2\train' `
    -EvalImages '.\data\raw\custom\tea_sets_2\eval'
.\scripts\Review-Capture.ps1 -Scene tea_sets_2
Start-Process '.\reports\custom_capture\tea_sets_2\poses.png'
Start-Process '.\reports\custom_capture\tea_sets_2\projections.png'
```

Baseline: video 64,07 s / 1.922 frames → 120 PNG theo timestamps → **105 train + 15 eval**. CPU SIFT/matching/mapper giới hạn 4 threads. Phải có một **connected model** register ≥90% train và mọi eval; không ghép components hoặc bỏ eval. Baseline model 1 register đủ 120/120, attempt nhỏ model 0 được giữ.

Nếu processing đã dừng sau mapping và có sparse models để khôi phục, dùng **thay cho việc process lại từ đầu**:

```powershell
.\scripts\Process-Capture.ps1 -Scene tea_sets_2 -CpuOnly -Recover `
    -TrainImages '.\data\raw\custom\tea_sets_2\train' `
    -EvalImages '.\data\raw\custom\tea_sets_2\eval'
```

### 3.3. Review thật và approval của capture

Xem `poses.png` và `projections.png` trước. Kiểm camera trajectory quanh cảnh, registration, frustums, sparse cloud và độ khớp projections. Sau khi thật sự review, chạy:

```powershell
$reviewer = Read-Host 'Your name after inspecting the pose and projection figures'
$notes = Read-Host 'Your actual observations about camera poses and sparse geometry'
if ([string]::IsNullOrWhiteSpace($reviewer) -or [string]::IsNullOrWhiteSpace($notes)) {
    throw 'A real reviewer and actual review notes are required.'
}
.\scripts\Approve-Capture.ps1 -Scene tea_sets_2 -Reviewer $reviewer -Notes $notes
.\scripts\Review-Capture.ps1 -Scene tea_sets_2 -VerifyOnly
```

Nếu checkout đã có approval hợp lệ cho exact capture, chỉ dùng `Review-Capture.ps1 -Scene tea_sets_2 -VerifyOnly`, không cần ghi reviewer khác. `-VerifyOnly` không tạo figures và không cấp approval. Capture approval là gate geometry, **không thay human research/independent replay endorsement**.

Video cũ `tea_sets.mp4` có tay xoay khay là attempt khác. Single-video held-out eval là interpolation, các views theo thời gian có tương quan; COLMAP sử dụng viewpoints để ước lượng pose, nhưng chỉ train pixels đi vào optimizer.

## 4. Full research có matrix đúng cho UI

### 4.1. Safety bắt buộc cho mỗi GPU stage

Mở Administrator PowerShell, runtime/data/capture đã hợp lệ. Mỗi GPU job tự reapply `nvidia-smi -i 0 -lgc 300,800`; thất bại sẽ chặn workload. `Check-GpuSafety.ps1` kiểm policy trước khi chạy. Chỉ start dưới 65°C; watchdog 2 s dừng ở ≥78°C, ≥80 W, ≥95% VRAM, clock vượt ceiling/tolerance hoặc telemetry thiếu/timeout. Đây là policy project, không phải rating nhà sản xuất.

Không tăng power limit/reset clocks để bypass. Log lý do ở `artifacts/logs/safety/`; [GPU safety protocol](docs/protocols/gpu_safety.md) nêu retry và giới hạn.

Nếu cần đọc telemetry trước lượt chạy, block này chỉ query trạng thái; không thay safety gate của wrappers:

```powershell
nvidia-smi -i 0 -q -d POWER,CLOCK,TEMPERATURE
if ($LASTEXITCODE -ne 0) { throw 'GPU telemetry query failed. Do not start a GPU workload.' }
```

### 4.2. Lượt mới: foreground, không cần tmux

**Luồng mặc định cho người muốn copy–paste setup → research → UI:**

```powershell
.\scripts\Check-GpuSafety.ps1
.\scripts\Run-Research.ps1 `
    -SessionDirectory '.\artifacts\logs\research\topic16-full' `
    -CustomScene tea_sets_2
```

Không chạy lại block lượt mới khi `artifacts/logs/research/topic16-full/session.json` đã tồn tại. Đọc state trước và dùng mục 4.3 nếu có stage chưa hoàn tất.

| Thứ tự | Scene / nhiệm vụ | Output |
|---|---|---|
| Preflight | Custom review, GPU safety, contracts/runtime, official data | Checks/evidence |
| Poster | Hai methods primary full smoke | `topic16-full-poster.json` |
| Calibration | Bonsai pair | `topic16-full-calibration.json` |
| Benchmark | Garden + Room pairs | `topic16-full-benchmark.json` |
| Custom | Tea sets pair | `topic16-full-custom.json` |
| Measurement | Exact configs từ các matrices → held-out timed render + exports | Videos/render timings + PLY + hashes |
| Analysis | Tables, figures và G-Core | `reports/topic16-full/` |

Tổng 10 train/eval runs; primary 30k / seed 42 / downscale 2. Poster bị loại khỏi bảng primary; custom là nhóm riêng. Budget iterations bằng nhau không bằng FLOPs hay batch semantics. Không override một method để né OOM rồi coi là cùng protocol.

Một lượt tái lập tạo run IDs, timings và evidence riêng; cùng seed/recipe không bảo đảm output giống từng byte trên phần cứng/runtime khác. `Run-Research` dựng lại bảng/figures/gate từ selected matrices, nhưng các HTML/cases/source bundles đã track ở `reports/topic16-full/review/` là snapshot của nghiên cứu gốc; không dùng chúng hoặc endorsement cũ để ký runs mới.

**Tại sao session name quan trọng?** `Run-Research` lấy basename của `SessionDirectory` làm prefix matrices/report. UI builder hiện đọc **cố định** bốn `topic16-full-*.json` và `reports/topic16-full`. Chỉ đổi `Ui.Selection` trong registry chưa đổi selection của builder hiện tại. `Run-Research` không tham số sẽ tạo UTC-name, không tạo đúng baseline UI. Adapter `Invoke-Topic16.ps1 research` cũng không truyền custom option; dùng script direct như block này.

### 4.3. Tiếp tục đúng direct session

Chỉ dùng khi đã xác nhận session cần tiếp tục và không còn worker active:

```powershell
.\scripts\Run-Research.ps1 `
    -SessionDirectory '.\artifacts\logs\research\topic16-full' `
    -CustomScene tea_sets_2 -Resume
```

Completed runs/stages được kiểm hashes và reuse; evaluation/render/export chưa xong retry với exact config. Resume luôn cùng custom selection/path. Không chọn `latest` hoặc đổi dataset/protocol giữa chừng.

Foreground phù hợp với chạy liên tục trong terminal. Ctrl+C/kill/reboot không phải cooperative checkpoint Stop; nếu cần pause để cất laptop, chọn **managed sessions ngay từ đầu** ở mục 6. Safety stop/unexpected kill cần kiểm state và evidence trước khi retry, không mặc định đã có clean resume checkpoint.

### 4.4. Đọc state và bước tiếp theo

```powershell
Get-Content -LiteralPath '.\artifacts\logs\research\topic16-full\session.json' -Raw -Encoding UTF8
Get-Content -LiteralPath '.\reports\topic16-full\g-core.json' -Raw -Encoding UTF8
```

`awaiting-evidence` là kết quả hợp lệ khi full artifacts có nhưng chưa đủ human reviews; không đồng nghĩa train failed. Đọc từng check trong gate. Với mục tiêu xem project, sang mục 5. Với nghiệm thu/release nghiên cứu, xem mục 9; không thay approval false bằng true khi chưa review.

### 4.5. Chỉ chạy official scenes khi chưa có custom video

Luồng này tạo 8 official runs và report riêng, **chưa tạo đầy đủ catalog 5 scenes mặc định**:

```powershell
.\scripts\Check-GpuSafety.ps1
.\scripts\Run-Research.ps1 -SessionDirectory '.\artifacts\logs\research\official-only'
```

Nếu cần tiếp tục official-only: thêm `-Resume` vào cùng lệnh, không thêm CustomScene giữa session. Khi có đủ custom input và muốn baseline UI, dùng selection đầy đủ mục 4.2; không rename/copy matrix để giả identity. Muốn UI baseline khác phải thay selection adapter và kiểm contracts của nó.

## 5. Từ full artifacts đến Spatial Studio

Sau khi full research tạo đủ eval/throughput/export của 10 runs:

```powershell
.\UI_design\scripts\Prepare-UIAssets.ps1
.\UI_design\scripts\Build-UI.ps1
.\UI_design\scripts\Start-UI.ps1 -Profile artifacts
```

Đây là các bước CPU/disk/frontend, không yêu cầu replay experiments. Builder sẽ từ chối partial pair, missing matrix/export, changed hash/runtime/split thay vì giả scene sẵn sàng. `-Profile artifacts` vẫn có gallery, dual 3D exports, saved comparison và benchmark; chỉ nút checkpoint render không được bật.

Khi cần exact-model render camera mới, dùng Stop ở terminal khác và Start inference như mục 2.3. UI renderer chạy N/S **tuần tự**, request result bind camera/run/catalog revision. Camera đổi trong lúc render thì kết quả stale bị bỏ, không ghép nửa pair.

### Thêm scene đã train ngoài bộ 5 scenes

Phải có **một pair primary mới** với exact configs, evaluation, held-out throughput và exports hợp lệ; matrix nằm trong repo. Sau đó:

```powershell
$extraMatrix = Read-Host 'Repo-relative path to the validated additional scene matrix'
if (-not (Test-Path -LiteralPath $extraMatrix -PathType Leaf)) { throw 'Extra matrix not found.' }
.\UI_design\scripts\Prepare-UIAssets.ps1 -ExtraMatrix $extraMatrix
```

`-ExtraMatrix` **bổ sung** vào baseline `topic16-full`, không thay baseline và không giúp clone trống bỏ qua missing matrices. Scene trùng identity bị reject. Restart UI để nhận catalog revision mới. Một lần Prepare sau đó không có `-ExtraMatrix` sẽ dựng lại chỉ baseline; luôn truyền lại extra selection khi muốn giữ scene bổ sung.

## 6. Lựa chọn: managed session để detach / pause / checkpoint resume

Chỉ dùng **thay cho direct research**, không khởi động đồng thời hai luồng trên cùng matrices. Prerequisite: Windows có WSL distro hoạt động, distro đó có **Python 3 + tmux**, console bridge dùng được; chỉ log console nằm trong WSL, toàn bộ Conda/CUDA vẫn native Windows. Chuẩn bị/kiểm console trước Start: script lưu job trước khi kiểm WSL, nên Start khi console chưa sẵn sàng có thể để lại job chưa chạy.

Lượt mới dùng Name `topic16-full` để hợp UI baseline; chỉ Start khi chưa có session/job và research selection này chưa chạy trực tiếp:

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name topic16-full -Task research -CustomScene tea_sets_2
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
```

**Ctrl+B rồi D** detach console; training vẫn chạy trong native worker. Đóng tmux không pause. Không đóng minimized worker window để yêu cầu checkpoint.

Ở terminal khác, xem state:

```powershell
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
```

Khi thật sự muốn dừng để cất máy:

```powershell
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
```

**Chờ `paused` và worker thoát trước khi shutdown/reboot.** Stop đặt request; trainer save sau iteration hoàn tất, eval/render dừng giữa cameras; export dừng owned child. Checkpoint lưu model/optimizer/scheduler/scaler/RNG/sampler/strategy; commit mỗi 500 bước và khi Stop.

Khi mở máy và muốn tiếp tục một session paused hợp lệ, trong Administrator PowerShell tại cùng checkout:

```powershell
$sessionHost = Get-Content -LiteralPath '.\artifacts\logs\sessions\topic16-full\host.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$env:TOPIC16_CONDA_EXE = $sessionHost.conda
if ($sessionHost.cuda_path) { $env:CUDA_PATH = $sessionHost.cuda_path }
.\scripts\Check-GpuSafety.ps1
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
```

Resume dùng saved job, không retype Task/CustomScene/budget. Segment mới tham chiếu committed parent checkpoint và chỉ chạy budget còn lại. Partial inference được loại khỏi measurements, stage chưa hoàn tất chạy lại; complete stages verify/reuse.

**Điều kiện identity:** giữ source, frozen data, runtime, GPU/protocol và registry snapshot. Managed worker hiện so sánh **toàn bộ registry**, nên session cũ trước khi thêm `Ui` cũng có thể bị reject nếu registry đổi; không sửa `settings.json` để vượt check. Runbook này không khẳng định session lịch sử sẽ Resume dưới registry mới. Laptop đã hoàn tất artifacts không cần Resume để mở UI; dùng mục 2. Chi tiết lịch sử/checkpoint và evidence tại [session_operations](docs/session_operations.md).

## 7. Lựa chọn: chạy/đo một pair hoặc một model

### 7.1. Diagnostic và primary phải riêng

Smoke nhanh kiểm pipeline, không chứng minh model quality/densification/full budget:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes poster -Protocol diagnostic -Iterations 100 `
    -MatrixPath '.\artifacts\logs\matrices\poster-check.json'
```

Một calibration pair primary, không dùng cùng file matrix diagnostic:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes bonsai `
    -MatrixPath '.\artifacts\logs\matrices\bonsai-primary.json'
```

Lượt tiếp tục matrix này dùng cùng scenes/protocol/seed/budget và thêm `-Resume`. Đây là nhánh riêng, không tự thêm nó vào baseline UI đã có Bonsai. Primary iterations/seed khác defaults bị reject; `repeat` seeds 43/44 có report riêng.

### 7.2. Train một model và dùng exact config trả về

```powershell
.\scripts\Train.ps1 -Method nerfacto -Dataset poster `
    -ResultPath '.\artifacts\logs\run-selection.json'
$selection = Get-Content -LiteralPath '.\artifacts\logs\run-selection.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$config = $selection.config
.\scripts\Evaluate-Run.ps1 -ConfigPath $config
.\scripts\Render-Run.ps1 -ConfigPath $config
.\scripts\Export-Run.ps1 -ConfigPath $config
```

`$config` là đường dẫn do trainer trả về; không là placeholder và không tìm config bằng timestamp. Nerfacto point export dùng Open3D normals; Splatfacto export có Gaussian attributes. Checkpoint bytes đo model state, PLY bytes đo artifact dẫn xuất.

### 7.3. Lấy hai configs chính xác từ matrix và render chung trajectory

Dùng một selected pair đã thành công, ví dụ calibration của full session:

```powershell
$matrix = Get-Content -LiteralPath '.\artifacts\logs\matrices\topic16-full-calibration.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$nerfactoConfig = Join-Path (Get-Location).Path $matrix.pairs.bonsai.runs.nerfacto
$splatfactoConfig = Join-Path (Get-Location).Path $matrix.pairs.bonsai.runs.splatfacto
$cameraPath = '.\reports\bonsai-shared-camera.json'
.\scripts\Create-CameraPath.ps1 -ConfigPath $nerfactoConfig -OutputPath $cameraPath
.\scripts\Render-Run.ps1 -ConfigPath $nerfactoConfig -CameraPath $cameraPath
.\scripts\Render-Run.ps1 -ConfigPath $splatfactoConfig -CameraPath $cameraPath
```

Camera JSON có `render_width`, `render_height` (positive/even), `camera_path` gồm `camera_to_world` 16 số và `fov`; FPS video default 24. Demo trajectory có thể khác held-out grid; benchmark primary vẫn dùng held-out camera hash và resolution. Warm-up 3 frames, 3 repeats, CUDA synchronize; load/IO/encoding nằm ngoài FPS. Partial/tampered measurements không PASS và không được overwrite để che attempt.

## 8. Analysis, QA và UI development

### 8.1. Analysis của đúng baseline matrices

Không cần train thêm nếu artifacts hợp lệ:

```powershell
$matrices = @(
    '.\artifacts\logs\matrices\topic16-full-poster.json',
    '.\artifacts\logs\matrices\topic16-full-calibration.json',
    '.\artifacts\logs\matrices\topic16-full-benchmark.json',
    '.\artifacts\logs\matrices\topic16-full-custom.json'
)
.\scripts\Analyze-Results.ps1 -MatrixPaths $matrices -OutputDirectory '.\reports\topic16-full'
```

Outputs `results.csv/json/md`, figures, `crops.json`, `g-core.json`. Poster là gate, không aggregate primary; custom có nhóm riêng. Nếu report selection đã có endorsed review, truyền lại đúng `-ReviewPath` để analysis không đánh giá gate thiếu review. Không đưa diagnostic matrix vào primary analysis.

Diagnostic riêng sau khi đã chạy mục 7.1:

```powershell
.\scripts\Analyze-Results.ps1 `
    -MatrixPaths '.\artifacts\logs\matrices\poster-check.json' `
    -Protocol diagnostic -OutputDirectory '.\reports\diagnostic'
```

### 8.2. QA không thêm training

```powershell
.\scripts\Test-Project.ps1 -RequireRuntime
.\UI_design\scripts\Test-UI.ps1
```

UI QA chạy typecheck, unit tests, PowerShell parse và CPU backend tests. Browser integration cần UI server đã mở và Windows browsers đã cài; chạy tại terminal khác, lấy URL thực:

```powershell
$uiState = Get-Content -LiteralPath '.\artifacts\ui\server.json' -Raw -Encoding UTF8 | ConvertFrom-Json
.\UI_design\scripts\Test-UI.ps1 -Browser -Url $uiState.url
```

CPU-only contributor có Git/PowerShell/Python 3.10+:

```powershell
.\scripts\Test-Project.ps1 -PythonExecutable python
```

CPU fixtures không xác nhận CUDA memory, training quality hoặc G-Core review. PSScriptAnalyzer optional; nếu reviewer đã cài module thì dùng `Test-Project.ps1 -RequireAnalyzer` để enforce. Test UI hiện cần environment/backend dependencies và Node setup; không hiểu CPU-only core test là đã setup đủ UI.

### 8.3. UI development

Sau UI setup + prepare:

```powershell
.\UI_design\scripts\Dev-UI.ps1
```

Vite dev URL mặc định port **5176**, backend là URL localhost được wrapper xác minh. Giữ terminal; Ctrl+C dừng dev. Thay UI source thì Build trước khi dùng production Start. Sau đổi pins trong registry, dùng **chỉ khi chủ động cập nhật dependency lock**:

```powershell
.\UI_design\scripts\Setup-UI.ps1 -UpdateLock
.\UI_design\scripts\Build-UI.ps1
```

Không dùng `-UpdateLock` cho mỗi lượt mở app. Native scripts và mọi UI code nằm trong `UI_design/`; contracts/runtime wrappers dùng core hiện có.

## 9. Nghiệm thu nghiên cứu và certified demo/release (tùy chọn riêng)

Để **xem Spatial Studio**, không cần phần này. Để ký G-Core/release, cần actual independent replay và research review endorse đúng run keys/settings/evidence, ngoài các artifacts contracts đã hoàn tất. Xem [review checklist](reports/topic16-full/review/review_checklist.md) và [reproduction runbook](reports/topic16-full/review/replay_runbook.md) cho reviewer/máy khác; không yêu cầu laptop đã xong replay để mở UI.

Tạo bản endorsement để reviewer chỉnh, không tự ghi đè review có sẵn:

```powershell
$reviewPath = '.\reports\review.json'
if (-not (Test-Path -LiteralPath $reviewPath)) {
    Copy-Item -LiteralPath '.\docs\protocols\review.example.json' -Destination $reviewPath
}
notepad.exe $reviewPath
```

Dừng để reviewer điền `run_keys`, `settings_hash` từ **exact current gate**, tên/nhận xét và evidence paths sau review thật. `review.pending.json` với approvals false là pending, không phải endorsed review.

Sau khi endorsement hợp lệ, cùng `$matrices` ở mục 8.1:

```powershell
.\scripts\Analyze-Results.ps1 -MatrixPaths $matrices `
    -OutputDirectory '.\reports\topic16-full' -ReviewPath '.\reports\review.json'
```

Nếu muốn direct research tiếp tục sang certified demo/release, cùng selection:

```powershell
.\scripts\Run-Research.ps1 `
    -SessionDirectory '.\artifacts\logs\research\topic16-full' `
    -CustomScene tea_sets_2 -Resume `
    -ReviewPath '.\reports\review.json' -DemoMethod splatfacto
```

Pipeline revalidate/reuse artifacts; chỉ G-Core PASS mới tạo shared demo trajectory, selected model, health evidence và release. `DemoMethod` là lựa chọn demo, không kết luận phương pháp thắng. UI và certified local demo là hai entrypoints khác nhau.

Sau khi pipeline in ra và tạo `reports/topic16-full/demo-splatfacto/model.json`, mở certified demo:

```powershell
.\scripts\Start-Demo.ps1 -ModelPath '.\reports\topic16-full\demo-splatfacto\model.json'
```

Service này dùng **127.0.0.1:7007**, fixed-camera slider, serial GPU request và gate/health checks; không phải Spatial Studio port 7016. Ctrl+C dừng. Nếu cần offline fallback, chạy riêng:

```powershell
.\scripts\Start-Demo.ps1 -ModelPath '.\reports\topic16-full\demo-splatfacto\model.json' -Fallback
```

Release không bundle dataset/checkpoint lớn vào Git. Transfer **đủ files listed in release graph** với checksums; chỉ copy checkpoint/PLY sẽ thiếu frozen split/config/runtime/data evidence. Loader relocate paths trong bộ nhớ, không sửa bytes của original config/checkpoint. New source/UI changes không tự làm immutable research source snapshot tương đương.

## 10. Repair có điều kiện và xử lý lỗi

### Native DLL repair / finalize

Chỉ dùng khi environment đã tồn tại và lỗi native tools tương ứng; không phải mỗi lần mở UI:

```powershell
.\scripts\Setup-Runtime.ps1 -RepairNativeTools
.\scripts\Test-Runtime.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Setup-Project.ps1 -FinalizeOnly
```

`FinalizeOnly` kiểm runtime, reuse/download official data và refresh freeze, không rebuild tiny-cuda-nn. Không chạy repair/update packages giữa hai segments cần giữ exact runtime identity.

| Triệu chứng | Cách xử lý đúng |
|---|---|
| Git/Conda chưa được tìm thấy sau cài | Mở PowerShell mới; Conda nonstandard dùng TOPIC16_CONDA_EXE ở mục 1.4 |
| Thiếu v142/compiler/SDK | Cài host build tools elevated; đọc Check-Environment, không đổi compiler tùy ý |
| PowerShell chặn script | Set-ExecutionPolicy -Scope Process Bypass cho shell hiện tại |
| GPU cap bị từ chối | Run as administrator; dừng trước workload, không bypass guard |
| GPU nóng/busy hoặc safety stop | Đọc safety logs, đóng workload khác, chờ cool start; giữ attempt |
| UI thiếu catalog/dist | Đủ research artifacts trước, rồi Prepare-UIAssets và Build-UI |
| UI thiếu topic16-full matrix | Session prefix chưa đúng/partial; kiểm mục 4, không lấy latest hoặc rename matrix |
| Prepare-UIAssets thiếu export/throughput | Hoàn tất stage từ exact pair config; report Markdown/CSV không thay checkpoint/PLY |
| Start-UI inference bị từ chối | Administrator + đúng Conda/runtime; dùng artifacts profile nếu chỉ cần xem exports |
| UI đang ở port khác | Đọc server.json/launcher URL; test dùng actual URL, backup bookmarks trước đổi origin |
| WebGL context lost / PLY loading error | Retry/Cancel trong pane, kiểm WebGL2/memory; saved images/metrics còn xem được |
| Custom pose/registration kém | Kiểm capture/projections; recovery nếu mapping đã đủ; scene mới khi nguồn khác |
| OOM | Giữ failed run, đóng workload khác; nếu đổi protocol phải áp dụng cả pair và báo cáo riêng |
| Matrix/session already exists | Status/state trước; Resume đúng selection khi cần, không Start/overwrite tiếp |
| Managed Resume báo registry/source mismatch | Dùng recorded identity; không sửa snapshot để hợp thức hóa; artifacts hoàn tất thì mở UI |
| Split/config/checkpoint hash mismatch | Tìm nguồn thay đổi và giữ evidence, không cập nhật hash thủ công |
| Unicode Open3D/TEMP lỗi | ASCII junction do wrapper tạo; TEMP cần ASCII và quyền tạo junction |
| G-Core BLOCKED/awaiting-evidence | Đọc actual checks; local UI vẫn dùng valid artifacts; reviewer bổ sung evidence khi nghiệm thu |
| PSScriptAnalyzer unavailable | Check được báo skipped; nếu cần enforce, cài module rồi RequireAnalyzer |

Downloads nghiên cứu bổ sung, không bắt buộc để mở UI:

```powershell
.\scripts\Download-Papers.ps1
.\scripts\Download-Repositories.ps1 -Mode research
```

Tóm lược paths để kiểm tra: `configs/project.psd1` (pins), `artifacts/logs/research/topic16-full/session.json` (research state), `artifacts/logs/matrices/topic16-full-*.json` (exact selections), `reports/topic16-full/g-core.json` (gate), `artifacts/ui/catalog.json` (UI assets), `artifacts/ui/server.json` (URL/profile state). Các files generated có thể Git ignored; giữ chúng khi chuyển máy hoặc cần resume. Các lệnh trong tài liệu đã được đối chiếu với entrypoints hiện tại; việc setup/retraining thành công trên một máy mới vẫn cần host/data thật, không được suy từ parser/CPU tests.
