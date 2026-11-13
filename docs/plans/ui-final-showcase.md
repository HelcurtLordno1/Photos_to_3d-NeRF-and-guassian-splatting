# Completed-results showcase — UI revision, 2026-11-13

User approved a consistent Baseline/Upgrade/Compare workflow for all five
completed scenes, a clearer benchmark presentation and bounded resource use.
This changes the UI only. Preserve every dataset, checkpoint, scientific report,
source pin and prior acceptance archive. No retraining or new quality claims.

## Workflow

- Default to the selected final Gaussian result for each scene. One parent
  display selection controls Results, Images, 3D and Benchmark.
- Keep original Nerfacto/Splatfacto studies under explicitly labelled Research
  history. Never insert a Gaussian into a Nerfacto slot or invent an upgraded
  NeRF run. Old bookmarked runs continue to resolve to their historical study.
- Native images share the frozen camera/GT; support wipe, side by side, detail
  zoom and bounded display-size RGB difference. High-resolution Compare requires
  both matching images.4K/8K are renders only, without high-resolution GT metrics.
- Benchmarks use the committed RGB8 metrics, per-view gains and regressions,
  full model footprint and scoped timing. Cross-scene rows are not pooled scores;
  Tea also changes training resolution. Retain parity misses and slow previews.

## Resource policy

- No WebGL or model fetch on initial navigation or benchmark/image tabs.
- Load only the current scene. 3D is explicitly opened; paired Gaussian loads
  are sequential and new renderers wait for prior resources to retire.
- Two-model preview allowance: combined1.5M Gaussians and384MiB PLY, plus the
  existing per-asset limits. Garden uses camera-preserving one-model switching;
  its saved-image Compare remains fully available.
- Final previews cap DPR at1 and drawing buffers at1280x720 per pane. Rendering
  remains demand-driven. Large saved images never change the native benchmark.
- Difference canvas is limited to1024px long edge. Keep Spark and historical
  research lazy; retain the180KiB initial bundle gate. No new packages.

## Acceptance

Native Windows build/typecheck/unit checks and bundle budget, then a separately
archived, guarded real-browser run against the built app and actual artifacts.
Check all five top-level dropdowns, model identity and metrics, camera changes,
view preservation between tabs, native/4K/8K availability, and research-history
access. Verify real paired3D orbit/camera synchronization, no repeat download on
camera changes, demand-driven idle, size-gated Garden switching, model cleanup
and rapid cancellation. Inspect desktop/mobile screenshots and console errors.
Publish new UI evidence under artifacts/ui/qa; do not rewrite old completion
records or imply that prior browser-parity numbers certify the new viewport.

## Completed validation — 2026-11-13

Implemented the shared final-results workspace without changing scientific
artifacts. The Room benchmark additionally exposes the committed Nerfacto
historical reference and fresh A/B/C diagnosis in a separate expandable table,
with native-float and common RGB8 measurements distinguished. This is not a
Gaussian upgrade or a fresh four-arm interaction study.

Native build/typecheck and the bundle gate passed: about85.5KiB initial gzip
against180KiB, with the renderer lazy. All28 frontend and27 backend tests passed.
The guarded built-app acceptance passed all five scenes, real native/4K/8K
images, exact displayed metrics, synchronized paired orbit, Garden's one-model
fallback, rapid scene switches, idle rendering, mobile/dark layout and history.
Observed maximum viewer contexts:2; remaining contexts after cleanup:0; browser
page errors:0. This verifies the exercised paths, not unlimited GPU headroom.

Final evidence is `artifacts/ui/qa/showcase-v2-r2/acceptance.json`, including the
hashed source ZIP, browser results/screenshots and successful GPU safety record.
The earlier r1 attempt remains retained. Reproduce against a running artifacts
server with `UI_design/scripts/Test-Showcase.ps1` in Administrator PowerShell;
use a new output directory for every acceptance run. Original scientific
completion and browser-parity records remain historical, immutable evidence.
