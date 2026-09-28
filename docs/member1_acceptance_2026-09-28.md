# Member 1 P0–P2 acceptance — 2026-09-28

Branch reviewed: `origin/p1-data-contract` at `92ed947`; merged locally by
fast-forward, then corrected/extended before publishing to `main`.

| Gate | Evidence | Result |
|---|---|---|
| P0 Windows runtime | `scripts/Check-Environment.ps1 -RequireRuntime` on lead RTX A4500; Git, Conda, v142, CUDA tensor, COLMAP, FFmpeg, `ns-train`, `ns-eval`, `ns-process-data` | PASS |
| P0 negative host | `tests/Test-HostContract.ps1`: isolated-process missing Conda/MSVC errors; no installed tools changed | PASS |
| P1 schema | `tests/Test-ManifestContract.ps1`: success/failure/running/custom; unknown field, missing completion/artifacts, invalid split hash, wrong key/version/time; atomic writer path with spaces/Unicode and running→failed transition | PASS |
| P2 dataset | `scripts/Download-Datasets.ps1 -Mode all` rerun on lead machine; poster 100 processed frames, garden 185, bonsai 292, room 311; sparse files; 12,535,427,936-byte archive and measured SHA-256 | PASS |
| P2 negative | `tests/Test-DatasetContract.ps1`: missing dataset and corrupt nonempty image rejected; invalid data did not replace prior manifest | PASS |

Original Member 1 commit added a schema and a hand-written test that printed a
failure case but exited 0 and never read the schema. It also did not implement
P2.5. The follow-up provides a schema-consuming PowerShell validator/writer,
fixture tests, scene manifests, exact image/pose checks, and a pinned measured
archive SHA-256. Dataset/archive/model data remain Git ignored.

Scope boundary: P1 offers a manifest contract, **not** an already instrumented
trainer. P4 must call `Write-RunManifest.ps1` and compute a real split hash; P5–P7
must consume the exact run key. No poster training or held-out inference was run
as part of this acceptance, so G-Core remains blocked.
