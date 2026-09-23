# Full PowerShell Setup & Command Runbook

> Dự án: **Photos to 3D — Nerfacto vs Splatfacto/3D Gaussian Splatting**
> Runtime: **native Windows PowerShell only**
> Máy đích: **RTX A4500 Laptop 16 GB, compute capability 8.6**
> Protocol: **30k iterations, seed 42, downscale 2, eval interval 8**
> Kiến trúc: [`Construction_architect.md`](Construction_architect.md)
> Working list: [`Modular_construct.md`](Modular_construct.md)

Trạng thái setup được kiểm chứng trên laptop ngày 2026-09-23:
[`docs/setup_status_2026-09-23.md`](docs/setup_status_2026-09-23.md). Kiểm tra
`G-Core` trước khi chạy training hoặc production.

Không chạy lệnh trong WSL, Git Bash hoặc CMD. Mọi block dưới đây chạy trong
**Windows PowerShell** tại project root. Script dùng `conda run`, vì vậy không cần
`conda activate` và không phụ thuộc trạng thái terminal.

## 1. Dataset commands — đặt ở đầu để dễ tìm

```powershell
# Vào đúng project (giữ dấu nháy vì path có khoảng trắng)
Set-Location 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass

# Benchmark chính: tải archive Mip-NeRF 360 chính thức, resume được,
# kiểm tra đúng 12,535,427,936 bytes và chỉ giải nén garden/bonsai/room.
.\scripts\Download-Datasets.ps1 -Mode benchmark

# Poster từ repository chính thức của Nerfstudio trên Hugging Face.
# Downloader tự tạo Python env tối thiểu; không cần CUDA để tải dữ liệu.
.\scripts\Download-Datasets.ps1 -Mode smoke

# Hoặc tải cả hai profiles bằng một lệnh.
.\scripts\Download-Datasets.ps1 -Mode all

# Xác nhận đúng folder project và dữ liệu dùng được.
Test-Path .\data\processed\nerfstudio\poster\transforms.json
@((Get-Content .\data\processed\nerfstudio\poster\transforms.json -Raw | ConvertFrom-Json).frames).Count
foreach ($scene in 'garden','bonsai','room') {
    Test-Path ".\data\raw\mipnerf360\$scene\images_2"
    Test-Path ".\data\raw\mipnerf360\$scene\sparse\0\cameras.bin"
}
```

Benchmark download cần tối thiểu 20 GiB trống; nên giữ 30–40 GiB cho data, model và
renders. Archive được cache tại `data\.cache\360_v2.zip`; không xóa nếu muốn rerun
không tải lại. Không commit dataset/archive lên Git.

Nguồn poster Google Drive của bản Nerfstudio pin có thể từ chối `gdown`.
`Download-Datasets.ps1` dùng bản chính thức
[`nerfstudioteam/datasets`](https://huggingface.co/datasets/nerfstudioteam/datasets/tree/main/poster)
ở commit đã pin trong `configs\project.psd1`. Repo này có 100 ảnh nhưng
`transforms.json` liệt kê 226 frames; script giữ nguyên nguồn tại `data\raw`, rồi
tạo subset hợp lệ 100 frames tại `data\processed\nerfstudio\poster`. Training
chỉ dùng folder processed. Script chỉ báo PASS sau khi kiểm tra từng ảnh gốc,
`images_2`, sparse points và mọi đường dẫn frame trong subset.

## 2. Quy ước PowerShell-only

- PowerShell 5.1 đi kèm Windows dùng được; PowerShell 7 cũng dùng được.
- Không chạy `make`, `.sh`, `bash`, `wsl` hoặc đổi path thành `/mnt/d/...`.
- Không `pip install --upgrade` thủ công trong base Conda.
- Tất cả pin nằm trong `configs\project.psd1`.
- Không chạy hai training jobs cùng lúc trên GPU 16 GB.
- Không mở viewer trong timed training.
- Production bị khóa cho đến khi `G-Core` trong `Modular_construct.md` PASS.

## 3. Mở PowerShell và preflight host

```powershell
Set-Location 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass
$Topic16Root = (Get-Location).Path

.\Invoke-Topic16.ps1 help
.\scripts\Check-Environment.ps1
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
Get-PSDrive -Name D | Select-Object Name,@{N='FreeGiB';E={[math]::Round($_.Free/1GB,1)}}
```

Preflight phải thấy `NVIDIA RTX A4500 Laptop GPU`, khoảng `16384 MiB` và compute
capability `8.6`. Dừng ở đây nếu `nvidia-smi`, Git hoặc Conda missing.

### 3.1 Cài host tools nếu thiếu

```powershell
# Kiểm tra/cài Git và Miniconda qua winget.
.\scripts\Install-HostTools.ps1

# Mở riêng Windows PowerShell bằng "Run as administrator" cho lệnh này.
# Cài Visual Studio Build Tools + C++ + MSVC v142 để build tiny-cuda-nn.
Set-Location 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Install-HostTools.ps1 -InstallBuildTools
```

Sau khi winget cài mới, đóng PowerShell, mở lại, vào project và chạy preflight lại.
Script runtime sẽ cài CUDA toolkit, COLMAP, FFmpeg và Ninja **trong Conda env**;
không cần cài các bản global riêng.

### 3.2 Một lệnh setup đầy đủ sau khi MSVC v142 đã cài

```powershell
Set-Location 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Setup-Project.ps1
```

Lệnh trên kiểm tra host, checkout Nerfstudio đúng commit, cài CUDA/COLMAP/PyTorch/
Nerfstudio/gsplat/tiny-cuda-nn vào `topic16-ns115`, tải hai dataset profiles vào
`data\raw`, kiểm tra GPU import và xuất danh sách dependency thực tế tại
`artifacts\logs\runtime\requirements.txt`. Nerfstudio v1.1.5 khai báo dependency
gốc trong `third_party\nerfstudio\pyproject.toml`; file `requirements.txt` sinh ra
là snapshot để kiểm toán, không phải một bộ pin cạnh tranh với
`configs\project.psd1`. Lệnh có thể chạy lại sau khi download bị ngắt.

## 4. Tạo native Windows runtime đã pin

| Component | Pin |
|---|---|
| Conda environment | `topic16-ns115` |
| Python | 3.10 |
| PyTorch / torchvision | 2.1.2+cu118 / 0.16.2+cu118 |
| CUDA toolkit | 11.8.0 |
| Nerfstudio | v1.1.5, exact commit |
| gsplat | 1.4.0 Windows wheel for pt21/cu118 |
| tiny-cuda-nn | exact commit, build for CC 8.6 |
| COLMAP | 3.9.1 |

```powershell
Set-Location $Topic16Root
.\scripts\Download-Repositories.ps1 -Mode runtime
.\scripts\Setup-Runtime.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
```

Không dùng Pixi: Nerfstudio v1.1.5 khai báo Pixi platform `linux-64`; native Windows
đi theo official Conda/PyTorch/MSVC path. Setup ưu tiên precompiled gsplat wheel để
giảm rủi ro compile, nhưng tiny-cuda-nn vẫn cần MSVC.

### 4.1 Kiểm tra thủ công không activate

```powershell
conda run --no-capture-output -n topic16-ns115 python -c "import torch,gsplat,nerfstudio,tinycudann; print(torch.__version__, torch.version.cuda); print(torch.cuda.get_device_name(0)); print(gsplat.__version__)"
conda run --no-capture-output -n topic16-ns115 ns-train --help
conda run --no-capture-output -n topic16-ns115 ns-process-data --help
conda run --no-capture-output -n topic16-ns115 ns-eval --help
conda run --no-capture-output -n topic16-ns115 colmap -h
```

### 4.2 Rebuild sạch environment khi thật sự cần

Lệnh này xóa **chỉ Conda env có tên đã pin**, không xóa dataset/artifacts:

```powershell
.\scripts\Setup-Runtime.ps1 -RebuildEnvironment
```

## 5. Tải dữ liệu và kiểm tra layout

```powershell
Set-Location $Topic16Root
.\scripts\Download-Datasets.ps1 -Mode smoke

Test-Path .\data\processed\nerfstudio\poster\transforms.json
Get-ChildItem .\data\processed\nerfstudio\poster -Directory
```

Benchmark có thể tải trước hoặc sau smoke gate:

```powershell
.\scripts\Download-Datasets.ps1 -Mode benchmark

foreach ($scene in 'garden','bonsai','room') {
    if (-not (Test-Path ".\data\raw\mipnerf360\$scene\images_2")) { throw "Missing images_2: $scene" }
    if (-not (Test-Path ".\data\raw\mipnerf360\$scene\sparse\0")) { throw "Missing sparse/0: $scene" }
    Write-Host "$scene OK"
}
Get-Item .\data\.cache\360_v2.zip | Select-Object FullName,Length
```

## 6. Smoke gate: training và inference tách riêng

### 6.1 Training core

```powershell
Set-Location $Topic16Root
nvidia-smi
.\scripts\Train.ps1 -Method nerfacto -Dataset poster
.\scripts\Train.ps1 -Method splatfacto -Dataset poster
```

Hai lệnh phải tạo checkpoint/config và provenance dưới:

```text
artifacts\runs\poster\<method>\<UTC-ID>\
artifacts\logs\poster\<method>\<UTC-ID>\
```

### 6.2 Chọn exact config vừa train

```powershell
$NerfPosterConfig = Get-ChildItem .\artifacts\runs\poster\nerfacto -Filter config.yml -File -Recurse |
    Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
$SplatPosterConfig = Get-ChildItem .\artifacts\runs\poster\splatfacto -Filter config.yml -File -Recurse |
    Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName

$NerfPosterConfig
$SplatPosterConfig
```

### 6.3 Inference/evaluation trên held-out views

```powershell
.\scripts\Evaluate-Run.ps1 -ConfigPath $NerfPosterConfig
.\scripts\Evaluate-Run.ps1 -ConfigPath $SplatPosterConfig

Get-ChildItem .\artifacts\metrics\poster -Filter metrics.json -File -Recurse
Get-ChildItem .\artifacts\renders\poster -File -Recurse | Select-Object -First 20
```

Smoke PASS khi cả hai có checkpoint, finite metrics và held-out renders, không
OOM/NaN. Poster chỉ kiểm tra pipeline, không đưa vào benchmark table.

### 6.4 Diagnostic run ngắn

Chỉ dùng debug, không trộn vào primary results:

```powershell
.\scripts\Train.ps1 -Method nerfacto -Dataset poster --max-num-iterations 1000
.\scripts\Train.ps1 -Method splatfacto -Dataset poster --max-num-iterations 1000
```

## 7. Benchmark chính: calibration trước matrix

Không chạy cả sáu job ngay. Đầu tiên chạy một paired scene để xác nhận 16 GB:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes bonsai
```

Khi pair này PASS:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes garden,room
```

Hoặc chạy full matrix từ đầu nếu chưa có run:

```powershell
.\scripts\Run-Benchmark.ps1
```

Orchestrator chạy tuần tự mỗi `scene × method`, rồi inference/eval ngay exact config.
Không mở terminal thứ hai để train song song.

```powershell
Get-ChildItem .\artifacts\metrics -Filter metrics.json -File -Recurse |
    Sort-Object FullName |
    ForEach-Object { Write-Host "=== $($_.FullName)"; Get-Content $_.FullName -Raw }

Get-ChildItem .\artifacts\logs -Filter timing.env -File -Recurse |
    Sort-Object FullName |
    ForEach-Object { Write-Host "=== $($_.FullName)"; Get-Content $_.FullName }
```

## 8. Phone dataset: raw → COLMAP → shared input

### 8.1 Tạo layout và copy ảnh

```powershell
$Scene = 'object_v1'
New-Item -ItemType Directory -Force ".\data\raw\custom\$Scene\train" | Out-Null
New-Item -ItemType Directory -Force ".\data\raw\custom\$Scene\eval" | Out-Null

(Get-ChildItem ".\data\raw\custom\$Scene\train" -File).Count
(Get-ChildItem ".\data\raw\custom\$Scene\eval" -File).Count
```

### 8.2 Process một lần, dùng chung cho cả hai methods

```powershell
.\scripts\Process-Capture.ps1 `
    -Scene $Scene `
    -TrainImages ".\data\raw\custom\$Scene\train" `
    -EvalImages ".\data\raw\custom\$Scene\eval"

Test-Path ".\data\processed\custom\$Scene\transforms.json"
```

Chỉ train khi ít nhất khoảng 90% ảnh train register, frustums hợp lý và sparse cloud
không tách cụm sai. Capture lại nếu pose hỏng; không tune model để che lỗi COLMAP.

### 8.3 Paired training và inference custom scene

```powershell
foreach ($method in 'nerfacto','splatfacto') {
    .\scripts\Train.ps1 -Method $method -Dataset "custom:$Scene"
    $config = Get-ChildItem ".\artifacts\runs\custom-$Scene\$method" -Filter config.yml -File -Recurse |
        Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
    .\scripts\Evaluate-Run.ps1 -ConfigPath $config
}
```

## 9. Viewer, render và export

```powershell
conda run --no-capture-output -n topic16-ns115 ns-viewer --load-config $NerfPosterConfig
```

Viewer mặc định mở port 7007. Không dùng viewer FPS làm metric chính nếu UI,
resolution hoặc camera path khác nhau.

Export Splatfacto Gaussian PLY:

```powershell
$SplatExport = Join-Path $Topic16Root 'artifacts\exports\poster\splatfacto'
New-Item -ItemType Directory -Force $SplatExport | Out-Null
conda run --no-capture-output -n topic16-ns115 ns-export gaussian-splat `
    --load-config $SplatPosterConfig `
    --output-dir $SplatExport
```

Export Nerfacto point cloud:

```powershell
$NerfExport = Join-Path $Topic16Root 'artifacts\exports\poster\nerfacto'
New-Item -ItemType Directory -Force $NerfExport | Out-Null
conda run --no-capture-output -n topic16-ns115 ns-export pointcloud `
    --load-config $NerfPosterConfig `
    --output-dir $NerfExport
```

Render camera path JSON đã lưu từ viewer:

```powershell
New-Item -ItemType Directory -Force .\artifacts\videos | Out-Null
conda run --no-capture-output -n topic16-ns115 ns-render camera-path `
    --load-config $NerfPosterConfig `
    --camera-path-filename 'D:\path\to\camera_path.json' `
    --output-path .\artifacts\videos\poster_nerfacto.mp4
```

Dùng cùng camera path/resolution cho Splatfacto.

## 10. Paper và reference source library

Không cần phần này để train:

```powershell
.\scripts\Download-Papers.ps1
.\scripts\Download-Repositories.ps1 -Mode research

Get-ChildItem .\docs\research\papers -Filter *.pdf
Get-ChildItem .\third_party -Directory | ForEach-Object {
    if (Test-Path (Join-Path $_.FullName '.git')) {
        $sha = git -C $_.FullName rev-parse --short HEAD
        "{0,-30} {1}" -f $_.Name,$sha
    }
}
```

Reference repos chỉ để đọc/đối chiếu paper; không pip-install chúng vào benchmark env.

## 11. PowerShell syntax và repository checks

```powershell
Set-Location $Topic16Root
$parseErrors = @()
Get-ChildItem -Recurse -Filter *.ps1 | ForEach-Object {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
    if ($errors) { $parseErrors += $errors }
}
if ($parseErrors.Count) { $parseErrors; throw 'PowerShell syntax validation failed.' }

.\scripts\Check-Environment.ps1 -RequireRuntime
git status --short
```

## 12. Git workflow

```powershell
git remote -v
git branch --show-current
git status --short
git check-ignore -v .\data\.cache\360_v2.zip

git add .
git status --short
git commit -m 'Add modular native Windows PowerShell pipeline'
git push origin main
```

Không `git add -f` dataset, PDF, third-party source, checkpoint, renders hoặc video.

## 13. Troubleshooting có thứ tự

### GPU không thấy

```powershell
nvidia-smi
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
```

### Conda không tìm thấy

```powershell
Get-Command conda -ErrorAction SilentlyContinue
Get-ChildItem "$env:USERPROFILE\miniconda3\Scripts\conda.exe" -ErrorAction SilentlyContinue
```

### `cl.exe`/tiny-cuda-nn build fail

```powershell
.\scripts\Install-HostTools.ps1 -InstallBuildTools
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
.\scripts\Setup-Runtime.ps1
```

Script thử MSVC 14.29 trước vì CUDA 11.8 nhạy với toolset mới. Không tự nâng CUDA,
Torch hoặc tiny-cuda-nn trong cùng protocol.

### CUDA/torch/gsplat lệch version

```powershell
Get-Content .\configs\project.psd1
conda run --no-capture-output -n topic16-ns115 python -c "import torch,gsplat; print(torch.__version__,torch.version.cuda,gsplat.__version__)"
```

Nếu environment bị sửa ngoài pipeline:

```powershell
.\scripts\Setup-Runtime.ps1 -RebuildEnvironment
```

### Splatfacto OOM

```powershell
nvidia-smi
Get-Content .\configs\project.psd1 | Select-String 'DownscaleFactor|TrainIterations'
```

Đóng workload GPU khác. Nếu vẫn OOM, tạo protocol low-memory mới và chạy lại **cả
Nerfacto lẫn Splatfacto**; không sửa riêng một run.

### Dataset download ngắt

```powershell
.\scripts\Download-Datasets.ps1 -Mode benchmark
```

### Xem run lỗi mới nhất

```powershell
$latestLog = Get-ChildItem .\artifacts\logs -Filter train.log -File -Recurse |
    Sort-Object LastWriteTime | Select-Object -Last 1
Get-Content $latestLog.FullName -Tail 120
```

## 14. Chuỗi lệnh tối thiểu

```powershell
Set-Location 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass

.\scripts\Check-Environment.ps1
.\scripts\Download-Repositories.ps1 -Mode runtime
.\scripts\Setup-Runtime.ps1
.\scripts\Download-Datasets.ps1 -Mode smoke
.\scripts\Train.ps1 -Method nerfacto -Dataset poster
.\scripts\Train.ps1 -Method splatfacto -Dataset poster
```

Sau đó evaluate exact hai `config.yml`; khi smoke PASS mới chạy benchmark và chỉ mở
production sau khi `G-Core` trong working list PASS.
