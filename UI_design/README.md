# Spatial Studio — sử dụng và quản lý UI

UI local cho project Topic 16: chọn ảnh/dataset, đi trong gallery 3D, xoay quanh
reconstruction, xem một hoặc hai phương pháp, so sánh ảnh và đọc bằng chứng.
Mọi frontend, backend, scripts, tests và tài liệu UI nằm trong thư mục này.
Phần thay đổi nhỏ ở `src/topic16/settings.py` và các caller chỉ xử lý tương thích
registry; các artifact thí nghiệm gốc không bị sửa.

## Mở thành phẩm trên laptop

Server đang được kiểm thử ở **http://127.0.0.1:7016**. Mở bằng trình duyệt.
Để chạy lại, từ root repo trong native Windows PowerShell:

```powershell
.\Invoke-Topic16.ps1 ui
# Tương đương:
.\UI_design\scripts\Start-UI.ps1
```

`auto` cho phép xem artifacts ngay. Khi tiến trình chạy trong Administrator
PowerShell, nó bật inference có GPU guard. Có thể chọn profile rõ ràng:

```powershell
.\UI_design\scripts\Start-UI.ps1 -Profile artifacts
# Administrator PowerShell cho camera mới qua checkpoint:
.\UI_design\scripts\Start-UI.ps1 -Profile inference
```

Nút render báo `ready`, `busy` hoặc `not-enabled`. Hai checkpoint chạy tuần tự.
Không huấn luyện model khi mở UI, chọn dataset, vào gallery hay chuẩn bị assets.
Nút **Render ảnh model** tạo ảnh ở camera hiện tại. Camera đổi trong lúc render
thì kết quả cũ bị hủy/bỏ; cặp kết quả chỉ công bố sau khi cả hai model và kiểm tra
cuối của GPU guard thành công. Preview dừng vẽ trong lúc CUDA chạy.

Port ưu tiên 7016, tự thử đến 7020 nếu bị chiếm. `-Port 7018` yêu cầu đúng port
đó. Launcher chỉ reuse service cùng checkout, catalog revision và profile phù
hợp; mở trình duyệt theo URL server thực sự công bố. Bookmarks thuộc browser
origin, vì vậy đổi port nên backup JSON trước.

## Chuẩn bị / build

Lần đầu hoặc sau khi thay đổi UI:

```powershell
.\UI_design\scripts\Setup-UI.ps1
.\UI_design\scripts\Prepare-UIAssets.ps1
.\UI_design\scripts\Build-UI.ps1
.\UI_design\scripts\Start-UI.ps1
```

Setup dùng Node và packages pin trong `configs/project.psd1: Ui`. Nếu thiếu Node
đúng version, script tải ZIP Windows chính thức, kiểm SHA-256 và giữ trong
`.tools/`. `package.json` được sinh từ registry; `package-lock.json` khóa cả
dependencies gián tiếp. Không cài package Python mới vào môi trường Nerfstudio.
Sau khi đổi pins, chạy `Setup-UI.ps1 -UpdateLock`.

Launcher tìm Conda từ override có sẵn, PATH và registered Python install paths
trên Windows, kể cả Miniconda ở ổ D trong shell mới/elevated. Nếu một máy khác
không register Conda, đặt `$env:TOPIC16_CONDA_EXE` tới `Scripts\conda.exe` rồi dùng
cùng các entrypoints; không cần activate environment.

Prepare đọc đúng matrices `topic16-full-custom/calibration/benchmark/poster`,
không lấy timestamp mới nhất. Mỗi pair phải qua config/checkpoint/source/runtime,
split, evaluation, export và throughput contracts. Tạo cover từ ảnh GT thật,
ảnh absolute RGB error ×4 và một allowlist. Catalog + asset index được publish
bằng một atomic JSON replace tại `artifacts/ui/catalog.json`.

Build kiểm TypeScript và tạo `dist/`. Initial bundle bị giới hạn 180 KiB gzip;
renderer, gallery và Mermaid được load lazy. Spark có exception riêng 1.1 MiB
gzip vì có WASM/worker decoder bên trong. Xem quyết định ở [SPIKE_DECISION.md](SPIKE_DECISION.md).

## Thao tác

- **Collection:** card và ảnh thật của Tea sets, Bonsai, Garden, Room, Poster;
  tìm theo tên/ID. Role của từng scene hiện rõ; Poster là smoke, không aggregate.
- **3D:** drag orbit, scroll zoom, right-drag pan. Chọn Song song / N / S;
  camera sync mặc định bật, có thể tắt để khảo sát riêng. Đổi một↔hai pane giữ
  pose hiện tại. Reset, eval presets, tự xoay, fullscreen, point size, grid/axes,
  camera coverage, WASD walk và Cancel/Retry assets có sẵn.
- **Biểu diễn:** N là point-cloud proxy để điều hướng; S là full Gaussian export
  qua Spark. Nhãn luôn hiện. Ảnh Nerfacto chính xác lấy từ evaluation hoặc nút
  render checkpoint; không gọi point cloud là neural image.
- **Ảnh:** cùng held-out index cho GT/N/S, wipe bằng slider, zoom, ROI lens với
  tọa độ source pixels, absolute error ×4. Latest exact-model render dùng group
  riêng, không trộn camera novel với GT/evaluation cũ và không tạo metric giả.
- **Research:** chart chọn 6 metrics, bảng từng run và đơn vị, diagram pipeline/
  Nerfacto/Splatfacto, zoom, chọn node, SVG export, original review/case figures,
  config/checkpoint/split hashes. Offline FPS, browser FPS và render latency có
  ý nghĩa khác nhau và được ghi nhãn riêng.
- **Gallery:** WASD/arrows, drag look, double-click mouse look, Esc thoát; speed
  slider, guided tour, wall bounds, map/teleport. E/Enter hoặc click tranh mở đúng
  scene; nút Open reconstruction và các DOM cards dùng được qua bàn phím.
  Quay lại gallery giữ vị trí. Có nút mũi tên cho touch/chuột.
- **Bookmarks:** lưu camera, restore scene/view, xóa, backup/import JSON; preview
  trước Merge/Replace. File giới hạn 200 entries/1 MB, kiểm schema và camera.
  Scene bị thiếu được báo, không tự gán sang model khác.
- **Export:** screenshot PNG kèm nhãn model và JSON camera/run/catalog metadata;
  Print/save PDF mở report chỉ đọc và giữ filter/metric/catalog revision. Trình
  duyệt thực hiện Save as PDF; source metrics và hashes không bị sửa.
- **Preferences:** light/dark, VI/EN cho navigation/onboarding, skip/reopen guide,
  tắt shortcuts. Các thuật ngữ nghiên cứu và một số tool labels giữ tiếng Anh.
  Shortcuts 1/2/3 đổi tab, R reset, bị vô hiệu khi nhập text hoặc đang có modal.

Camera tọa độ OpenGL trong split đã là model frame. Không apply lại dataparser
transform và không căn hai phương pháp độc lập. Camera controls có thể đi ngoài
coverage quan sát; chất lượng vùng chưa chụp phụ thuộc reconstruction. Gallery
có wall collision; scene reconstruction chỉ có bounds, không có collision mesh.

## Cấu trúc mã

```text
UI_design/
  frontend/
    main.tsx                 app shell, routes, dataset selection, inference flow
    Viewer.tsx               two adapters, camera controls/sync and lifecycle
    point.worker.ts          binary PLY decoder with transferable typed arrays
    Gallery.tsx              gallery geometry, exhibits, movement, tour/map
    Compare.tsx              saved/live image groups, shared ROI and wipe
    Research.tsx             metrics, charts, diagrams, figures and provenance
    types.ts api.ts           typed catalog/camera/job contracts and HTTP client
    bookmarks.ts             portable backup validation
    global.css               tokens, theme, a11y, print
    studio.module.css        component styling and responsive layout
  backend/
    catalog.py               exact-pair validation and atomic asset publication
    server.py                localhost HTTP, assets/Range, CSRF, profiles
    jobs.py                  owner lease, one active + latest pending, cache
    worker.py                separate native CUDA process and atomic images
    cli.py                   prepare/serve entrypoint
  scripts/                   native PowerShell setup/prepare/build/start/stop/dev/test
  tests/                     CPU, bookmark, fixtures, actual browser/API/inference QA
  spike/                     renderer feasibility test and original measurements
  IMPLEMENTATION_PLAN.md     ordered work and completion evidence
  ACCEPTANCE.md              U01–U40 statuses and precise test limits
```

HTTP process không import Torch. CUDA chỉ được import trong worker do server sở
hữu; worker dùng đúng Conda Python, exact config và checkpoint, kiểm split đã nạp,
giữ shared GPU lock và dùng guard của project. Source snapshots/checkpoints/PNG
gốc và research release gate được giữ nguyên; UI là local research application.

Owner lease 45 giây, heartbeat 10 giây; tab khác được đọc nhưng không giành
inference lease. Tab ẩn/đóng release; expiry hủy pending/active một cách cooperative.
Hủy trong một CUDA/native call chờ call đó trả về; không giả vờ preempt giữa kernel.
Stop chờ worker tối đa 30 giây rồi dừng riêng owned process tree khi cần.

Inference cache giới hạn 2 GiB; eviction chỉ vào `artifacts/ui/jobs`, bảo vệ job
active/pending và cặp thành công gần nhất. Không xóa checkpoint/data/export/report.
Ảnh derived và catalog đang tham chiếu được giữ riêng; recipe error v2 có identity
khác v1. Browser không giữ model toàn bộ trong IndexedDB; adapter dispose GPU
buffers/worker/context khi rời scene và có ngân sách file 600 MiB/3 triệu vertices.

## Thêm một scene đã chạy

1. Hoàn thành paired run/evaluation/export/throughput theo contracts project.
2. Tạo matrix có `status: succeeded`, scene identity và hai **exact config paths**.
3. Đặt matrix trong repo; không dùng một thư mục chứa timestamp để chọn latest.
4. Chạy `Prepare-UIAssets.ps1 -ExtraMatrix 'artifacts/logs/matrices/my-extra.json'`.
5. Builder kiểm toàn bộ contracts, từ chối duplicate scene và publish atomic.
6. Restart UI để dùng catalog revision mới; xem cùng eval camera và kiểm alignment.

Tên chưa có descriptor dùng scene ID/role `additional`; thêm metadata trình bày
vào `catalog.py: LABELS` nếu cần tên đẹp. Không sửa hash của run để ép capability.
Unknown major catalog version bị từ chối; tạo bản chuẩn mới bằng builder, không
ghi đè các record thí nghiệm cũ. UI-only registry migration có negative tests
cho mọi trường thí nghiệm; snapshot legacy vẫn giữ nguyên bytes/hash.

## QA / development / dừng

```powershell
.\UI_design\scripts\Test-UI.ps1
.\UI_design\scripts\Test-UI.ps1 -Browser -Url 'http://127.0.0.1:7016'
.\UI_design\scripts\Dev-UI.ps1
.\UI_design\scripts\Stop-UI.ps1
```

Các bài QA bổ sung dùng server đã chạy và source tools ngay trong thư mục này:

```powershell
. .\UI_design\scripts\Common-UI.ps1
Invoke-UiNode -Arguments @((Join-Path $UiRoot 'tests\api.mjs'))
Invoke-UiNode -Arguments @((Join-Path $UiRoot 'tests\interactions.mjs'))
# Cần primary server ở profile inference; kiểm service phụ artifacts, không render:
Invoke-UiNode -Arguments @((Join-Path $UiRoot 'tests\service.mjs'))
# Actual paired + từng model riêng, chạy tuần tự khi không chạy browser QA khác:
Invoke-UiNode -Arguments @((Join-Path $UiRoot 'tests\ui-inference.mjs'))
```

Service dùng Windows exclusive socket binding để một cổng không có hai listeners.
Không sửa `SO_REUSEADDR` về mặc định Python khi chỉnh launcher. `service.mjs`
kiểm strict port, auto fallback, shutdown/process exit và giữ nguyên server chính.

Browser QA dùng Brave/Chrome/Edge đã cài trên Windows, PLY thật và screenshot thực.
Fixture E2E trong CI dùng dữ liệu synthetic riêng, không gọi là benchmark GPU.
Actual inference QA ở `tests/inference.mjs`; chạy qua `Invoke-UiNode` từ
`Common-UI.ps1` khi cần kiểm lại. Không cần rerun toàn bộ thí nghiệm để mở UI.
Chi tiết test/evidence: [ACCEPTANCE.md](ACCEPTANCE.md).

Brave/Chrome/Edge cần WebGL2; nếu graphics context mất hoặc model tải lỗi, pane
báo lỗi và cho Retry/Cancel, saved images/metrics vẫn xem được. Nếu inference
fails, cặp thành công trước được giữ; không ghép nửa pair. GPU guard dừng đúng
điều kiện project, UI báo lý do từ worker. Paths Windows có spaces/tiếng Việt
được derive từ script location; không cần activate shell.

Dependency formatting reference: [Prettier 3.6](https://prettier.io/blog/2025/06/23/3.6.0).
Notices từ direct runtime packages đã cài: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
