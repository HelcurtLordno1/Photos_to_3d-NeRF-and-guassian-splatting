# Teacher-first research plan — Room Nerfacto diagnosis, then Gaussian delivery

Updated 2026-11-12. This is the current execution plan, authorized by the user.
The teacher assignment takes priority over all pending visual-quality upgrades.
Previous plans and evidence remain immutable; the preceding master plan is saved
at `upgrade/reports/plans/upgrade_to_baseline-before-teacher-room-20261112.md`.
`docs/plans/final-quality-campaign.md` remains the frozen Gaussian protocol, now
subordinate to the Room diagnostic/report gate in this document.

## 1. Problem, evidence and hypotheses

The original academic DOCX reports Room Nerfacto PSNR 22.9068 dB. Its saved
configuration enables camera optimizer SO3xR3 and 32-dimensional appearance
conditioning, evaluated with the mean training embedding. Room Splatfacto turns
camera optimization off. These are confirmed settings, not proof of causality.
The teacher requests fresh Room A/B/C runs; no warm-start from any old checkpoint.
A result around 29–31 dB for C is a hypothesis, never a tuning target or a
permission to alter the frozen test, silently change methods, or conceal losses.

The primary question is whether camera refinement and/or appearance conditioning
explain the low Nerfacto score. New Gaussian improvements, UI polishing,4K/8K
outputs and other scenes cannot answer it and must wait for its report.

## 2. Scheduling and preserved work

1. Cooperatively pause `topic16-final-quality-v1`; verify state=paused and retain
   Bonsai checkpoint13790/30000, optimizer/sampler/RNG and all existing attempts.
   Tea replication, capacity selection and delivery evidence are reused, not rerun.
2. CPU audit baseline Room contracts and freeze the diagnostic declaration,
   source archive, exact input hashes, config recipe, runtime and safety identity.
3. Preflight all A/B/C configs and parser outputs before the first long run.
   All three real GPU integration checks must also pass: fresh model, two TRAIN
   updates, save/reload the exact checkpoint, finite TRAIN-camera inference.
   QA is excluded from quality tables. Freeze only the tested source/settings.
4. Sequential A train30k -> A exact-checkpoint eval39 -> common CPU evaluation;
   then B completely, then C completely. No concurrent GPU jobs or manual coding
   between arms. Save partial tables as each arm completes.
5. Finish the teacher report/table/gallery/evidence manifest. Only a complete,
   integrity-valid matrix/report unlocks the queued Gaussian work. A low score
   remains a valid negative result; it is not silently treated as a diagnosis
   solved. Unresolved causes and further checks are prominently reported.
6. Resume the already declared Gaussian final campaign from its saved Bonsai
   state, then Room -> Garden -> Poster. Preserve its original source pins,
   chosen Tea model, model budgets and dataset-first acceptance gates. No new
   NeRF sweep is propagated to these scenes, and no completed Tea arm is repeated.
7. Complete the final UI acceptance using the existing delivery machinery.

One new managed session owns this entire sequence:
`topic16-teacher-room-v1`. Older sessions stay paused and must not be resumed in
parallel. No automatic retries change scientific settings. Integrity/resource
failures pause the queue, retain evidence and require debugging before Resume.
The old campaign remains recoverable independently if subsequent priorities change.

## 3. Frozen Room experiment

|Run|Camera optimizer|Appearance during train|Appearance at test|Initialization|
|---|---|---|---|---|
|Historical reference|SO3xR3|32-dimensional embedding|Average|Existing untouched30k run|
|A|Off|32-dimensional embedding|Average|Fresh, no checkpoint/config warm-start|
|B|SO3xR3|Disabled|No embedding|Fresh, no checkpoint/config warm-start|
|C|Off|Disabled|No embedding|Fresh, no checkpoint/config warm-start|

All new runs clone the **saved original Room Nerfacto configuration**, not the
latest library defaults. Keep30,000 iterations, seed42, batch4096, network,
proposal sampling, optimizer/LR schedules, initial density, losses, background,
mixed precision and dataparser normalization unchanged. Seed equality does not
promise bitwise CUDA training. Only the declared model toggles differ. Operational
changes are output/run identities, relocation of identical inputs, four CPU
image-loading threads and persistence/audit hooks; serialize their exact diff.
Keep the original single loader process and500-step checkpoint interval.

Use all272 train/39 test views, downscale2,1557x1037 output, original explicit
split/poses/intrinsics/distortion and canonical pixels. Do not rerun COLMAP,
resize again, change the split to match a paper, or write inside baseline data.
Verify all input hashes; instantiate both parser splits and compare every camera
and filename to the frozen baseline before training. Initial live model checks
must verify optimizer mode, actual absence/presence of field embedding, camera
parameter groups, start_step=0 and all load_* paths empty.

**Important:** `use_average_appearance_embedding=False` means zero embedding at
inference; it does not remove conditioning. B/C use
`use_appearance_embedding=False` from model creation and train from scratch.
Use the primary held-out protocol without per-test-image fitting. A later test-time
appearance optimization experiment needs its own frozen calibration/scoring pixel
split and must not be pooled with ordinary unseen-image evaluation.

## 4. Comparison validity and diagnosis

Audit baseline config/checkpoint/evaluation and runtime fingerprints. The old
on/average point remains a historical reference; A–C are a current controlled
set. Report C−B (camera intervention with embedding off) and C−A (appearance
intervention with camera off). Do not claim an unbiased full2x2 interaction from
a historical fourth cell. If runtime/protocol differences prevent a firm
historical comparison, explicitly request/declare a fresh on/average control as
a separate follow-up; never add it secretly or resume the old weights.

Primary evidence: all39 saved RGB predictions + byte-identical GT, one CPU
PSNR/SSIM/AlexNet-LPIPS evaluator for both historical methods and A/B/C, per-view
scores/deltas, unrounded aggregates and actual metric/runtime versions. Retain
original float/native metrics separately; RGB8 common PSNR is not numerically
identical to float PSNR. No color correction or test exposure fitting.

Record actual final step29999, config/checkpoint/source/runtime hashes, live
initialization proof, learned camera correction norms, train time, sampled device
VRAM, safety logs, all interrupted attempts and exact commands. Validate all
image dimensions and image counts before reporting. Recompute and hash cached
metric inputs before reuse; valid empty Git diagnostics are allowed and hashed.

Produce incremental results after each arm; the final report includes:
- A/B/C and both historical methods, native and common metrics, time and VRAM;
- per-view CSV, camera/appearance conditional effects, model/pipeline provenance;
- gallery of all39 matched views and error maps, with full-resolution links;
- whether the teacher hypothesis is supported and what remains unexplained;
- differences from literature (implementation, split, image size and budget),
  without claiming29–31dB is guaranteed or a reproduction of another NeRF method.

If C is still low: preserve that finding and prioritize a separately frozen
follow-up audit of camera/GT alignment, normalization, distortion/cropping,
photometric variation, convergence and saved-vs-runtime config. These are
hypotheses, not confirmed bugs. Do not launch parameter searches against Room test.
The diagnostic matrix/report can be technically complete with an unresolved
scientific cause; downstream Gaussian claims remain scoped to GS-vs-GS.

## 5. Report and upgrade integration

Preserve `reports/Photos_to_3D_Academic_Project.docx` as the submitted historical
manuscript. Generate a teacher-response supplement under
`upgrade/reports/teacher-room-v1/` (report.md/report.json/results.csv/per-view.csv/
gallery.html) before any further Gaussian training. It explicitly marks the old
broad NeRF-vs-GS conclusion as provisional while diagnosing Nerfacto. The current
implementation does not automatically rewrite the historical DOCX or fabricate
teacher approval. Incorporate the supplement into a revised manuscript only
with an accurate separation of historical, diagnostic and upgrade results.

Reuse the existing Gaussian campaign/report/UI stages only after the supplement
gate. Their baseline columns are retained historical references, not corrected
Nerfacto results. No SOTA, geometry-ground-truth or new4K/8K-source-detail claims.
4K/8K renders and UI acceptance run after all priority Room computation/report.

## 6. Resources, estimates and Stop/Resume

One native Windows GPU worker, shared baseline GPU lock, CPU4, clock300–800MHz,
start<65C, stop78C/80W/95%VRAM or missing telemetry. Keep the existing safety
policy and runtime pins; install no packages or change baseline configs.
Reserve at least30GiB and pre-budget diagnostic outputs; GPU stage time cap3h
per arm (historical Room train3417s≈57min, three training runs≈2h51min proxy).
With eval/common scoring/startup, plan roughly3–5h for the teacher branch;
this is an estimate, to replace with measured rates after A starts. Gaussian
remainder has its independent original budget. No promise of zero failures.

Teacher runs never resume model state: Stop saves the current checkpoint for
forensics; Resume skips verified completed arms/stages but starts an interrupted
training arm afresh in a new attempt. A completed30k arm awaiting evaluation is
reused after integrity/safety checks, never trained twice. Gaussian continuation
retains its original exact-state Resume behavior. This distinction is explicit
in console, state and reports.

Initial preparation/launch (already executed by the agent; do not start a second owner):
```powershell
.\upgrade\scripts\Test-TeacherRoom.ps1
.\upgrade\Invoke-Upgrade.ps1 teacher-plan -Study teacher-room-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Start -Name topic16-teacher-room-v1 -Task teacher -Study teacher-room-v1
```

Monitoring/Stop/Resume, PowerShell at repository root:
```powershell
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-teacher-room-v1
wsl.exe --exec tmux attach -t topic16-teacher-room-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Stop -Name topic16-teacher-room-v1
# Wait for paused before shutdown. Teacher's interrupted arm restarts fresh.
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-teacher-room-v1
```
Detach tmux: Ctrl+B, then D. Tmux is the monitor, not the GPU runtime.

Declaration/state: `upgrade/artifacts/jobs/teacher/teacher-room-v1/`.
Console: `upgrade/artifacts/logs/sessions/topic16-teacher-room-v1/console.log`.
Results: `upgrade/reports/teacher-room-v1/`. Previous reports stay local/ignored.
The two old architecture filenames mentioned by the skill are absent in this
checkout; current README and docs/session_operations.md are used as the actual
architecture/runbook references. G-Core release approval remains unchanged.
