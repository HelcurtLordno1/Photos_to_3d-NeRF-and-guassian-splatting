# Sessions: tmux console, native Windows worker, checkpoint stop/resume

User-requested tmux bridge (2026-09-30). Public entrypoint remains native
`scripts/Manage-Session.ps1`. CUDA/Conda/COLMAP run on Windows; WSL/tmux is a
read-only log console. No second Linux CUDA environment and no Bash pipeline.

## Chạy tiếp sau khi cất máy / reboot (phiên topic16-full)

### Trạng thái hiện tại — 2026-10-02

Phiên `topic16-full` đã hoàn tất **10/10 train/eval và toàn bộ render/export**,
worker đã thoát, state `awaiting-evidence`. Không cần Resume để train lại. G-Core
còn thiếu human research approval và independent clean-machine GPU replay.
Báo cáo phân tích, 14 camera cases từ 115 held-out views và clean-Python artifact
audit ở [research review](../reports/topic16-full/review/research_review.md).
[Replay runbook](../reports/topic16-full/review/replay_runbook.md) phân biệt kiểm
tra artifact, Conda mới cùng máy và replay trên máy khác; CPU audit không đóng
gate GPU. Endorsement hiện tại chỉ là `review.pending.json`, cả hai approval false.

Lệnh read-only để xem state:

```powershell
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
```

Không tự Resume bằng pending endorsement để mong vượt gate; chỉ Resume với
actual endorsed evidence khi muốn pipeline tiếp tục sang demo/release.

### Lịch sử khắc phục lỗi render ngày 2026-10-02

Đã hoàn tất **10/10 run primary train + evaluate**, gồm cả hai methods của
`tea_sets_2`. Phiên dừng ở render `room/nerfacto/20261001T071118206Z`, sau khi
render/export poster, bonsai và garden đã complete. Không cần train lại.

Lỗi `Installed dependencies differ from this exact trained model` là lỗi
snapshot phụ thuộc thứ tự import: setuptools thêm `setuptools/_vendor` vào
`sys.path`, khiến metadata xuất hiện thêm 12 distributions trong snapshots của
room dù môi trường không đổi. Runtime snapshot mới tách packages được cài khỏi
metadata đi kèm setuptools. Loader vẫn kiểm tra đúng SHA-256 snapshot đã lưu,
hoặc đúng inventory legacy gồm toàn bộ vendor metadata của cùng bản setuptools;
không bỏ qua thay đổi package/version thực sự và không sửa provenance/checkpoint
cũ. Evidence: `artifacts/logs/validation/runtime-snapshot-fix-20261002.json`.

Lần Resume khắc phục lỗi đã verify/reuse matrices train/evaluate, hoàn tất
render/export room và bộ trà rồi analysis. Pipeline đã kết thúc ở
`awaiting-evidence`, không tự ký G-Core PASS. Khối Resume bên dưới giữ làm runbook
cho pause/lỗi trong tương lai; nó không chứng nhận approval nghiên cứu.

### Lần pause checkpoint trước đó (lịch sử ngày 2026-10-01)

Lần dừng mới nhất theo yêu cầu: **2026-10-01 lúc 16:55:30 (UTC+7)**.
`topic16-full` đã chuyển sang **paused**, worker PID 6048 đã thoát.
Checkpoint **Nerfacto / custom:tea_sets_2**, run
`custom-tea_sets_2/nerfacto/20261001T091714741Z`, đã commit ở step **24.347**.
Resume bắt đầu từ **24.348**, còn **5.652 iterations** để đạt tổng 30.000.
Step đánh số từ 0: checkpoint này đã hoàn tất 24.348 iterations (~81,16%).

| Phần việc | Trạng thái khi dừng |
|---|---|
| Poster, bonsai, garden, room × hai methods | Đủ **8/8 run primary train + evaluate**, đã complete và sẽ được verify/reuse |
| Bộ trà — Nerfacto | Paused ở checkpoint `step-000024347.ckpt`; tiếp tục số bước còn lại rồi evaluate |
| Bộ trà — Splatfacto | Chưa train primary; sẽ train 30k và evaluate sau Nerfacto |
| Render / export / analysis | Chạy sau khi đủ các paired matrices; completed artifacts được verify/reuse |
| Demo / release | Vẫn cần actual G-Core PASS và review evidence |

Checkpoint lưu model, optimizers, schedulers, scaler, RNG và sampler/strategy
state; resume record và custom matrix đã giữ đúng config của run đang dừng.
Evidence kiểm tra checkpoint/config SHA-256, đọc checkpoint trên CPU, source và
runtime snapshot ở
`artifacts/logs/validation/session-user-pause-20261001T095530Z.json`.
Evidence lần dừng bonsai trước đó vẫn giữ tại
`artifacts/logs/validation/session-user-pause-20261001.json`.

### Lệnh Resume / Attach cho phiên đã lưu

Mở **Windows PowerShell → Run as administrator**, rồi chạy lần lượt:

```powershell
Set-Location -LiteralPath 'D:\Desktop_informations\SGK năm 4\SGK kì 1 năm 4\ComputerVision - MToan\CVCourse\Project\Topic_16_CV'
Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = 'Stop'

# Khóa xung lại sau khi mở máy; cả hai lệnh phải chạy thành công.
nvidia-smi -i 0 -lgc 300,800
if ($LASTEXITCODE -ne 0) { throw 'Không khóa được xung GPU; dừng trước khi Resume.' }
nvidia-smi -i 0 -q -d POWER,CLOCK,TEMPERATURE
if ($LASTEXITCODE -ne 0) { throw 'Không đọc được trạng thái GPU; dừng trước khi Resume.' }

# Dùng đúng Conda executable của phiên đã lưu, không cần activate.
$sessionHost = Get-Content -LiteralPath '.\artifacts\logs\sessions\topic16-full\host.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$env:TOPIC16_CONDA_EXE = $sessionHost.conda
if ($sessionHost.cuda_path) { $env:CUDA_PATH = $sessionHost.cuda_path }
.\scripts\Check-GpuSafety.ps1
# Chỉ tiếp tục nếu Check-GpuSafety PASS.
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
```

Resume sẽ tự tạo lại tmux console nếu WSL đã tắt/reboot. Không dùng Start cho
phiên này. Preflight chạy lại trước training; nó verify/reuse completed stages,
restore committed trainer checkpoint và tiếp tục toàn pipeline tuần tự.
Giữ source/config/runtime/dataset/checkpoint đúng snapshot để resume được.
Lệnh không cần thêm `-Task`, `-CustomScene`, `-Iterations` hoặc `-ConfigPath`:
job và matrices đã lưu đầy đủ lựa chọn của phiên. Run segment sau resume có ID
mới và tham chiếu checkpoint cha; đó là tiếp tục training, không phải học lại từ 0.
Trong lần tiếp tục checkpoint ngày 2026-10-01, log có
`Resume loaded model/optimizer/scheduler/scaler/RNG at step 24347; target 30000`.
Hiện training đã complete, lần resume sau lỗi render sẽ không cần restore
trainer hay tạo training segment mới. Các scene đã complete không bị train lại.

Giữ nguyên `data/`, `artifacts/`, `src/`, `scripts/`, `configs/` và Conda runtime
trước lần resume này. Không reset repository, xóa checkpoint/log/matrix hoặc
update dependency/driver giữa hai segment. Cập nhật tài liệu này không đổi source
snapshot được kiểm tra khi resume. Junction trong Windows TEMP chỉ là alias đến
repo gốc và được tạo lại khi cần; không phải bản sao duy nhất của checkpoint.

Nếu đang trong **WSL**, attach bằng:

```text
tmux attach -t topic16-full
```

**Ctrl+B rồi D** detach; worker vẫn chạy. Khi cần cất máy lần nữa:

```powershell
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
```

Đợi **paused** trước khi shutdown/cất máy. Lệnh Resume khôi phục training;
tmux attach mở console. Không chạy Resume lúc worker vẫn active.
Exit code **75** và thông báo lỗi chung của Conda trong log lần dừng này là
cooperative pause đã xác nhận, không phải mất checkpoint.

## One full session

At the repo in PowerShell (Administrator avoids a UAC prompt on worker launch):

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name topic16-full -Task research -CustomScene tea_sets_2
.\scripts\Manage-Session.ps1 -Action Attach -Name topic16-full
```

From WSL, attach directly:

```text
tmux attach -t topic16-full
```

Detach with **Ctrl+B, then D**. Detach closes the console client; training
continues. Closing/killing the tmux pane does not request a training stop.
The Windows worker owns the job and survives a disconnected console/Codex turn.
Do not close its minimized PowerShell window or kill CUDA processes to pause.

```powershell
.\scripts\Manage-Session.ps1 -Action Status -Name topic16-full
.\scripts\Manage-Session.ps1 -Action Stop -Name topic16-full
# Wait until Status reports paused; it must finish the current safe boundary.
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full
```

Start refuses an existing name. Resume uses saved job/scene/protocol/registry;
no need to retype them. Completed sessions are reused, not trained again.
A worker OS handle prevents concurrent owners of one session; the GPU lock
prevents concurrent CUDA work across sessions. Do not start simultaneous jobs
and expect them to queue: the second job fails clearly and can be resumed later.

Worker logs/state at `artifacts/logs/sessions/<name>/`:
`job.json`, `settings.json`, `host.json`, `state.json`, `console.log`,
`active-run.json`, `stop.json`, `worker.lock`. `host.json` records the discovered
Conda path because elevated processes do not inherit the initiating shell's
Conda PATH. `worker.lock`/GPU lock handles are released on process exit.
These files are operational state, not a replacement for immutable run evidence.

## Stop and resume semantics

| Operation | Stop | Resume |
|---|---|---|
| Training | Next completed iteration saves atomically, exits and releases GPU | Explicit committed checkpoint; model + optimizer + scheduler + scaler + RNG, same total budget |
| Training's whole-image eval | Stop between cameras, save the completed training step | Same training checkpoint |
| Held-out eval | Stop between cameras; failed/partial metrics stay excluded | Same completed model; rerun the incomplete evaluation stage |
| Timed render | Stop between frames | Archive the interrupted attempt, rerun the full timed measurement; partial timing is never FPS evidence |
| Export | Terminate the owned read-only export child tree | Archive interrupted output and export again from the same model |
| Local demo | Stop request closes the local server; cleanup releases GPU | Reload the selected model and rerun startup checks |
| Completed stages | Retain exact hashes/configs | Verify and reuse |

Checkpoint interval: 500 completed iterations, pinned in `configs/project.psd1`.
A requested stop also saves immediately at the next completed iteration.
Atomic `.tmp` → `.ckpt` → `resume.json` commit precedes deletion of older
checkpoints in that attempt. Failed/completed P1 manifests remain immutable;
a resumed segment has a new run key and explicit hashed ancestor evidence.

Pinned upstream loops `start_step .. start_step + max_num_iterations`; the
adapter reduces only the live loop's remaining count and keeps `config.yml`'s
total budget unchanged. Splatfacto replaces Gaussian Parameters while loading:
optimizers are reconstructed after the model is loaded/resized, then optimizer,
scheduler and scaler states are restored and live parameter bindings checked.
The checkpoint also stores RNG, full-image camera sampler and gsplat strategy
accumulators. No upstream checkout is patched.

Resume requires identical source files, registry, runtime, frozen split and GPU/
driver identity. Preserve the exact source snapshot before editing an active run.
Periodic checkpoints limit lost work after an unexpected process failure, but
power loss/kill/safety stops require evidence inspection; clean cooperative stop
is the supported automatic resume path. Do not treat a corrupt/missing snapshot
as reusable. Resume does not guarantee bit-identical future minibatches across
multiprocessing/CUDA workers. Training time includes active segments/reloads,
excludes the time spent paused; VRAM uses maximum sampled segment values. Report
interruptions when comparing speed against uninterrupted runs.

Exit 75 denotes a cooperative pause. Conda may print its generic “command failed”
message for this exit; `state.json=paused`, committed resume record and successful
safety record distinguish it from a failed or unsafe job. Do not raise safety
thresholds or bypass clock reapply to resume.

## Other tasks and review

```powershell
.\scripts\Manage-Session.ps1 -Action Start -Name custom-smoke -Task benchmark `
    -Scenes 'custom:tea_sets_2' -Protocol diagnostic -Iterations 100
.\scripts\Manage-Session.ps1 -Action Start -Name single-train -Task train `
    -Method nerfacto -Dataset poster -Protocol primary
.\scripts\Manage-Session.ps1 -Action Start -Name render-check -Task inference `
    -Operation render -ConfigPath <exact-config.yml>
.\scripts\Manage-Session.ps1 -Action Start -Name runtime-check -Task runtime
.\scripts\Manage-Session.ps1 -Action Start -Name local-demo -Task demo -ModelPath .\reports\model.json
```

The full research worker ends `awaiting-evidence` if human reviews are missing.
After actual review/replay, endorse its exact run_keys/settings_hash and resume:

```powershell
.\scripts\Manage-Session.ps1 -Action Resume -Name topic16-full -ReviewPath .\reports\review.json
```

GPU policy still re-applies 300–800 MHz for every job, starts below 65°C and
stops on temperature/power/VRAM/clock/telemetry violations. WDDM driver 597.06
returns N/A for requested `power.limit`; the watchdog queries live
`enforced.power.limit` (85 W observed), preserving the conservative 80 W stop
policy. It does not ignore missing telemetry.

## Actual acceptance

- Elevated worker runtime/CUDA/native CLI checks PASS under re-applied clock cap.
- Tmux attach and Ctrl+B,D detach exercised; Windows worker is independent.
- Nerfacto: stop at step 734, resume at 735, complete at 999 (1,000 total).
- Splatfacto: stop at 634 after refinement starts, resume at 635, complete at 999;
  optimizer live-parameter bindings, schedulers/scaler restoration PASS.
- Static custom evaluation: stop after a rendered camera; resume same training
  config; final paired acceptance recorded in implementation_status.
- Full 30k matrix is a separate live run; diagnostics do not certify full memory
  or research/demo/release quality. Artifact/safety logs record actual outcomes.

Tmux commands: [official getting-started guide](https://github.com/tmux/tmux/wiki/Getting-Started).
Power telemetry semantics: [NVIDIA System Management Interface](https://docs.nvidia.com/deploy/nvidia-smi/index.html).

Render acceptance `topic16-render-check`: Stop trong GPU measurement → paused,
Resume archive attempt cũ và render đủ 15 camera từ exact custom Nerfacto model;
`render.json` completed, partial durations excluded. Export acceptance `topic16-export-check`: owned child stopped → paused; Resume
archive output dở, load lại exact custom Splatfacto checkpoint và export PLY PASS.
