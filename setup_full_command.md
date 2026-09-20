# Full Setup & Command Runbook

> Dự án: **Photos to 3D — Nerfacto vs Splatfacto/3D Gaussian Splatting**
> Runtime chuẩn: **WSL2/Linux + Nerfstudio v1.1.5 + gsplat 1.4.0**
> Protocol chuẩn: **30k iterations, seed 42, downscale 2, eval interval 8**
> Kiến trúc và lý do chọn từng thành phần: [`Construction_architect.md`](Construction_architect.md)

Tài liệu này là danh sách lệnh vận hành đầy đủ. Chạy theo thứ tự; không cần tự clone
hoặc `pip install` phiên bản khác ngoài các script đã cung cấp.

## 0. Quy ước quan trọng

- Các command bên dưới chạy trong **Ubuntu/WSL2 Bash**, không chạy trực tiếp trong
  Windows CMD.
- Đường dẫn Windows `D:\Desktop_informations\...\Topic_16_CV` tương ứng với:

  ```bash
  /mnt/d/Desktop_informations/SGK năm 4/SGK kì 1 năm 4/ComputerVision - MToan/CVCourse/Project/Topic_16_CV
  ```

- Luôn đặt đường dẫn có khoảng trắng trong dấu nháy kép.
- Không cài `gsplat main`, Nerfstudio `main` hoặc PyTorch khác đè lên runtime pin.
- Dataset, paper PDF, third-party repos và checkpoints đã được `.gitignore`.
- Không chạy đồng thời hai training job trên RTX A4500 16 GB.

## 1. Mở WSL và vào project

### 1.1 Project đã có sẵn trên ổ D

Từ PowerShell:

```powershell
wsl --update
wsl
```

Trong WSL Bash:

```bash
cd "/mnt/d/Desktop_informations/SGK năm 4/SGK kì 1 năm 4/ComputerVision - MToan/CVCourse/Project/Topic_16_CV"
pwd
```

### 1.2 Hoặc clone mới từ GitHub

```bash
cd /path/to/your/workspace
git clone https://github.com/HelcurtLordno1/Photos_to_3d-NeRF-and-guassian-splatting.git Topic_16_CV
cd Topic_16_CV
```

Từ đây về sau, lưu root để quay lại sau khi activate environment:

```bash
export TOPIC16_ROOT="$(pwd -P)"
```

## 2. Cài host tools một lần

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  git \
  curl \
  unzip \
  ffmpeg \
  make \
  ripgrep
```

Kiểm tra GPU. Lệnh này phải thấy `NVIDIA RTX A4500 Laptop GPU` và khoảng 16384 MiB:

```bash
nvidia-smi
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv
```

Trong WSL2, không cài Linux NVIDIA display driver đè lên Windows NVIDIA driver. Pixi
sẽ cung cấp CUDA toolkit/runtime phù hợp cho environment của project.

## 3. Cài Pixi

```bash
curl -fsSL https://pixi.sh/install.sh | bash
source ~/.bashrc
pixi --version
```

Nếu `pixi` vẫn chưa có trong `PATH`, đóng terminal WSL, mở lại và `cd` về project.

## 4. Preflight host

```bash
cd "$TOPIC16_ROOT"
make help
make check
```

Trước khi environment được activate, dòng `ns-train pending` là bình thường. Các
host tools hoặc `nvidia-smi` bị `missing` thì phải sửa trước bước tiếp theo.

Kiểm tra disk:

```bash
df -h "$TOPIC16_ROOT"
du -sh "$TOPIC16_ROOT"
```

Nên còn tối thiểu 20 GiB để downloader benchmark chạy; thực tế nên dự trù 30–40 GiB
cho archive, ba scene, checkpoint và renders.

## 5. Clone runtime repo và tạo environment

Lệnh `make repos` clone đúng commit Nerfstudio đã pin vào `third_party/nerfstudio`:

```bash
cd "$TOPIC16_ROOT"
make repos
make setup
```

`make setup` chạy upstream Pixi `post-install`, cài COLMAP/hloc/tiny-cuda-nn và kiểm
tra PyTorch có nhìn thấy CUDA hay không.

### 5.1 Activate environment trong terminal hiện tại

```bash
cd "$TOPIC16_ROOT/third_party/nerfstudio"
pixi shell
```

Sau khi prompt Pixi xuất hiện, quay về project:

```bash
cd "$TOPIC16_ROOT"
```

Mỗi terminal mới cần lặp lại hai lệnh activate trên trước khi chạy `ns-*`, training
hoặc evaluation.

### 5.2 Kiểm tra runtime sau activate

```bash
which python
which ns-train
ns-train --help
ns-process-data --help
ns-eval --help

python - <<'PY'
import torch
import gsplat
import nerfstudio

print("torch:", torch.__version__)
print("torch CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0))
print("gsplat:", getattr(gsplat, "__version__", "unknown"))
print("nerfstudio:", getattr(nerfstudio, "__version__", "unknown"))
PY

make check
```

## 6. Download paper và source repo nghiên cứu

### 6.1 Bảy PDF paper cốt lõi

```bash
cd "$TOPIC16_ROOT"
make papers
ls -lh docs/research/papers/
```

### 6.2 Reference repositories

Không cần bước này để train. Chỉ tải khi cần đọc/tái lập code paper:

```bash
bash scripts/download_repos.sh research
```

Lệnh trên lấy exact commits của:

- original NeRF,
- MultiNeRF,
- Instant-NGP và submodules,
- original INRIA Gaussian Splatting và submodules,
- gsplat,
- COLMAP.

Tải cả runtime lẫn reference repos trong một lệnh:

```bash
bash scripts/download_repos.sh all
```

Kiểm tra các snapshot:

```bash
for repo in third_party/*/.git; do
  repo_dir="${repo%/.git}"
  printf '%-45s ' "$repo_dir"
  git -C "$repo_dir" rev-parse --short HEAD
done
```

## 7. Download datasets đã chốt

### 7.1 Smoke dataset: Nerfstudio poster

Phải chạy trong Pixi environment đã activate:

```bash
cd "$TOPIC16_ROOT"
make data-smoke
```

Kiểm tra:

```bash
test -f data/raw/nerfstudio/poster/transforms.json
find data/raw/nerfstudio/poster -maxdepth 2 -type d | sort
```

### 7.2 Benchmark: Mip-NeRF 360

Lệnh này tải archive chính thức 12,535,427,936 bytes, hỗ trợ resume, kiểm tra size và
ZIP, sau đó chỉ extract `garden`, `bonsai`, `room`:

```bash
cd "$TOPIC16_ROOT"
make data-benchmark
```

Hoặc gọi trực tiếp:

```bash
bash scripts/download_datasets.sh benchmark
```

Download cả smoke và benchmark:

```bash
bash scripts/download_datasets.sh all
```

Kiểm tra layout:

```bash
for scene in garden bonsai room; do
  test -d "data/raw/mipnerf360/$scene/images_2"
  test -d "data/raw/mipnerf360/$scene/sparse/0"
  echo "$scene: OK"
done

du -sh data/.cache/360_v2.zip data/raw/mipnerf360/*
```

Giữ `data/.cache/360_v2.zip`: lần chạy sau downloader sẽ kiểm tra và bỏ qua network
download. Không commit hoặc upload archive vào GitHub.

## 8. Smoke gate bắt buộc

Đảm bảo Pixi environment đang active và không có workload GPU khác:

```bash
nvidia-smi
cd "$TOPIC16_ROOT"
```

Train cả hai methods:

```bash
bash scripts/train.sh nerfacto poster
bash scripts/train.sh splatfacto poster
```

Lấy config mới nhất:

```bash
NERF_POSTER_CONFIG="$(find artifacts/runs/poster/nerfacto -mindepth 2 -maxdepth 2 -type f -name config.yml | sort | tail -n 1)"
SPLAT_POSTER_CONFIG="$(find artifacts/runs/poster/splatfacto -mindepth 2 -maxdepth 2 -type f -name config.yml | sort | tail -n 1)"

printf 'Nerfacto:  %s\n' "$NERF_POSTER_CONFIG"
printf 'Splatfacto: %s\n' "$SPLAT_POSTER_CONFIG"
test -n "$NERF_POSTER_CONFIG"
test -n "$SPLAT_POSTER_CONFIG"
```

Evaluate đúng held-out split của từng config:

```bash
bash scripts/evaluate.sh "$NERF_POSTER_CONFIG"
bash scripts/evaluate.sh "$SPLAT_POSTER_CONFIG"
```

Kiểm tra outputs:

```bash
find artifacts/metrics/poster -type f | sort
find artifacts/logs/poster -type f | sort
find artifacts/renders/poster -type f | head -n 20
```

Smoke gate chỉ pass khi cả hai có checkpoint, finite metrics JSON, renders và không
OOM/NaN. Không đưa metrics `poster` vào bảng benchmark cuối.

### 8.1 Diagnostic run ngắn khi cần debug

Command sau chỉ dùng debug, không đưa vào primary results:

```bash
bash scripts/train.sh nerfacto poster --max-num-iterations 1000
bash scripts/train.sh splatfacto poster --max-num-iterations 1000
```

## 9. Chạy benchmark chính

Protocol mặc định đã nằm trong `configs/project.env`:

```bash
sed -n '1,200p' configs/project.env
```

Chạy 3 scenes × 2 methods rồi evaluate ngay run vừa tạo:

```bash
for scene in garden bonsai room; do
  for method in nerfacto splatfacto; do
    echo "===== TRAIN $scene / $method ====="
    bash scripts/train.sh "$method" "$scene"

    config="$(find "artifacts/runs/$scene/$method" -mindepth 2 -maxdepth 2 -type f -name config.yml | sort | tail -n 1)"
    test -n "$config"

    echo "===== EVAL $scene / $method ====="
    bash scripts/evaluate.sh "$config"
  done
done
```

Xem toàn bộ metrics:

```bash
find artifacts/metrics -type f -name metrics.json -print | sort
```

Xem nhanh JSON nếu có `jq`:

```bash
sudo apt install -y jq
find artifacts/metrics -type f -name metrics.json -print0 \
  | xargs -0 -n1 sh -c 'echo "===== $0"; jq . "$0"'
```

Kiểm tra logs/timing/GPU:

```bash
find artifacts/logs -type f -name timing.env -print -exec sed -n '1,20p' {} \;
find artifacts/logs -type f -name gpu.csv -print
```

## 10. Phone capture và COLMAP processing

### 10.1 Tạo layout ảnh raw

Thay `object_v1` bằng slug lowercase của scene:

```bash
mkdir -p data/raw/custom/object_v1/train
mkdir -p data/raw/custom/object_v1/eval
```

Copy ảnh train/eval vào hai folder. Không để một ảnh xuất hiện trong cả hai split.
Sau đó kiểm tra count:

```bash
find data/raw/custom/object_v1/train -maxdepth 1 -type f | wc -l
find data/raw/custom/object_v1/eval -maxdepth 1 -type f | wc -l
```

### 10.2 Process bằng ns-process-data/COLMAP

```bash
bash scripts/process_capture.sh object_v1 \
  data/raw/custom/object_v1/train \
  data/raw/custom/object_v1/eval
```

Kiểm tra output:

```bash
test -f data/processed/custom/object_v1/transforms.json
find data/processed/custom/object_v1 -maxdepth 2 -type d | sort
```

Xem log/visualization COLMAP và chỉ train khi ít nhất khoảng 90% ảnh train register,
camera frustums hợp lý và sparse cloud không tách thành cluster sai.

### 10.3 Train và evaluate custom scene

```bash
for method in nerfacto splatfacto; do
  bash scripts/train.sh "$method" custom:object_v1

  config="$(find "artifacts/runs/custom-object_v1/$method" -mindepth 2 -maxdepth 2 -type f -name config.yml | sort | tail -n 1)"
  test -n "$config"
  bash scripts/evaluate.sh "$config"
done
```

## 11. Viewer, render và export

### 11.1 Mở model đã train

```bash
ns-viewer --load-config "$NERF_POSTER_CONFIG"
```

Hoặc Splatfacto:

```bash
ns-viewer --load-config "$SPLAT_POSTER_CONFIG"
```

Mở URL viewer do terminal in ra, mặc định dùng port `7007`. Nếu chạy remote WSL/SSH,
forward port 7007 trước.

### 11.2 Export Gaussian PLY

```bash
mkdir -p artifacts/exports/poster/splatfacto
ns-export gaussian-splat \
  --load-config "$SPLAT_POSTER_CONFIG" \
  --output-dir artifacts/exports/poster/splatfacto
```

### 11.3 Export point cloud từ Nerfacto

```bash
mkdir -p artifacts/exports/poster/nerfacto
ns-export pointcloud \
  --load-config "$NERF_POSTER_CONFIG" \
  --output-dir artifacts/exports/poster/nerfacto
```

`artifacts/exports/` có thể rất lớn và đã được `.gitignore`; không dùng `git add -f`
để commit model binary lên GitHub.

### 11.4 Render camera path

Trong viewer, tạo và lưu camera path JSON, sau đó:

```bash
mkdir -p artifacts/videos
ns-render camera-path \
  --load-config "$NERF_POSTER_CONFIG" \
  --camera-path-filename /path/to/camera_path.json \
  --output-path artifacts/videos/poster_nerfacto.mp4
```

Lặp lại cùng camera path/resolution cho Splatfacto để so sánh công bằng.

## 12. GPU monitoring thủ công

`scripts/train.sh` đã tự tạo GPU CSV. Khi cần monitor một process khác:

```bash
bash scripts/monitor_gpu.sh artifacts/logs/manual_gpu.csv 10
```

Hoặc xem trực tiếp:

```bash
watch -n 2 nvidia-smi
```

Dừng monitor foreground bằng `Ctrl+C`.

## 13. Kiểm tra code trước commit

```bash
cd "$TOPIC16_ROOT"
bash -n scripts/*.sh scripts/lib/*.sh
make help
make check
git status --short
```

Nếu đã cài ShellCheck:

```bash
sudo apt install -y shellcheck
shellcheck scripts/*.sh
```

Không chạy GPU training trong CI thông thường. CI/local lint chỉ kiểm tra scripts và
code nhóm; smoke training chạy trên máy RTX A4500.

## 14. Git workflow và push GitHub

Remote chính:

```text
https://github.com/HelcurtLordno1/Photos_to_3d-NeRF-and-guassian-splatting.git
```

Kiểm tra trước commit:

```bash
git remote -v
git branch --show-current
git status --short
git check-ignore -v data/.cache/360_v2.zip 2>/dev/null || true
```

Commit/push thay đổi source và tài liệu:

```bash
git add .
git status --short
git commit -m "Update project architecture and reproducible pipeline"
git push origin main
```

Không dùng `git add -f` cho dataset, PDF, `third_party/`, checkpoint hoặc renders.
Không dùng force push trừ khi nhóm đã thống nhất và hiểu lịch sử sẽ bị thay đổi.

Pull thay đổi mới trước khi bắt đầu làm việc:

```bash
git pull --ff-only origin main
```

## 15. Troubleshooting nhanh

### `nvidia-smi` không chạy

```bash
wsl.exe --shutdown
```

Sau đó cập nhật NVIDIA Windows driver hỗ trợ WSL, mở lại WSL và kiểm tra. Không tiếp
tục setup Python cho đến khi GPU xuất hiện.

### `pixi` không tìm thấy

```bash
source ~/.bashrc
command -v pixi
```

### `ns-train` không tìm thấy

```bash
cd "$TOPIC16_ROOT/third_party/nerfstudio"
pixi shell
cd "$TOPIC16_ROOT"
command -v ns-train
```

### CUDA extension compile lỗi

```bash
cd "$TOPIC16_ROOT"
git -C third_party/nerfstudio rev-parse HEAD
rg 'NERFSTUDIO_COMMIT|GSPLAT_COMMIT' configs/project.env
make setup
```

Không chữa lỗi bằng cách nâng ngẫu nhiên PyTorch/gsplat.

### Splatfacto OOM

```bash
nvidia-smi
rg 'DOWNSCALE_FACTOR|TRAIN_ITERATIONS' configs/project.env
```

Đóng workload GPU khác và xác nhận đang dùng `DOWNSCALE_FACTOR=2`. Nếu vẫn OOM,
định nghĩa một low-memory protocol riêng trong config/tài liệu; không thay duy nhất
một run rồi trộn với baseline.

### Dataset download bị ngắt

Chạy lại cùng command; `curl --continue-at -` sẽ resume:

```bash
make data-benchmark
```

### Xem lỗi run gần nhất

```bash
find artifacts/logs -type f -name train.log | sort | tail -n 1
latest_log="$(find artifacts/logs -type f -name train.log | sort | tail -n 1)"
tail -n 100 "$latest_log"
```

## 16. Thứ tự tối thiểu cần nhớ

```bash
cd "$TOPIC16_ROOT"

# Một lần cho máy/repo
make check
make repos
make setup

# Mỗi terminal mới: activate Pixi rồi trở về project
cd "$TOPIC16_ROOT/third_party/nerfstudio"
pixi shell
cd "$TOPIC16_ROOT"

# Data và smoke gate
make data-smoke
bash scripts/train.sh nerfacto poster
bash scripts/train.sh splatfacto poster

# Sau khi smoke pass
make data-benchmark
```

Sau đó chạy experiment matrix ở section 9; mọi kết quả phải được evaluate bằng đúng
`config.yml` do run đó sinh ra.
