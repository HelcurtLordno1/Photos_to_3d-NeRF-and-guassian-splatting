# Tea visual quality — kế hoạch thực thi hiện hành

Cập nhật 2026-11-12. User đã cho phép triển khai, debug và chạy toàn bộ chuỗi
Tea bên dưới. Trạng thái thực tế nằm trong job/session artifacts, không suy từ
việc launch. Bản kế hoạch và toàn bộ lịch sử thay đổi trước đây được bảo toàn ở
[archive](upgrade/reports/plans/upgrade_to_baseline-through-v3-20261112.md).

## 1. Mục tiêu và nguyên tắc

Ảnh 3D sắc nét, sạch, chi tiết đúng GT và hiệu quả trên RTX A4500 Laptop16GB.
Ưu tiên toàn bộ105 ảnh train sẵn có; cùng15 camera test/canonical SfM với baseline.
Tea trước; Bonsai, Room, Garden và campaign60-view cũ tiếp tục dừng. Không chọn
seed đẹp nhất hoặc sửa tham số dựa vào Tea test. Tea đã được xem nhiều lần nên
kết luận là khám phá; cần independent scene/seed để xác nhận tổng quát.

Không hứa SOTA hay không có lỗi. Bất kỳ lỗi, kết quả âm hoặc điều kiện chưa đạt
phải được giữ, giải thích và chặn bước phụ thuộc khi cần. Không sửa checkpoint,
source pin, lịch train hoặc protocol của run đã bắt đầu để biến nó thành run mới.

## 2. Những gì đã có bằng chứng

- Q0: chỉnh projection/SH/filter theo renderer và đo parity trên checkpoint cũ.
  Các số của audit không được gán thành production parity hay GT quality.
- Q1 hoàn thành native719×1279,105/15,30k,seed42,289331 Gaussian. Cùng native
  output, PSNR+1.7738dB, LPIPS−11.24% so với half-trained control30k. ROI PSNR
  +1.9492dB nhưng LPIPS chỉ−10.11%, chưa đạt mục tiêu−15%. Direct half359×639
  kém hơn control−1.0114dB. Q1 không phải Improved-GS.
- Q1 được đưa vào tab Visual quality riêng, đủ15view/GT/control/candidate,
  metrics cả hai resolution và PLY thật. Không tạo cặp Nerfacto native giả.
- Q1.5 hoàn thành12/12 cells, dùng hai checkpoint cũ × hai output resolutions ×
  direct-classic / calibrated2x float-area / 2D-AA. Exact half supersampling là
  718×1278, khác native719×1279. Q1 half2x đạt30.0588dB, còn dưới control30.3560dB;
  FPS khoảng141→71. Native direct vẫn tốt hơn area2x. AA làm LPIPS xấu hơn.
  Giữ classic làm default; AA flag không phải full Mip-Splatting.
  [Báo cáo](upgrade/reports/tea-research-v3/q15/report.md).
- Official CUDA dùng lại PLY Q1: parity64.72/63.48/61.33dB tại camera0/10/13.
  Đây là phép kiểm tra camera/PLY/renderer, không phải điểm GT.

## 3. Bài học từ pilot v3 — giữ nguyên, không gọi là full result

Pilot AbsGS dùng generic CLI threshold0.0003, sinh hơn1.24M Gaussian vào khoảng
4500steps. Wrapper đã bỏ sót preset AbsGS của upstream: threshold0.0006. Pilot
được dừng trước held-out evaluation, checkpoint và Stop/Resume proof được giữ.
Không chuyển checkpoint pilot sang protocol mới. Threshold mới lấy từ source
preset đã pin, không từ điểm test. Hai phương pháp cùng dùng0.0006 để cô lập
nhóm thay đổi densification; không dùng riêng learning rate0.00016 của preset
AbsGS vì như vậy sẽ thêm một thay đổi giữa hai bên.

QA ban đầu đòi raw-parameter/ten-step loss gần như bitwise và đã thất bại. Tất cả
failed proofs/source pins được giữ. CUDA backward có unordered atomicAdd; sau
khi kiểm tra exact restore, tiêu chí cuối đo hợp đồng checkpoint trực tiếp:

1. TẤT CẢ model/optimizer/exposure/gradient/RNG/sampler/method state restore khớp
   tuyệt đối; cùng camera sequence.
2. FIRST pre-update forward loss lệch tối đa1e-7.
3. Sau10steps, float RGB agreement tại ba camera TRAIN cố định đạt ít nhất60dB.
4. Báo nguyên raw-parameter/loss drift; không hứa bitwise trajectory. Không dùng
   held-out quality để chọn ngưỡng QA.

Cả hai phương pháp đã qua gate này ở v3. Managed full-run Stop tại1093 đã lưu
đủ sáu Adam states1093, RNG/sampler; Resume tiếp tục đúng schedule30k. V4 phải
chạy lại QA mới vì threshold thay đổi. Chi tiết/lý do sửa gate:
[acceptance history](upgrade/reports/tea-research-v3/resume-acceptance-amendment-r4.md).

## 4. Q2 hiện hành — Tea research v4

Nguồn cấu hình: `upgrade/configs/tea-research.psd1`. Profile v3 được giữ riêng tại
`tea-research-v3.psd1`; registry `configs/project.psd1` của baseline/upgrade cũ
không đổi. Không tự nâng safety ceiling khi model tăng lớn.

| Hạng mục | Cố định |
|---|---|
| Dataset | Tea,105train/15eval, đúng camera/GT canonical, native719×1279 |
| Upstream | official Improved-GS, commit20b5db343a87c2f9fb4b70c6e39ff1f042a8a47a, source sạch |
| Runtime | isolated topic16-improvedgs-v1, Torch2.1.2+cu118, CUDA11.8; khác recipe cu121 tác giả khuyến nghị |
| Cặp chạy | official backend AbsGS control → Improved-GS package candidate |
| Chung | seed42,30k,SH3, cùng sparse init, optimizerours_adam, positionLR4e-5, densify threshold0.0006 |
| Tắt cả hai | depth, exposure, pose optimization, random background, AA |
| Candidate | LAS/EAS/RAP/MU official; budget300k,warmup multiplier3; MU20k/24k theo commit |
| Khác biệt cần báo | native Gaussian growth, số optimizer updates và compute thực; không gọi là matched compute/count |
| Ngân sách | tối đa3h train/method,6h pair;12GiB allocator,1.5M Gaussian hard ceiling,30GiB disk reserve |
| Safety | một native GPU worker, lock chung,300–800MHz, start<65°C, stop78°C/80W/95%VRAM hoặc telemetry thiếu; CPU4 |

Đây là adaptation có kiểm soát trên Tea, không phải exact paper reproduction.
Không chọn best repeat; không gộp bất cứ pilot nào vào kết quả30k.

### Thứ tự tự động

1. Verify baseline153protected files/10runs và Q1 immutable report. Khóa declaration,
   source.zip/tree, split, settings và binary/runtime fingerprints trước GPU.
2. Reuse Q1.5 đã xác minh, không render/train lại checkpoint cũ. Chạy lại parity
   official backend trên PLY Q1 theo declaration mới.
3. Chạy600-step checkpoint/replay QA mới cho CẢ HAI phương pháp. Cả hai qua mới
   bắt đầu lượt30k đầu tiên. QA bị Stop được chạy lại ở thư mục attempt mới.
4. Train AbsGS30k; exact checkpoint eval; common RGB8PSNR/TorchMetricsSSIM/AlexNet
   LPIPS, all15images, locked ROI, PLY, offline FPS và tài nguyên. Sau đó Improved-GS
   làm đủ cùng chuỗi. Atomic checkpoints mỗi500steps và khi Stop; hai recovery
   slots giữ current/preceding, append history hash. Không đụng checkpoints cũ.
5. Báo cả so với same-backend AbsGS và Q1 native, kể cả âm. Giữ native/half/Q1.5
   bằng chứng. Báo Gaussian count, optimizer updates, train time và allocator peak;
   offline FPS không phải browser FPS. Kiểm tra GPU safety record trước publish.
6. Xuất report.json/report.md và shared catalog. Chỉ refresh server artifacts-only
   thuộc checkout; không dừng inference server khác. F5 UI để xem kết quả mới.
7. DỪNG sau Tea pair để review chất lượng/chi tiết/scale/cost. Chỉ khi có tín hiệu
   mạnh mới đề nghị thêm2seed rồi independent Bonsai. Không tự resume campaign cũ.

### Tiêu chí nghiên cứu

Mục tiêu đã nêu vẫn là ROI PSNR tăng khoảng1dB và LPIPS giảm15%, toàn ảnh không
thoái lui rõ. Không đổi ngưỡng để biến kết quả thành thành công. Một phương pháp
có thể tốt hơn về cost nhưng kém về quality: báo trade-off riêng. Chưa có A/B
mù, geometry GT và independent scene thì không kết luận sản phẩm/SOTA đã đạt.

## 5. Theo dõi / Stop / Resume

PowerShell tại root repository:

```powershell
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-tea-research-v4
.\upgrade\scripts\Manage-Session.ps1 -Action Attach -Name topic16-tea-research-v4
.\upgrade\scripts\Manage-Session.ps1 -Action Stop -Name topic16-tea-research-v4
# Chờ state=paused trước khi tắt máy.
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-tea-research-v4
```

Trong WSL: `tmux attach -t topic16-tea-research-v4`. Detach: Ctrl+B rồi D.
Tmux chỉ monitor native Windows worker; không có lệnh `tmux resume`.
UI: http://127.0.0.1:7016/?scene=custom%3Atea_sets_2&tab=quality
Trong training, xem saved images/metrics; interactive GPU view tự khóa.

Kết quả: `upgrade/reports/tea-research-v4/report.json` và `.md`.
Trạng thái: `upgrade/artifacts/jobs/research/tea-research-v4/state.json`.
Tiến độ/checkpoint: `upgrade/artifacts/research/tea-research-v4/runs/<method>/`.
Session log: `upgrade/artifacts/logs/sessions/topic16-tea-research-v4/console.log`.
Ước tính cặp train/eval khoảng1–3h, cập nhật bằng tiến độ thực; launch không phải
completion. G-Core baseline/research release review vẫn chưa được chứng nhận.
