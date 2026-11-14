<p align="center">
  <img src="docs/assets/topic16-hero.svg" alt="Photos to 3D — neural field, Gaussian splats và Spatial Studio" width="100%" />
</p>

<h1 align="center">Photos to 3D · Spatial Studio</h1>

<p align="center">
  <strong>Từ ảnh chụp nhiều góc nhìn đến một không gian có thể khám phá.</strong><br/>
  Nerfacto · Splatfacto · Improved-GS
</p>

<p align="center">
  <a href="#bo-suu-tap">5 datasets</a> ·
  <a href="#ket-qua">Kết quả</a> ·
  <a href="#chay-ui">Chạy UI</a> ·
  <a href="#cai-dat">Cài đặt</a> ·
  <a href="setup_full_command.md">Runbook</a>
</p>

Project Computer Vision so sánh **neural radiance field** và **3D Gaussian Splatting**, sau đó nghiên cứu bản Gaussian cải tiến trên Tea và chuyển sang các scene còn lại. **Spatial Studio** đưa model 3D, ảnh đối chiếu và số đo vào cùng một trải nghiệm.

| Khám phá không gian | Kiểm tra chất lượng | Đọc kết quả nghiên cứu |
|:---|:---|:---|
| Gallery 3D, orbit/zoom, camera sync, presets và bookmarks | GT / baseline / upgrade, wipe, ROI và ảnh held-out cùng camera | PSNR, SSIM, LPIPS, chi phí, kết quả theo view và các thí nghiệm |

<a id="bo-suu-tap"></a>

## Năm cảnh · từ vật thể nhỏ đến không gian thực

![Bộ sưu tập Tea sets, Bonsai, Room, Garden và Poster](docs/assets/scene-collection.svg)

*Ảnh đại diện từ dữ liệu thực, crop để trình bày. Cả năm scene đã có baseline, bản Gaussian upgrade, ảnh evaluation và export 3D.*

<details>
<summary><strong>Xem không gian 3D và art gallery trong Spatial Studio</strong></summary>

![Workspace 3D với camera đồng bộ, Nerfacto proxy và Splatfacto Gaussian](docs/assets/spatial-studio-workspace.png)

![Art gallery với các scene của project](docs/assets/spatial-studio-gallery.png)

Nerfacto trong viewport là point-cloud proxy để điều hướng; ảnh neural chính xác lấy từ checkpoint. Các screenshots này minh họa workspace baseline và gallery.

</details>

<a id="ket-qua"></a>

## Kết quả · giữ baseline, đo phần cải thiện

Baseline **10 runs / 5 scene** được giữ nguyên. Nghiên cứu resolution, AbsGS/Improved-GS, repeated seeds và capacity tập trung trên Tea; sau đó mỗi scene còn lại chạy một phương án Gaussian đã chọn. Pipeline có checkpoint resume, checksum và giới hạn tài nguyên; cache CUDA giới hạn hai camera giúp xử lý scene lớn.

| Scene | Splatfacto baseline · PSNR ↑ | Improved-GS · PSNR ↑ | Chênh lệch |
|---|---:|---:|---:|
| **Tea sets** | 28.68 dB | **31.73 dB** | **+3.05 dB** |
| **Bonsai** | 31.50 dB | **32.45 dB** | **+0.96 dB** |
| **Room** | 31.66 dB | **32.34 dB** | **+0.69 dB** |
| **Garden** | 26.24 dB | **26.65 dB** | **+0.41 dB** |
| **Poster** | 32.56 dB | **33.74 dB** | **+1.18 dB** |

Mean theo held-out views, cùng GT/camera và evaluator RGB8; SSIM/LPIPS trung bình cũng cải thiện trên cả năm scene. Tea còn thay resolution training, nên mức tăng không cô lập riêng kiến trúc; Poster là ca chuyển giao. [Số đo đầy đủ và phạm vi](docs/research/results-2026-11-13.json).

**Room Nerfacto A/B/C:** ba cấu hình train mới 30k bước để kiểm tra camera optimizer và appearance embedding. Tắt cả hai đạt **30.30 dB native float** trên 39 held-out views; đây là kết quả một seed, tách biệt với bảng Gaussian ở trên.

**Giới hạn:** một số view Room/Poster chưa đạt mục tiêu browser parity; Garden chưa đạt 30 FPS ở profile đo. Ảnh 4K/8K là output inference, không phải dữ liệu nguồn mới. Các kết quả âm và giới hạn vẫn được giữ trong benchmark.

<a id="chay-ui"></a>

## Mở Spatial Studio

**Máy đã có artifacts:** mở Windows PowerShell tại root repo, chạy:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Invoke-Topic16.ps1 ui
```

Mở URL launcher thông báo, mặc định **http://127.0.0.1:7016**. Chọn scene → **Bản hiển thị: Compare** → **Improved-GS · selected final · 30,000 steps**. Dùng **Ctrl+F5** nếu còn cache cũ.

<details>
<summary><strong>Cập nhật catalog/build hoặc dừng UI</strong></summary>

```powershell
.\Invoke-Topic16.ps1 ui-prepare
.\Invoke-Topic16.ps1 ui-build
.\Invoke-Topic16.ps1 ui
```

Dừng server từ terminal khác:

```powershell
.\Invoke-Topic16.ps1 ui-stop
```

</details>

<a id="cai-dat"></a>

## Cài đặt và chạy trên máy mới

**Windows PowerShell Administrator**, NVIDIA GPU và Git. Cấu hình đã kiểm chứng: **RTX A4500 Laptop 16 GB**. Dataset, checkpoints và full reports được giữ local; clone Git chỉ lấy source và tài liệu công khai.

<details>
<summary><strong>Clone, cài môi trường và chạy baseline</strong></summary>

```powershell
git clone https://github.com/HelcurtLordno1/Photos_to_3d-NeRF-and-guassian-splatting.git
Set-Location Photos_to_3d-NeRF-and-guassian-splatting
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Install-HostTools.ps1 -InstallBuildTools
```

Mở lại PowerShell Administrator tại repo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Invoke-Topic16.ps1 setup-all
.\Invoke-Topic16.ps1 ui-setup
```

Sau khi chuẩn bị và duyệt video Tea theo [runbook](setup_full_command.md), chạy baseline:

```powershell
.\scripts\Run-Research.ps1 -SessionDirectory '.\artifacts\logs\research\topic16-full' -CustomScene tea_sets_2
```

Hoàn tất training rồi chạy `ui-prepare`, `ui-build`, `ui`. Nhánh Improved-GS có runtime/protocol riêng dưới `upgrade/`; dùng đầy đủ artifacts đã xác thực hoặc tạo evidence mới để xem bản upgrade.

</details>

| Cần tìm gì? | Tài liệu |
|---|---|
| Setup dữ liệu, lệnh đầy đủ, stop/resume | [Runbook](setup_full_command.md) |
| Thao tác UI, profiles và QA | [Spatial Studio](UI_design/README.md) |
| Số đo và nguồn hình nghiên cứu | [Results snapshot](docs/research/results-2026-11-13.json) |

**Nhóm thực hiện:** Khổng Gia Minh · Nguyễn Phú Nam · Hồ Đức Mạnh · Đinh Nam Khánh.
