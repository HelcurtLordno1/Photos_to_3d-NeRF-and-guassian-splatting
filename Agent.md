# Lessons and operating rules — Topic 16

User instruction recorded 2026-11-08: finish one dataset completely before moving
to the next; prioritize full-budget, properly evaluated results and conserve GPU,
disk and existing valid evidence. Authorization covers the sequential full study
across the existing main datasets; do not ask again merely to launch the next
already declared dataset after its predecessor passes its gate.

Current operator override (2026-11-08, 23:03 +07): the user explicitly requested
pausing Bonsai and the full campaign to test the UI and use the machine for
other work. Session `topic16-upgrade-full` is paused, with Bonsai Splatfacto
checkpoint step 14320 of 30000 committed. Tea is complete. Do not automatically
resume this session or start another training worker until the user requests
resuming. Use the existing session's Resume action when that request arrives.

Updated objective (2026-11-09): prioritize visibly sharper, cleaner 3D and
measured hardware efficiency using the full existing baseline data. Image-count
reduction is secondary. Diagnose Tea and review credible papers before further
dataset expansion. The proposed plan is
[Tea Visual Quality v2](upgrade/reports/plans/tea-visual-quality-v2.md).
User approved implementation on 2026-11-11. The executable plan is now
[upgrade_to_baseline.md](upgrade_to_baseline.md): proceed with Q0 then Q1 in
`topic16-tea-quality-v2`, with gated Improved-GS research afterward. Native
resolution is a separately declared protocol. Do not resume the old 60-view
campaign or expand other datasets merely because this new work is authorized.

## Mistakes that must not recur

- Calling launch, resumed iteration progress, passing tests or four short pilot
  jobs a successful product upgrade. These establish only their tested scope.
- Making Upgrade default to a 6-image/10-step smoke run. Smoke is diagnostic and
  must be excluded from ordinary selection, charts and quality conclusions.
- Replacing a complete interactive 3D experience with a missing-export message,
  duplicated dashboard, disconnected filters, excessive technical fields or
  an experimental feature without evidence.
- Comparing 60-view/10k outputs with 105-view/30k outputs as an improvement claim.
  Label budget trade-offs and obtain matched-budget controls and one evaluator.
- Claiming coverage selection helps when actual paired metrics show a loss.
  Preserve and publish negative results. Never tune against held-out images.
- Treating legitimate empty Git diagnostics as corrupt checkpoints. Diagnostics
  must exist and match their hash; required artifacts must also be nonempty.
- Changing experiment source or schedules silently, overwriting resume plans,
  losing the latest attempt config, or treating publication failure as failed
  computation. Preserve attempts, exact configs, immutable archives and hashes.
- Expanding all datasets at once while the first full dataset lacks end-to-end
  validation. A frozen queue is not proof the queued experiments have completed.

## Required execution policy

1. Preserve root baseline source/config/data/reports and historical runs. New
   compute and derivative evaluations stay under upgrade/. Never rerun the old
   baseline merely to populate UI or repair a report.
2. Prepare a concrete versioned matrix and estimates before GPU work. Freeze
   source, protocol, split, seed, resolution, total schedule, evaluator and safety
   identities. Reuse only validated matching runs; 10k is not a 30k checkpoint.
3. Finish Tea sets first. Then proceed in increasing measured cost: Bonsai,
   Room, Garden. One native Windows GPU worker at a time, shared baseline lock,
   four CPU workers, downscale 2 and the existing fail-closed GPU policy.
4. A full dataset includes both methods, a full-train-pool 30k reference, matched
   subset controls at 30k, exact-checkpoint held-out evaluation with a common
   evaluator, saved images, selected full-reference 3D exports, measured resources
   and a comparison report. Deduplicate selectors when they select the full pool.
5. Historical baseline gets the same CPU evaluator on existing saved predictions
   as a derivative report under upgrade/. Preserve the original native metrics.
6. Validate complete reports/exports and build the shared catalog before marking
   a dataset complete. The next dataset must not acquire GPU until this gate
   passes. On failure or a Stop request, retain evidence and stop the sequence.
7. Resume skips completed stages and restores valid training state. Record the
   actual remaining work. Never delete checkpoints or hide a half-pair to proceed.

## Required product and research acceptance

- Keep the baseline gallery, paired 3D, image controls and bookmarks usable.
  Completed full-budget results take priority; incomplete studies are labelled
  as running, not presented as an inferior replacement model.
- Use a single consistent scene/run selection and benchmark view. Keep optional
  capture/provenance details secondary. Avoid duplicate filters/tables and raw
  technical plumbing in the normal workflow.
- Verify fresh-default navigation, selected run/budget, real image loading, 3D
  capabilities, source/GT compatibility and actual browser interactions. Zero
  JavaScript errors alone is insufficient acceptance.
- Report exact completed/queued counts, limitations and measured comparisons.
  A general predictor needs independent scene-group validation and may abstain.
- Do not claim a certified release or alter G-Core review/replay requirements.
  This work remains experimental research until the real review gates pass.


## 2026-11-12 approved next research sequence

The user authorized implementation and execution of Tea research v3: publish Q1
as a single-method experiment, diagnose multi-scale inference before more model
changes, then run official same-backend AbsGS/Improved-GS control/candidate with
full-state resume checks. `upgrade_to_baseline.md` records the frozen matrix,
resource limits and new checkpoint retention policy. This overrides the earlier
pause only for the new Tea study; the old Bonsai/full campaign stays paused.
Native resolution is explicit, not a hidden downscale override. Never label an
AA flag as full Mip-Splatting, a resolution intervention as Improved-GS, a launch
as completion, or a one-seed Tea result as SOTA. Exact odd image sizes and pixel
centers must be validated. Same iterations with MU do not mean same optimizer
updates or compute. Publish negative results and ROI target misses unchanged.


Resume QA must distinguish exact state restoration from bitwise CUDA training.
Retain failed original checks. Before Q2 full training, r2 showed exact saved
state recovery and77–91dB render agreement despite raw parameter drift. The
explicit acceptance amendment in upgrade_to_baseline.md uses exact restored
state plus fixed train-camera functional replay; never silently loosen a failed
gate or use held-out quality to select its tolerance. Backend repairs use a
separately archived controller/trainer revision, preserving original declarations.

## Current Tea protocol — v4 (2026-11-12)

V3 AbsGS was stopped as a resource pilot before held-out evaluation: wrapper
used generic CLI threshold0.0003, overlooking upstream configs/absgs.json's
0.0006. Preserve that pilot and all QA failures. Current approved execution is
tea-research-v4: shared threshold0.0006, explicit ours_adam and positionLR4e-5
for both methods, fresh30k jobs; reuse only identical validated Q1.5 derivatives.
Never modify a running declaration/checkpoint to implement a new protocol.
Read method-specific upstream presets before freezing a wrapper, and make every
shared training override explicit. The final direct checkpoint QA gate is in
the rewritten upgrade_to_baseline.md; it does not promise bitwise CUDA training.
Old Bonsai/full and v3 resource pilot remain paused.

## Approved v5 and repository publication (2026-11-12)

User authorized push of all source changes and execution of the v5 plan.
Report/reports directories are local-only: stop Git tracking without deleting
their local contents. Preserve historical Git history and all source-pin bytes.
The current versioned plan is docs/plans/tea-quality-v5.md. Implement P0→P1→P2
and honor measured gates; later capacity/Mip/Bonsai work is conditional. Never
claim the queued long runs or a failed gate have completed successfully.

P1 v5 exposed two precision stages in Spark: input decoding and intermediate
render accumulation. Extending input alone did not fix parity. Preserve the
2x2 negative results; the adopted research profile is packed input + extended
accumulator, not the slower fully extended profile. Candidate parity passes;
AbsGS still has misses and wide zoom exposes uncovered backgrounds. Review
allows controlled replication, not a clean360/production claim. A resume must
reuse exact committed inspection bytes so its review hash stays valid; validate
the full UI interaction proof before allowing fresh training.

Latest authorization (2026-11-12): finish bounded Tea research, then apply the
selected method once per other existing scene against its preserved baseline.
Include Poster; do not propagate the Tea ablation matrix to other scenes. The
versioned plan is docs/plans/final-quality-campaign.md. A continuous managed
queue may proceed through already declared gates; stop on integrity/resource
failure, preserve negative quality results, and do not wait for coding between
validated stages.4K/8K are explicitly labelled inference outputs, not new source
detail. Old full/Bonsai sessions remain paused. Preserve v4 numerical source;
CPU-backed loading must have separate source and exact-input/replay evidence.

Active owner is now `topic16-final-quality-v1`. The former
`topic16-tea-quality-v5` session was cooperatively paused at seed2026 Improved-GS
step24827 and handed off without changing its experiment/trainer. A verified
checkpoint copy and handoff.json are retained under
upgrade/artifacts/jobs/final/final-quality-v1/handoff/. Resume the final session,
not the former v5 session. Existing Tea-weight component QA also checks camera
changes without PLY re-download; explicit preset redraw must work even when
OrbitControls emits no pose change. Failed QA attempts remain preserved.


## Teacher-first Room override — 2026-11-12

The user explicitly prioritized the teacher's Room Nerfacto diagnosis before
pending Gaussian upgrades. `upgrade_to_baseline.md` is the current master plan.
`topic16-final-quality-v1` was cooperatively paused at Bonsai13790/30000; preserve
its exact source/optimizer/RNG checkpoint. New owner `topic16-teacher-room-v1`
runs fresh Room A/B/C (camera off/average, on/appearance off, off/appearance off),
then emits a complete39-view common-evaluator supplement before resuming the
unchanged Gaussian campaign. No old baseline weights may initialize these arms.
Queue Resume skips completed arms but restarts interrupted teacher training in a
new attempt; it does not load the partial model. Do not confuse disabling the
average inference embedding with disabling appearance conditioning from training.
Never claim GS improvements resolve the Nerfacto confound, nor29–31dB as a
guaranteed outcome. Keep historical comparisons provisional and separate from
current controlled A–C contrasts. Older sessions stay paused; only the new owner
may continue the saved final campaign after the teacher report gate.


## User pause — 2026-11-13, 02:13 +07

The user wants to stop for the night and continue tomorrow. Session
`topic16-teacher-room-v1` is confirmed paused at Bonsai step25303/30000;
checkpoint SHA256 a5e369d1e208220802e63136935ae06c7c896c52fe340fc3513dde5ae7c8b71a
was reverified. All Room A/B/C arms, evaluation and the teacher supplement are
complete; preserve their committed bytes. No automatic training restart until
the user requests Resume. Resume the teacher session, not an older owner; it
skips completed Room work and continues the Gaussian checkpoint.
A controller-only Resume repair prevents incremental publication from replacing
a committed complete teacher report. The original declarations/trainer pins
remain unchanged; archive the live controller separately on execution.


## Explicit resume authorization — 2026-11-13

The user requested continuing the run through completion. Resume authorization
supersedes the overnight pause for `topic16-teacher-room-v1` only. The managed
worker was resumed from Bonsai checkpoint25303; all completed Room A/B/C and
their committed teacher report must remain unchanged. Continue the existing
Bonsai -> Room -> Garden -> Poster queue and final report/UI gates without
starting older sessions or adding experiments. Resource and integrity failures
still pause safely; do not label a launch or intermediate progress as completion.


## Completed delivery — 2026-11-13, 14:49 +07

`topic16-teacher-room-v1` finished with status=succeeded and
ui_catalog=all-scenes-browser-verified-and-refreshed. Teacher Room A/B/C are
complete (C native PSNR30.2981dB). All five GS scene reports/exports and the
production UI browser checks passed their declared delivery gates; final
completion is `upgrade/reports/final-quality-v1/completion.json`. The transient
UI restart/readiness timeouts recovered without any retraining. Preserve all
committed reports, source pins and weights; there is no remaining training in
this campaign and no authorization to start extra experiments automatically.
Keep the measured limitations visible: Room/Poster have per-view browser
parity misses against the stricter target; Garden browser p95 is about90.2ms.
All five native comparisons improve mean PSNR/SSIM/LPIPS versus the retained
Splatfacto references; this is experimental evidence, not SOTA certification.

## UI restoration requested — 2026-11-13

The user rejected the showcase redesign in3939fb7 and explicitly requested the
original UI. That revision was reverted in full, restoring the interface from
5a35d16. Preserve its layout, navigation and existing interactive controls.
Passing functional/browser tests did not establish that the redesign met the
user's visual or workflow requirements. Do not reapply the rejected workspace,
benchmark redesign or removed controls. Future UI changes must stay narrowly
within the user's requested scope; retain all scientific results and artifacts.

The subsequent user instruction permits a narrow integration of final upgrades
into the existing Display/condition selectors and existing 3D/image controls.
Only Benchmark & architecture may receive readability/presentation improvements;
retain the current Tea Visual quality design and every other layout. The plan is
docs/plans/ui-existing-layout-integration.md. Do not substitute a new workspace
or remove existing camera, bookmark, image, audit or architecture controls.

Scoped implementation passed guarded browser acceptance for all five scenes in
`artifacts/ui/qa/existing-layout-v1-r4/acceptance.json`. The original FinalQuality,
Quality, Gallery and global/studio styles remain byte-identical to5a35d16.
Completed Gaussian runs use `selected-final:<scene>` in the existing condition
selector; original paired NeRF/GS conditions remain available. Benchmark styles
are scoped to its tab. Keep native GT metrics separate from renderer parity,
resolution tests and historical costs, and preserve negative precision/seed
results. Functional acceptance is evidence of those tested interactions, not a
substitute for the user's judgment of the design.
