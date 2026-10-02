# UI implementation plan

This plan records the implementation of the reviewed UI design and problem list.
The earlier planning documents were removed from the current source tree;
the maintained feature/architecture guide is [README.md](README.md), and
implementation evidence is recorded in [ACCEPTANCE.md](ACCEPTANCE.md).
The user authorized the complete local UI and packages on 2026-10-02.
All UI frontend, backend, scripts, tests and operational documentation live here.
Research artifacts remain immutable. This is the authorized local research UI;
it does not change the existing research gate or publish a certified release.

## Ordered acceptance gates

- [x] 0. Inspect real Gaussian/point-cloud exports; pin and install compatible
  renderer packages; prove worker decoding and test Tea sets + Garden in a real
  browser. Record multi-view decision, primitive counts, timing and memory.
- [x] 1. Separate UI settings from experiment identity; prove UI-only changes
  compatible and training/safety/data/runtime drift rejected before inference.
- [x] 2. Native PowerShell setup/build/prepare/start/test entrypoints, Unicode
  paths and registry-derived dependency manifests.
- [x] 3. Exact-pair artifact catalog, safe asset index, thumbnails, camera
  presets/alignment, saved evaluation views, evidence and metrics.
- [x] 4. Local concurrent HTTP API, byte ranges, sessions, bounded GPU jobs,
  owner leases, atomic paired results and protected cache eviction.
- [x] 5. React/TypeScript workspace: dataset selector, single/dual synced 3D,
  camera controls, point/Gaussian adapters, saved image wipe/crop/error tools,
  benchmarks, interactive diagrams and read-only report export.
- [x] 6. Walkable gallery with framed dataset images, labels, speed, map,
  collision bounds, guided tour, keyboard/touch navigation and return position.
- [x] 7. Exact-checkpoint free-camera inference, guarded serial CUDA worker,
  proxy while moving, actual paired-camera render acceptance.
- [x] 8. Onboarding, CSS Modules/themes, i18n, bookmarks backup, errors,
  responsive/touch/DPI/forced-colors support and lazy bundle budgets.
- [x] 9. Backend/frontend/fixture E2E tests, native Windows contract checks,
  real Brave/Chrome/Edge asset tests, screenshot/trace inspection and CI.
- [x] 10. Start the finished UI, record actual URL and results, update runbook
  and U01–U40 acceptance with honest tested/untested statuses.

## Evidence

Machine-generated QA lives under artifacts/ui/qa (ignored). Source test tools,
spike decision, acceptance summary and commands live in UI_design.
No full training or GPU replay is required for UI acceptance. Hardware/assistive
technology unavailable for testing is recorded explicitly rather than inferred.

## Completed delivery — 2026-10-02

Local inference-profile UI: http://127.0.0.1:7016. All ten implementation
milestones and initial renderer/registry gate are complete. This is a running
application, with source and native launchers under UI_design.

- Renderer evidence: SPIKE_DECISION.md and actual Brave/Chrome/Edge records;
  five real scenes, worker `loadPackedSplats`, single/dual camera retention,
  large-asset cancel/retry, real NVIDIA renderer, no uncaught page errors.
- Immutable identity: ten validated exact runs, 722 allowlisted assets,
  original snapshots preserved, positive UI-only and negative experiment drift
  contracts. PLY header counts and architecture fields come from verified files.
- Functional frontend: gallery/tour/map/return, camera controls, synchronized
  structural viewing, exact saved/live image groups, ROI/wipe, benchmark,
  architecture/config, bookmarks/import/export, screenshot sidecar, report PDF.
- Inference: actual UI button passed for both checkpoints together, Nerfacto
  alone and Splatfacto alone; actual translated novel-camera pair also passed.
- Validation: 75 existing Python tests, 10 UI Python tests, 7 bookmark tests,
  5 fixture browser E2E tests, 46 native PowerShell files parsed, typecheck/build
  and lazy bundle budgets. Hosted GitHub Actions is configured, not claimed run.
- Service: Unicode/fresh-shell Conda discovery, strict occupied-port rejection,
  automatic fallback to 7017, owned shutdown, original 7016 server preserved.
  Windows exclusive socket binding fixes SO_REUSEADDR duplicate listeners.
- Export/lifecycle: actual PNG + metadata downloads, simulated real WebGL context
  loss and recovery, forced-colors emulation, gallery return and PDF source
  identities verified. ACCEPTANCE.md records exact scope of each observation.

Physical touch hardware, Windows OS-level DPI changes, NVDA, a long memory soak,
forced CUDA/native termination and a genuinely new sixth trained scene were
not available or deliberately not injected into this completed local delivery.
They are recorded as PARTIAL/NOT TESTED in ACCEPTANCE.md; implementation is
complete and those records do not masquerade as passing hardware evidence.

Development smoke also passed: Vite 5176 proxies the exact active backend,
rewrites mutation Origin correctly, and acquires/releases a lease through the
dev origin. Dev readiness now requires the selected catalog revision.
