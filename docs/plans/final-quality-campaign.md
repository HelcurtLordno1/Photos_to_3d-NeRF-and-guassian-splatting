# Final quality campaign — authorized 2026-11-12

The user's latest instruction extends the Tea plan to every existing dataset.
Keep all historical baseline models. Explore on Tea, then run one selected
upgrade per other scene; do not repeat the Tea ablation matrix elsewhere.
This is experimental research, not G-Core certification.

## Sequence and stopping rules

1. Finish v5 paired seeds17/2026; reuse42. Keep every negative result. Existing
   three-seed signal gates remain unchanged. Do not expand if this gate fails.
2. One bounded Tea capacity experiment: fixed seed42,90train/15validation drawn
   only from the105 training views by deterministic pose coverage. Freeze
   GT-only object boxes before either model. Compare300k versus450k for30k with
   identical CPU-backed input adapter, backend/modules/schedule/optimizer and
   one common evaluator. Never select using Tea's15 held-out test views.
3. Choose450k only if validation ROI LPIPS falls>=5%, mean PSNR loss<=0.2dB,
   PLY<=110MiB and fixed browser candidate parity35/30dB + p95<=33.3ms pass.
   Otherwise retain300k and stop this branch. No600k search or unbounded Mip
   integration. Only a winning450k receives one full105train30k confirmation;
   otherwise reuse the existing valid full300k Tea result.
4. Freeze method modules, source/runtime and resource policy before other
   scenes. Run sequentially Bonsai -> Room -> Garden -> Poster. Each gets one
   full30k Improved-GS, baseline derivatives, all held-out images/common metrics,
   one PLY, measured resources, browser inspection, reports and UI publication.
   No new AbsGS/Nerfacto/subset/seed sweep on those scenes.
5. Finish and validate one scene before the next acquires GPU. Integrity,
   calibration, nonfinite loss, missing telemetry, RAM/VRAM/disk or time-budget
   failures checkpoint and pause. A valid negative quality result is published
   honestly; it does not trigger hidden parameter tuning or erase the baseline.

## Dataset contracts and capacity

Reuse baseline frozen train/test, exact output K/dimensions, existing raw/SfM and
30k checkpoints. Derivative CPU metrics never overwrite original baseline
metrics. A baseline-trained model is not an upgraded Nerfacto.

|Scene|Train/eval|Training output|Predeclared candidate budget|
|---|---:|---|---:|
|Tea|105/15|719x1279 native study|300k, or450k only after validation gate|
|Bonsai|255/37|1559x1039 baseline output|1,000,000|
|Room|272/39|1557x1037 baseline output|1,000,000|
|Garden|161/24|2593x1680 baseline output|1,200,000|
|Poster|87/13|539x959 baseline output|300,000|

Bonsai/Room budgets follow the pinned official method presets. Garden's official
3M budget exceeds this laptop's declared1.5M growth ceiling, so1.2M is an explicit
resource adaptation, not exact paper reproduction. Poster uses the selected Tea
budget. These counts are fixed before new test evaluation, not chosen by test
PSNR. Positive explicit upstream `budget` takes precedence over the alternate
`final_budget * budget_multiplier` branch: the older plan's blanket3x transient
ceiling estimate does not apply to that code path. Keep the hard1.5M/12GiB guards;
do not infer safe growth solely from final budget.

## Bounded loading and preflight

All-image CUDA caching is unsuitable for larger scenes. Use lossless uint8 RGB
storage on CPU, an exact float32 lookup table matching PIL normalization, a
bounded two-camera CUDA cache and CPU-backed edge maps computed by the unchanged
GPU edge operator. Preserve sample order, random states, RGB values/strides,
mask semantics and MU gradients. Pixel-weight transfer already exists upstream.
Freeze this adapter separately; do not modify the v4 trainer or its source pins.

Verify cache decoding against original camera tensors and edge maps, plus the
existing full-state replay check, before full training. Scene preflight uses
TRAIN only and the first3500 steps of its actual30k run, including early growth
and the all-camera EAS branch. Commit that checkpoint and continue the same run;
do not create a disposable full training model. Publish measured and projected
cost separately. A projection is not proof of later memory safety: guards stay on.

One GPU worker, four CPU threads,300–800MHz, start<65C, stop78C/80W/95%VRAM or
missing telemetry, allocator<=12GiB, host free>=4GiB and disk free>=30GiB. New
scene training has an explicitly frozen6h ceiling per model, reflecting the
user's authorization for the longer complete campaign; no automatic extension.
Tea v5 keeps its original3h budget. Disk preflight includes all remaining scenes
and atomic recovery slots. No concurrent WebGL during timed CUDA work.

## UI and 4K/8K

Baseline gallery and paired legacy3D remain. Completed final upgrades add one
consistent baseline/selected-upgrade comparison per scene, with shared camera,
native GT/images, common metrics and resource scope. Keep Tea intermediate
experiments in its research archive. Pending/failed profiles stay labelled;
never show missing evidence as an inferior replacement for a complete model.

Keep training at the declared input/output sizes. Add long-edge3840 and7680
render profiles, preserving aspect ratio and exactly scaled intrinsics, from
the same checkpoints. These are high-resolution renders, not new4K/8K captures
or proof of recovered4K/8K detail. Only a small fixed camera set is exported;
native held-out metrics remain the quality benchmark. No PSNR-to-upscaled-GT.
Measure actual pixel dimensions/time/peak allocator. Render only with enough
memory reserve; an unsupported optional8K profile must be reported honestly.
No approximate tile stitching presented as pixel-exact rendering.

## Continuous execution and evidence

Prepare the complete stage graph/code and verify its contracts before handing
off to a new managed final session. Adopt completed/paused v5 evidence with the
same declarations; do not run two owners or resume the old full/Bonsai campaign.
Stop commits current state; Resume skips verified stages. Publication failure
retries publication without training again. Each stage has input/output hashes,
source/runtime identities and an attempt history; committed evidence is immutable.

Final reports include per-view/ROI where locked, per-seed Tea statistics, every
scene's baseline-versus-upgrade deltas, resource limits, browser approximation
and performance, high-resolution profiles, negative results and exact commands.
Git contains source/plans only; report folders stay local and are not deleted.

Other-scene preview policy is declared before their runs: candidate PLY native
round trip must reach60dB at every eval camera. Browser35/30dB and33.3ms remain
reported targets, not promises for a1M-point scene. A miss is labelled approximate
or slower and never claimed pixel-identical/30FPS. Mean browser agreement<25dB
or any view<20dB is a separate catastrophic-calibration guard and pauses the
queue before publication. This does not change Tea's stricter P1/P3 selection
targets. Real UI tests must still load both models and their actual images.
