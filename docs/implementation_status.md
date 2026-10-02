# Implementation và bằng chứng nghiệm thu

Cập nhật acceptance **2026-10-02**: toàn bộ 10 primary train/eval và render/export
đã complete, session `topic16-full` là `awaiting-evidence`. Bảng 8 main runs được
tính lại chính xác bằng venv native Windows package-free; 14 selected camera cases
từ 115 held-out views, charts/crops/error maps, trade-offs và limitations đã có tại
[research review](../reports/topic16-full/review/research_review.md). Fresh-Python
CPU QA: 38 PowerShell parsers, 19 fixture successes, 75 Python tests PASS;
PSScriptAnalyzer unavailable/SKIPPED. Đây không phải fresh GPU replay hoặc human
approval. Hai approvals vẫn false, **G-Core BLOCKED**. Evidence:
`reports/topic16-full/review/{artifact-audit.json,cpu-qa.log,review.pending.json}`.

Các sections tiếp theo giữ lịch sử audit/integration ngày **2026-09-30**.
Kế hoạch: [completion_plan](completion_plan.md).
Lệnh: [runbook](../setup_full_command.md). Code implemented và acceptance bằng
run thật là hai trạng thái khác nhau. Full 30k/custom thực nghiệm hiện đã có
evidence; human review, independent replay và demo/release acceptance vẫn chưa
hoàn tất. Không có số benchmark giả hoặc approval giả.

## Trước và sau integration

Member 1 P0–P2 đã bàn giao tại audit ngày 2026-09-28; acceptance note riêng đã được lược bỏ khỏi cây tài liệu hiện tại. Phần dưới giữ lịch sử integration; xem [README](../README.md#6-cấu-trúc-project-và-điểm-vào-code) để tìm code và tài liệu đang sử dụng.
Lúc audit, các wrapper train/eval/benchmark chưa nối đầy đủ immutable manifest,
exact checkpoint, paired resume, held-out evidence hoặc analysis/demo gate.

Đã triển khai pipeline trong một package `src/topic16/`, public PowerShell ở
`scripts/`, common helper duy nhất `scripts/lib/Common.ps1`. `contracts`,
`data/video`, `safety/runtime`, `experiments`, `analysis/demo`, `cli` có ranh giới
đọc/ghi rõ. Generated-config checks của helper cũ đã port vào runtime; bỏ hai
helper không có caller và notebook placeholder. Raw/source/artifacts cũ giữ nguyên.
Toán/paper notes chuyển về `docs/research/` để root docs tập trung vào code/operation.

## Kiểm tra từng stage

| Stage | Code/contract | Bằng chứng thật và phần còn thiếu |
|---|---|---|
| P0 Runtime | Implemented | A4500 16 GB, pinned Conda/PyTorch/gsplat/native CLIs đã PASS trước safety update; elevated managed runtime/CUDA/native CLIs PASS dưới clock cap |
| P1 Manifest | Integrated | Writer lifecycle + path/hash/schema negative tests PASS; real running→succeeded/failed artifacts |
| P2 Official data | Accepted tại audit | Archive SHA/bytes, counts, từng ảnh/sparse metadata PASS; nguồn official đủ |
| P3 Canonical/custom | Implemented | Cả bốn official canonical PASS; tea_sets_2 đủ 120/120 connected poses + canonical/frozen split + agent visual audit |
| P4 Train | Implemented, diagnostic verified | Poster/bonsai/custom paired 100 bước; actual stop/resume 1.000 bước cả hai trainers PASS; primary có session riêng |
| P5 Eval/render/export | Implemented, diagnostic verified | Poster 13 và bonsai 37 held-out views/method; poster paired FPS + hai PLY exports PASS |
| P6 Matrix/resume | Implemented | Official/custom diagnostic matrices PASS; training checkpoint + custom eval stop/resume thật PASS; primary theo managed session |
| P7 Analysis | Implemented, diagnostic verified | CSV/JSON/MD, bonsai same-camera crop, plots và diagnostic gate BLOCKED đã sinh thật |
| P8/P9 Demo/release | Implemented, activation gated | Camera-path generation chạy thật bằng CPU; positive model warm-up/service/video fallback/release chưa accepted vì G-Core chưa PASS |
| P10 QA | CPU PASS | 38 PowerShell files parsed, 19 host/schema/data fixture successes, 69 Python tests trên native Windows; CI definition có, chưa có remote CI evidence |
| Safety | Implemented, fail-closed verified | Native reapply exit 4 bị chặn trước workload; mock overheat/clock/power/VRAM/telemetry tests PASS; actual elevated runtime/training/eval và cooperative pause PASS |

PSScriptAnalyzer chưa có trên host, nên analyzer **SKIPPED**, không ghi lint PASS.
`Test-Project.ps1 -RequireAnalyzer` sẽ fail rõ nếu chưa cài. Full GPU memory ở
30k/densification, custom full-quality/human research review và clean-machine replay không được suy từ tests.

## Dataset inventory

| Source | Số ảnh/frame | Kiểm tra / vai trò |
|---|---:|---|
| Nerfstudio poster | 100 images / 226 raw metadata records | Matched processed subset 100; 13 eval views; smoke gate |
| Mip-NeRF 360 garden | 185 | 24 eval views; source/sparse valid |
| Mip-NeRF 360 bonsai | 292 | 37 eval views; source/sparse valid; canonical + paired diagnostic đã chạy |
| Mip-NeRF 360 room | 311 | 39 eval views; source/sparse valid |
| tea_sets.mp4 | 1.996 decoded frames | 66,533333 s, 720×1280, 30 FPS; video nguồn giữ nguyên |
| tea_sets extracted (attempt cũ) | 120 PNG | 105 train/15 eval; không dùng cho rigid scene benchmark |
| tea_sets_2.mp4 (chính) | 1.922 decoded frames | 64,066667 s, 720×1280, 30 FPS; camera di chuyển quanh cảnh tĩnh |
| tea_sets_2 canonical | 120 PNG / 120 poses | 105 train + 15 eval; connected model 1; frozen split + agent visual audit PASS |

Archive `360_v2.zip`: **12.535.427.936 bytes**;
SHA-256 `77332bf4eba3b8ca0c7f70130849b1e394efdd60d8f20efa6f217081d08a8b2a`.
Official inventory evidence ở `artifacts/logs/datasets/{poster,garden,bonsai,room}.json`.
Tea video SHA-256 `e37424126afb6d6b77e50e588640b4fec3fe3cc6b1f8bf722d2f6e83fc117f53`;
frame selection hash `77b4f283836d44901ed99b5dd79ef3c1b54d935a62dcc33f3087f43960534a7e`.
Ảnh/index/time/checksums ở `data/raw/custom/tea_sets/video.json`.

Video đầu có tay xoay khay, giữ nguyên làm attempt cũ. Người dùng đã quay lại
cảnh tĩnh `tea_sets_2.mp4`; source SHA-256 `dda518b9a383dc97f88d53d60ee6c972e5cb13c12e1f9d9ac770a4d7335b5c9d`,
frame selection hash `d176080fa1c04478980bce19796901828019edc1bea51292b4b25bbb1a16bb5d`. Source/frame provenance
ở `data/raw/custom/tea_sets_2/video.json`.

CPU COLMAP có model 0 chỉ hai train và model 1 đủ 105 train/15 eval. Pipeline chọn
model 1, refine/convert qua pinned SDK và giữ default failed conversion trong
`.attempts`. Không ghép components/không loại eval. Mean final bundle residual
cost 0,549521 px; 16.894 sparse points. Rotation orthogonality max error
1,6234e-7; determinant [0,9999998843; 1,0000001234].

Actual visual audit đã xem [frustums](../reports/custom_capture/tea_sets_2/poses.png)
và [sparse projection](../reports/custom_capture/tea_sets_2/projections.png): camera
orbit quanh bộ trà; points bám vật thể, ghế và nền ở eval 0/7/14. Reviewer ghi
**Codex (agent visual audit)**, notes/evidence hashes trong `capture.json`; không
ký thay human research/independent replay. Native `Review-Capture -VerifyOnly`
đã PASS frozen 105 train/15 eval và tất cả review hashes.

Bốn official scenes và custom đều có successful canonical `preparation.json`.
Single-video eval đo interpolation; temporally adjacent viewpoints tương quan;
COLMAP dùng mọi viewpoint cho pose, eval pixels không train model. Đã có paired diagnostic GPU metrics trên 15 eval views (100 bước); không
kết luận full-quality từ registration ratio hoặc diagnostic budget.

## Các lỗi đã tìm bằng actual runtime

1. Processed poster JSON có UTF-8 BOM: upstream parser không đọc được. Generator
   và validator đã sửa; local processed JSON repaired có backup, raw không sửa.
2. Open3D Windows từ chối Unicode PLY path. ASCII TEMP junction trỏ repo/input
   xử lý path, không copy dataset; manifest vẫn dùng repo-relative path.
3. Splatfacto tự undistort/crop GT nhưng Nerfacto dùng distorted GT. Run thử đầu
   bị evaluator reject dimensions. Giữ failed evidence; tạo canonical common
   pinhole image grid/intrinsics/splits/points rồi train lại cả hai methods.
4. Nerfacto exporter default đòi model normals. Dùng upstream Open3D normals cho
   derived point cloud; không nhầm PLY bytes với checkpoint bytes.
5. Pinned parallel datamanager có shutdown destructor issue. Loader cleanup
   terminate/join workers, move model CPU và release CUDA sau eval/render/demo.
6. Phiên agent không elevated không áp dụng được `-lgc` (exit 4). Bổ sung safety
   gate không cho job chạy nếu thiếu quyền, không tin idle clock hoặc bypass.
7. Torch + NumPy MKL/OpenMP cùng tiến trình vẽ pose gây native exit 3. Tách
   plot worker CPU không import Torch; actual plot/audit chạy lại PASS, không
   dùng KMP_DUPLICATE_LIB_OK.
8. Re-analyze đổi gate timestamp sẽ làm selected model gate hash mất hiệu lực;
   nay giữ nguyên bytes khi evidence không đổi. Primary FPS giữ held-out path
   khi bổ sung shared demo path; regression tests PASS.

## Exact diagnostic selection

Matrices được chọn rõ:

- `artifacts/logs/matrices/poster-diagnostic.json`: Nerfacto
  `poster/nerfacto/20260930T125546831Z`; Splatfacto `poster/splatfacto/20260930T125630450Z`.
- `artifacts/logs/matrices/bonsai-diagnostic.json`: Nerfacto
  `bonsai/nerfacto/20260930T131202856Z`; Splatfacto `bonsai/splatfacto/20260930T131621149Z`.

Tất cả **100 iterations**, seed 42/downscale 2. Exact config/checkpoint/evaluation
hashes và same GT đã validator kiểm chứng. Kết quả tại
[diagnostic table](../reports/diagnostic/results.md); không dùng đánh giá winner
hoặc thay primary 30k. Poster FPS đo warm-up 3, repeats 3, synchronized GPU,
cùng held-out cameras; đây là tốc độ của model diagnostic này, không claim chung.
Các run này có trước safety policy mới; chưa chứng nhận theo policy mới, không
resume chúng vào matrix có registry khác hoặc trộn với primary results mới.

## Safety nghiệm thu và bước tiếp theo

Xem [GPU safety protocol](protocols/gpu_safety.md). Mỗi GPU job reapply 300–800 MHz,
start <65°C; watchdog 2 giây stop ≥78°C/≥80 W/≥95% VRAM/clock hoặc telemetry lỗi.
Không bảo đảm tuyệt đối phần cứng/CPU/pin; không tăng power limit hoặc reset GPU.

Managed full session (native Windows worker elevated + tmux console):

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name topic16-full -Task research -CustomScene tea_sets_2
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
# Chờ Status=paused rồi:
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
```

`Run-Research` chạy full primary poster → bonsai calibration → garden/room →
custom, eval + synchronized render + export + analysis, tuần tự. `tea_sets_2`
đã qua P3. Tmux attach/detach không stop worker. Trainer checkpoint atomic mỗi
500 bước và khi clean stop; resume restore model/optimizer/scheduler/scaler/RNG,
đúng total budget. Eval/render/export stage chưa hoàn tất chạy lại exact model;
partial FPS/metrics không được nghiệm thu. Chi tiết: [session_operations](session_operations.md).
Thiếu human replay/research review thì session ghi `awaiting-evidence`.

Static custom P3 kỹ thuật đã chuẩn bị, có agent visual evidence. Còn full paired
training/evaluation → researcher review + independent replay evidence → G-Core
→ shared demo trajectory/video → selected model health/release. `Run-Research`
đã tự nối các stage cuối khi G-Core PASS; human approvals không tự điền và phải
endorse exact `run_keys`/`settings_hash`. Local service mở riêng bằng Start-Demo.

Đã gọi thật `Run-Research -CustomScene tea_sets_2` ở session
`artifacts/logs/research/20260930T153605402Z`: custom preflight PASS, clock reapply
exit 4 nên **failed trước CUDA workload**. Session và safety reason giữ nguyên.
Đây là failed attempt lịch sử được giữ nguyên. Sau đó managed launcher đã mở
Windows Administrator worker thành công; mỗi GPU stage reapply cap thật. Runtime
positive và diagnostic stop/resume đã PASS, không còn block quyền này.

## Validation log locations

- `artifacts/logs/validation/project-20260930.log`: actual Windows parser/tests.
- `artifacts/logs/validation/gpu-safety-block-20260930.log`: expected permission failure.
- `artifacts/logs/validation/video-extraction-20260930.log`: native FFmpeg extraction.
- `artifacts/logs/validation/artifact-audit-20260930.log`: exact bonsai config/checkpoint/eval audit.
- `artifacts/logs/validation/tea2-{extraction,capture,recovery,pose-review,approval,audit}-20260930.log`: static video và CPU SfM/pose evidence.
- `artifacts/logs/validation/canonical-remaining-20260930.log`: garden/room CPU preparation.
- `artifacts/logs/validation/research-safety-stop-20260930.log`: actual ordered-session custom preflight + fail-closed clock stop.
- `artifacts/logs/safety/`: safety lifecycle/policy/reason records.

CPU unit/fixture tests verify contracts and stop logic; GPU diagnostic evidence
verify real integration. Neither replaces remaining full training/pose/human gates.

## Managed-session nghiệm thu thực tế

- `topic16-runtime-check`: Windows Administrator worker, clock reapply/CUDA/import/
  native CLIs PASS. Driver 597.06 WDDM trả `power.limit=N/A`; query chuyển sang
  `enforced.power.limit` (85 W), giữ stop policy 80 W và fail-closed telemetry.
- `topic16-resume-nerf`: poster diagnostic 1.000 bước; clean stop checkpoint 734,
  segment mới restore 735 → final 999. Exact ancestor/hash/safety audit PASS.
- `topic16-resume-splat`: clean stop 634 sau refinement, restore 635 → final 999;
  optimizer rebind live Gaussian Parameters, scheduler/scaler và ancestry audit PASS.
- Tmux interactive attach + Ctrl+B,D detach đã thực hiện; native worker vẫn chạy.
- `topic16-custom-verified`: `custom:tea_sets_2`, 100 bước mỗi method; Stop sau
  một camera đã render trong eval, Resume cùng Nerfacto config, complete cả pair.
  15 held-out cameras/method, identical GT/frozen split và completed safety PASS.
  Runs: `custom-tea_sets_2/nerfacto/20260930T163635661Z` và
  `custom-tea_sets_2/splatfacto/20260930T164151196Z`.
  [Actual diagnostic results](../reports/custom_diagnostic/results.md): Nerfacto
  PSNR 18,9146 / SSIM 0,6124 / LPIPS 0,6687; Splatfacto
  18,2013 / 0,6428 / 0,6950. Budget nhỏ không dùng chọn winner.
- Splat eval từng failed vì FullImageDatamanager dataloader là readonly property;
  adapter dùng public SDK averaging API với stoppable iterator. Failed attempt
  `topic16-custom-check` được giữ, pair acceptance dùng `topic16-custom-verified`.
- CPU final QA: 38 PS parsed, 19 fixture successes, 69 Python tests PASS;
  readonly loader, cooperative pause, budget/tamper/ancestry-cycle tests included.
  Analyzer vẫn SKIPPED, remote CI/independent replay chưa có evidence.

Logs từng managed task: `artifacts/logs/sessions/<name>/console.log`; matrix custom
ở `artifacts/logs/matrices/topic16-custom-verified.json`. Final native QA và resumed
artifact audits ở `artifacts/logs/validation/session-{project,audit}-20260930.log`.
Full 30k session có lifecycle/progress riêng; không đóng G-Core bằng diagnostics.

Render acceptance `topic16-render-check`: Stop trong GPU measurement → paused,
Resume archive attempt cũ và render đủ 15 camera từ exact custom Nerfacto model;
`render.json` completed, partial durations excluded. Export acceptance `topic16-export-check`: owned child stopped → paused; Resume
archive output dở, load lại exact custom Splatfacto checkpoint và export PLY PASS.

Full primary đã launch: `topic16-full`, native Administrator worker,
`artifacts/logs/sessions/topic16-full/{state.json,console.log}` và
`artifacts/logs/research/topic16-full/session.json`. Bắt đầu 2026-09-30
17:01:52 UTC (2026-10-01 00:01:52 GMT+7). Đây là phiên dài đang thực thi;
chỉ final artifact/session state mới chứng nhận hoàn tất. Stop/Status/Resume
và tmux attach xem [session_operations](session_operations.md).

Full preflight thực tế PASS: 38 PS parsers, 19 fixture successes, 69 Python tests,
elevated host/runtime/CUDA và bốn official dataset validators. Training chính
đã vào `poster/nerfacto/20260930T170359134Z`, target 30.000; đã vượt 1.000 bước
và commit checkpoint 500/1.000. Actual full tmux attach/detach PASS, worker vẫn
chạy. Mẫu quan sát 63°C/795 MHz/47,50 W/5.044 MiB; đây là sample, không chứng nhận
phần còn lại của run. Snapshot source hiện tại khớp source manifest của run.
Evidence: `artifacts/logs/validation/session-full-started-20260930.json`.

## User-requested overnight pause — 2026-10-01

`topic16-full` đã **paused** theo yêu cầu, worker exited. Poster primary pair
complete; Nerfacto/bonsai dừng ở checkpoint step 16.998/target 30.000, file
176.077.054 bytes, SHA-256 verified. Safety succeeded + job_outcome paused;
GPU sau cleanup 53°C/300 MHz/17,89 W/650 MiB. Resume next step 16.999,
remaining 13.001 iterations. Full session chưa complete; trạng thái hiện tại
là paused, thay cho các quan sát running trước đó. Lệnh hardcap/resume/attach
đầu [session_operations](session_operations.md). Evidence:
`artifacts/logs/validation/session-user-pause-20261001.json`.
