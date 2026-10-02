# Topic 16 — Nerfacto vs Splatfacto

So sánh novel-view synthesis từ ảnh thật trên **một RTX A4500 Laptop 16 GB**:
PSNR/SSIM/LPIPS held-out, thời gian train, VRAM, checkpoint bytes và offline FPS.
Runtime native Windows + PowerShell + Nerfstudio đã pin; không tự viết lại CUDA
renderer hay metric implementation.

Trạng thái nghiệm thu thực tế: [implementation_status](docs/implementation_status.md).
Member 1 P0–P2 đã nghiệm thu; dữ liệu official đủ. Code research, analysis và
adapter demo đã triển khai. **Code có mặt không có nghĩa G-Core đã PASS.**
Static custom `tea_sets_2` đã có paired train/eval thật (diagnostic 100 bước).
Stop/resume cả hai trainers đã kiểm chứng 1.000 bước; full primary 30k và
human research/independent replay có trạng thái riêng trong evidence.

## Bắt đầu

Mở Windows PowerShell **Administrator** tại repo cho mọi lệnh GPU; không cần activate Conda:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Check-GpuSafety.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Test-Project.ps1
.\scripts\Test-Datasets.ps1 -Mode all -WriteManifest
```

Máy mới cài theo [runbook](setup_full_command.md). Máy CPU dùng
`Test-Project.ps1 -PythonExecutable python` với Python 3.10+ để chạy contract tests;
không cần cài CUDA. `configs/project.psd1` là nguồn pin duy nhất;
`artifacts/logs/runtime/requirements.txt` là snapshot kiểm toán.

Mỗi GPU job reapply `nvidia-smi -i 0 -lgc 300,800`; thiếu quyền thì chặn trước
workload. Watchdog độc lập dừng job ở ≥78°C, ≥80 W, ≥95% VRAM, clock vượt cap hoặc
mất telemetry. Chỉ bắt đầu dưới 65°C. Xem [policy/retry/giới hạn](docs/protocols/gpu_safety.md).

Diagnostic có nhãn riêng, không đi vào primary table:

```powershell
.\scripts\Run-Benchmark.ps1 -Scenes poster -Protocol diagnostic -Iterations 100 `
    -MatrixPath .\artifacts\logs\matrices\poster-check.json
```

Full primary pipeline (30k, seed 42, downscale 2; các job tuần tự):

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name topic16-full -Task research -CustomScene tea_sets_2
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
# Ctrl+B rồi D để detach; worker vẫn chạy.
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
# Đợi trạng thái paused rồi:
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
```

Tmux là console WSL; GPU/Conda vẫn chạy native Windows trong worker elevated.
[Hướng dẫn sessions](docs/session_operations.md) nêu checkpoint, inference resume
và yêu cầu giữ source/registry đúng snapshot. Không tự lấy config “latest”. Với một run:

```powershell
.\scripts\Train.ps1 -Method nerfacto -Dataset poster -ResultPath .\artifacts\logs\selected-run.json
$config = (Get-Content .\artifacts\logs\selected-run.json -Raw -Encoding UTF8 | ConvertFrom-Json).config
.\scripts\Evaluate-Run.ps1 -ConfigPath $config
.\scripts\Render-Run.ps1 -ConfigPath $config
.\scripts\Export-Run.ps1 -ConfigPath $config
```

## Dữ liệu và tính công bằng

| Dataset | Source đã kiểm tra | Eval interval 8 | Vai trò |
|---|---:|---:|---|
| poster | 100 matched processed frames; raw metadata 226 | 13 | Smoke, không phải primary result |
| garden | 185 | 24 | Outdoor benchmark |
| bonsai | 292 | 37 | Indoor calibration/benchmark |
| room | 311 | 39 | Indoor benchmark |
| custom:tea_sets_2 | Video 64,07 s → 105 train + 15 eval | Frozen filename lists | Cảnh tĩnh chính; 120/120 pose đã đăng ký |

```powershell
.\scripts\Extract-Video.ps1 -Video .\data\testing_real_video\tea_sets_2.mp4 -Scene tea_sets_2
.\scripts\Process-Capture.ps1 -Scene tea_sets_2 -CpuOnly `
    -TrainImages .\data\raw\custom\tea_sets_2\train -EvalImages .\data\raw\custom\tea_sets_2\eval
.\scripts\Review-Capture.ps1 -Scene tea_sets_2 -VerifyOnly
```

Frame/provenance ở `data/raw/custom/tea_sets_2/`; [ảnh mẫu](reports/custom_capture/tea_sets_2_frames.jpg),
[quỹ đạo camera](reports/custom_capture/tea_sets_2/poses.png),
[chiếu sparse points](reports/custom_capture/tea_sets_2/projections.png).
Đã chọn connected model 1 với đủ 105 train/15 eval; canonical scene và agent
visual audit có hashes/reviewer/notes. Đây chưa phải human research/replay review
cho G-Core. Video đầu `tea_sets.mp4` có tay xoay khay, được giữ làm attempt cũ.
Single-video eval đo interpolation; các góc gần nhau có tương quan, không đại diện
cho independent capture hoặc test tổng quát hóa.

`Prepare-Scene.ps1` tạo **cùng pinhole images, intrinsics, poses, sparse points và
explicit split** ở `data/processed/canonical/<scene>/`. Cần bước này vì pinned
Splatfacto tự undistort/crop distorted images, khác Nerfacto. Bỏ qua sẽ làm GT
khác nhau dù cùng folder gốc. Raw giữ nguyên; canonical là derived data có hashes.
Ảnh được undistort bằng routine upstream rồi resize một lần bằng LANCZOS.
Train tự chuẩn bị/kiểm chứng canonical scene trước khi tạo run.

Nerfacto và Splatfacto giữ batch/model defaults riêng. Budget iterations bằng nhau
không có nghĩa cùng FLOPs. FPS upstream trong metrics gồm nhiều overhead; bảng FPS
chỉ dùng renderer đã warm-up, `torch.cuda.synchronize`, cùng camera/resolution,
không tính encoding/IO. VRAM là max mẫu mỗi 10 giây, có thể bỏ lỡ spike.

## Cấu trúc để đọc code

```text
configs/             pins và training schema
scripts/             entrypoints PowerShell; lib/Common.ps1 dùng chung
src/topic16/         contracts + data/video + safety/runtime/sessions + experiments + analysis/demo
tests/               contract, negative và integration fixtures
docs/                kế hoạch, evidence, protocol và paper notes
reports/             bảng/figure/report/model/release manifests
data/                raw + processed; không commit dữ liệu
artifacts/           runs/logs/metrics/renders/videos/exports theo cùng run key
third_party/         pinned upstream; không sửa trực tiếp
```

Bắt đầu đọc `contracts.py`, rồi `data.py`, `runtime.py`, `experiments.py`.
`sessions.py` và `training_worker.py` xử lý cooperative stop/checkpoint resume.
`safety.py` bảo vệ mọi GPU entrypoint; `video.py` chuẩn bị custom input bằng CPU.
`analysis.py` chỉ nhận paired manifests được chọn rõ; `demo.py` chỉ kích hoạt
model có G-Core và checksum hợp lệ. Không tạo cây production/app/scripts/tests
song song với package hiện có. Notebook placeholder đã bỏ.

- [Kiến trúc và interface](Construction_architect.md)
- [Stages và acceptance gates](Modular_construct.md)
- [Phân công và bàn giao](Members_jobs.md)
- [Kế hoạch hoàn thiện A–Z](docs/completion_plan.md)
- [Lệnh setup, resume, capture, analysis và demo](setup_full_command.md)
- [Toán nền](docs/research/foundations.md) và [paper notes](docs/research/paper_notes.md)

Mọi số trong báo cáo phải truy về exact run key + checkpoint/config hash.
Diagnostic, estimate và claim paper được tách khỏi kết quả primary trên laptop.

Full primary đã launch: `topic16-full`, native Administrator worker,
`artifacts/logs/sessions/topic16-full/{state.json,console.log}` và
`artifacts/logs/research/topic16-full/session.json`. Bắt đầu 2026-09-30
17:01:52 UTC (2026-10-01 00:01:52 GMT+7). Đây là phiên dài đang thực thi;
chỉ final artifact/session state mới chứng nhận hoàn tất. Stop/Status/Resume
và tmux attach xem [session_operations](docs/session_operations.md).
