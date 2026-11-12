# Upgrade plan — Spatial Studio: Capture Intelligence

Ngày lập: 20/10/2026. Cập nhật: 21/10/2026 theo yêu cầu dùng chung UI. Trạng thái: đề xuất triển khai, chưa phải tính năng hoặc kết quả đã nghiệm thu.

**Quyết định đề xuất:** giữ nguyên **baseline training code + baseline benchmark**; xây code nghiên cứu và outputs mới trong **`upgrade/`**; mở rộng **một Spatial Studio dùng chung tại `UI_design/`** để xem toàn bộ benchmark, reconstruction và graphs. UI là lớp tích hợp được phép phát triển; dữ liệu, kết quả và logic training baseline vẫn được bảo toàn. Đặt mục tiêu hoàn thành code trong **một ngày triển khai**, tách riêng thời gian setup, GPU execution và nghiên cứu xác nhận.

## 1. Nhận xét thẳng về proposal của DeepSeek

Mình đồng ý với hướng “biết trước khi train”. Nó tạo thêm một khả năng hữu ích: trước khi chạy reconstruction dài, người dùng có cơ sở để quyết định dữ liệu đã ổn chưa, nên chạy phương pháp nào theo ngân sách, và nên bổ sung quan sát ở đâu.

Tuy nhiên, proposal đang đi quá nhanh từ ý tưởng tới lời hứa định lượng:

| Ý trong proposal | Đánh giá và cách sửa trong upgrade |
|---|---|
| Dự đoán trước PSNR từ capture | Là giả thuyết nghiên cứu đáng thử; phải đo sai số trên dữ liệu không dùng để fit/tune. |
| Khoảng 20 samples đủ train predictor | Nhiều subsets từ một video vẫn tương quan. Hiện chỉ có bốn scenes phân tích chính; Poster là smoke, không tự trở thành một scene nghiên cứu độc lập. |
| Random cross-validation trên subsets | Dễ rò rỉ scene identity. Phải giữ toàn bộ subsets/seeds của một scene trong cùng nhóm train hoặc test. |
| 10k steps đủ để suy chất lượng cuối | Chưa được chứng minh. Nhãn 10k chỉ chứng minh chất lượng ở 10k; dự báo 30k cần nhãn/validation 30k riêng. |
| “Thêm 15 frame tăng khoảng 2 dB” | Chưa suy ra được từ tương quan giữa features và PSNR. Cần intervention thực tế và ảnh đối chứng. |
| Lấy gradient predictor để chọn góc chụp | Gradient boosting dạng cây không có gradient trơn theo cách diễn đạt này; ngay cả model khả vi cũng không biến feature attribution thành tác động nhân quả. Dùng candidate scoring có ràng buộc và kiểm chứng sau. |
| Ensemble/dropout/variance Gaussian là uncertainty | Ensemble chỉ cung cấp một proxy; Nerfacto hiện tại chưa có sẵn MC dropout đã được xác nhận. Độ phân tán Gaussian attributes không mặc nhiên là uncertainty của ảnh. |
| “Smart selection chắc chắn thắng uniform” | Không đúng cho mọi scene. Mất overlap hoặc tập trung vào vùng sắc nét có thể làm kết quả kém hơn. Cần đối chứng cùng số ảnh. |
| “Splatfacto thắng toàn diện, không còn gì khám phá” | Kết quả hiện tại giới hạn ở scenes, seed, budget và runtime đã đo. Dữ liệu ít, chất lượng capture, ngân sách thời gian và storage vẫn là câu hỏi mở. |
| Mặc định 4–6 tuần | Không dùng cách chia này cho triển khai của chúng ta. Code có timebox một ngày; số giờ GPU được lập riêng theo run thực tế. |

**Định vị hợp lý:** một hệ thống hỗ trợ quyết định có truy vết, có thể từ chối dự báo khi thiếu bằng chứng. Chưa tuyên bố thuật toán đầu tiên, predictor tổng quát hoặc cải thiện chất lượng đã được chứng minh.

## 2. Điều gì làm bản upgrade đáng giá?

Tên bản phát triển: **upgrade — Spatial Studio: Capture Intelligence**.

Hai câu hỏi nghiên cứu trong scope đầu:

1. **Trước training:** features của capture có dự báo được chất lượng reconstruction tốt hơn predictor đơn giản chỉ biết số ảnh và method không?
2. **Với cùng tài nguyên:** chọn frame theo coverage/overlap có đạt chất lượng tốt hơn, hoặc giữ chất lượng với ít ảnh hơn, so với nearest-uniform selection không?

Pilot-assisted learning-curve forecast là nhánh mở rộng sau, không nằm trong critical path ngày đầu.

Khả năng mới mà người dùng nhìn thấy:

> Trong cùng Spatial Studio: chọn scene → xem Baseline / Upgrade / Compare → kiểm tra ảnh cùng camera và graphs chất lượng–chi phí → xem capture audit và dự báo nếu có đủ bằng chứng.

Điểm thuyết phục khi bảo vệ là chuỗi **dữ liệu → dự báo → quyết định → kết quả kiểm chứng**, cùng chi phí GPU đã tiết kiệm hoặc phát sinh. Giá trị nghiên cứu nằm ở kết quả thực nghiệm và phạm vi kết luận; UI giúp người khác kiểm tra chuỗi này.

## 3. Tách baseline và upgrade: quyết định kiến trúc

### 3.1. Giữ root hiện tại là baseline

Không di chuyển training source hiện tại vào thư mục `baseline/`: việc đó có thể làm hỏng scripts, manifests và đường dẫn đang hoạt động. Training pipeline tại root chính là baseline; `UI_design/` trở thành lớp trình bày chung, còn implementation nghiên cứu mới nằm trong `upgrade/`.

```text
Topic_16_CV/
├── Invoke-Topic16.ps1             # giữ commands baseline; ui mở Spatial Studio chung
├── configs/project.psd1          # baseline registry: giữ nguyên
├── scripts/                     # baseline scripts: giữ nguyên
├── src/topic16/                  # baseline implementation: giữ nguyên
├── UI_design/                   # UI CHUNG: Baseline / Upgrade / Compare
│   ├── frontend/                # gallery, workspace, benchmark, capture, graphs
│   └── backend/                 # baseline/upgrade providers, catalog và asset API
├── data/                        # baseline data: giữ nguyên
├── artifacts/                   # baseline research outputs giữ nguyên; ui/ là cache chung
├── reports/topic16-full/         # baseline benchmark/report: giữ nguyên
├── deepseek_ideas.md
├── upgrade_plan.md
└── upgrade/                     # toàn bộ bản phát triển mới
    ├── README.md
    ├── Invoke-Upgrade.ps1
    ├── configs/project.psd1      # registry độc lập cho upgrade
    ├── scripts/
    ├── src/topic16_upgrade/
    ├── tests/
    ├── data/                   # input/subsets phát sinh của upgrade
    ├── artifacts/              # checkpoints, features, jobs, models mới
    └── reports/                # study và comparison mới
```

Tái sử dụng core bằng **source snapshot có nguồn gốc**: mang các module cần thiết sang upgrade và chỉnh namespace/imports tại bản sao. Chấp nhận duplication có kiểm soát cho training pipeline để chạy riêng; **không copy frontend, backend UI, Node environment hoặc tạo app UI thứ hai**. Shared UI đọc outputs qua providers, không trở thành nơi chứa thuật toán upgrade.

### 3.2. Ranh giới bắt buộc

- Upgrade không import trực tiếp `src/topic16` của baseline, không monkey-patch hoặc sửa validator cũ.
- Launcher xác minh `topic16_upgrade.__file__` thuộc cây upgrade; Python path không âm thầm fallback sang root baseline.
- Root/config/data/output của upgrade suy từ `$PSScriptRoot`; hỗ trợ Windows paths có dấu và khoảng trắng.
- Mỗi bản giữ executable pins tại `configs/project.psd1` của chính bản đó. Upgrade khởi đầu bằng cùng training/runtime/safety pins; mọi thay đổi được ghi riêng.
- Protocols mới như `capture-subset-10k-v1`, `capture-confirm-30k-v1` chỉ tồn tại ở upgrade. Không sửa enum `primary/diagnostic/repeat` của baseline để nhét thí nghiệm mới vào.
- Upgrade không tự gọi research toàn bộ baseline, không tự regenerate reports hoặc sửa run manifests baseline. Shared UI được rebuild catalog/cache dẫn xuất khi có outputs mới.
- Chỉ có một UI service, port range hiện tại 7016–7020, một Node build, một gallery/workspace và một owner lease. Không tạo thêm service 7116 hoặc sao chép các feature hiện có.
- Shared UI có baseline provider giữ validation cũ và upgrade provider kiểm schema mới. Không nới validator baseline để chấp nhận mọi protocol upgrade.
- Core upgrade không import training core baseline. Shared UI được giữ baseline adapter hiện có và đọc upgrade index bằng JSON/CPU adapter; không import Torch hoặc chạy training trong HTTP process.
- GPU jobs giữa hai bản vẫn phải tuần tự, dù source/output đã tách.

### 3.3. Khóa GPU giữa hai bản là chi tiết quan trọng

Baseline hiện khóa byte tại `artifacts/logs/gpu.lock` theo root. Nếu chỉ copy code và đổi root, hai bản sẽ có hai locks khác nhau và vẫn có thể cùng chiếm GPU.

Trong cùng checkout, upgrade phải acquire **đúng lock hiện có của baseline**, rồi dùng safety guard/logs của upgrade. Đây chỉ là điểm phối hợp tài nguyên; không dùng nó làm nơi lưu training logs hoặc sửa artifact nghiên cứu cũ. Tách lock acquisition khỏi log root trong code upgrade để tránh nested acquisition/deadlock.

Khi upgrade được đặt trong checkout riêng, phải cấu hình chung lock path trước khi chạy GPU cạnh baseline. Không tự nhận rằng hai locks theo hai root đã bảo vệ toàn máy.

### 3.4. Dataset và environment

- Trên máy hiện tại, có thể đọc baseline data qua đường dẫn explicit, kiểm hashes và chỉ mở để đọc. Không copy lại toàn bộ official archives.
- Subset manifests, canonical derivatives mới và checkpoints luôn nằm dưới upgrade. Không hardlink ảnh rồi thực hiện chỉnh sửa tại chỗ.
- Trên máy clone mới, upgrade có setup/data entrypoints độc lập và tạo dữ liệu trong cây của nó; không yêu cầu chạy training baseline trước.
- Python environment mặc định riêng, dự kiến `topic16-upgrade-ns115`; shared UI tiếp tục dùng Node dependencies/build hiện có. Không `pip install` thêm vào environment baseline.
- Có thể tái sử dụng environment baseline đã xác minh chỉ khi không thay packages; lựa chọn này phải explicit và được ghi provenance. Setup/build environment có thể dài hơn thời gian viết code.

## 4. Đóng băng baseline trước triển khai

Việc viết plan hiện tại chưa tạo snapshot, Git tag hoặc backup. Khi bắt đầu implementation:

1. Ghi source revision, trạng thái working tree và snapshot các thay đổi local liên quan; một tag trỏ vào HEAD không bảo toàn được uncommitted changes.
2. Tạo `upgrade/reports/baseline-inventory.json`: danh sách 10 run keys, matrices, registry/source/runtime identity, split/config/checkpoint/export hashes, report references và tình trạng tồn tại.
3. Phân biệt **baseline code hiện tại** với **source của benchmark gốc**. Kết quả gốc ghi experiment commit `dd71887cec246234d10c298dc6da94877c1d407d`; source adapter/UI về sau có thể khác. Giữ cả hai identities.
4. Đối chiếu inventory với manifests/hash records có sẵn. Full hashing file lớn là bước integrity tùy chọn có ghi thời gian; không giả rằng việc tạo inventory tự chứng minh mọi byte.
5. Lưu bản sao độc lập của dữ liệu không có trong Git khi có nơi lưu phù hợp. Snapshot code không thay backup video/checkpoints.
6. Sau implementation và một phiên upgrade thực, kiểm tra baseline training source/config/report cùng các artifact được bảo vệ vẫn giữ identity. UI tích hợp có source revision mới và QA riêng; không đòi hash của UI đang phát triển giống snapshot UI cũ.

Từ đầu tới cuối: không xóa attempts cũ, không cleanup checkpoint baseline để lấy chỗ cho upgrade. Snapshot trước tích hợp giữ cả UI nguyên bản để truy lại phiên bản cũ; bản làm việc chỉ duy trì một shared UI.

## 5. Code upgrade trong một ngày: phạm vi chốt

Một ngày là **timebox triển khai mục tiêu**, với repo/runtime hiện có làm đầu vào. Đầu ra là pipeline chạy được và có QA phù hợp. Xác nhận predictor hoặc chất lượng scene phụ thuộc dữ liệu và GPU execution; không thể suy từ việc code đã xong.

### A. Capture audit và feature extraction

Đầu vào: train observations và poses hợp lệ. Đầu ra: `capture-features.json`, per-frame table, coverage figure và provenance.

- Blur: thống kê Laplacian variance trên ảnh chuẩn hóa kích thước; dùng như chỉ báo, không coi texture ít là blur chắc chắn.
- Exposure: clipping sáng/tối, luminance distribution; ghi rằng khác nội dung ảnh cũng làm histogram thay đổi.
- Redundancy: khoảng cách ảnh và pose; chọn ngưỡng từ training/calibration partition.
- Coverage: angular/elevation bins, khoảng cách camera chuẩn hóa theo scene, hướng nhìn. Scene unbounded không ép vào sphere quanh object nếu giả định không phù hợp.
- Overlap: track visibility của sparse points trong các train frames; lưu missing values nếu không có observations phù hợp, không điền số giả.
- Features không đọc held-out RGB hoặc metrics. Sparse model có nguồn transductive SfM phải được ghi nhãn đúng; visibility features chỉ tổng hợp train observations.

### B. Selector có đối chứng

Hai recipes ban đầu: `uniform` và `coverage-overlap`.

- Cùng train frame pool, cùng số ảnh, cùng held-out eval và canonical camera frame.
- Recipe mới cân bằng coverage, overlap, sharpness và redundancy; giới hạn số tham số để tránh tuning theo eval.
- Candidate scoring/greedy selection phải deterministic với seed, ghi rõ lý do và thứ tự chọn.
- Đây là chọn lại trong tập đã chụp. Gợi ý camera để chụp thêm là đầu ra khác, ghi mức hỗ trợ hình học và chưa hứa tăng PSNR.

### C. Predictor nhẹ với phạm vi rõ ràng

Target đầu tiên: **PSNR theo method và budget xác định**. SSIM/LPIPS tiếp tục đo thật; chỉ thêm predictor cho chúng khi đủ bằng chứng.

- Model khởi đầu: regularized linear regression trên NumPy đã có, ít features, chuẩn hóa chỉ bằng training fold. Chưa thêm gradient boosting/dependency mới trong critical path.
- So với predictor mean theo method/budget và predictor chỉ dùng số ảnh + method.
- Mỗi prediction ghi model ID, feature schema, training groups, target budget, input range và validation status.
- Bản đầu chỉ có `capture-only` forecast. Schema dành chỗ cho `pilot-assisted` về sau; chưa xây thêm workflow học learning curve trong ngày đầu. Short runs ở E1/E2 hiện chỉ tạo nhãn đúng budget và kiểm chứng selector.
- Khi chưa có model phù hợp: hiển thị `insufficient-evidence`, vẫn cho xem audit/selection. Không phát sinh PSNR giả để lấp UI.
- Ngày đầu chỉ báo lỗi validation và phạm vi features/budget đã thấy; chưa xây calibrated prediction intervals. Chưa đủ dữ liệu thì không gắn nhãn “95% confidence”.

### D. Experiment queue và evidence

- Dry-run in ra run matrix, số jobs mới, cache hits, dung lượng dự kiến và ETA có nguồn.
- Tái sử dụng đúng kết quả hoàn tất qua experiment key: variant/source/runtime + scene/capture group + subset/split + method + seed + budget/schedule + resolution + evaluator + safety identity.
- Chạy training riêng evaluation; evaluate đúng generated config/checkpoint. Không load “latest”.
- Resume sau interruption, không làm lại completed jobs; job hỏng hoặc half-pair không trở thành bằng chứng hoàn chỉnh.
- Resume giữ optimizer/scheduler/RNG và total schedule. Run có schedule 10k riêng mang identity khác và không được đổi thành checkpoint trung gian của schedule 30k; ngày đầu không xây extrapolator learning curve.

### E. Một UI chung: benchmark, visuals và showcase

Mở rộng `UI_design/` hiện tại, giữ gallery, workspace, camera controls, image comparison, bookmarks và research diagrams. Không redesign hoặc viết lại các phần đã chạy tốt.

Luồng chọn: **Scene → Baseline / Upgrade / Compare → Method → Run/recipe/budget**. Method N/S và variant Baseline/Upgrade là hai trục độc lập:

- `Baseline · N vs S` hoặc `Upgrade · N vs S`: so sánh hai biểu diễn trong cùng variant/condition.
- `Baseline vs Upgrade · cùng Nerfacto` hoặc `cùng Splatfacto`: nhìn tác động recipe, tránh lẫn thay đổi method vào cải thiện upgrade.
- Bảng benchmark thấy toàn bộ completed runs, có filters theo scene/variant/method/views/budget/seed/evaluator. Không gộp nhiều scenes thành một overall score tùy tiện; Poster có nhãn smoke.

Chốt **bốn nhóm visual**, tái sử dụng chart primitives, SVG và components sẵn có; không thêm chart framework lớn:

| Nhóm visual | Thiết kế và ý nghĩa |
|---|---|
| Ảnh và reconstruction | GT + A/B cùng held-out camera, wipe, shared ROI và fixed-scale error map. Dual 3D sync chỉ khi có exports và camera frame đã khớp; thiếu export vẫn xem ảnh/metrics, không bắt export mọi pilot. N giữ nhãn point-cloud proxy. |
| Chất lượng–chi phí | Scatter PSNR/LPIPS theo training time; bảng/bar cho VRAM, checkpoint/export size và FPS. Mỗi điểm là run thật, click để mở ảnh và provenance. Pareto chỉ tính trong cùng scene và measurement scope phù hợp. |
| Capture và số views | Đường metric theo 30/60/105 train views, tách method/budget/selector; camera coverage trước/sau lựa chọn và thumbnails giữ/bỏ. Chỉ nối những conditions cùng study; không nội suy thành kết quả đã đo. |
| Forecast khi có bằng chứng | Predicted-vs-observed với đường y=x, per-scene error và MAE so với simple predictor. Chưa đủ nhãn thì hiện trạng thái thiếu bằng chứng, không vẽ giả accuracy/confidence. |

Quy ước xuyên suốt: màu nhận diện variant, nét/marker nhận diện method, legend và units rõ; baseline historical, controlled study và prediction có nhãn riêng. Giữ actual và predicted ở series tách biệt. Không gộp proxy geometry, coverage heuristic và GT image error thành một loại heatmap.

Không hiện một badge “upgrade tốt hơn X%” khi đang so baseline 105 views/30k với upgrade 60 views/10k: đây là hai điều kiện khác nhau, chỉ dùng để xem trade-off có nhãn. Badge cải thiện selector lấy từ controlled pair cùng method/budget/evaluator; số ảnh có thể là biến can thiệp đã khai báo. Không biểu diễn ΔPSNR dB thành phần trăm accuracy. FPS chỉ so khi cùng camera/resolution và định nghĩa phép đo.

**Showcase ngắn trong cùng UI:** mở baseline scene → chọn cùng method của upgrade → wipe/ROI thấy vùng khác biệt → click điểm trên graph để thấy chất lượng và chi phí → xem frame selection/forecast giải thích quyết định. Screenshot/PDF dùng export hiện có, kèm scene/run/budget identity; không tạo một showcase app riêng.

### F. Tích hợp catalog đủ nhỏ và đúng contract

Đã đối chiếu code: `catalog.py` hiện từ chối duplicate scene và gọi `validate_pair(..., primary_only=True)`; `Dataset.methods` gắn một cặp N/S mỗi scene; `Research.tsx` có caption cố định 30k/seed 42. Vì vậy `-ExtraMatrix` đơn thuần không đủ nhập nhiều variants/subsets/budgets của cùng scene.

Plan tích hợp:

1. Upgrade xuất `upgrade/reports/ui-index.json` có schema, run references, hashes, metrics, images và optional exports. Index chỉ công bố outputs đã validate; HTTP không đọc arbitrary paths từ browser.
2. Provider chuẩn hóa thành `scene_id → run_sets → method runs`, mỗi `run_set_id` gồm variant/study/selection/budget/seed và identity cần thiết. Scene vẫn là một mục trong gallery; không nhân thành hàng chục scene cards cho mọi subset.
3. Baseline provider dùng validators hiện có; upgrade provider xác minh input/eval hashes, method, source/runtime, budget và capability theo schema upgrade. Không yêu cầu pilot phải có export/FPS để hiện PSNR, và không ép records thiếu thành zero.
4. Shared catalog có version rõ, publish atomically, revision bao gồm cả baseline và upgrade index. Prepared cache nằm tại `artifacts/ui/`; outputs nghiên cứu upgrade vẫn ở `upgrade/artifacts/` và `upgrade/reports/`. Không sửa source reports để migration UI.
5. Bỏ caption hardcode; labels lấy budget/seed/downscale/evaluator của selection. Scene bookmarks cũ resolve về baseline default; bookmark mới mang run-set identity để không đổi model âm thầm.
6. Saved-image/metric comparison là scope bắt buộc ngày đầu. Upgrade exact novel-camera inference là capability chỉ bật khi worker adapter đã xác minh run/config/checkpoint và dùng đúng environment; chưa có thì UI tắt đúng lý do. Baseline inference hiện có tiếp tục hoạt động.
7. Nhận index mới không tự chạy CUDA. Catalog lỗi/missing upgrade chỉ cô lập nguồn upgrade và báo lý do; baseline vẫn mở được. Giữ allowlisted asset IDs, bounds và GPU lease hiện tại.

Nếu cùng scene nhưng camera frames/eval pixels không tương thích, vẫn cho xem riêng và đọc metadata; tắt sync/paired difference. Không auto-fit geometry để che khác biệt.

## 6. Thí nghiệm tránh tự đánh lừa mình

### 6.1. Hai loại so sánh

**Historical reference:** đọc bảng baseline đã có để hiển thị và tham khảo chi phí. Không training lại, không sửa số cũ. Nếu evaluator mới, tạo report dẫn xuất riêng.

**Controlled upgrade study:** chạy uniform và coverage-overlap trong cùng upgrade runtime/source/evaluator. Thí nghiệm này đo tác động selector mà không bị lẫn thay đổi hạ tầng giữa hai bản.

Mỗi row có `variant`, `source_id`, `scene_group`, `protocol_id`, `selection_id`, `budget`, `seed`, `split_hash`, `evaluator_id`. Comparison engine từ chối gọi là paired improvement nếu các yếu tố cần khớp lại khác nhau.

### 6.2. Vòng đầu: Tea sets

- Giữ train pool 105 ảnh và 15 eval cũ; cả hai methods dùng cùng một subset trong từng condition.
- Pilot nhỏ nhất: 60 ảnh uniform và 60 ảnh coverage-overlap, hai methods, cùng seed/budget → **4 training runs mới**.
- Nếu có tín hiệu đáng khảo sát, mở rộng 30/60/105 ảnh. Full pool 105 của hai selectors giống nhau nên deduplicate → **5 conditions × 2 methods = 10 runs tổng**, gồm 4 runs đã làm nếu identity khớp.
- Camera poses từ canonical scene cũ được freeze để nghiên cứu ảnh hưởng train-view selection. Đây là known-camera/transductive experiment; không chứng minh ít ảnh hơn vẫn đủ chạy SfM từ đầu.
- Muốn tuyên bố tiết kiệm toàn bộ capture/preprocessing phải có study khác chạy SfM từ từng subset và tính cả thất bại registration.

Vòng Tea sets đủ để kiểm tra pipeline và within-scene behavior. Nó chưa đủ train một predictor tổng quát cho capture mới.

### 6.3. Khi predictor được phép đưa ra con số

- Within-scene experiment giữ các capture/trajectory hoặc subset families tách biệt khi đánh giá; kết luận chỉ nằm trong scene đó. Với subsets cùng video, vẫn công bố dependence.
- Cross-scene experiment gom toàn bộ subsets/seeds của một scene thành một group; dùng leave-one-scene-out khi đủ dữ liệu. Hyperparameters chọn trong training groups, không tune trên scene đang test.
- Bốn scenes chính hiện tại chỉ là exploratory validation rất nhỏ. Thêm điểm từ cùng Tea sets không thay thêm independent scenes/captures.
- Chỉ thêm Bonsai/Room theo từng đợt đã dự trù. Garden là stress case cuối; Poster dùng smoke.
- Chọn method phải đánh giá decision regret và so với always-Splatfacto. Nếu dữ liệu không có trường hợp đổi quyết định thì không tuyên bố đã học được selector method hữu ích.

### 6.4. Thước đo thành công

| Hạng mục | Cách đánh giá |
|---|---|
| Forecast | MAE/RMSE theo dB, per-scene errors; rank correlation chỉ báo khi có đủ biến thiên; so với simple predictors. |
| Reliability | Sai số theo scene/budget và tỷ lệ từ chối; interval calibration để sau. |
| Frame selection | ΔPSNR/LPIPS tại cùng số ảnh, cùng iterations/schedule/resolution; thêm matched-wall-time study riêng khi cần. |
| Tiết kiệm GPU | Tổng thời gian audit + short runs + training + evaluation liên quan tới quyết định; không giấu chi phí tìm recipe. |
| N/S comparison | Cùng GT và evaluator mới cho study; SSIM baseline method-native vẫn giữ caveat gốc. |
| Resource | Sampled VRAM, allocator peak nếu bổ sung đúng cách, checkpoint/export bytes; không nhập chúng thành một chỉ số memory. |

Mục tiêu thiết kế ban đầu: forecast MAE ≤2 dB trong phạm vi test đã công bố; selector nhắm giữ chất lượng với ít ảnh hơn hoặc cải thiện tại cùng số ảnh. Đây là **target**, chưa là kết quả. Ngưỡng chấp nhận cho quyết định sử dụng phải chốt trước lượt confirmatory; nếu không đạt thì công bố thất bại và giữ audit capability.

Không hứa “thêm góc X tăng 2 dB” chỉ từ feature score. Để kiểm chứng lời gợi ý phải chụp/thêm ảnh thật, đăng ký về cùng scene frame, giữ eval độc lập và đối chiếu với cách bổ sung ảnh đơn giản ở cùng ngân sách.

## 7. Dự toán GPU theo số đã đo

Nguồn: `reports/topic16-full/results.csv`. Thời gian dưới đây cộng training của N và S; training có overhead theo định nghĩa report. Không gồm đầy đủ eval, timed render, export, setup, cooldown hoặc thời gian pause.

| Scene | Nerfacto 30k | Splatfacto 30k | Một pair 30k | Proxy 10k = thời gian pair / 3 |
|---|---:|---:|---:|---:|
| Tea sets | 48,66 phút | 22,96 phút | 71,62 phút | 23,87 phút |
| Bonsai | 48,08 phút | 55,19 phút | 103,26 phút | 34,42 phút |
| Room | 56,95 phút | 60,52 phút | 117,48 phút | 39,16 phút |
| Garden | 74,32 phút | 143,85 phút | 218,17 phút | 72,72 phút |

Riêng tám runs của bốn scenes trên đã khoảng **8,51 giờ training**. Chưa tính Poster và các stages sau train, nên không bật “rerun all” làm bước mặc định.

**Cột 10k là phép ngoại suy sơ bộ, chưa đo.** Progressive resolution, densification, kích thước subset và fixed overhead khiến runtime không tuyến tính theo iterations hoặc số ảnh. Sau pilot đầu phải thay proxy bằng actual durations, kèm phạm vi ETA và cập nhật dung lượng.

| Đợt execution | Số training runs mới | Dự toán training sơ bộ | Vai trò |
|---|---:|---:|---|
| E0: inventory + audit + đọc baseline | 0 | Không training GPU | Đầu ra có ích ngay; đo riêng CPU time. |
| E1: Tea 60, hai selectors, hai methods, 10k | 4 | Khoảng 48 phút theo proxy | Kiểm tra flow và tín hiệu ban đầu. |
| E2: Tea 30/60/105, deduplicate full pool | 6 bổ sung sau E1 | Khoảng 72 phút bổ sung; tổng E1+E2 khoảng 2 giờ | Khảo sát within-scene; chưa đủ cross-scene predictor. |
| E3: confirm Tea 60, hai selectors, hai methods, 30k | 4 | Khoảng 2,39 giờ nếu chạy mới toàn bộ | Kiểm chứng kết luận ở 30k; resume chỉ khi schedule/state tương thích. |
| E4: thêm independent scene/capture | Tùy matrix | Bonsai pair 30k khoảng 103 phút làm mốc | Generalization; chạy theo evidence gap. |

E1–E3 nếu đều chạy mới theo cách tính trên khoảng **4,38 giờ training**, vẫn chưa có overhead ngoài train và chưa đủ xác nhận generalization. Nếu resume đúng schedule, phần training đã thực hiện được trừ theo actual records; không cộng full budget lần nữa. Không mặc định khai triển E4 hoặc ensemble cho mọi scene.

Planner phải phân biệt iteration-budget với hard wall-clock budget. Đạt budget thì ghi completed/paused đúng nghĩa, không lấy metric dở dang làm final 30k.

## 8. Hardware budget giữ theo máy hiện tại

Máy đã kiểm tra trong phiên trao đổi: i7-12800H, 14 cores/20 threads, RAM khoảng 32 GB, RTX A4500 Laptop 16 GB; ổ D còn khoảng 162 GiB tại thời điểm kiểm tra. Dung lượng trống phải query lại trước execution.

- Giữ downscale 2 cho paired study đầu; thay resolution tạo protocol riêng cho cả hai methods.
- Giữ CPU worker limit 4 theo policy hiện tại, một GPU job, không viewer trong timed runs.
- Giữ clock 300–800 MHz, start dưới 65°C, stop ở ≥78°C / ≥80 W / ≥95% VRAM, watchdog và fail-closed telemetry như baseline.
- Chỉ load model đang cần; không giữ hai methods hoặc ensemble đồng thời trong VRAM.
- Đọc features theo batches; không decode toàn bộ video/PLY lớn vào RAM một lượt.
- Plan dung lượng bao gồm Conda environment, canonical derivatives, checkpoints, eval predictions và caches. Dùng reserve trong registry upgrade, dự kiến tối thiểu 30 GiB; fail trước workload nếu không đủ. Đây là ngưỡng vận hành đề xuất, không bảo đảm đủ cho mọi matrix.
- Không export full Gaussian/point cloud cho mọi pilot; chỉ tạo metrics và checkpoints cần cho study. Export visual cho selected completed runs.
- Cache cleanup chỉ trong khu vực upgrade được quản lý; bảo vệ input, active jobs, selected evidence và checkpoints cần resume. Không cleanup baseline.

## 9. Work packages trong một ngày triển khai

Phân bổ mục tiêu khoảng 10 giờ làm việc, không phải các tuần nối tiếp. Thứ tự ưu tiên: preservation + pipeline → shared benchmark/image comparison → selector study/graphs → forecast khi có dữ liệu. Có thể điều chỉnh nội bộ theo lỗi phát sinh; mọi phần chưa verify phải được ghi đúng trạng thái.

| Khoảng làm việc | Công việc và đầu ra review được |
|---|---|
| Giờ 0–1,5 | Inventory, source snapshot, upgrade tree/namespace, registry, launchers, output isolation và shared GPU lock design. |
| Giờ 1,5–3 | Feature extractor, audit artifacts, deterministic selector, subset/split contracts. |
| Giờ 3–5 | Queue/dry-run/resume/cache, evaluator cho study, evidence rows và runtime estimator. |
| Giờ 5–6,5 | Predictor nhẹ, grouped evaluation, simple baselines, refusal theo input range và evidence; chưa làm learning-curve forecast. |
| Giờ 6,5–8,5 | Shared UI providers/run sets, Baseline/Upgrade/Compare, graphs và saved-image comparison; tái sử dụng gallery/workspace. |
| Giờ 8,5–10 | Tests trọng điểm, native PowerShell parsing, frontend build, CPU smoke, clone runbook, baseline integrity check. |

Sau ngày code, kỳ vọng có pipeline thực thi hoàn chỉnh cho scope trên. Model forecast có thể đang `insufficient-evidence` cho đến khi có nhãn thật; short runs/confirmation/generalization là các đợt execution độc lập. Không dùng synthetic fixture như bằng chứng predictor hoạt động trên capture thật.

**Đã lược khỏi ngày đầu:** app/UI/Node build thứ hai, redesign gallery, chart framework lớn, interactive training control panel, learning-curve extrapolator, calibrated intervals, tự động hứa mức tăng dB khi chụp thêm, và worker novel-camera cho upgrade khi chưa có adapter. Giữ shared UI đọc kết quả, graphs và comparison làm trọng tâm showcase.

**Ngoài scope đầu:** full 4D reconstruction, relighting, mesh/CAD chính xác, MC dropout, ensemble toàn bộ scenes, predictor deep learning, LoD/streaming overhaul. Các nhánh này tăng số biến mà chưa giúp kiểm chứng câu hỏi trung tâm.

## 10. Trải nghiệm clone và chạy hai bản

Baseline giữ nguyên training commands trong README hiện tại. Upgrade có README/setup/runbook cho compute riêng; cả hai dùng một UI launcher. Tài liệu chỉ rõ video custom và artifacts không nằm trong Git.

Các commands sau là **giao diện dự kiến phải triển khai**, chưa phải commands chạy được ở thời điểm viết plan:

```powershell
# Một UI chung: benchmark baseline và mọi upgrade index hợp lệ.
.\Invoke-Topic16.ps1 ui

# Upgrade: setup độc lập, đọc baseline inventory mà không retrain.
.\upgrade\scripts\Setup-Upgrade.ps1
.\upgrade\Invoke-Upgrade.ps1 inventory -BaselineRoot '.'
.\upgrade\Invoke-Upgrade.ps1 audit -Scene tea_sets_2
.\upgrade\Invoke-Upgrade.ps1 plan -Study tea60-v1

# Chạy study đã khai báo; chỉ resume các jobs còn thiếu/paused đúng identity.
.\upgrade\Invoke-Upgrade.ps1 run -Study tea60-v1 -Resume

# Sau khi có outputs mới: shared builder nhập hai nguồn, không retrain.
.\UI_design\scripts\Prepare-UIAssets.ps1
.\Invoke-Topic16.ps1 ui
```

Người clone có ba lựa chọn được tài liệu hóa: chạy training baseline riêng; chạy training upgrade riêng từ dữ liệu; hoặc đọc results bundle đã phát hành trong cùng UI. Filters `Baseline`, `Upgrade`, `Compare` quyết định cách xem, không quyết định tự động chạy pipeline nào. Không yêu cầu họ tự train cả hai bản chỉ để mở giao diện; thiếu nguồn nào thì hiển thị đúng khả năng nguồn còn lại.

`Setup-Upgrade.ps1` không tạo UI thứ hai. Khi cần UI, hướng người dùng tới setup/build launcher hiện có tại `UI_design/`. Shared builder cần hỗ trợ cả trường hợp chỉ baseline, chỉ upgrade và có cả hai; không bắt upgrade-only clone có đủ 10 baseline checkpoints mới mở được benchmark của mình.

Fresh training tạo run IDs và evidence mới. Historical benchmark cần artifact bundle có checksums để audit sâu; Git clone đơn thuần không có đủ checkpoint/video và không bảo đảm bitwise reproduction.

## 11. Gates và tiêu chí nghiệm thu

### Trạng thái G-Core hiện tại

`reports/topic16-full/g-core.json` đang `BLOCKED`: `research_review=false`, `clean_machine_replay=false`; các artifact checks đã true. Không sửa file để tạo PASS và không tự phát động replay toàn bộ chỉ để mở upgrade.

Theo skill `topic16-powershell`, production code/release phải sau G-Core. Giai đoạn code một ngày ở đây được định vị là **experimental research upgrade**; việc nghiệm thu/certified release giữ gate riêng và cần evidence thật. Không lấy audit trên artifacts cũ thay independent replay.

Skill còn dẫn chiếu `Construction_architect.md` và `Modular_construct.md`, nhưng hai file không có tại root hiện tại. Trước khi thay execution flow thực tế, đối chiếu README/runbook/contracts hiện có và tìm source kiến trúc chính thức nếu cần; không giả đã đọc hai file vắng mặt. Việc viết plan không sửa execution flow.

### Tiêu chí code hoàn tất

- [ ] Baseline training source/config/report được bảo toàn; snapshot giữ local changes và UI trước tích hợp.
- [ ] Upgrade core chạy được mà không import training code baseline; setup không sửa env baseline; UI chung là lớp tích hợp được phép thay đổi.
- [ ] Upgrade compute không ghi output sang baseline research paths, kể cả junction/reparse path đã resolve. Shared UI chỉ ghi cache/catalog vào `artifacts/ui/` đã khai báo; source reports/checkpoints được bảo vệ.
- [ ] Hai variant tranh cùng GPU lock thì một bên bị chặn; một shared UI service/owner, không spawn hoặc stop nhầm compute worker.
- [ ] Split không overlap train/eval; selectors không xem eval RGB/metrics; subset identity deterministic.
- [ ] Queue dry-run chính xác; completed reuse, interruption/resume và failed half-pair có kiểm tra.
- [ ] Predictor evaluation giữ scene groups và training-only preprocessing; thiếu evidence không tạo forecast giả.
- [ ] Study comparator phân biệt historical reference với controlled pair; evaluator/budget mismatch bị chặn.
- [ ] Cùng scene có nhiều run sets mà không duplicate gallery cards; caption phản ánh đúng budget/seed; bookmark cũ vẫn mở baseline.
- [ ] Shared UI chạy khi chỉ có baseline, chỉ có upgrade hoặc cả hai; malformed upgrade index không làm mất baseline.
- [ ] Missing metrics/exports hiển thị unavailable; sync/paired difference chỉ bật khi camera/GT tương thích; graph và ảnh click qua đúng run.
- [ ] Changed PowerShell parse, Python contracts, frontend typecheck/build và CPU smoke PASS đúng phạm vi.
- [ ] Runbook có cả đường chạy fresh clone và đường reuse artifacts trên máy hiện tại.

### Tiêu chí scientific validation hoàn tất

- [ ] E1/E2/E3 có actual run identities, safety logs, timings và common-evaluator results theo scope đã chạy.
- [ ] Báo cả selector không cải thiện nếu xảy ra; không chỉ chọn views hoặc seeds thuận lợi.
- [ ] Forecast báo MAE/per-scene error và simple-predictor comparison; generalization claims chỉ theo groups đã test.
- [ ] Short-run cost được tính vào nghiên cứu; 10k predictions không được đổi nhãn thành final 30k.
- [ ] Camera guidance chỉ báo measured gain khi có intervention study thật.
- [ ] Certified release có review/replay evidence theo gate, tách khỏi trạng thái code/UI hoạt động.

## 12. Nguồn đối chiếu và phạm vi tính mới

Nguồn nội bộ: `README.md`, `Report_computer_vision.md`, `deepseek_ideas.md`, `configs/project.psd1`, `setup_full_command.md`, `src/topic16/runtime.py`, `src/topic16/settings.py`, `scripts/lib/Common.ps1`, `UI_design/ACCEPTANCE.md`, `reports/topic16-full/results.csv` và `g-core.json`.

Các công trình liên quan đã kiểm tra để tránh tuyên bố quá mức:

- [ActiveNeRF — ECCV 2022](https://arxiv.org/abs/2209.08546): uncertainty và active selection để bổ sung quan sát. Ý tưởng hướng dẫn chụp thêm đã có tiền lệ.
- [NeRF-NQA](https://arxiv.org/abs/2412.08029): đánh giá chất lượng NVS không cần ảnh tham chiếu. Bài toán này đánh giá cảnh đã được tổng hợp; khác forecast capture-only trước training, nhưng cho thấy quality assessment đã là lĩnh vực nghiên cứu.
- [Active View Selector](https://arxiv.org/abs/2506.19844): dùng cross-reference image quality assessment để chọn views, áp dụng qua nhiều biểu diễn. Không xem view selection là bài toán đã tự giải quyết chỉ vì có coverage heuristic.
- [Bayes' Rays — CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Goli_Bayes_Rays_Uncertainty_Quantification_for_Neural_Radiance_Fields_CVPR_2024_paper.pdf): post-hoc uncertainty cho trained radiance fields; có thể tham khảo sau, không giả định thay vào Nerfacto/Splatfacto hiện tại là chạy được ngay.

Chưa có systematic literature review để kết luận forecast capture-only ở cấu hình của chúng ta là mới. Đóng góp đề xuất là quy trình hỗ trợ quyết định có kiểm chứng và chi phí rõ trên laptop, được xây cạnh baseline training/benchmark được bảo toàn và thể hiện trong một UI chung. Mức độ thành công và giá trị nghiên cứu cuối cùng do thí nghiệm quyết định.

## 13. Đánh giá “đẳng cấp” trên thang 10

**Chấm thiết kế sau điều chỉnh: 8,5/10** trong phạm vi project Computer Vision chạy trên laptop. Đây là đánh giá chủ quan về hướng phát triển và khả năng showcase, không phải điểm nghiệm thu hay xếp hạng công trình nghiên cứu.

| Tiêu chí | Trọng số | Điểm dự kiến | Cơ sở |
|---|---:|---:|---|
| Giữ thành quả và chạy tái lập | 25% | 9/10 | Baseline training/benchmark được bảo toàn, upgrade độc lập, shared UI đọc hai nguồn. |
| Visual và câu chuyện demo | 20% | 9/10 | Một nơi nối ảnh cùng camera, graphs, capture selection và provenance. |
| Hợp phần cứng và compute budget | 25% | 8,5/10 | Không retrain baseline; short study trước, run resume/reuse, mở rộng theo evidence. |
| Scope code một ngày | 15% | 8/10 | Tận dụng UI hiện có và loại phần dư; catalog/providers và QA vẫn là công việc thực. |
| Chiều sâu nghiên cứu dự kiến | 15% | 7,5/10 | Có câu hỏi kiểm chứng được; dữ liệu scene độc lập còn ít, tính mới và predictor chưa được xác nhận. |

Điểm có thể tiến tới **9/10** khi controlled study cho kết quả có ý nghĩa trên hơn một independent scene/capture, forecast thắng simple predictor trong đúng phạm vi đánh giá, và UI cho người xem tự kiểm chứng ảnh–metric–chi phí. Chỉ thêm graphs đẹp mà không có evidence mới thì chưa đạt mức đó. Không chấm 10/10 khi tính tổng quát và đóng góp phương pháp còn chưa được chứng minh.

**Chốt triển khai:** baseline training riêng, upgrade training/outputs riêng, **một Spatial Studio chung**. Ưu tiên làm khác biệt nhìn thấy được và kiểm tra được; mọi con số trên UI phải truy về bằng chứng thật.
