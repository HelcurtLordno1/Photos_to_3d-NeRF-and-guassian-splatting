# Paper and pinned-source reading notes

Historical design review; runtime API is determined by the pinned local checkout.


### 5.1 Bản đồ paper → thành phần project

| Paper | Ý tưởng dùng trong project | Repo | Vai trò |
|---|---|---|---|
| NeRF (ECCV 2020) | Radiance field + volume rendering | `bmild/nerf` | Nền tảng lý thuyết |
| Mip-NeRF 360 (CVPR 2022) | Unbounded contraction, proposal sampling/distortion ideas | `google-research/multinerf` | Thành phần tư tưởng của Nerfacto + dataset |
| Instant-NGP (SIGGRAPH 2022) | Multiresolution hash encoding, fused CUDA MLP | `NVlabs/instant-ngp`, tiny-cuda-nn | Gia tốc Nerfacto |
| Nerfstudio (SIGGRAPH 2023) | Modular pipeline, Nerfacto, common CLI/eval | `nerfstudio-project/nerfstudio` | Runtime chính |
| 3DGS (SIGGRAPH 2023) | Explicit anisotropic Gaussians + densification + rasterizer | `graphdeco-inria/gaussian-splatting` | Nền tảng Splatfacto |
| gsplat (JMLR 2025) | Memory-efficient CUDA Gaussian rasterization | `nerfstudio-project/gsplat` | Backend Splatfacto |
| COLMAP / SfM Revisited (CVPR 2016) | Robust incremental Structure-from-Motion | `colmap/colmap` | Camera poses/sparse init |

### 5.2 NeRF — Representing Scenes as Neural Radiance Fields for View Synthesis

**Nguồn:** [project](https://www.matthewtancik.com/nerf),
[paper](https://arxiv.org/abs/2003.08934),
[official code](https://github.com/bmild/nerf).

**Paper làm gì.** NeRF học hàm liên tục
$F_\Theta(\mathbf{x},\mathbf{d})\rightarrow(\sigma,\mathbf{c})$. Một pixel được
tạo bằng lấy mẫu nhiều điểm trên camera ray rồi tích phân thể tích khả vi. Direction
đi vào nhánh màu để mô hình hóa view-dependent appearance; positional encoding giúp
MLP học chi tiết tần số cao. Coarse/fine sampling dành nhiều mẫu ở vùng có density.

**Kiến trúc paper.** Hai MLP coarse/fine; input vị trí 3D qua Fourier positional
encoding; viewing direction vào các layer muộn; alpha compositing tạo RGB; loss RGB
giữa render và ảnh thật cập nhật network.

**Repo làm gì.** Repo TensorFlow 1.x là reference implementation: loaders cho
Blender/LLFF/DeepVoxels, training/render script và Tiny-NeRF notebook. Nó hữu ích để
đọc formulation nguyên bản nhưng chậm và dependency cũ; project không dùng nó làm
runtime.

**Đầu tư sâu cho bài.** Hiểu volume rendering weights, transmittance và tại sao nhiều
query/ray làm rendering tốn kém. Khi phân tích artifact, liên hệ blur/floater với
density phân tán và pose error; không gọi Nerfacto là kiến trúc NeRF 2020 nguyên bản.

### 5.3 Mip-NeRF 360 — Unbounded Anti-Aliased Neural Radiance Fields

**Nguồn:** [project + dataset](https://jonbarron.info/mipnerf360/),
[paper](https://arxiv.org/abs/2111.12077),
[official code](https://github.com/google-research/multinerf).

**Paper làm gì.** Mở rộng mip-NeRF cho cảnh unbounded bằng scene contraction phi
tuyến, proposal MLP được online distillation để phân bổ samples, và distortion loss
để giảm floaters/background collapse. Đây là paper đứng sau benchmark thật 360° mà
dự án dùng.

**Kiến trúc paper.** Ray intervals được biểu diễn bằng conical frustums/integrated
encoding; tọa độ xa được contract vào miền hữu hạn; proposal network dự báo vùng có
khối lượng; NeRF chính render; proposal và distortion objectives regularize samples.

**Repo làm gì.** MultiNeRF là code JAX cho Mip-NeRF 360, Ref-NeRF và RawNeRF; có
LLFF/COLMAP loader, train/eval/render configs. Repo đã được GitHub đánh dấu archive
ngày 2025-02-11, nên chỉ là reference source, không phải runtime được bảo trì cho bài.

**Liên hệ Nerfacto.** Nerfacto mượn tinh thần proposal sampling và scene contraction,
nhưng thêm hash encoding, appearance conditioning, pose refinement và các lựa chọn
engineering khác. Kết quả Nerfacto không phải reproduction của Mip-NeRF 360 paper.

### 5.4 Instant Neural Graphics Primitives (Instant-NGP)

**Nguồn:** [project/paper](https://nvlabs.github.io/instant-ngp/),
[official code](https://github.com/NVlabs/instant-ngp),
[tiny-cuda-nn](https://github.com/NVlabs/tiny-cuda-nn).

**Paper làm gì.** Thay Fourier features lớn + MLP sâu bằng multiresolution hash tables
chứa feature học được và MLP nhỏ; hash collisions được phân giải qua nhiều mức độ
phân giải. Fully fused CUDA kernels giảm memory traffic và overhead.

**Repo làm gì.** Một C++/CUDA testbed cho NeRF, SDF, neural image và neural volume;
chứa GUI, bindings và dùng tiny-cuda-nn. Nó không chỉ là một Python NeRF package và
không dùng trực tiếp trong benchmark.

**Liên hệ Nerfacto.** Nerfacto dùng hash encoding và fused MLP cho density/field,
đây là lý do thực tế khiến “NeRF hiện đại” nhanh hơn NeRF 2020 nhiều bậc. Báo cáo cần
tách contribution của representation khỏi contribution của CUDA implementation.

### 5.5 Nerfstudio — A Modular Framework for Neural Radiance Field Development

**Nguồn:** [paper](https://arxiv.org/abs/2302.04264),
[official code](https://github.com/nerfstudio-project/nerfstudio),
[Nerfacto docs](https://docs.nerf.studio/nerfology/methods/nerfacto.html),
[installation](https://docs.nerf.studio/quickstart/installation.html).

**Paper làm gì.** Đề xuất framework module hóa DataParser → DataManager → Model →
Pipeline → Trainer/Viewer và giới thiệu Nerfacto như cấu hình kết hợp nhiều kỹ thuật
đã chứng minh hữu ích cho real captures.

**Nerfacto architecture.** Piecewise initial sampler; hai proposal density fields;
scene contraction cho unbounded content; multires hash encodings + small MLP; per-image
appearance embeddings; tùy chọn camera pose refinement; volume renderer.

**Repo làm gì.** Cung cấp `ns-process-data`, `ns-train`, `ns-eval`, `ns-render`,
viewer, exporters, data conventions và nhiều method. Nó là integration layer duy
nhất của project. Pin `v1.1.5` vì release này có Pixi environment Linux gồm CUDA
11.8/PyTorch 2.2.x để tham chiếu và `pyproject.toml` pin `gsplat==1.4.0`. Vì Pixi
manifest chỉ khai báo `linux-64`, Windows runtime dùng Conda với cặp theo official
Windows guide: PyTorch 2.1.2/cu118, Python 3.10, COLMAP 3.9.1, gsplat wheel 1.4.0
pt21/cu118 và tiny-cuda-nn commit đã pin.

**Giới hạn.** Nerfacto là “defacto method”, không phải một paper architecture độc
lập với ablation đầy đủ cho mọi thành phần. Splatfacto cũng có thể drift khỏi code
3DGS gốc; phải ghi version và tên method cụ thể.

### 5.6 3D Gaussian Splatting for Real-Time Radiance Field Rendering

**Nguồn:** [project/paper](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/),
[official code](https://github.com/graphdeco-inria/gaussian-splatting).

**Paper làm gì.** Dùng sparse SfM points để khởi tạo tập 3D Gaussian tường minh.
Mỗi Gaussian có mean, anisotropic covariance (scale + rotation), opacity và spherical
harmonics cho màu phụ thuộc hướng. Visibility-aware tile rasterizer chiếu ellipse 2D
và alpha composite theo depth. Interleaved optimization/density control clone, split
hoặc prune primitive.

**Repo làm gì.** Bốn phần chính theo README upstream: PyTorch optimizer, network
viewer, SIBR real-time viewer và conversion script từ ảnh sang SfM layout. Đây là
implementation chuẩn để đọc/tái lập paper, nhưng có CUDA extensions/submodules và
stack riêng.

**Ràng buộc hardware.** Upstream yêu cầu GPU compute capability ≥7.0 và ghi 24 GB
VRAM cho paper-evaluation-quality training; 4 GB là khuyến nghị viewer. Đây là lý do
không chọn repo này làm critical path trên A4500 16 GB.

**Đầu tư sâu cho bài.** Giải thích covariance projection, ordered alpha blending,
densification và vì sao tập primitive có thể phình thành hàng triệu phần tử. Artifact
“needle/spike”, floater và model size phải được liên hệ với scale/densification, không
chỉ mô tả bằng mắt.

### 5.7 gsplat — An Open-Source Library for Gaussian Splatting

**Nguồn:** [JMLR paper](https://jmlr.org/papers/v26/24-1476.html),
[official code](https://github.com/nerfstudio-project/gsplat),
[docs](https://docs.gsplat.studio/).

**Paper/library làm gì.** Cung cấp CUDA-accelerated differentiable Gaussian
rasterization với Python API, memory-efficient training, nhiều camera model và các
strategy densification. Đây là rendering backend, không tự nó là toàn bộ reconstruction
pipeline.

**Repo làm gì.** Có core operators, examples train COLMAP captures, benchmark script,
viewer và evaluation so với implementation gốc. Upstream báo cáo tối đa 4× ít memory
và tối đa 15% ít training time trong benchmark của họ; bài này sẽ coi đó là hypothesis
cần đo trên A4500.

**Liên hệ project.** Splatfacto dùng gsplat. Không cài gsplat `main` riêng vì có thể
không tương thích; Nerfstudio v1.1.5 pin 1.4.0. Repo gsplat mới chỉ clone khi nghiên
cứu source, không override package runtime.

### 5.8 COLMAP — Structure-from-Motion Revisited

**Nguồn:** [paper](https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html),
[official code/docs](https://github.com/colmap/colmap).

**Paper làm gì.** Cải thiện incremental SfM bằng scene graph, robust initialization,
triangulation và bundle adjustment để suy ra intrinsics, extrinsics và sparse 3D
points từ ảnh overlap.

**Repo làm gì.** Feature extraction/matching, sparse/dense reconstruction, GUI/CLI và
camera models. `ns-process-data` gọi COLMAP rồi chuyển convention camera sang format
Nerfstudio.

**Tại sao quan trọng.** Pose error ảnh hưởng cả hai methods và có thể lớn hơn khác
biệt representation. Project phải log tỷ lệ registered images, xem sparse point cloud
trước khi train, và không kết luận “model kém” nếu COLMAP fail.

---



Các link dưới đây được ưu tiên hơn blog/tutorial thứ ba và đã được kiểm tra khi xây
blueprint ngày 2026-09-21.

### Papers, projects, code

- NeRF: [project](https://www.matthewtancik.com/nerf) ·
  [paper](https://arxiv.org/abs/2003.08934) ·
  [code](https://github.com/bmild/nerf)
- Mip-NeRF 360: [project/dataset](https://jonbarron.info/mipnerf360/) ·
  [paper](https://arxiv.org/abs/2111.12077) ·
  [MultiNeRF code](https://github.com/google-research/multinerf)
- Instant-NGP: [project/paper](https://nvlabs.github.io/instant-ngp/) ·
  [code](https://github.com/NVlabs/instant-ngp) ·
  [tiny-cuda-nn](https://github.com/NVlabs/tiny-cuda-nn)
- Nerfstudio: [paper](https://arxiv.org/abs/2302.04264) ·
  [code/releases](https://github.com/nerfstudio-project/nerfstudio) ·
  [installation](https://docs.nerf.studio/quickstart/installation.html) ·
  [Nerfacto](https://docs.nerf.studio/nerfology/methods/nerfacto.html) ·
  [Splatfacto](https://docs.nerf.studio/nerfology/methods/splat.html) ·
  [data convention](https://docs.nerf.studio/quickstart/data_conventions.html)
- 3D Gaussian Splatting: [project/paper](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) ·
  [official code](https://github.com/graphdeco-inria/gaussian-splatting)
- gsplat: [JMLR paper](https://jmlr.org/papers/v26/24-1476.html) ·
  [code](https://github.com/nerfstudio-project/gsplat) ·
  [docs](https://docs.gsplat.studio/)
- COLMAP: [SfM paper](https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html) ·
  [code/docs](https://github.com/colmap/colmap)

### Dataset/download verification

- Official Mip-NeRF 360 archive:
  `https://storage.googleapis.com/gresearch/refraw360/360_v2.zip`
- The current gsplat official downloader uses the same archive:
  [`examples/datasets/download_dataset.py`](https://github.com/nerfstudio-project/gsplat/blob/main/examples/datasets/download_dataset.py)
- Nerfstudio smoke command and poster capture:
  [`ns-download-data nerfstudio --capture-name=poster`](https://github.com/nerfstudio-project/nerfstudio)

### Pin registry in this repo

`configs/project.psd1` là registry executable cho exact commits, dataset size, selected
scenes và protocol defaults. Khi nâng version, tạo một change có review, rerun smoke
gate, và không trộn kết quả trước/sau upgrade trong cùng bảng.
