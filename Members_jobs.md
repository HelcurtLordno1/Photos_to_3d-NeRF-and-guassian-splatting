# Phân công 4 thành viên — Topic 16 (Nerfacto vs Splatfacto)

> Bản giao việc cho nhóm, dựa trên [kiến trúc](Construction_architect.md),
> [working list P0–P10](Modular_construct.md) và
> [runbook PowerShell](setup_full_command.md). Các tài liệu đó là source of truth
> về protocol; file này xác định **ai sở hữu việc gì, giao gì, kiểm chứng ra sao**.
>
> Trạng thái cập nhật 2026-09-24: dữ liệu `poster`, `garden`, `bonsai`, `room`,
> MSVC v142 và runtime CUDA đã PASS trên laptop lead. **Training/inference thật
> chưa PASS**; G-Core chưa mở. Không coi ô `[x]` về *code đã viết* trong working
> list là bằng chứng module đã chạy end-to-end. Xem
> [setup audit](docs/setup_status_2026-09-23.md).

## 1. Nguyên tắc phân công và giới hạn phần cứng

| Người | Máy | Dải Px sở hữu liên tục | Vai trò chính |
|---|---|---|---|
| Member 1 — Platform/Data (CPU) | Chỉ CPU | **P0–P2** | Runtime scripts, contracts, dataset acquisition/validation |
| Member 2 — Capture/Training (CPU) | Chỉ CPU | **P3–P4** | Ảnh điện thoại, frozen split, training wrapper/provenance |
| Member 3 — Eval/Research (GPU 6 GB) | GPU PC 6 GB VRAM | **P5–P7** | Inference/eval, paired orchestration, phân tích và hồ sơ G-Core |
| Member 4 — Lead/Integration (bạn) | RTX A4500 Laptop 16 GB, 80 W | **P8–P10** | QA xuyên suốt, nghiệm thu tất cả GPU gates, rồi production/demo sau G-Core |

Mỗi người chỉ nhận **một dải số Px liền nhau**, không sở hữu các P rời rạc.
`P10` là QA xuyên suốt nên lead thực hiện từ ngày đầu dù nằm cuối dải P8–P10;
**không** vì vậy mà triển khai P8/P9 trước P7. Lead là *người vận hành máy nghiệm
thu* cho P0 và P4–P7, nhưng code ownership vẫn thuộc Member 1/2/3. Việc nghiệm
thu chung không đổi thứ tự Px và không biến lead thành tác giả tất cả module.

Máy CPU có thể viết/kiểm tra PowerShell, contracts, fixture, manifest, báo cáo;
không thể xác nhận CUDA, `gsplat`, training hay inference GPU. GPU 6 GB có thể làm
diagnostic rất nhỏ **nếu** runtime tương thích, nhưng không dùng kết quả đó thay
benchmark trên A4500 16 GB. Baseline chính là 30.000 iterations, downscale 2,
seed 42, eval interval 8, chạy tuần tự trên **cùng** A4500 80 W. Không chuyển qua
PC 6 GB để “cứu” một run OOM rồi ghép vào bảng chính; power/thermal khác cũng
làm sai so sánh wall time. Nếu phải giảm memory, định nghĩa protocol mới có tên,
áp dụng cho **cả hai** methods và báo cáo riêng.

Mọi runtime entrypoint là Windows PowerShell `.ps1`; không đưa Bash/WSL vào pipeline.
Pin chỉ sửa qua `configs/project.psd1` có lead review. Dữ liệu raw và artifact lớn
không commit Git. Mỗi PR/commit phải ghi Px, thay đổi contract, lệnh test, kết quả
PASS/FAIL và phần **chưa kiểm chứng**. Không gắn `DONE` khi mới chỉ parse được code.

## 2. Quy tắc bàn giao giữa bốn người

```text
Member 1: P0 → P1 → P2  ── dataset + runtime/data contracts ──┐
Member 2:                 P3 → P4  ── frozen scene + run key ────┤
Member 3:                         P5 → P6 → P7  ── G-Core ──────┤
Lead:     GPU nghiệm thu P0/P4/P5/P6/P7; P10 QA toàn tuyến ────┘
                                      G-Core PASS → P8 → P9
```

- **H0 — P0→P1/P2:** Member 1 bàn giao registry pins, runtime validation log,
  folder contracts và dữ liệu hợp lệ. Lead đã cài MSVC v142 và chạy
  `Setup-Project.ps1 -FinalizeOnly` trên laptop; runtime PASS ngày 2026-09-24.
  Member 1 không
  phải có GPU hoặc quyền admin trên laptop của lead.
- **H1 — P2/P3→P4:** Member 1 bàn giao `poster` processed 100 frame và 3 benchmark
  scenes; Member 2 bàn giao custom `transforms.json`, danh sách train/eval bất biến,
  tỷ lệ ảnh register và kết quả kiểm tra trùng lặp. P4 không train custom nếu pose
  hoặc split chưa PASS.
- **H2 — P4→P5:** Member 2 bàn giao **exact** `config.yml`, checkpoint, `run.env`,
  `command.txt`, `timing.env`, `gpu.csv` cho từng run; Member 3 không lấy “model mới
  nhất” theo trí nhớ. Lead tạo các artifact GPU thật trên A4500.
- **H3 — P5→P6/P7:** Member 3 chỉ đưa run vào paired manifest nếu metrics hữu hạn,
  có held-out GT/pred đúng số lượng, provenance đủ và hai method cùng scene/split.
  Half-pair hoặc failed run không thành kết quả nghiên cứu.
- **H4 — P7→P8:** Member 3 lập hồ sơ G-Core với link đến artifact; lead và cả nhóm
  review. Chỉ khi **mọi** checkbox G-Core PASS mới mở code production P8/P9. Nếu
  chưa PASS, lead chỉ làm P10, GPU validation và chuẩn bị demo/báo cáo dạng kế hoạch.

Để giảm xung đột Git: Member 1 sở hữu `configs/`, `scripts/lib/`, downloader/setup;
Member 2 sở hữu capture và train wrapper; Member 3 sở hữu eval/benchmark/aggregate;
lead sở hữu test tích hợp, release và production **sau gate**. Thay đổi chung vào
`configs/project.psd1` hoặc contract phải được lead và người tiêu thụ downstream
review trước khi merge.

## 3. Member 1 (CPU) — P0 → P1 → P2

### P0 — Windows runtime substrate

**Mục tiêu:** người dùng đi theo PowerShell runbook có thể cài lại đúng stack đã
pin, và lỗi host/runtime phải được chỉ rõ thay vì âm thầm tạo environment lệch.

**Việc cần làm:**

1. Audit `Install-HostTools.ps1`, `Check-Environment.ps1`, `Setup-Runtime.ps1`,
   `Setup-Project.ps1`, `lib/Common.ps1` và pin trong `configs/project.psd1`;
   đảm bảo đường dẫn có khoảng trắng/Unicode, `conda run`, exit code, retry và
   idempotency hoạt động đúng. Không đổi version để “cho cài được” nếu chưa có
   proposal protocol mới được duyệt.
2. Tách ba trạng thái kiểm tra: host ready, data ready, GPU runtime ready. Lỗi
   MSVC v142/CUDA/Conda/NVIDIA phải có thông điệp và lệnh khắc phục cụ thể.
   Không báo `setup complete` chỉ vì Conda env tồn tại.
3. Hỗ trợ lead cài **MSVC v142/14.29** trên laptop bằng Windows PowerShell elevated;
   sau đó lead chạy `Setup-Project.ps1` trong PowerShell thường. Lưu version,
   `pip freeze`, GPU import và output CLI tại `artifacts/logs/runtime/` (ignored).
4. Kiểm tra script không tự xóa env/dữ liệu. `-RebuildEnvironment` chỉ được dùng
   khi lead yêu cầu rõ vì nó xóa env đã pin; tuyệt đối không xóa dataset/artifacts.

**Test/DoD:** parser PowerShell PASS; negative test khi thiếu Conda/MSVC trả lỗi
đúng; trên A4500 `Check-Environment.ps1 -RequireRuntime` PASS, import
`torch/gsplat/tinycudann/nerfstudio` và CUDA tensor thành công, `ns-train`,
`ns-eval`, `colmap`, `ffmpeg` có thể gọi. CPU machine chỉ ký **code review PASS**;
lead ký **runtime PASS**.

### P1 — Config, data và artifact contracts

**Mục tiêu:** mọi module dùng một định danh scene/run và một layout, không tự tạo
đường dẫn khác nhau khi ghép code.

**Việc cần làm:**

1. Chốt dataset keys `poster`, `garden`, `bonsai`, `room`, `custom:<slug>` và run
   key `<scene>/<method>/<UTC-ID>`; ghi contract machine-readable/JSON schema cho
   run manifest (P1.5), input/output fields, schema version và trạng thái
   `running/succeeded/failed` để P4–P7 dùng chung.
2. Ghi rõ `poster` lấy từ `data/processed/nerfstudio/poster` (subset 100 frame),
   benchmark từ `data/raw/mipnerf360/<scene>`, custom từ
   `data/processed/custom/<scene>`. Raw bất biến; processed có provenance; artifact
   run/log/metrics/renders cùng key. Cập nhật các chỗ tài liệu còn ghi poster tải
   chưa xong hoặc vẽ sai luồng raw→processed.
3. Định nghĩa cách ghi manifest an toàn (file tạm rồi đổi tên), UTC timestamp,
   artifact path không đụng run cũ, `config.yml`/checkpoint/checksum tương ứng;
   định nghĩa version và migration nếu schema đổi.
4. Viết fixture/test cho slug không hợp lệ, path có Unicode/khoảng trắng, key
   trùng, file thiếu, lookup sai scene/method, và kiểm tra `.gitignore` không để
   dataset/checkpoint bị stage. Chỉ test trên fixture nhỏ trong `tests/`.

**Test/DoD:** cùng một run key ánh xạ đúng một bộ run/log/metric/render; contract
có ví dụ hợp lệ và bất hợp lệ; Member 2/3 đọc schema rồi tự code được mà không
phải hỏi lại cách đặt tên/path. Lead review thay đổi contract trước khi dùng.

### P2 — Dataset acquisition và validation

**Mục tiêu:** tải/đánh giá dữ liệu không cần CUDA và luôn biết chính xác scene nào
đủ điều kiện để đưa vào training.

**Việc cần làm:**

1. Duy trì downloader `smoke|benchmark|all` trong `Download-Datasets.ps1`.
   `poster` tải từ Nerfstudio Hugging Face ref đã pin, giữ raw 226 metadata frames
   nguyên vẹn và tạo processed subset 100 ảnh tương ứng; kiểm tra **mọi**
   `file_path` và `images_2`, sparse PLY, không chỉ `Test-Path transforms.json`.
2. Benchmark dùng archive Mip-NeRF 360 chính thức, verify đúng
   `12,535,427,936` byte, chỉ extract `garden/bonsai/room`, xác nhận ảnh
   `images_2` và COLMAP `sparse/0`. Không yêu cầu cả nhóm tải archive 12,5 GB;
   dữ liệu lớn chỉ cần trên máy lead hoặc máy GPU nào thực sự chạy diagnostic.
3. Làm P2.5: manifest từng scene gồm nguồn URL/revision, archive size/checksum
   **nếu đã tính**, image count, resolution đọc từ ảnh, sparse files, thời điểm
   validate, raw/processed path, protocol downscale. Không ghi checksum tưởng tượng
   hoặc ghi dữ liệu nguồn vào Git. Nếu cần checksum toàn archive, đo thật rồi lưu
   kết quả cùng cách tái tính.
4. Thử rerun, ngắt mạng/partial download và file hỏng qua fixture nhỏ; script
   phải fail rõ, giữ partial file để resume, không báo PASS trên dataset không đủ.
   Với Mip archive lớn, chỉ thử resume thật trên laptop nếu cần, không cố làm lại
   download đã hoàn thành chỉ để “test”.

**Test/DoD:** `Download-Datasets.ps1 -Mode all` exit 0 ở laptop, rerun không tải lại;
manifest/đường dẫn/count đúng; kiểm tra độc lập processed `poster` 100/100 frame,
`garden` 185, `bonsai` 292, `room` 311 ảnh `images_2` theo dữ liệu hiện đã tải.
Nếu nguồn upstream đổi, không hard-code count mới âm thầm: review revision/protocol.

## 4. Member 2 (CPU) — P3 → P4

### P3 — Phone capture, COLMAP pose và frozen split

**Mục tiêu:** một scene ảnh điện thoại thật, train/eval tách rõ, pose đủ tốt và cả
hai methods dùng chính xác cùng input.

**Việc cần làm:**

1. Lên kế hoạch chụp khoảng 80–150 ảnh sắc tổng cộng, static, ánh sáng ổn định, hai vòng góc
   thấp/cao, overlap khoảng 70–80%; thêm eval views riêng khoảng 10–15%, xen
   giữa quỹ đạo train nhưng **không trùng** frame. Cố định lens/zoom/exposure khi
   khả thi; ghi số ảnh bị loại vì blur và lý do. Có thể dùng điện thoại của bất kỳ
   thành viên nào; GPU không liên quan tới chụp ảnh.
2. Đặt ảnh ở `data/raw/custom/<scene>/train|eval` với tên không trùng. Kiểm tra
   file type, ảnh lỗi/zero-byte, hash train-vs-eval, và không xử lý crop/rotate
   thủ công không log. Không đẩy ảnh private/raw lên Git.
3. Audit/hoàn thiện `Process-Capture.ps1`: validate slug/path, chạy
   `ns-process-data images --eval-data` một lần, không ghi đè scene processed;
   xuất báo cáo registered/total train images (P3.4), eval count, rejected files,
   split file list/hash. Nếu xử lý bị gián đoạn, giữ log và yêu cầu scene version
   mới hoặc quy trình recovery được lead đồng ý; không xóa tùy tiện.
4. Trên máy có COLMAP phù hợp, có thể xử lý pose bằng CPU nếu tốc độ chấp nhận
   được; nếu wrapper/runtime đã pin không chạy CPU-only thì giao ảnh cho lead để
   chạy `Process-Capture.ps1` trên A4500. Dù chạy ở đâu, phải review bằng mắt camera
   frustums/sparse cloud; không suy ra pose đúng chỉ từ exit code.

**Test/DoD:** ≥90% ảnh train register; `transforms.json` và sparse points hợp lệ;
train/eval filenames bất biến, không hash trùng, không eval frame lọt vào train;
ảnh, frustums và sparse geometry được ít nhất Member 2 + lead duyệt. Test fixture
cho thiếu eval, slug sai, duplicate và output đã tồn tại đều fail đúng; chưa đủ
ảnh/pose thì P4 custom bị BLOCKED.

### P4 — Training core

**Mục tiêu:** một wrapper chung gọi Nerfacto/Splatfacto đúng parser nhưng không
trộn training với inference, và mọi run đều có provenance/exit state.

**Việc cần làm:**

1. Hoàn thiện `Train.ps1`/`Monitor-Gpu.ps1`: route `poster` processed,
   Mip-NeRF 360 COLMAP và `custom:<slug>` filename split đúng; validate
   `transforms.json`, `images_2`, sparse points, split trước khi chiếm GPU.
2. Lấy pins/30k/downscale2/seed42/eval interval8 từ registry. Không tự hạ
   resolution, iterations, densification cho một method. Diagnostic 100–1000
   iterations phải có nhãn riêng và **không** đi vào bảng primary.
3. Tạo run ID UTC duy nhất, ghi exact command, code SHA + dirty status, data
   manifest/split hash, GPU/driver, thời điểm start/end, wall time, GPU CSV;
   machine-readable status `running/succeeded/failed` theo schema P1. Monitor
   dừng kể cả khi exception; lỗi OOM/NaN giữ log và exit khác 0.
4. Khi run exit 0, kiểm tra đúng vị trí `config.yml`, checkpoint không rỗng và
   run/log key tương ứng. Không chọn checkpoint khác vì tên folder sắp xếp đẹp.
   Không tự gọi `ns-eval` trong trainer: P5 là module độc lập.
5. Trên CPU, kiểm chứng bằng mock command/fixture và parser; bàn giao script cho
   lead chạy **lần lượt** hai poster diagnostic/full smoke trên A4500. Member 2
   nhận log lỗi, sửa code, lặp đến khi cả hai checkpoint pass. GPU 6 GB không là
   máy nghiệm thu baseline.

**Test/DoD:** route/parser/argument arrays đúng trên đường dẫn Unicode; fail trước
GPU khi thiếu data/split; forced nonzero/NaN/OOM tạo `failed` + log, không tạo
`succeeded`; thành công tạo config/checkpoint/log/timing/GPU monitor đủ. Lead xác
nhận hai poster methods chạy được trên A4500 trước khi P4 DONE.

## 5. Member 3 (GPU PC 6 GB) — P5 → P6 → P7

### P5 — Inference, held-out eval, render và export

**Mục tiêu:** sau training, dùng đúng checkpoint/config của run để đo trên camera
held-out, không dùng training views làm evidence.

**Việc cần làm:**

1. Hoàn thiện `Evaluate-Run.ps1`, rồi `Render-Run.ps1`/`Export-Run.ps1` theo P5:
   nhận exact `config.yml` trong `artifacts/runs`, kiểm tra checkpoint và run
   manifest, ghi output theo **cùng run key**. Không tự chọn `latest` khi kết quả
   sẽ công bố. Nếu CLI upstream không hỗ trợ flag dự kiến, kiểm tra `--help` của
   version đã pin và sửa wrapper, không đoán.
2. Chạy `ns-eval` trên held-out set, kiểm tra JSON parse được và PSNR/SSIM/LPIPS
   hữu hạn; kiểm tra số GT/pred frames và danh sách camera/index trùng với frozen
   eval split, không chỉ kiểm tra folder render không rỗng. Lưu model/checkpoint
   byte size cùng metric provenance.
3. Dùng cùng camera path/resolution để render hai methods; đo offline throughput
   sau warm-up, ghi frame count, timing, FPS và VRAM, không thay bằng viewer FPS.
   Export Gaussian PLY/Nerfacto point cloud theo run key; không so kích thước hai
   format mà không ghi rõ định nghĩa.
4. Có thể thử scene/tiny run riêng trên GPU 6 GB để phát hiện lỗi CLI và UI. Ghi
   rõ `diagnostic-6gb`, hardware/seed/flags; không nhập số đó vào baseline hoặc
   dùng nó để khẳng định 16 GB chắc chắn PASS. Nghiệm thu chính dùng checkpoint
   được lead train/eval trên A4500; nếu 6 GB OOM thì chuyển sang fixture/mock,
   không ép thay protocol chính.

**Test/DoD:** reject config ngoài `artifacts/runs`, checkpoint thiếu, metric NaN,
render count lệch, train-frame leakage; với hai poster configs từ lead, evaluator
trả hữu hạn metrics và GT/pred đúng held-out cameras. P5 chỉ DONE sau lead xác
nhận inference GPU thật trên A4500.

### P6 — Paired benchmark orchestrator

**Mục tiêu:** một scene chỉ PASS khi có cả Nerfacto lẫn Splatfacto cùng protocol;
run lỗi không bị chọn lại nhầm hoặc lẫn với run của scene khác.

**Việc cần làm:**

1. Audit `Run-Benchmark.ps1`: chạy scene × method **tuần tự** trên một GPU;
   evaluate exact `config.yml` vừa tạo; có explicit scene list và fail-fast nếu
   thiếu artifact. Tránh `Sort-Object` chọn “latest” trong trường hợp có diagnostic
   hoặc failed run xen giữa; dùng run ID/status/manifest vừa sinh.
2. Hoàn thiện P6.3 paired manifest: scene, protocol ID, dataset/split hash,
   method, run IDs, config/checkpoint paths, eval paths, GPU/driver, seed,
   iterations, downscale, trạng thái; PASS chỉ nếu đủ hai method và mọi metric
   valid. Half-pair hoặc khác split/protocol → FAIL/BLOCKED, không aggregate.
3. Hoàn thiện P6.4 resume **ở run boundary**: run đã PASS giữ nguyên; run failed
   được tạo attempt mới có ID mới; không âm thầm resume checkpoint hoặc overwrite
   log. Dry-run/fixture tests chứng minh không chạy hai jobs đồng thời.
4. Lead trên A4500 chạy `bonsai` calibration pair trước, đo peak VRAM/nhiệt,
   kiểm tra không OOM và artifact; sau đó mới `garden`/`room`. PC 6 GB chỉ chạy
   fixture/diagnostic riêng, không chạy full matrix để chứng minh baseline.

**Test/DoD:** fixture gồm good pair, half-pair, wrong split, NaN, failed attempt,
resume; chỉ good pair PASS. Trên A4500 có 3 scenes × 2 methods, mỗi run đủ
config/checkpoint/log/metrics/renders và không GPU jobs chồng nhau.

### P7 — Research analysis và hồ sơ G-Core

**Mục tiêu:** biến artifact thành kết luận có thể truy xuất, không “điền số đẹp”
vào bảng và không tuyên bố phương pháp nào luôn tốt hơn.

**Việc cần làm:**

1. Viết `src/topic16/validate_runs.py` và `aggregate.py` (hoặc PowerShell wrapper
   gọi Python trong Conda env): đọc paired manifests, validate schema P1, lọc
   failed/diagnostic/half-pair, xuất bảng PSNR↑/SSIM↑/LPIPS↓, wall time, peak VRAM,
   model bytes, offline FPS. Mọi hàng bảng link về exact run ID + Git SHA.
2. Chọn cùng held-out camera và crop cho `garden` foliage/thin branches,
   `bonsai` specular/fine detail, `room` low-overlap; ghi crop coordinates và
   image names. Tách **measured** trên A4500 khỏi planning estimate và upstream
   claims trong README/papers.
3. Với custom scene, liên kết camera quality/registration với artifact khác nhau
   của hai methods; ghi limitation do 80 W laptop, one seed, Windows runtime,
   GPU CSV sampling 10 giây và batch semantics khác nhau. Không kết luận tổng quát
   “NeRF vs 3DGS” khi chỉ đo Nerfacto vs Splatfacto.
4. Chuẩn bị checklist G-Core từng dòng có đường dẫn minh chứng: poster pair,
   `bonsai` calibration, đủ 6 benchmark runs, paired custom, zero leakage/NaN,
   clean-machine PowerShell rerun. Lead và nhóm ký review; nếu thiếu một dòng thì
   G-Core = BLOCKED, P8/P9 không mở.

**Test/DoD:** aggregator trên fixture xáo thứ tự input vẫn ra bảng xác định;
loại đúng half-pair/nonfinite/diagnostic; mỗi số trong report truy về metrics và
log; figure dùng cùng camera/crop. G-Core chỉ PASS khi **artifact thật** đầy đủ,
không PASS chỉ vì script/giấy tờ đã viết.

## 6. Member 4 — Lead RTX A4500 16 GB/80 W — P8 → P9 → P10

### Vai trò tích hợp GPU trước G-Core (không phải Px sở hữu rời rạc)

Lead là người duy nhất có máy nghiệm thu baseline. Điều này là trách nhiệm vận
hành/review xuyên dải, **không** chuyển code ownership P0/P4/P5/P6 từ thành viên
khác sang lead.

1. MSVC v142 và runtime A4500 đã PASS ngày 2026-09-24. Khi một thay đổi P0
   chạm setup, chạy lại `Check-Environment.ps1 -RequireRuntime` và lưu GPU
   imports/dependency snapshot. Nếu runtime FAIL, gửi log chính xác cho Member 1;
   không giữ trạng thái P0 PASS trên revision lỗi.
2. Cấp máy A4500 theo lịch: poster Nerfacto → poster Splatfacto → eval cả hai →
   `bonsai` pair → `garden`/`room` pair → custom pair. Mỗi job tuần tự; cắm nguồn,
   performance mode, thông gió; ghi GPU name/driver, 80 W thermal/power behavior,
   temperature, VRAM và wall time. Không chạy viewer/workload GPU khác khi timed.
3. Review và ký H0–H4; trả log cho chủ Px nếu fail. Không sửa lặng lẽ code của
   người khác trên laptop để ra kết quả; fix phải qua PR/commit, rerun và lưu Git
   SHA. Không trộn run trước/sau đổi pin/protocol vào cùng bảng.

### P8 — Production adapter, **chỉ sau G-Core PASS**

**Mục tiêu:** phục vụ inference của model đã chọn, tuyệt đối không train/tune trong
request path. Trước G-Core chỉ được viết acceptance criteria/thiết kế trên giấy;
không triển khai app/service.

**Việc cần làm khi gate mở:** chọn model bằng report manifest; tạo immutable
`production/manifests/model.json` gồm method, run key, config/checkpoint hash,
version, expected input/camera/resolution; viết read-only loader và thin
viewer/render adapter, `production/scripts/Start-Demo.ps1`, warm-up/health check,
queue tối đa 1 trên laptop 16 GB, timeout và lỗi rõ khi model/CUDA/input sai.
Không cho app ghi `data/raw` hoặc `artifacts/runs`; không bắt GPU 6 GB phải host
model 16 GB nếu không fit.

**Test/DoD:** start/stop PowerShell; hash sai/model mất/CUDA mất/input sai fail
rõ; hai lần render cùng model/camera có sai số trong ngưỡng đã ghi; RAM/VRAM
không tăng vô hạn, request đồng thời được xếp hàng; source artifacts không đổi
checksum sau test. Nghiệm thu trên A4500.

### P9 — Demo, release và báo cáo, **sau P8 PASS**

**Mục tiêu:** người ngoài nhóm chạy được demo và lần ngược mọi số liệu trong
báo cáo.

**Việc cần làm:** tạo viewer demo và video fallback cùng camera path; release
manifest có Git SHA, dependency snapshot, dataset citations, model hashes,
protocol ID; viết hướng dẫn copy-paste PowerShell cho máy mới, chuẩn bị 6–8 trang
báo cáo và presentation. Chỉ stage model cần demo; không commit dataset, PDF,
checkpoint lớn hay secret. Kiểm tra model/video có sẵn thì demo offline vẫn chạy.

**Test/DoD:** một người **không viết code** làm theo runbook từ clone/setup đến
load model, xem video fallback, tìm được artifacts; mọi bảng/figure có run ID;
release không chứa data lớn/private hoặc absolute path cá nhân.

### P10 — QA/CI xuyên suốt từ ngày đầu

**Mục tiêu:** phát hiện lỗi bằng test rẻ trước khi đốt thời gian A4500; giữ ba tài
liệu kiến trúc/working list/README đồng bộ với code và trạng thái thật.

**Việc cần làm:** duy trì parser test cho mọi `.ps1`; PSScriptAnalyzer khi có;
fixture contract/path/JSON/split, unit tests cho P0–P7; kiểm tra `.gitignore`,
no secret/no dataset in Git, dependency pins một nơi; review CLI flags với
upstream version đã pin. Thu GPU acceptance logs từ lead nhưng test CPU vẫn chạy
độc lập. Khi nâng pin phải tạo protocol ID mới, rerun P0/P4/P5, không sửa kết quả
cũ. Cập nhật README để các con số thời gian/FPS chưa đo không được gọi là kết quả
đã kiểm chứng; cập nhật working list theo evidence, không theo kỳ vọng.

**Test/DoD:** parser không lỗi, fixture/unit tests PASS trong Windows PowerShell;
test cố ý đưa data thiếu/NaN/half-pair phải FAIL đúng; clean worktree/không có
artifact lớn staged; GPU smoke thủ công được ghi log trên A4500. P10 không được
coi là xong chỉ vì parse pass một lần.

## 7. Ma trận test/thiết bị và bằng chứng tối thiểu

| Gate | Ai chuẩn bị | Nơi chạy để ký PASS | Bằng chứng bắt buộc |
|---|---|---|---|
| Script/parser/schema/fixture | Chủ Px + lead P10 | Windows PowerShell CPU đủ | Test command, exit code, fixture kết quả |
| P0 runtime CUDA | Member 1 | Lead A4500 16 GB | Host check, import/version, CUDA tensor, CLI, `requirements.txt` snapshot |
| P2 datasets | Member 1 | CPU/laptop lead | Scene manifest, frame/file counts, repeat download skip |
| P3 pose/split | Member 2 | CPU nếu COLMAP chạy được; nếu không lead | Registration report, hashes/split lists, visual frustums |
| P4 training | Member 2 | Lead A4500 16 GB | 2 poster checkpoints/config/log/status/GPU CSV |
| P5 inference/eval | Member 3 | Lead A4500 16 GB | Poster held-out metrics hữu hạn, GT/pred count/camera IDs |
| P6 benchmark | Member 3 | Lead A4500 16 GB | Bonsai calibration rồi 6 paired benchmark runs, manifests |
| P7/G-Core | Member 3 + toàn nhóm review | Artifact audit; clean-machine replay nếu có máy phù hợp | Checklist từng dòng + exact run links, report tables/figures |
| P8/P9 | Lead sau G-Core | Lead A4500 16 GB và người test độc lập | Model hash, startup/render/offline demo/release checks |

Không ép CPU members cài CUDA, chạy `Setup-Project.ps1` hoặc chạy
`Check-Environment.ps1 -RequireRuntime` trên máy không có NVIDIA GPU. Không báo
nghiệm thu GPU nếu chỉ chạy mock. GPU 6 GB là
máy phát triển/diagnostic phụ; **A4500 80 W là máy đo chính duy nhất**. Nếu máy
mới trong G-Core không có GPU tương đương, chỉ xác minh phần setup/data/CLI; ghi
rõ phần training replay chưa được kiểm chứng, không nói “reproduce complete”.

## 8. Lịch thực hiện theo dependency, không theo cảm tính

1. **Ngay:** Member 1 duy trì P0/P1/P2 và xử lý doc drift; Member 2 chuẩn bị
   capture/fixture P3, thiết kế test P4; Member 3 thiết kế fixture/schema consumer
   P5–P7; lead chạy P10 và bảo quản runtime A4500 đã PASS. Đây là chuẩn bị song song, không
   đánh dấu downstream PASS trước upstream.
2. **P0 runtime đã PASS:** lead cấp GPU slot cho P4 poster pair; Member 2 sửa
   wrapper theo log, Member 3 nối P5 evaluator. CPU members tiếp tục P2 manifest
   và P3 quality gate mà không chiếm GPU.
3. **Khi poster train/eval PASS:** Member 3 hoàn thiện P6; lead chạy `bonsai`
   calibration trước, kiểm tra nhiệt/VRAM của laptop 80 W. OOM → giữ failed run,
   xét protocol low-memory riêng cho cả cặp; không tự giảm một method.
4. **Khi `bonsai` PASS:** lead chạy `garden`, `room`, custom scene tuần tự;
   Member 3 kiểm tra paired manifests, làm P7 analysis. Cả nhóm review G-Core.
5. **Chỉ sau G-Core PASS:** lead mở P8 rồi P9; Member 1–3 hỗ trợ review/test theo
   contract, không tự làm production sớm. P10 tiếp tục đến release.

## 9. Cách chạy kiểm tra cơ bản (Windows PowerShell)

```powershell
Set-Location -LiteralPath $Topic16Root  # khai báo $Topic16Root theo mục đầu setup_full_command.md
Set-ExecutionPolicy -Scope Process Bypass

# CPU-safe: parser và source control; không cần CUDA.
$parseErrors = @()
Get-ChildItem .\scripts -Recurse -Filter *.ps1 | ForEach-Object {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $_.FullName, [ref]$tokens, [ref]$errors)
    if ($errors) { $parseErrors += $errors }
}
if ($parseErrors.Count) { $parseErrors; throw 'PowerShell parse failed.' }
git status --short
```

Chỉ lead chạy block này trên A4500; **CPU members dừng ở block trước**:

```powershell
Set-Location -LiteralPath $Topic16Root
.\scripts\Setup-Project.ps1
.\scripts\Check-Environment.ps1 -RequireRuntime
Test-Path .\artifacts\logs\runtime\requirements.txt
```

Lệnh clone và setup theo từng loại máy, train/eval/export và xử lý custom nằm
trong [`setup_full_command.md`](setup_full_command.md). Setup runtime A4500 đã
PASS; lệnh **training/eval** chưa được coi là PASS cho đến khi lead thực sự chạy,
lưu log và ký gate. `requirements.txt` được sinh ở
`artifacts\logs\runtime\requirements.txt` trên từng máy sau setup và bị Git
ignore; dùng `configs\project.psd1` làm nguồn pin, không copy snapshot của lead
thành lệnh cài đặt trên máy CPU/6 GB.

## 10. Reference pack bắt buộc theo Px — đọc paper, đọc code, rồi mới code

Các link sau là **nguồn gốc** (tác giả paper/dataset, repository upstream hoặc
tài liệu chính thức), không phải blog/đoạn code AI tự tạo. Dùng tài liệu web để
hiểu khái niệm; dùng **source Nerfstudio tại commit đã pin** để quyết định tên
class, parser, flag và output thực tế. Trang web `main` có thể đã đổi sau v1.1.5.
Nếu link web và checkout khác nhau, checkout đã pin + `--help` trong env cài thật
là chuẩn cho project; ghi khác biệt vào PR. Không tự thêm dependency/CLI flag chỉ
vì một câu trả lời AI nói là có.

| Px, người đọc | Nguồn bắt buộc và phần cần đối chiếu | Kết luận phải rút ra trước khi code |
|---|---|---|
| **P0 — Member 1** | [Nerfstudio installation](https://docs.nerf.studio/quickstart/installation.html), [PyTorch 2.1.2/cu118 official versions](https://docs.pytorch.org/get-started/previous-versions/), [tiny-cuda-nn repository](https://github.com/NVlabs/tiny-cuda-nn), [gsplat v1.4.0 release](https://github.com/nerfstudio-project/gsplat/releases/tag/v1.4.0), [pinned Nerfstudio dependency manifest](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/pyproject.toml). | Windows compiler/CUDA/Torch/gsplat/tcnn là một stack tương thích phải **được chạy kiểm chứng**, không suy từ `pip install` exit 0. Lấy pin từ `configs/project.psd1`, không từ phiên bản mới nhất trên web. |
| **P1 — Member 1** | [Nerfstudio data conventions](https://docs.nerf.studio/quickstart/data_conventions.html), [JSON Schema reference](https://json-schema.org/understanding-json-schema/reference), [pinned parser source](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/data/dataparsers/nerfstudio_dataparser.py). | `transforms.json`, camera convention, split và artifact schema là contract; chỉ parser của commit pin quyết định `eval_mode`/`downscale_factor` có ý nghĩa gì. |
| **P2 — Member 1** | [Poster dataset của Nerfstudio](https://huggingface.co/datasets/nerfstudioteam/datasets/tree/461701c17e83c3f4d2481db32315aa7df703d2f8/poster), [Mip-NeRF 360 project/dataset](https://jonbarron.info/mipnerf360/), [official archive](https://storage.googleapis.com/gresearch/refraw360/360_v2.zip), [pinned COLMAP parser](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/data/dataparsers/colmap_dataparser.py). | Poster source hiện có 100 ảnh nhưng 226 metadata frames: raw giữ nguyên, processed chỉ chứa matched frames. Archive benchmark phải được validate bằng bytes, layout và ảnh; URL không đồng nghĩa dữ liệu đã hợp lệ. |
| **P3 — Member 2** | [Nerfstudio custom data](https://docs.nerf.studio/quickstart/custom_dataset.html), [COLMAP tutorial](https://colmap.github.io/tutorial.html), [COLMAP sparse output format](https://colmap.github.io/format.html), [pinned `process_data.py`](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/scripts/process_data.py). | Camera intrinsics/poses và sparse points đến từ COLMAP; `--eval-data` là held-out input, không phải ảnh tăng cường train. Không đảo trục/hệ tọa độ bằng code tự đoán. |
| **P4 — Member 2** | [Nerfacto method](https://docs.nerf.studio/nerfology/methods/nerfacto.html), [Splatfacto method](https://docs.nerf.studio/nerfology/methods/splat.html), [pinned method configs](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/configs/method_configs.py), [pinned Nerfacto](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/models/nerfacto.py), [pinned Splatfacto](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/models/splatfacto.py). | Hai methods có batch semantics khác nhau nhưng dùng cùng scene/split/protocol. Wrapper gọi model hiện có; không tự dựng “NeRF mới” hoặc “3DGS mới” từ mô tả paper. |
| **P5 — Member 3** | [Official `ns-eval` CLI](https://docs.nerf.studio/reference/cli/ns_eval.html), [pinned `eval.py`](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/scripts/eval.py), [pinned `render.py`](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/scripts/render.py), [pinned `exporter.py`](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/scripts/exporter.py). | Eval phải load exact generated `config.yml`, dùng frozen held-out views và metric implementation đã pin. CLI flag/format phải được đối chiếu bằng `--help`; không viết lại PSNR/SSIM/LPIPS cho bảng chính. |
| **P6 — Member 3** | [Nerfstudio CLI index](https://docs.nerf.studio/reference/cli/index.html), [pinned trainer/method configs](https://github.com/nerfstudio-project/nerfstudio/blob/6b60855003011b2ca23c2fe3f8e2ca6314c69924/nerfstudio/configs/method_configs.py), chính `Train.ps1` và `Evaluate-Run.ps1` trong repo. | P6 chỉ orchestration; không thêm hyperparameter ẩn. Pair được định nghĩa bằng scene + split hash + protocol ID + cả hai run IDs, không bằng “hai folder gần nhất”. |
| **P7 — Member 3** | [NeRF paper](https://arxiv.org/abs/2003.08934), [Mip-NeRF 360 paper/project](https://jonbarron.info/mipnerf360/), [3DGS paper/project](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/), [gsplat paper](https://jmlr.org/papers/v26/24-1476.html), [Nerfstudio paper](https://arxiv.org/abs/2302.04264). | Paper giải thích *vì sao* xuất hiện quality/speed/memory trade-off; kết quả nhóm phải đến từ artifacts A4500, không lấy claim paper/GPU khác thay số đo. Gọi đúng Nerfacto vs Splatfacto. |
| **P8 — Lead, sau G-Core** | [Nerfstudio CLI/viewer](https://docs.nerf.studio/reference/cli/index.html), pinned `eval.py`/`render.py`/`exporter.py` ở P5, report manifest P7. | Adapter chỉ load artifact bất biến đã chọn, read-only; không tự đổi camera convention hoặc train trong request. Không bắt đầu code trước G-Core. |
| **P9 — Lead, sau P8** | [Nerfstudio rendering/export CLI](https://docs.nerf.studio/reference/cli/index.html), [Mip-NeRF 360 dataset attribution](https://jonbarron.info/mipnerf360/), citations trong `Construction_architect.md`. | Demo/video/report dùng cùng run/camera path; release chỉ là manifest + retrieval instructions, không đưa dataset/model lớn vào Git. |
| **P10 — Lead, xuyên suốt** | [Pester quick start](https://pester.dev/docs/quick-start), [Microsoft PSScriptAnalyzer](https://learn.microsoft.com/en-us/powershell/module/psscriptanalyzer/invoke-scriptanalyzer?view=ps-modules), [JSON Schema](https://json-schema.org/understanding-json-schema/reference). | Test ở CPU xác minh contract, path, fail-fast; GPU smoke trên A4500 xác minh runtime. Static lint/AI review không thay được chạy thật. |

**Kho code nghiên cứu gốc để hiểu kiến trúc (không phải runtime để `pip install`):**

| Ý tưởng cần đọc | Repository tác giả | Ai đọc/phân biệt với runtime |
|---|---|---|
| NeRF volume rendering, coarse/fine sampling | [bmild/nerf](https://github.com/bmild/nerf) | Member 2/3: NeRF 2020 là nền tảng toán, **không** phải code Nerfacto đang chạy. |
| Scene contraction, proposal/distortion trên unbounded scenes | [google-research/multinerf](https://github.com/google-research/multinerf) | Member 2/3: đọc ý tưởng Mip-NeRF 360, không thay Nerfstudio loader bằng JAX loader. |
| Hash-grid encoding và fused MLP | [NVlabs/instant-ngp](https://github.com/NVlabs/instant-ngp), [NVlabs/tiny-cuda-nn](https://github.com/NVlabs/tiny-cuda-nn) | Member 1/2: hiểu acceleration và compiler dependency; không đưa Instant-NGP testbed vào benchmark. |
| Gaussian primitives, densification, rasterization gốc | [graphdeco-inria/gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) | Member 2/3: so với Splatfacto đã pin; không giả định class/flag giống code INRIA. |
| CUDA rasterizer dùng trong Splatfacto | [nerfstudio-project/gsplat](https://github.com/nerfstudio-project/gsplat), [release v1.4.0](https://github.com/nerfstudio-project/gsplat/releases/tag/v1.4.0) | Member 1/3: đọc source/release tương ứng, không lấy API của `main` hiện tại để viết wrapper v1.1.5. |
| Camera pose/SfM | [colmap/colmap](https://github.com/colmap/colmap) | Member 2: hiểu reconstruction và file format; CLI cuối cùng phải kiểm tra trong COLMAP 3.9.1 đã cài. |

Exact research SHAs đã nằm ở `configs/project.psd1`; dùng
`Download-Repositories.ps1 -Mode research` nếu cần bản local. Repo nghiên cứu chỉ
để đọc/đối chiếu paper và khác biệt implementation; `third_party/nerfstudio` ở
commit pin vẫn là code thực thi của cả hai methods trong project.

**Cách dùng offline và chống version drift:** runtime source ở
`third_party/nerfstudio/` đã checkout commit `6b608550...`; mở file cùng path như
link GitHub ở bảng trên. Các repo paper tham chiếu khác có thể tải bằng
`Download-Repositories.ps1 -Mode research` **khi thật sự cần đọc code**, không cài
vào environment benchmark. Không dùng code trên `main` để đoán API v1.1.5.
Nguồn COLMAP web có thể là bản mới hơn package `3.9.1` đã pin; dùng nó để hiểu
format/thuật ngữ, sau đó kiểm tra CLI trên package thực tế.

## 11. Sơ đồ kiến trúc và công thức tối thiểu để review code

Đây là **bản đồ đối chiếu**, không phải yêu cầu tự triển khai lại các thuật toán
CUDA. Source cụ thể nằm ở bảng P4/P5 phía trên và mục 5 trong
[`Construction_architect.md`](Construction_architect.md).

```text
Ảnh + intrinsics/poses ── P2/P3: cùng camera và split cố định ──┐
                                                               ├─ P4: Nerfacto
                                                               │    ray → proposal samples
                                                               │    → hash field/MLP
                                                               │    → volume compositing
                                                               └─ P4: Splatfacto
                                                                    sparse points → Gaussians
                                                                    → gsplat rasterization
                                                                    → alpha compositing
                    hai config.yml + checkpoints ── P5: ns-eval held-out
                                               └── P6: paired manifest
                                               └── P7: bảng/figures/G-Core
                                               └── G-Core PASS → P8/P9
```

**P3, camera/pose.** Với điểm thế giới `X`, phép chiếu lý tưởng viết ngắn là
`u ~ K [R|t] X_h` (tọa độ đồng nhất); sai pose hoặc intrinsics làm *cả hai* method
render sai. COLMAP lưu pose world→camera; Nerfstudio dùng convention camera khác.
Đọc [COLMAP output format](https://colmap.github.io/format.html) và
[Nerfstudio data conventions](https://docs.nerf.studio/quickstart/data_conventions.html);
để parser đã pin chuyển hệ, không tự viết phép lật dấu theo phỏng đoán.

**P4, Nerfacto.** NeRF tích phân màu dọc ray; dạng rời rạc đủ để code review là
`C(r) ≈ Σ_i T_i (1 − exp(−σ_i Δ_i)) c_i`, với
`T_i = exp(−Σ_{j<i} σ_j Δ_j)`. Nerfacto thêm proposal sampling, scene
contraction và hash encoding, nên không đồng nhất nó với NeRF 2020 nguyên bản.
Đối chiếu [paper NeRF](https://arxiv.org/abs/2003.08934),
[Nerfacto guide](https://docs.nerf.studio/nerfology/methods/nerfacto.html) và
`models/nerfacto.py` ở commit pin. **Không** tự tính lại integral trong wrapper.

**P4, Splatfacto.** Một Gaussian có center `μ`, rotation `R`, scale `S` và
covariance `Σ = R S Sᵀ Rᵀ`; sau phép chiếu cục bộ, covariance màn hình gần đúng
`Σ₂D = J W Σ Wᵀ Jᵀ`. Màu pixel là alpha compositing theo depth:
`C = Σ_i c_i α_i ∏_{j<i}(1 − α_j)`. Sparse COLMAP points khởi tạo Gaussian;
densification/pruning làm số primitives và VRAM thay đổi. Đối chiếu
[3DGS paper](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/),
[Splatfacto guide](https://docs.nerf.studio/nerfology/methods/splat.html) và
`models/splatfacto.py` ở commit pin. Công thức là khung kiểm tra logic, không phải
lời hứa backend Splatfacto v1.1.5 giống hệt implementation INRIA.

**P5–P7, evaluation.** Với ảnh dự đoán `I` và GT `I*`, `MSE = mean((I−I*)²)`;
`PSNR = 10 log10(MAX²/MSE)` khi `MSE > 0` (đơn vị intensity phải nhất quán).
SSIM đo cấu trúc cục bộ, LPIPS đo khoảng cách feature perceptual: lấy **cùng
implementation `ns-eval` đã pin** cho cả hai methods, không thay bằng công thức
AI viết lại. Cùng metric trên **training views** không chứng minh novel-view
quality; camera IDs của eval phải không giao với train. Iterations bằng nhau
không đồng nghĩa cùng FLOPs vì Nerfacto lấy ray batch còn Splatfacto lấy image
batch. Báo cáo phải ghi cả wall time, peak VRAM và model bytes.

## 12. Quy trình bắt buộc khi thành viên dùng AI để viết code

AI là công cụ hỗ trợ tìm/soạn, **không phải nguồn chứng cứ**. Mỗi người làm theo
chuỗi sau cho mọi thay đổi có tác động đến architecture, CLI hoặc metric:

1. Viết một câu *mục tiêu và contract*: input, output, side effects, Px owner,
   DoD; chỉ rõ code cần nối vào file nào trong repo.
2. Dẫn **ít nhất một nguồn chính thức** từ bảng Px; với API/flag, nêu file và
   function/class tại commit đã pin hoặc output `--help` của env cài thật. Nếu
   không tìm thấy trong source, đánh dấu `UNVERIFIED`, không merge dù AI trả lời
   rất tự tin. Trang `main`/blog chỉ là gợi ý tìm kiếm.
3. Yêu cầu AI đưa *patch nhỏ* theo contract, không tái thiết kế toàn project,
   không thêm dependency mới, không đổi pin/protocol, không tự code CUDA/renderer
   hoặc metric vốn upstream đã cung cấp. Mọi đề xuất đổi giao diện phải qua review
   của cả owner upstream và downstream.
4. Chạy test âm/dương: fixture hợp lệ phải PASS; data/config/split thiếu, NaN,
   wrong path hoặc failed run phải FAIL rõ. Trên CPU chỉ kết luận code/contract;
   trên A4500 mới kết luận GPU. Lưu lệnh, exit code và artifact path trong PR.
5. PR phải có mục `Nguồn chính thức + commit/section`, `Điểm khác upstream`,
   `Test đã chạy`, `Test chưa thể chạy`, `Tác động tới split/protocol`,
   `Người nghiệm thu GPU`. Nếu câu trả lời AI và source xung đột, giữ source +
   test thực tế, bỏ đoạn AI. Không gắn `DONE` khi còn `UNVERIFIED` ở critical path.

**Ví dụ lỗi phải bắt:** AI đề xuất một flag `ns-train` chỉ có ở Nerfstudio `main`,
đổi `eval-mode` làm lẫn train/eval, copy config của “latest” khác run, so sánh
FPS giữa PC 6 GB và laptop 80 W, hoặc đưa Splatfacto thành code 3DGS INRIA
trong khi project đã chốt Nerfstudio/gsplat. Mọi trường hợp này đều cần trả về
source pin và contract P1 trước khi sửa code.

**Khuôn yêu cầu AI cho một task:**

```text
Px: <P0...P10>; owner: <member>; file được phép sửa: <path>.
Mục tiêu/input/output/side effects: <contract cụ thể>.
Source of truth: Construction_architect.md + Modular_construct.md +
configs/project.psd1 + <file/function trong Nerfstudio commit 6b608550...>.
Hãy chỉ dùng API/CLI đã xác minh trong source pin hoặc --help của env thật.
Nếu thiếu bằng chứng, ghi UNVERIFIED và hỏi lại; không bịa flag/class/version.
Đề xuất patch nhỏ và test PASS/FAIL trên fixture. Nêu rõ test nào cần A4500.
Không sửa upstream, không đổi split/protocol/pins, không làm P8/P9 trước G-Core.
```

Sau khi AI trả lời, thành viên **tự mở source được dẫn** và chạy test; mẫu prompt
không thể bảo đảm AI không hallucinate nếu bỏ bước review/nghiệm thu này.
