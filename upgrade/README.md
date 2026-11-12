# Spatial Studio — Capture Intelligence

Experimental research upgrade alongside the preserved Topic 16 benchmark. All
training, datasets, attempts, checkpoints and reports created here stay under
`upgrade/`. The single Spatial Studio at `UI_design/` reads both sources.
This does not certify G-Core, reconstruct SfM from fewer raw photographs, or
establish a general PSNR predictor from one video.

## Current authorized work: Tea quality v5

The full campaign described below is historical and paused. V4 completed both
native 30k models; v5 audits their scale/zoom/continuous path and packed browser
renderer, then confirms paired seeds17/2026 only when P0/P1 gates pass. It reuses
the exact frozen v4 trainer and seed42 evidence. Read
[the approved plan](../docs/plans/tea-quality-v5.md) and [Agent.md](../Agent.md).

```powershell
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-tea-quality-v5
.\upgrade\scripts\Manage-Session.ps1 -Action Attach -Name topic16-tea-quality-v5
.\upgrade\scripts\Manage-Session.ps1 -Action Stop -Name topic16-tea-quality-v5
# Wait for paused before poweroff. Later:
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-tea-quality-v5
```

Native Windows owns compute. WSL `tmux attach -t topic16-tea-quality-v5` is only
the monitor; Ctrl+B,D detaches. There is no `tmux resume` command. Reports and
their generated assets are intentionally ignored by Git and stay on the local
machine. Historical reports already committed remain in older Git history.
Never delete reports to make a source-only clone resemble a completed study.
Keep raw data, source pins, checkpoints and local reports in the user's backup.

## Historical full campaign (2026-11-08; paused)

Read [../Agent.md](../Agent.md) before operating this checkout. The old `tea60-v1`
is a completed **10k pilot**, not the full-budget result. Smoke results remain
archived but are excluded from the ordinary gallery and quality charts.

The current full campaign is `topic16-full-v1`: **Tea → Bonsai → Room → Garden**,
six 30,000-step runs per dataset, 24 total. Each dataset runs the full train pool
with both methods, then 60-view uniform and coverage-overlap with both methods.
Full-pool selectors deduplicate. The frozen definitions derive the existing
`tea-confirm-v1` protocol from the registry; the registry is not rewritten.

The next dataset is blocked until the current one passes exact-checkpoint
evaluation, the common saved-image evaluator, paired full-reference 3D exports,
held-out throughput, comparison reports and shared catalog validation. Baseline
saved predictions receive a read-only CPU evaluation under `upgrade/reports/`;
baseline training and artifacts are preserved. Failed gates stop the campaign.

```powershell
# Plan once; source is frozen before execution.
.\upgrade\Invoke-Upgrade.ps1 full-plan -Study topic16-full-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Start -Task full -Name topic16-upgrade-full -Study topic16-full-v1

# Attach / inspect without interrupting compute:
wsl.exe --exec tmux attach -t topic16-upgrade-full
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-upgrade-full

# Before shutdown, request Stop and wait for status=paused:
.\upgrade\scripts\Manage-Session.ps1 -Action Stop -Name topic16-upgrade-full
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-upgrade-full

# Later, resume the saved campaign (there is no tmux resume command):
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-upgrade-full
wsl.exe --exec tmux attach -t topic16-upgrade-full
```

Detach with **Ctrl+B, D**; this keeps compute running. Campaign state is
`upgrade/artifacts/jobs/campaigns/topic16-full-v1.json`; completed dataset reports
are `upgrade/reports/full/<scene>/gate.json`, `report.md`, `comparison.csv`.
An active native worker pauses interactive GPU rendering in the shared UI;
saved images and metrics remain available. Restart the UI after a dataset gate
to load the new catalog revision. Do not change numerical sources or packages
between segments. Resume revalidates previous datasets and reuses valid stages.

## Existing laptop

Use native Windows PowerShell at the repository root. Compute remains native
Windows; WSL/tmux is a read-only console. Scripts discover Conda without shell
activation. The setup below clones the installed environment and leaves its
packages unchanged. The verified editable Nerfstudio checkout is read-only and
its location is recorded in `upgrade/artifacts/logs/host.json`.

```powershell
# Once only; already executed on the current laptop.
.\upgrade\scripts\Setup-Upgrade.ps1 -CloneFrom topic16-ns115

.\upgrade\Invoke-Upgrade.ps1 inventory -BaselineRoot '.'
.\upgrade\Invoke-Upgrade.ps1 audit -Scene tea_sets_2
.\upgrade\Invoke-Upgrade.ps1 plan -Study tea60-v1
.\upgrade\scripts\Test-Upgrade.ps1
```

Audit does not open held-out RGB or metrics. It verifies train image hashes,
uses fixed-size luminance/Laplacian statistics, and records geometric coverage,
exposure and redundancy. COLMAP overlap uses only train observations from the
explicitly selected connected model and the canonical preparation mapping.
Without a verified mapping overlap remains unavailable; pose continuity is
labelled as a heuristic. Repeated audit/plan calls reuse the same immutable
feature record while the extractor, images, split and sparse mapping agree.

Uniform and coverage-overlap use the same train pool, budget, seed, camera
frame, resolution, sparse initialization and held-out images. They share a
subset between Nerfacto and Splatfacto. Full-pool selector conditions deduplicate.
All experiments using these canonical poses remain known-camera/transductive.

## Start, detach, checkpoint and resume

Run Start/Resume in Administrator PowerShell; a non-elevated launcher requests
Windows elevation. WSL Ubuntu needs tmux installed. The GPU guard reapplies
300–800 MHz at each GPU stage, checks a cool start below 65°C and stops at
78°C, 80 W or 95% VRAM, including missing telemetry. The upgrade acquires the
baseline's exact `artifacts/logs/gpu.lock`. A separate queue lock protects the
ledger without acquiring the GPU lock twice.

```powershell
.\upgrade\scripts\Manage-Session.ps1 -Action Start -Name topic16-upgrade -Study tea60-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Attach -Name topic16-upgrade
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-upgrade
```

From WSL, `tmux attach -t topic16-upgrade` attaches the same console. Press
**Ctrl+B, then D** to detach. Detaching keeps the native worker running.

Before shutting down the laptop, request a committed checkpoint and wait for
the state to become `paused`; an attached console alone does not control compute:

```powershell
.\upgrade\scripts\Manage-Session.ps1 -Action Stop -Name topic16-upgrade
.\upgrade\scripts\Manage-Session.ps1 -Action Status -Name topic16-upgrade
# After state=paused and the worker exits, shutdown is safe for this session.

# Later, in the same checkout with the same source, data and runtime:
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-upgrade
.\upgrade\scripts\Manage-Session.ps1 -Action Attach -Name topic16-upgrade
```

There is no `tmux resume` command: Resume belongs to the managed pipeline.
Training retains optimizer/scheduler/scaler, Python/NumPy/Torch/CUDA RNG,
sampler and Gaussian strategy state, saving every 500 steps and on Stop.
The total schedule stays fixed. A separate 10k schedule cannot become a 30k
intermediate checkpoint. A resumed attempt references the original checkpoint
and preserves prior attempts. Interrupted evaluation reruns from the exact
completed config; completed validated jobs are reused. Do not edit source or
package pins between segments of an active study. Keep `upgrade/data`,
`upgrade/artifacts`, host provenance and the checkout when transferring a run.

## Study budgets

| Study | Conditions | Training runs | Meaning |
|---|---|---:|---|
| `tea-smoke-verify-v2` | 6 views, uniform, 10 iterations | 2 | Infrastructure only; excluded from selector claims |
| `tea60-v1` | 60 views, both recipes, 10k | 4 | Completed E1 pilot; archived comparison |
| `tea-sweep-v1` | 30/60/105 views, both recipes, 10k | 10 total | E2; reuses the four identical E1 experiments |
| `tea-confirm-v1` | 60 views, both recipes, 30k | 4 | E3; new total schedules |

The legacy commands below describe individual pilot studies. The full campaign
above is the user's current execution choice. Start other individual studies with a distinct session name after inspecting the actual
pilot results and available disk. The full campaign advances only after its
dataset gates. Initial ETA is historical same-scene time scaled by iterations,
explicitly an unmeasured nonlinear proxy; actual completed times are reported
alongside it. Storage reserves 30 GiB plus an estimated 2 GiB per new job;
these are planning estimates, not guarantees of maximum checkpoint size.

```powershell
.\upgrade\Invoke-Upgrade.ps1 plan -Study tea-sweep-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Start -Name topic16-upgrade-sweep -Study tea-sweep-v1
```

Direct execution is also available, but do not combine it with an active
managed session: `.\upgrade\Invoke-Upgrade.ps1 run -Study tea60-v1 -Resume`.

## Evidence and the shared UI

The native method metrics remain recorded. A second evaluator applies the same
PSNR, TorchMetrics SSIM and AlexNet LPIPS implementation to each method's saved
8-bit RGB images on CPU. Its ID is `common-rgb8-psnr-tmssim-alexlpips-v1`, bound
to the installed runtime and exact evaluation hashes. Historical SSIM/FPS
retain their original measurement scope; no common-evaluator improvement is
claimed against historical method-native rows.

`upgrade/reports/ui-index.json` publishes only validated completed runs. Optional selected exports and throughput can be produced from exact completed
configs using `upgrade/scripts/Export-Run.ps1` and `Render-Run.ps1`. These commands
verify the recorded checkpoint and shared GPU lock, then republish the index.
No export is scheduled for every pilot.

Partial
pairs appear as individual measurements; they cannot produce selector deltas.
Run-set gallery/image comparison requires both methods and identical cameras
and GT. Optional missing exports/FPS remain unavailable rather than zero.
Controlled selector deltas require the same scene/pool, method, budget, seed,
resolution, source, runtime, evaluator, safety policy and eval-camera hash.
PSNR deltas use dB, never percentages. Accounting includes audit CPU time,
training and common evaluation; native evaluation and safety stage timestamps
remain available in each run's evidence. Failed/paused attempts are retained.

The worker refreshes the shared catalog when its study finishes. To refresh
manually or after changing an index:

```powershell
.\upgrade\Invoke-Upgrade.ps1 publish
.\UI_design\scripts\Prepare-UIAssets.ps1
.\UI_design\scripts\Build-UI.ps1
.\Invoke-Topic16.ps1 ui
```

Restart an already-running studio to load a new catalog revision. One checkout
owns one UI server/lease, in the existing 7016–7020 range. Gallery cards remain
one per scene. Run-set selection and bookmarks identify the exact recipe and
budget; old bookmarks resolve to baseline. Upgrade novel-camera inference is
disabled until a verified adapter is supplied. Saved-image N/S comparison and
Baseline/Upgrade comparison of the same method reuse wipe, ROI and fixed-scale
RGB error. Different GT/camera frames disable synchronized comparison.

The ridge predictor uses train-fold standardization and leave-one-scene-out
evaluation against mean and view-count baselines. The fixed regularization is
not tuned on held-out groups. Fewer than four independent groups, a model that
does not beat both baselines, a different method/budget/evaluator or features
outside training ranges produces `insufficient-evidence`. It reports only
exploratory validation; no calibrated confidence interval or causal gain from
additional photographs is inferred. Synthetic tests are never research labels.

## Fresh clone / independent data preparation

The baseline training pipeline is not required. Run
`.\upgrade\scripts\Setup-Upgrade.ps1` without `-CloneFrom` for the independently
pinned Windows runtime (MSVC v142/build tools are prerequisites). This writes
only the new environment and `upgrade/third_party`. No UI/Node application is
copied. Setup may take substantially longer than cloning an existing runtime.

Official data download and canonicalization have independent entry points:

```powershell
.\upgrade\scripts\Download-Datasets.ps1 -Mode benchmark
.\upgrade\scripts\Prepare-Scene.ps1 -Dataset bonsai
# Produces upgrade/data/captures/bonsai/split.json without baseline training.
.\upgrade\Invoke-Upgrade.ps1 audit -Scene bonsai -BaselineRoot '.\upgrade' `
    -SplitPath '.\upgrade\data\captures\bonsai\split.json'
```

Add a separately named study in `upgrade/configs/project.psd1` for Bonsai before
running it, and pass the same explicit input root and split in its direct run.
Custom capture reuse needs an approved canonical bundle containing full-size
images, images_2, sparse PLY, transforms and its frozen split with hashes.
Tea sets video/checkpoints are not included in Git. Fresh custom SfM and its
pose review are separate from selecting views of an existing canonical capture.
An artifact-only clone can open the shared UI after importing a checksummed
results bundle; with only upgrade results, no baseline checkpoints are required.

When running beside a different checkout, pass a common absolute
`-SharedGpuLock` at setup. Per-checkout locks do not serialize independent
checkouts automatically. Output path checks resolve junctions before writing.

## Preservation and verification

`reports/preservation/source-before-upgrade.zip` stores the initial tracked
source/UI and the two untracked proposal files; `baseline-source.json` records
HEAD, working-tree state and protected source/report hashes.
`baseline-inventory.json` identifies ten historical runs, registry/runtime,
matrices, split/config/checkpoint/export references and recorded checksums.
Large model files initially use size/mtime plus their original recorded hashes;
full rehashing is explicit with inventory `-FullHash`. This is not an off-disk
backup of videos/checkpoints. `.\upgrade\Invoke-Upgrade.ps1 verify` checks the
protected baseline after execution. Original benchmark experiment commit and
current adapter/source revision remain distinct.

```powershell
.\upgrade\scripts\Test-Upgrade.ps1
.\scripts\Test-Project.ps1 -PythonExecutable 'D:\Miniconda3\miniconda_download\envs\topic16-upgrade-ns115\python.exe'
.\UI_design\scripts\Test-UI.ps1
.\upgrade\Invoke-Upgrade.ps1 verify
```

The exact checks and native smoke status are recorded in `reports/IMPLEMENTATION.md`.
G-Core's independent research-review/replay requirements remain separate from
working experimental code and a locally inspectable UI.


## Recovery of an already recorded study

The 2026-11-08 recovery fixed ancestry validation of a legitimate empty
`git-diff.txt`. Empty Git diagnostics must still exist and match their exact
SHA-256; checkpoint/config/metrics files remain nonempty and checksum-verified.
Original run manifests, checkpoints, Git text, and source archives are unchanged.

When a controller/validator repair is needed after training, explicitly preserve
that study's original numerical adapter before Resume:

```powershell
.\upgrade\Invoke-Upgrade.ps1 repair-study -Study tea60-v1
.\upgrade\Invoke-Upgrade.ps1 preflight -Study tea60-v1
.\upgrade\scripts\Manage-Session.ps1 -Action Resume -Name topic16-upgrade
```

The recovery pin verifies the original source archive and every extracted file
under `upgrade/artifacts/source-pins/`. It also checks that the registry remains
byte-identical. Future child trainers import this frozen adapter, keeping the
existing experiment keys and training conditions. The repaired live controller
is independently archived as `controller-source.zip` in each new run and
identified separately in provenance. Neither source checks nor checkpoint
hashes are disabled. An unrelated study does not inherit this pin.

Preflight validates the real completed-training graph or committed resume graph,
materializes/checks every selected dataset, and checks disk reserve before GPU
work. Changed dry-runs are saved as proposed plans rather than replacing the
recorded resume matrix. A publication failure retains completed computation;
interrupted training records the actual latest attempt rather than a stale
parent config. JSON state writes flush before atomic replacement and retry
bounded Windows sharing violations.

At successful completion, the study writes
`upgrade/reports/tea60-v1/completion.json`, `results.csv`, and
`upgrade/artifacts/jobs/tea60-v1-completion.json`. Completion requires every
planned experiment to pass validation. A process merely reaching another
training iteration is not a completed study.
