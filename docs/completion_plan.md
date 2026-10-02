# Kế hoạch hoàn thiện và nghiệm thu A–Z

Ngày audit: 2026-09-30. Giữ native Windows PowerShell và runtime đã pin;
không thay model engine, không xóa raw data hoặc artifacts cũ.

Cập nhật 2026-10-02: full primary train/eval/render/export đã complete. Hồ sơ
[research review](../reports/topic16-full/review/research_review.md) có phân tích
định lượng/định tính và audit Python sạch; [replay runbook](../reports/topic16-full/review/replay_runbook.md)
ghi rõ phần GPU replay và human approvals chưa thực hiện. Các trạng thái launch/
pause bên dưới là lịch sử, không thay trạng thái hiện tại `awaiting-evidence`.

| Bước | Thay đổi | Kiểm chứng trước bước sau |
|---|---|---|
| 1 / P0–P2 | Audit Member 1, runtime, checksum archive, từng ảnh và sparse files | Host/runtime thật + dataset validator + negative fixtures |
| Safety / mọi GPU stage | Reapply 300–800 MHz; watchdog nhiệt/công suất/VRAM; owned-process stop | Administrator success, fail-closed permission/telemetry/threshold tests |
| 2 / P3 | Capture validation, registration report, immutable split/hash, visual review | Duplicate/corrupt/missing/partial-output rejected; ≥90% train register; duyệt pose |
| Video / P3 | Extract tea_sets_2, CPU COLMAP component selection, canonical và pose evidence | 105 train/15 eval; 120/120 registered; agent visual audit và frozen hashes PASS |
| 3 / P4 | Trainer lifecycle, exact artifact return, protocol label, GPU lock/provenance | Failed attempt giữ log; posterior config/checkpoint; hai methods train thật |
| 4 / P5 | Exact checkpoint eval, held-out identities/GT/pred, synchronized FPS, render/export | Leakage/nonfinite/hash/count rejected; GPU eval và export thật |
| 5 / P6 | Sequential paired matrix + explicit resume manifest | Half-pair/mixed protocol rejected; resume không chọn latest; bonsai calibration |
| 6 / P7 | Artifact validation, deterministic tables/plots/crops, evidence gate | Ba benchmark pairs + custom + poster, fresh-machine replay và reviews |
| 7 / P8–P9 | Selected model checksum manifest, serial viewer/render demo, release provenance | G-Core required at activation; missing/tampered model fails; offline fallback |
| 8 / P10 | Parser, integration/negative tests, CLI contracts, documentation consistency | CPU checks + actual GPU smoke; remaining unverified gates recorded honestly |

Theo yêu cầu hoàn thiện toàn bộ code của chủ repo, adapter demo được chuẩn bị
cùng research core; kích hoạt/release vẫn bắt buộc G-Core. Không đánh dấu GPU,
full custom GPU quality, human research review hay clean-machine replay PASS bằng mock test.

Cấu trúc mục tiêu: `configs/`, `scripts/` (entrypoints), `src/topic16/` (logic),
`tests/`, `docs/`, `reports/`, và ba nơi chứa dữ liệu lớn `data/`, `artifacts/`,
`third_party/`. Không tạo `production/app/scripts/tests` riêng; dùng cùng package
và scripts. Xóa duy nhất placeholder không có người tiêu thụ; giữ các ranh giới
raw/processed và run/log/metric vì chúng bảo vệ tính tái lập.

Kết quả nghiệm thu thực tế nằm trong `docs/implementation_status.md`; kế hoạch
không thay thế bằng chứng chạy. Chỉ dữ liệu được đo mới được đưa vào báo cáo.

## Trạng thái cuối lượt integration

- P0–P10 code/interfaces đã nối; minimal single package/shared helpers.
- CPU QA native Windows: 38 PowerShell parsers, 19 fixture successes và 69 Python
  tests PASS; PSScriptAnalyzer chưa có nên SKIPPED.
- Official data đủ, cả bốn canonical scenes đã prepare thành công. Custom chính
  tea_sets_2 đã extracted/mapped/canonical/frozen/reviewed bởi agent có evidence.
- Actual diagnostics: poster và bonsai paired 100 steps, held-out GT identical;
  poster synchronized FPS và PLY exports. Không thay primary 30k.
- Elevated managed worker runtime/safety PASS; tmux attach/detach thật PASS.
- Trainer Stop/Resume thật cả hai methods: 1.000 tổng bước, resume 734/634 → 999;
  optimizer/scheduler/scaler/RNG và checkpoint ancestry audit PASS.
- Static custom paired 100 bước + 15 eval cameras/method PASS; Stop giữa eval rồi
  Resume exact model PASS. Partial inference không được nhập vào metric/FPS.
- Managed full session chạy 10 primary training runs (5 scenes × 2 methods)
  + eval/render/export → human research/independent replay
  → G-Core → demo health/video/release positive. Không đánh dấu các gates này
  hoàn tất bằng code hoặc unit tests.

`Run-Research -Resume` giữ exact session/matrix/config, reuse complete artifacts;
review endorse exact run_keys/settings_hash. Khi G-Core PASS, workflow tiếp tục
shared demo rendering → explicit model selection → health check → release;
release cần exact-model health/safety evidence; local service có lệnh riêng để không giữ pipeline trong HTTP loop.

## Vận hành xuyên sessions

[session_operations](session_operations.md) là runbook Stop → paused → Resume và
attach/detach. Native Windows worker giữ CUDA/Conda/GPU guard; tmux WSL chỉ xem
log. Checkpoint interval 500, requested stop checkpoint sau completed iteration;
resume dùng remaining budget, không thêm 30k vào số bước đã chạy. Giữ source/
registry/runtime/frozen cameras ổn định; prior safety failures giữ evidence.
Full research tự đi đến analysis và chờ human gate khi thiếu review/replay thật.

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
