# Renderer decision — actual laptop evidence

Decision: **two WebGL contexts**, at most one point-cloud pane and one Gaussian
pane. Each owns an independent Three/Spark renderer; a shared camera pose and
target synchronize inputs. This is the documented fallback selected for this
implementation. We did not assert that a single scissored Spark canvas passed.
Two-context rendering has now loaded all five real paired scenes successfully.

Pins: Spark 2.3.1, Three 0.186.1, native Node 24.16.0. Source of truth is
`configs/project.psd1: Ui`. Spark's pinned `SplatLoader.loadInternal` calls
`workerPool.withWorker` and `worker.call("loadPackedSplats", ...)`; its WASM
decoder returns packed typed arrays using ArrayBuffer transfer. This proves
PLY decoding, separately from the sorting worker. Actual browser worker events
were also captured; production point-cloud decode uses our dedicated worker.

Initial real-asset spike, Brave 154.0.8037.93, 1366 × 768, native ANGLE / NVIDIA
RTX A4500 Laptop GPU / D3D11:

| Gaussian asset | File | Primitives | Initial load | Main JS heap after load | Device VRAM sample |
|---|---:|---:|---:|---:|---:|
| Tea sets | 58.1 MiB | 245,656 | 703 ms | 26.8 MiB | 774 MiB |
| Garden | 391.9 MiB | 1,656,903 | 1,830 ms | 159.2 MiB | 945 MiB |

VRAM baseline was 690 MiB; these are whole-device snapshots, not isolated
allocation measurements. JS heap omits worker/WASM/native allocations. The
spike is a local performance observation, not a benchmark result or peak-RSS
claim. Raw measurements and screenshots live in `artifacts/ui/qa/spike/`.

Outliers made bounding-box framing unusable. Default camera now comes from the
frozen eval split. OrbitControls changes the camera during construction, so
the adapter reapplies the pose **after** constructing controls. A saved camera
round-trip was measured on Brave, Chrome and Edge and matches the frozen pose
to below 1e-6. Neither method gets a separate scene fit or scale adjustment.

Spark auto-update fire-and-forget promises can reject while disposing a sorting
worker. The adapter therefore disables auto-update and LoD, owns each explicit
`spark.update()` promise, and awaits pending update/load before disposing Spark
and its context. Controlled fetch streams permit cancellation without cloning
hundreds of MiB into per-vertex objects. Point decode terminates its own worker.
Five-scene switching and return from gallery now run without page errors.

The displayed Gaussian is the full export, with a 600 MiB input limit and a
3 million vertex limit; no reduced tier is silently substituted. Spark's packed
representation may quantize attributes; the browser preview is labelled and is
not claimed to match CUDA gsplat pixel for pixel. Nerfacto exports are labelled
point-cloud proxies. Exact model images are produced by the separate guarded
native worker, and are compared only within one immutable camera request.

Primary implementation references: [Spark SplatMesh](https://sparkjs.dev/docs/splat-mesh/),
[SparkRenderer](https://sparkjs.dev/docs/spark-renderer/),
[OrbitControls](https://threejs.org/docs/pages/OrbitControls.html).
