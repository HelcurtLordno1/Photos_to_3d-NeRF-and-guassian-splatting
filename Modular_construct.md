# Stages và acceptance gates — Topic 16

Kế hoạch A–Z: [completion_plan](docs/completion_plan.md). Evidence cập nhật:
[implementation_status](docs/implementation_status.md). Interface thực:
[Construction_architect](Construction_architect.md). Lệnh: [runbook](setup_full_command.md).

`IMPLEMENTED` = có code và contract tests. `ACCEPTED` = đủ DoD + actual evidence.
Không dùng checkbox code để khẳng định GPU, custom pose hay research gate đã PASS.

## Dependency và trạng thái

| Stage | Interface / files chính | DoD và bằng chứng bắt buộc |
|---|---|---|
| P0 Runtime | setup/check/test runtime + registry | CUDA/import/native CLIs đúng pin; host negative tests |
| Safety xuyên stage | Check-GpuSafety + `safety.py` | reapply 300–800 MHz; cool start; thermal/power/VRAM watchdog; Administrator positive check |
| P1 Contracts | schema, atomic writer, `contracts.py` | key/schema/lifecycle/hash/path invariants; negative fixtures |
| P2 Data | download/test datasets | source/checksum/count/image/pose PASS; không download lại dữ liệu hợp lệ |
| P3 Input chung | Process/Review/Approve/Prepare-Scene + `data.py` | canonical pinhole + frozen split; custom registration và visual review |
| P4 Train | Train + `runtime.py`/`training_worker.py` | exact config/final checkpoint, provenance, succeeded/failed, telemetry; actual poster full pair |
| P5 Eval/render/export | Evaluate/Render/Export | cùng held-out GT/camera, finite metrics, checksum/count; synchronized throughput và PLY |
| P6 Pair orchestration | Run-Benchmark + `experiments.py` | same protocol/data/hardware; sequential; explicit matrix resume; calibration rồi 6 benchmark runs |
| P7 Analysis | Analyze-Results + `analysis.py` | deterministic tables/crops/figures, primary/diagnostic/repeat separation, evidence G-Core |
| P8 Adapter | Select-Model/Start-Demo + `demo.py` | exact model/gate hashes, CUDA warm-up/health, bounded local serial requests, determinism |
| P9 Release | Write-Release + report template | same camera video fallback, source/dependency/data/model hashes, independent runbook replay |
| P10 QA | Test-Project + tests + Windows CI | parser/contract/negative/integration + explicit runtime/analyzer/GPU results |

Dependency: P0/P1 → P2 → P3 → P4 → P5 → P6 → P7 → activation P8 → P9.
P10 kiểm tra xuyên suốt. P3 canonical preparation áp dụng cả official scenes;
phone capture chỉ cần cho custom branch, không chặn development official branch.

## Checklist code đã nối

- [x] Registry-only pins, no activated shell, native Windows entrypoints.
- [x] Strict P1 writer được gọi từ trainer lifecycle; config/checkpoint/split/settings hashes.
- [x] Raw/processed/artifact boundaries; Unicode junction cho native Open3D.
- [x] Shared undistortion/crop/intrinsics/split, GT equality giữa methods.
- [x] Registration report, corruption/duplicate checks, recorded visual review command.
- [x] Exact returned config; no latest selection; GPU OS lock + sampled monitor cleanup.
- [x] Per-job clock reapply, fail-closed watchdog, owned-process emergency stop và safety provenance.
- [x] Video timestamps/frame hashes, deterministic train/eval extraction và contact sheet.
- [x] Eval giữ upstream metric implementation; required finite values + camera/count/checksum guards.
- [x] Renderer warm-up/synchronize/repeats; checkpoint bytes riêng derived export bytes.
- [x] Paired matrix, atomic checkpoint + optimizer/scheduler/RNG resume đúng total budget.
- [x] Managed native worker + tmux attach/detach; cooperative stop từng camera/stage.
- [x] Primary/diagnostic/repeat reports, same-camera crops, gate computed from artifacts.
- [x] Selected immutable model + local serial demo + release manifest.
- [x] Windows parser, negative/integration fixtures và CI definition.

## G-Core: không tự điền PASS

Gate machine-readable ở `reports/<selection>/g-core.json`:

1. Poster **primary full pair** train + held-out eval.
2. Bonsai **primary calibration pair** không OOM, complete artifacts.
3. Đủ garden/bonsai/room × nerfacto/splatfacto primary runs.
4. Custom capture approved, frozen split và primary paired eval.
5. Không leakage/nonfinite/half-pair/missing provenance hay modified artifacts;
   có paired held-out FPS và cả hai exports dưới đúng safety policy.
6. Independent clean-machine replay có reviewer, notes và evidence files.
7. Research review có evidence: cùng camera/crop, limitations, failure analysis.

Diagnostic report luôn `BLOCKED` và không được dùng kích hoạt demo/release.
`tea_sets_2` đã có 120/120 pose trong một connected model, canonical data và agent
visual audit có evidence hashes, paired GPU diagnostic 100 bước PASS.
Administrator runtime/safety positive và trainer stop/resume 1.000 bước PASS.
Full primary hiện đã có 10 completed runs và eval/render/export (2026-10-02).
[Phân tích nghiên cứu](reports/topic16-full/review/research_review.md) và
same-host clean-Python artifact audit đã chuẩn bị; human research/replay approvals
vẫn cần xác nhận và evidence thực tế, không suy từ CPU audit.
Thông tin máy mới có thể chỉ xác nhận CPU/setup thì ghi rõ; không coi đó là
full GPU replay. Full training 30k cần chạy thật, không suy memory từ 100 iterations.

## Nghiệm thu theo stage

```powershell
.\scripts\Test-Project.ps1
.\scripts\Check-GpuSafety.ps1  # Administrator, trước mọi GPU nghiệm thu
.\scripts\Check-Environment.ps1 -RequireRuntime
.\scripts\Test-Datasets.ps1 -Mode all -WriteManifest
.\scripts\Run-Benchmark.ps1 -Scenes poster -MatrixPath .\artifacts\logs\matrices\poster-primary.json
.\scripts\Run-Benchmark.ps1 -Scenes bonsai -MatrixPath .\artifacts\logs\matrices\bonsai-primary.json
# Or run the full ordered research session:
.\scripts\Run-Research.ps1 -CustomScene tea_sets_2
```

`Test-Project -RequireAnalyzer` fail nếu analyzer chưa có; không âm thầm báo lint PASS.
`-PythonExecutable python` dùng cho máy CPU/CI. GPU nghiệm thu thuộc A4500;
CPU/6 GB chỉ ký các test thực sự chạy trên máy đó.
