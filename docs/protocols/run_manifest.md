# P1 run-manifest contract (schema 1.0)

Source of truth: [`configs/run_manifest_schema.json`](../../configs/run_manifest_schema.json).
`scripts/Test-RunManifest.ps1` validates this Draft-07 subset and checks the
cross-field scene/method/run-key and artifact-path invariants. It uses Windows
PowerShell 5.1 without an extra Python package. `tests/Test-ManifestContract.ps1`
exercises valid and invalid fixtures. `runtime.py` now calls this writer for
every training lifecycle transition; evaluation remains a separate sidecar.

The `scene` value is `poster`, `garden`, `bonsai`, `room`, or
`custom:<lowercase-slug>`. The `run_key` is
`<scene-folder>/<method>/<YYYYMMDDTHHMMSSfffZ>`; `custom:object_v1` maps to
`custom-object_v1` because the existing training wrapper uses that folder name.
The same key maps to `artifacts/runs/`, `artifacts/logs/`, `artifacts/metrics/`,
and `artifacts/renders/`. Paths inside the manifest use project-relative forward
slashes; no machine-specific paths.

For a successful training run, `artifacts.config_path` must be exactly
`artifacts/runs/<run_key>/config.yml` and `artifacts.checkpoint_dir` exactly
`artifacts/runs/<run_key>/nerfstudio_models`. `execution_metrics.wall_time_seconds`
and `finished_at` are required. A failed run requires `failure_reason` and
`finished_at`. A running run has no completion requirement. The 64-character
`provenance.dataset_split_hash` is the SHA-256 of the frozen split manifest; it
must be computed from real data, not a placeholder. GPU fields may be absent on
CPU fixtures; official runs on A4500 record them from the actual driver.

The runtime writes the initial `running` JSON to a temporary file, then calls:

```powershell
.\scripts\Write-RunManifest.ps1 -InputPath '.\my-running-manifest.json'
```

After training exits, P4 writes a separate `succeeded` or `failed` JSON with
the **same run key** and calls the same command. The writer validates against
the tracked schema, saves atomically to `artifacts/logs/<run_key>/manifest.json`,
and refuses a second write after terminal status. It does not create or rename
checkpoints and does not infer the latest run. P5 may add metrics through a
future schema migration, but must not mutate an already completed 1.0 manifest.
`provenance.json` records exact config/checkpoint, registry/runtime/source archive,
GPU identity and safety record. `evaluation.json` records separate running/failed/
succeeded lifecycle, exact checkpoint/split, finite metrics, GT/pred identities and
hashes. `render.json` records synchronized durations, resolution and frame/video
hashes; `export.json` records derived PLY size/checksums. The training schema stays
1.0, terminal manifests are not mutated to add evaluation. Watchdog emergency
termination can leave `running`; its safety failure excludes the run from results.

For schema changes, bump `schema_version`, review with P4–P7 owners, add migration
tests, and never silently reinterpret old artifacts.

Run the CPU-safe tests with:

```powershell
.\tests\Test-ManifestContract.ps1
```
