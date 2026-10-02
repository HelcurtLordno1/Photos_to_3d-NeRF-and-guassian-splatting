# GPU safety — mọi phiên native Windows

Policy duy nhất: [`configs/project.psd1`](../../configs/project.psd1).
Thực thi: [`safety.py`](../../src/topic16/safety.py) dưới OS lock của runtime.
Đây là policy bảo thủ của project, không phải nhiệt độ định mức nhà sản xuất
hoặc bảo đảm chống shutdown tuyệt đối.

## Bắt đầu mỗi phiên

Mở **Windows PowerShell → Run as administrator** tại repo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Check-GpuSafety.ps1
.\scripts\Test-Runtime.ps1
```

Trước **mỗi job** train/eval/render/export/GPU COLMAP/demo/runtime smoke, pipeline gọi
`nvidia-smi -i 0 -lgc 300,800` và bắt buộc exit 0. Xung idle 300 MHz không chứng
minh khóa xung; không tin trạng thái phiên trước sau restart/reset. Thiếu quyền
hoặc không hỗ trợ: dừng trước workload, lưu `blocked`. Managed launcher mở
worker elevated trước job; safety guard không bypass hoặc tự đổi quyền giữa job.

NVIDIA mô tả `-lgc` là cặp xung mong muốn gần nhất được phần cứng hỗ trợ và yêu
cầu quyền quản trị: [NVIDIA System Management Interface](https://docs.nvidia.com/deploy/nvidia-smi/).
`nvidia-smi -i 0 -q -d POWER,CLOCK,TEMPERATURE` chỉ báo cáo trạng thái.

| Điều kiện | Policy hiện tại |
|---|---|
| Graphics clock lock | 300–800 MHz, sai số quan sát tối đa 15 MHz |
| Bắt đầu job | GPU dưới 65°C; cooldown tối đa 300 s, query mỗi 5 s, chưa bắt đầu workload |
| Dừng job | GPU từ 78°C |
| Dừng do công suất | Từ 80 W hoặc power limit hiện tại nếu thấp hơn |
| Dừng do VRAM | Từ 95% tổng VRAM |
| Watchdog | Mỗi 2 giây, mỗi query timeout 5 giây |
| Query thiếu/N/A/nonfinite/timeout | Dừng an toàn |
| Emergency grace | 10 giây để thoát; sau đó terminate Python job hiện tại |
| CPU library/FFmpeg threads | 4 |

Không enforce xung tối thiểu khi idle. Không dùng `-pl`, `-rgc`, `-rmc`, reset GPU,
thay fan curve hay sửa Windows. Utilization 100% tự nó không là lỗi; nhiệt,
công suất, VRAM và clock mới quyết định stop.

## Watchdog, failure và retry

Watchdog độc lập với stdout. Khi lỗi, ghi reason/sample vào
`artifacts/logs/safety/<UTC>-<pid>.json`, dừng đúng child process tree của project;
inline inference nhận interrupt. Nếu CUDA treo không thoát, watchdog terminate
**Python job và data-loader children của project**, không shutdown laptop/kill ứng dụng GPU khác.

Training/eval thông thường unwind ghi `failed`. Emergency termination có thể
ngăn `finally` và để manifest `running`: record `unsafe-stopped` chứng minh lỗi,
run không được nghiệm thu. Clean cooperative pause ghi `succeeded` safety +
`job_outcome=paused`, khác unsafe/failed stop. Train/eval/render/export mới ghi `gpu_safety_path`; validator yêu cầu safety
record `succeeded` với đúng policy. OS lock trả lại khi process chết.

`gpu.csv` mẫu 10 giây dùng báo cáo VRAM; watchdog 2 giây bảo vệ riêng.
`Monitor-Gpu.ps1` là observer thủ công, không thay watchdog hoặc quản lý workload.
Sau unsafe stop: đọc log, để máy nguội dưới 65°C, kiểm tra evidence trước retry.
Clean requested Stop: chờ paused rồi Resume đúng managed session/checkpoint. Không
retry vô hạn, tăng ngưỡng để bỏ qua lỗi hoặc hạ riêng cấu hình một method.
Policy clock/nhiệt vào registry hash; không trộn số cũ với primary protocol mới.

Phạm vi là GPU 0; `nvidia-smi` không đo nhiệt CPU/pin/toàn laptop. Phản ứng có
độ trễ và phụ thuộc driver/OS. Giữ tản nhiệt thông thoáng, nguồn ổn định và
theo dõi nhiệt CPU bằng công cụ của máy khi chạy dài.

## Bằng chứng hiện tại

2026-09-30: GPU 49°C, power limit 85 W, idle graphics 300 MHz. Phiên agent không
elevated reapply nhận exit **4**; gate đã chặn trước workload và lưu `blocked`.
Tests kiểm tra overheat, telemetry loss, clock/power/VRAM và process-stop bằng
fixture; không cố làm nóng máy. Sau đó elevated managed worker runtime/CUDA và actual training/eval/clean pause
đã PASS; evidence ở `artifacts/logs/sessions/` và implementation_status.
Driver WDDM 597.06 trả requested `power.limit=N/A`: query dùng live
`enforced.power.limit` (85 W), giữ project stop 80 W. Không bỏ qua N/A telemetry.

## CPU-only operations

`Extract-Video`, `Prepare-Scene`, `Review-Capture` và `Process-Capture -CpuOnly`
không tạo GPU workload; không gọi clock lock và không cần Administrator. Chúng
vẫn giữ shared OS lock để không chạy song song với một job project khác. CPU
libraries/FFmpeg/SIFT/matching/mapper được giới hạn 4 threads; bundle adjustment
không có flag num_threads trong COLMAP này, dùng giới hạn OMP/MKL environment.
Không suy CPU/battery thermal safety từ GPU telemetry.
