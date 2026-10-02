# Phân công và bàn giao — 4 thành viên

Protocol/interface chung: [Construction_architect](Construction_architect.md).
Stages/gates: [Modular_construct](Modular_construct.md). Evidence hiện tại:
[implementation_status](docs/implementation_status.md).

| Thành viên | Máy / ownership liên tục | Công việc và artifact bàn giao |
|---|---|---|
| Member 1 | CPU; P0–P2 | Registry, native setup, dataset downloader/validator, P1 writer/schema; dataset/source manifests và negative fixtures |
| Member 2 | CPU; P3–P4 | Capture/process/pose review, canonical pinhole/split, trainer; exact returned config + checkpoint + logs/manifests |
| Member 3 | GPU 6 GB; P5–P7 | Held-out eval/render/export, paired resume, tables/crops/gate; code/fixtures và evidence từ A4500 |
| Member 4 — lead | A4500 Laptop 16 GB; P8–P10 | QA xuyên suốt, actual GPU acceptance, model selection/demo/release và independent replay coordination |

Ownership không đổi khi lead chạy GPU để nghiệm thu code của Member 1/2/3.
Theo yêu cầu chủ repo ngày 2026-09-30, integration bổ sung toàn bộ code core và
adapter; **activation/release** vẫn bắt buộc G-Core. Không tạo kết quả hoặc chữ ký
giả để đóng stage.

## Bàn giao và điều kiện nhận

| Handoff | Bên nhận phải kiểm tra |
|---|---|
| H0 P0/P1/P2 → P3/P4 | pinned runtime/source, đủ official data, archive SHA-256, ảnh/sparse hợp lệ |
| Safety → mỗi GPU stage | Administrator clock reapply 300–800 MHz; start <65°C; watchdog policy và log |
| H1 P3 → P4 | canonical images/poses/intrinsics + split hash; custom ≥90% train register, mọi eval register; reviewer/notes/evidence hashes |
| Sessions → mọi stage | Managed worker/tmux, atomic checkpoint, đúng total budget; actual stop/resume Nerfacto/Splatfacto và custom eval |
| H2 P4 → P5 | succeeded manifest, final checkpoint, exact config, timing/GPU, source/dependency/data hashes; không chọn latest |
| H3 P5 → P6/P7 | finite required metrics, same held-out identities/GT pixels, render count/checksums, complete pair |
| H4 P7 → P8/P9 | actual G-Core PASS với official/custom runs và independent replay/research reviews |

Member 1 đã nghiệm thu P0–P2 theo [acceptance 2026-09-28](docs/member1_acceptance_2026-09-28.md).
Audit integration phát hiện BOM trong processed poster: validator P2 trước đó
chưa chứng minh parser runtime đọc được. Fix và evidence mới ở implementation status.
Member 2/3 đọc `contracts.py` và [run manifest protocol](docs/protocols/run_manifest.md)
trước khi đổi interface; schema 1.0 training completed vẫn immutable, eval ở sidecar.

## Reviewer checklist

- CPU: `Test-Project.ps1 -PythonExecutable python`; không cài CUDA để ký parser/contracts.
- Lead: actual poster pair, bonsai calibration rồi garden/room/custom tuần tự, đúng A4500.
- Safety: mọi GPU job chạy elevated và reapply clock cap; không bypass gate hoặc coi idle clock là proof.
- GPU 6 GB: chỉ diagnostic với nhãn riêng; không ghép vào baseline hoặc hạ một method.
- Capture: 80–150 ảnh sharp, static/consistent lighting, overlap 70–80%, train/eval riêng;
  tên và nội dung không trùng. Review frustums/cloud, không suy pose đúng từ exit 0.
- Tea sets: dùng `tea_sets_2` cảnh tĩnh; 120 frame/pose, canonical split và agent visual audit đã có.
  Lead kiểm tra bằng chứng trước human research review; video đầu giữ làm attempt cũ.
- Research: checkpoint size khác PLY size; synchronized FPS khác viewer/upstream FPS;
  10-second VRAM sampling và thermal conditions phải được ghi.
- Failure analysis: chọn cùng camera/crop cho foliage/thin edges, specular/fine texture,
  low-overlap; dẫn artifact IDs và giả thuyết, không tự điền kết luận từ paper.
- Release: retrieval + hashes, không commit raw/checkpoint/PDF/third-party source hoặc secret.

Mỗi PR ghi: mục tiêu/contract, official pinned source/function, thay đổi preprocessing,
lệnh và kết quả thực tế, phần chưa kiểm chứng, người nghiệm thu GPU. AI/static tests
không là bằng chứng model quality, pose acceptance hoặc independent replay.

## Source map cần đọc

| Phần | Pinned source trong `third_party/nerfstudio/nerfstudio/` |
|---|---|
| Camera/split | `data/dataparsers/{nerfstudio,colmap}_dataparser.py`, `data/utils/dataparsers_utils.py` |
| Shared GT | `data/datamanagers/full_images_datamanager.py::_undistort_image` |
| Method defaults | `configs/method_configs.py`, `models/nerfacto.py`, `models/splatfacto.py` |
| Checkpoint loader | `utils/eval_utils.py::eval_setup` và callback |
| Metrics / combined GT-pred | `pipelines/base_pipeline.py::get_average_eval_image_metrics`; hai model metric functions |
| Export | `scripts/exporter.py`; default Nerfacto cần Open3D normals |
| Camera path | `cameras/camera_paths.py::get_path_from_json` |

Toán/paper/reference repositories: [foundations](docs/research/foundations.md),
[paper notes](docs/research/paper_notes.md). Không dùng upstream `main` đoán API pin.

## Bàn giao vận hành sessions

Lead giữ source/registry ổn định khi phiên dài chạy. Member 2 đọc
`training_worker.py` (Gaussian optimizer rebind, checkpoint/RNG/remaining budget);
Member 3 đọc `sessions.py` + partial eval/render/export lifecycle; Member 4 quản lý
`Manage-Session.ps1`/`Session-Worker.ps1`, tmux và safety evidence. Attach/detach
không pause GPU; Stop → chờ paused → Resume là thao tác được kiểm chứng.
Lệnh: [session_operations](docs/session_operations.md).
