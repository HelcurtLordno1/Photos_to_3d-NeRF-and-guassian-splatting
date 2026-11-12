# Tea Quality v5 — đề xuất sau kết quả v4

**Trạng thái: APPROVED — user cho phép triển khai và chạy sau khi push Git.**
V4 hoàn thành; mọi checkpoint/report/source pin cũ được giữ nguyên. Thực hiện
P0→P1→P2 trước; mọi bước sau phải theo gate và ngân sách trong kế hoạch này.
Báo cáo/số liệu nằm local dưới reports/, không được Git theo dõi theo yêu cầu
user. Tài liệu này không thay declaration hay kế hoạch thực thi v4.

## 1. Quyết định nghiên cứu

Giữ Improved-GS300k làm ứng viên chính. Ưu tiên theo thứ tự:

**UI/evidence → scale & 3D inspection → seed confirmation → một cải tiến có giả
thuyết → independent Bonsai → đóng gói bản nghiên cứu.**

Mục tiêu vẫn là chi tiết thật, ảnh sạch và hardware hiệu quả. Không tăng steps,
budget, SH, loss, filter và module cùng lúc; không mở một cuộc grid search.
Không đồng nhất tăng PSNR với mọi chi tiết đẹp hơn hoặc tăng offline FPS với
browser FPS. Mọi số trong mục tiêu dưới đây là tiêu chí ĐỀ XUẤT cho thí nghiệm
mới, phải đóng băng trước khi đo; không dùng để sửa kết luận v4.

## 2. Bằng chứng hiện có và khoảng trống

Nguồn: `../tea-research-v4/review/assessment.md` và `verification.json`.

| Native719×1279,105train/15eval,30k | PSNR ↑ | SSIM ↑ | LPIPS ↓ |
|---|---:|---:|---:|
| Q1 |30.4228|0.91470|0.12253|
| AbsGS cùng backend |30.7445|0.92864|0.08942|
| Improved-GS300k |31.7343|0.93507|0.08729|

- Vs Q1: PSNR+1.3116dB, LPIPS−28.76%; cả ba thuận hơn15/15view. Object ROI
  +0.8344dB/LPIPS−20.62%. Original target so với half-control đã đạt.
- Vs AbsGS: PSNR+0.9899dB, Gaussian−49.61%, train time−25.20%; nhưng LPIPS chỉ
  thắng7/15view và ROI PSNR thua#8/#9/#13. Kết luận là lợi thế quality/cost của
  package trong protocol này, chưa phải thắng mọi chi tiết.
- Ly thủy tinh còn mờ/thiếu hoa văn. Q2 chưa có kiểm tra half/zoom/continuous
  orbit đầy đủ. Tea test đã được xem nhiều lần;3seed không biến nó thành test
  độc lập và15view không phải15thí nghiệm độc lập.
- UI hiện mở đầu bằng Q1 và dòng target-not-met của Q1, dù Q2 ở phần dưới đã
  thành công. Cần tránh user xem nhầm model cũ hoặc nhầm trạng thái.

## 3. P0 — nền tảng thực nghiệm và UI rõ ràng

**Không train lại. Ước lượng2–4giờ engineering/CPU; không phải giờ GPU.**

### Thay đổi có giới hạn

1. Tách scene/run/backend/seed/resolution/budget/render profile thành declaration
   có schema. Chỉ khái quát phần cần cho seed và scene mới; không viết lại toàn
   bộ training engine. Loại hardcode tên v3/v4, seed42 hoặc Tea khỏi những chỗ
   quản lý hàng đợi/report/publish. Giữ adapter cũ replay được theo source pin.
2. Preflight đối chiếu method preset upstream với các shared overrides. Archive
   resolved config và binary/runtime identity trước GPU. Thay parameter/protocol
   tạo experiment mới; không chỉnh run đang chạy.
3. Giữ Train → Evaluate → Export/Benchmark → Publish là các stage độc lập, có
   input/output hash. Publish lỗi không train lại; time/resource stop có checkpoint.
   Kiểm tra resume sau densification/RAP và tại MU có gradient đang tích lũy;
   exact saved-state/first-forward là contract, không hứa bitwise CUDA trajectory.
4. UI hiển thị một lựa chọn model/thí nghiệm thống nhất: Q1, AbsGS, Improved-GS;
   ảnh/3D/benchmark/ROI/cost phải theo đúng lựa chọn. Với scene Tea, mở trực tiếp
   kết quả v4 trong khu nghiên cứu, có baseline/control để đối chiếu. Ghi rõ Q1
   target miss và Q2 target pass theo đúng reference. Không promote model chưa
   qua visual/scale gate thành bản sản phẩm mặc định.
5. Ghi frame time/load time/total memory theo đúng measurement scope. UI ngừng
   redraw khi đứng yên nếu hành vi thực tế phù hợp; không giảm SH/LOD/resolution
   ngầm để báo FPS cao. Công bố renderer profile riêng nếu có tối ưu chất lượng.

### Gate P0

- Fresh-default, đổi model/camera/resolution, saved image URL,3D asset/checkpoint
  và bảng benchmark đều nhất quán; chọn đúng Q2 thay vì vô tình mở Q1.
- Không có Nerfacto native giả, không có duplicate benchmark/filter, lịch sử vẫn
  đọc được. Browser interaction thật và contract/negative cases qua.
- Nguồn/preset/seed/split/camera/evaluator/GPU policy được kiểm tra trước train.

## 4. P1 — xác định chất lượng 3D thực tế, dùng checkpoint sẵn có

**Không retrain. Ước lượng1–3giờ triển khai/kiểm tra;15–45phút GPU/CPU đo đạc.**

### Ma trận và phép đo

- Model chính: AbsGS và Improved-GS v4. Q1 dùng làm mốc lịch sử, không cần render
  lại mọi cell nếu đã có artifact đúng identity từ Q1.5.
- Chất lượng có GT: toàn bộ15eval cameras ở native719×1279 và half359×639.
  Dùng GT/camera half đã khóa, không resize native bằng tỷ lệ xấp xỉ. So direct
  classic với fixed2x float-area reference; render half2x là718×1278.
- Đổi focal/zoom:0.75×/1×/1.5×, cố định camera principal point/convention. Chỉ
  chấm metric GT ở những crop/resample tạo được camera và pixels khớp chính xác;
  view không có GT chỉ là kiểm tra rendering/consistency, không gán PSNR-to-GT.
- Dùng15view và ROI đã khóa; xem riêng#0/#1/#8/#9/#10/#13 và ly/ấm/khay/sàn.
  Không chỉ chọn view thắng. Crop chi tiết mới chỉ dùng mô tả hoặc validation
  từ train, không tuyên bố đã pre-register ROI sau khi xem candidate.
- Một trajectory liên tục khoảng120camera, nằm gần coverage capture. Ghi mọi
  pose/K, renderer/filter và output size. RGB/depth/opacity phụ trợ để định vị
  vệt kéo, Gaussian quá lớn, chỗ trống hoặc lỗi sorting. Không coi motion-image
  difference thô là flicker score và không gọi sweep qua train cameras là GT
  temporal benchmark.
- Browser/CUDA parity: cùng calibrated camera, SH3, background, classic filter;
  phân biệt Spark packed production path và float audit path. Chạy cùng viewport,
  draw-buffer size/DPR, model, camera, LOD/SH/filter và GPU clocks khi so FPS.
- Browser profile mục tiêu: Chrome trên RTX A4500,viewport1280×720,DPR1,SH3,
  LODoff,một model. Warm-up và đo frame-time median/p95 trên một trajectory cố
  định; báo actual canvas dimensions, browser/GPU identity và dropped frames.
  Native pixel-parity audit là một profile riêng, không tráo hai measurement.

### Quyết định sau P1

- Mục tiêu parity: mean≥35dB, không view<30dB so với CUDA ở profile đúng camera.
  Đây là gate engineering đề xuất, không phải quality-to-GT. Không đạt thì phân
  loại packing/sort/projection/filter trước khi đụng training.
- Mục tiêu interaction: p95frame time≤33.3ms tại profile browser cố định. Báo cả
  load time và idle activity; không hứa60FPS khi chưa đo.
- Gate quality ở output hỗ trợ: Improved-GS không thấp hơn Q1 cùng scale quá
  0.2dB PSNR hoặc LPIPS tăng quá5% ở mean; luôn báo view/object ROI thua. Đây là
  guardrail v5 đề xuất, không xóa hay thay tiêu chí original ROI của v4.
- Nếu native ổn và chỉ lỗi sampling/browser: sửa renderer/profile có kiểm soát,
  giữ model300k; công bố quality/cost của inference intervention riêng.
- Nếu có lỗi scale thật cần training filter: mở nhánh P3-Mip, không bật AA mặc
  định trên checkpoint classic. Nếu coverage thiếu, không tăng point để ngụy tạo
  chi tiết chưa có dữ liệu.

## 5. P2 — xác nhận ổn định bằng thêm hai seed

**Chỉ sau gate P0/P1. Bốn lượt full mới; không chạy lại seed42 hợp lệ.**

| Seed | AbsGS control30k | Improved-GS300k30k |
|---|---|---|
|42|Reuse v4 đã xác minh|Reuse v4 đã xác minh|
|17|Mới|Mới|
|2026|Mới|Mới|

- Giữ105/15 cameras, native output, initialization source, source/backend,
  shared threshold0.0006,positionLR4e-5,ours_adam,SH3 và safety như v4. Chỉ đổi
  seed, áp dụng cho Python/NumPy/Torch/CUDA và sampler/method pools.
- Nếu refactor thay số học/training path thì phải qua semantic replay; không
  coi run mới cùng identity với v4. Khi không chứng minh tương đương, khai báo
  protocol mới và cần control tương ứng thay vì reuse thiếu căn cứ.
- Chạy sequential theo cặp:seed17 control→candidate đầy đủ eval/export/report,
  rồi seed2026. Không dừng vì một kết quả kém; chỉ dừng vì lỗi/integrity/resource
  gate, giữ toàn bộ seed và attempts. Không chọn best repeat bằng testPSNR.
- Báo từng seed, paired deltas, mean/std/min/max theo seed; view-wise và ROI
  regressions. Không dùng15view như n=15 để khẳng định statistical significance.

### Tín hiệu đủ để tiếp tục (đề xuất, khóa trước run mới)

- Trung bình paired PSNR gain≥0.5dB, SSIM không giảm, ROI LPIPS không xấu hơn
  AbsGS theo mean của3seed; hướng PSNR thuận ở ít nhất2/3seed. Báo rõ nếu một
  chỉ số không qua; không đổi trọng số sau khi xem kết quả.
- Giữ lợi thế tài nguyên đáng kể: Gaussian final300k, PLY khoảng≤80MiB,
  candidate mean training time≤90%control trong cùng measurement protocol.
- Các ngưỡng là gate nghiên cứu thực dụng, không phải chứng minh tổng quát/SOTA.

### Ngân sách P2

Từ23.93+17.90phút/cặp hiện có:2cặp mới≈84phút training. Dự trù1.5–2.5giờ cả
QA/eval/export; dừng trần3giờ GPU cho đợt này. Setup engineering không tính là
GPU time. Dự trù thêm4–10GiB artifacts, kiểm free disk trước khi chốt queue.

## 6. P3 — chọn tối đa MỘT nhánh nâng chất lượng

Không chạy cả hai nhánh ngay. Chọn theo chẩn đoán P1 và tín hiệu P2.

### P3-A: capacity/quality, khi scale đã ổn

**Giả thuyết:** budget300k có thể đánh đổi một phần chi tiết ly/cạnh;450k có thể
cải thiện detail với chi phí còn hợp lý. Việc AbsGS tốt hơn LPIPS ở8view chỉ là
động cơ kiểm tra, chưa chứng minh nguyên nhân là capacity.

- Một biến duy nhất: Improved-GS budget300k→450k. Giữ method modules,seed,LR,
  schedule,filter,training views và evaluator. Warmup multiplier3 có ceiling
  1.35M, vẫn dưới hard limit1.5M; theo dõi cả allocator transient khi split.
- Chọn một validation split15view từ105TRAIN, dựa trên camera coverage và seed
  cố định, không dùng15test. Train hai config bằng90train còn lại, cùng input
  SfM scope; so cả hai trên15validation. Không đem model90train so thắng với
  v4 model105train rồi gọi là controlled pair.
- Tối đa2pilot30k, một seed đã khai báo. Dừng nhánh nếu không có lợi thế rõ;
  không thử tiếp600k/750k chỉ để tìm điểm cao.
- Tiêu chí chọn đề xuất: validation ROI LPIPS giảm≥5%, PSNR không giảm quá0.2dB,
  browser vẫn≥30FPS theo p95profile, file≤110MiB và VRAM trong policy. Các chỉ
  số phải hiện cả per-view và mean; không dùng held-out Tea để chọn config.
- Chỉ nếu qua mới retrain config được chọn bằng đủ105train30k và test một lần;
  kết luận vẫn exploratory trên Tea. Mode450k chỉ được công bố là Quality mode
  khi có lợi thế thật; nếu không giữ300k Balanced.

Ước lượng2–3giờ engineering; khoảng1–2giờ GPU gồm pilot và một full confirm nếu
qua. Đây là ước lượng, phải cập nhật từ đo growth ở đầu run.

### P3-B: Mip filtering, khi lỗi phụ thuộc scale còn rõ

**Giả thuyết:** giới hạn tần số trong3D và tích phân pixel2D giúp scale stability.
Mip-Splatting dùng cả3D smoothing và2D Mip filter; một AA flag không đủ.
Nguồn: [paper/project](https://niujinshuchong.github.io/mip-splatting/),
[official code](https://github.com/autonomousvision/mip-splatting).

- Worktree/env riêng pin commit; giữ Improved-GS densification,300k budget và
  mọi yếu tố khác để có control cùng backend. Không đồng thời lấy densification
  mới từ nhánh GOF của repo Mip rồi gán gain cho filtering.
- Compute filter bằng TRAIN cameras chính xácfx/fy/cx/cy; không dùng camera test
  để chọn mức filter. Kiểm tra mask/filter arrays theo clone/split/prune, lưu
  full state và replay cả MU boundary có pending gradients.
- Phải tái hiện pair control/candidate với cùng train/validation. PLY có fused3D
  filter và2D browser filter phải được mô tả đúng; không export model mới rồi
  render như classic và gọi đó là đủ pipeline.
- Gate: cải thiện multi-scale validation rõ ràng, native giữ trong guardrail,
  browser/CUDA parity và resource policy qua. Chỉ sau đó full105train/test.
- Ước lượng tích hợp/QA1–3ngày trên Windows, GPU thăm dò tối đa2giờ trước review.
  Không hứa plug-in vài phút; repo upstream có runtime recipe khác và đã thêm
  GOF densification. Nếu gate backend không đạt, giữ v4, báo blocker cụ thể.

Nếu sampling và capacity đều không giải thích được phần thiếu ở ly trong suốt,
đề xuất nghiên cứu biểu diễn appearance/material như một nhánh mới có paper
review riêng. Không thêm shader/loss/pretrained model vào v5 một cách ngầm định.

## 7. P4 — xác nhận độc lập trên Bonsai

Chỉ sau khi hoàn tất Tea gates; không resume Bonsai Splatfacto14320 của campaign
cũ vào backend/protocol mới. Chốt toàn bộ phương pháp trước khi nhìn test Bonsai.

- Dữ liệu hiện có:255train/37eval, baseline output1559×1039. Cặp mới phải dùng
  cùng frozen cameras/split/output giữa control và candidate. Reuse raw/SfM,
  không tái chạy preprocessing chỉ để đổi tên experiment.
- Preflight3–5phút đầu bằng TRAIN-only để đo residency/growth. Hiện worker cache
  cả ảnh train trên CUDA; riêng255RGBfloat32 ảnh1559×1039≈4.6GiB, alpha masks
  ≈1.5GiB và edge maps≈1.5GiB cho candidate: khoảng7.7GiB trước model/optimizer/
  temporaries. Không suy VRAM từ Tea. Đây là ước tính residency từ tensor shape,
  không phải số đo peak thực tế.
- Nếu cần CPU-backed loading/boundedGPU cache, áp dụng cùng cơ chế cho cả hai
  phương pháp, archive source mới và test sampler/order/numerical behavior. Không
  downscale riêng candidate. Nếu đổi common resolution phải là protocol riêng,
  gắn nhãn rõ với baseline lịch sử.
- Run AbsGS và candidate được chọn,full30k, một seed xác nhận trước; export,
  same evaluator/allviews/ROI nếu có GT-defined boxes, resources,3D/UI/gate hoàn
  chỉnh mới xét seed bổ sung hoặc Room. Budget Gaussian scene-specific phải
  khai báo từ train-only capacity probe; không mặc định300k phù hợp mọi scene.
- Chưa ấn định runtime bằng tốc độ Tea. Freeze estimate và ngân sách sau probe,
  trước full run; duy trì3h/method và safety cứng, không tự nới trần.

Bonsai là phép kiểm tra transfer phương pháp với protocol scene đã công bố;
không tuning theo test rồi dùng test đó làm bằng chứng độc lập. Room/Garden vẫn
đợi, đặc biệt Garden output2593×1680 có cost khác nhiều.

## 8. Nghiệm thu bản nghiên cứu

- UI mở đúng model đã chọn, đồng bộ GT/camera/metrics/3D, thể hiện quality/cost và
  giới hạn; có baseline/control, bookmark, ảnh/crop/native size và export.
- Một report tổng hợp: all seeds/scenes, matched/trade-off comparisons, source/
  dependency/safety/checkpoint identities, failure/negative results và commands
  reproduce. Bằng chứng đã commit không bị viết lại để sửa typo/status.
- Native PowerShell, tmux monitor, Stop checkpoint và Resume kiểm chứng được;
  postprocessing/publish idempotent; không training lại khi UI/catalog lỗi.
- Một GPU job,CPU4,clock300–800MHz,start<65°C,stop78°C/80W/95%VRAM hoặc thiếu
  telemetry; allocator12GiB,30GiBfree reserve. Không viewer trong timed CUDA run.
- G-Core/review requirements của baseline giữ nguyên. Completion nghiên cứu
  không được diễn giải thành chứng nhận production hoặc claim SOTA.

## 9. Phạm vi đợt tiếp theo nên duyệt

**Đề nghị thực hiện P0 + P1 + P2 trước**, trần3giờ GPU mới (phần lớn≈84phút train),
engineering/CPU dự kiến nửa đến một ngày tùy tình trạng refactor/viewer audit.
Báo một review gate sau đó, gồm cả kết quả xấu. P3 chỉ chọn một nhánh khi có
chẩn đoán đủ rõ; P4 chỉ sau khi Tea được khóa. Không tự triển khai cả roadmap
như một campaign dài không có điểm kiểm tra.

## 10. P1 renderer amendment — 2026-11-12

P1 đã chạy: native/half quality và browser frame time đạt. Packed Improved-GS
mean35.50095dB nhưng view4 chỉ29.85630dB, không qua min30dB; giữ nguyên phép đo
ở `upgrade/reports/tea-quality-v5/inspection.json`. Chưa chạy seed mới.

Kiểm tra đúng một giả thuyết inference: độ chính xác packing ở input và render
accumulator của Spark. Ma trận2×2 trên cả hai model giữ nguyên checkpoint, SH3,
camera, classic filter, sorting, viewport và các ngưỡng35/30dB,33.3ms. Đo/nguồn
được archive riêng; không sửa packed failure thành pass. Extended input đơn lẻ
không đạt parity; extended cả hai bước đạt parity nhưng p95 candidate47.1ms.

**Profile research được chọn: packed input + extended accumulator (`packed-ext`).**
Improved-GS mean36.38445dB,min30.47078dB,p95 frame interval24.3ms, qua ngưỡng
không đổi. AbsGS mean34.77209,min29.75823dB,p9529.9ms; vẫn có parity miss,
không được tuyên bố cả hai model đều qua. Đây là sửa viewer P1, giữ nguyên model
v4 và trainer. Profile đo một lần; không diễn giải timing thành cam kết FPS.

P0 thực tế đã kiểm fresh-default/model/camera/resolution, 300k3D load/drag/idle
với zero page errors. Review P1 giữ rõ lỗi background ngoài coverage khi zoom0.75,
ghosting/chi tiết ly mờ, ROI regressions và giới hạn contact sheet không chứng
minh flicker-free. Gate cho phép paired replication, chưa phải clean360 release.
P2 đã được mở sau review; kết quả mới chỉ công bố khi đủ bốn lượt30k. Giữ trần
3giờ compute; P3 và Bonsai chờ kết quả P2. Báo cáo chi tiết local:
`upgrade/reports/tea-quality-v5/review/assessment.md` và `inspection-r4.json`.
