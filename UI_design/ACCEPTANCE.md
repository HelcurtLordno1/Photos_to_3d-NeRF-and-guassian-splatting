# Nghiệm thu Spatial Studio — 2026-10-02

Thành phẩm chạy tại **http://127.0.0.1:7016**, profile `inference`, native Windows.
Frontend/backend/scripts/tests nằm trong `UI_design/`. Plan triển khai đã hoàn tất;
bảng này phân biệt phần thực sự kiểm thử với kiểm tra thiết bị/thủ công chưa làm.
`PASS` chỉ áp dụng trong phạm vi bằng chứng mô tả ở từng dòng. `PARTIAL` nghĩa là
code đã có, một phần kiểm tra mở rộng chưa được thực hiện. Không có kết quả
hardware, benchmark hay release gate nào được suy ra từ fixture.

Catalog được nghiệm thu:
`b28aa3cd41f4f197b2fa369a29ed135e1d7117e33a1360814bc279fa1e50e33a`.
Builder đã xác minh 10 exact runs và 722 assets; cảnh lấy từ matrices cố định.
Config, checkpoint, split, source/runtime, PNG, export và throughput đều qua
contracts. Các trường kiến trúc được đọc bằng YAML BaseLoader không tạo Python
objects, từ config đã xác minh; chỉ expose allowlist model fields.

| Scene | Scope | Train / eval | Nerfacto points | Splatfacto Gaussians |
|---|---|---:|---:|---:|
| custom:tea_sets_2 | custom capture | 105 / 15 | 1,002,387 | 245,656 |
| bonsai | calibration | 255 / 37 | 1,002,644 | 428,861 |
| garden | benchmark | 161 / 24 | 1,003,326 | 1,656,903 |
| room | benchmark | 272 / 39 | 1,002,789 | 532,932 |
| poster | smoke, ngoài aggregate | 87 / 13 | 1,002,800 | 211,800 |

## Bằng chứng thực thi

Các file QA lớn được giữ local, ignore Git, dưới `artifacts/ui/qa/`.

| Nhóm | Kết quả và evidence |
|---|---|
| Existing contracts | 75 Python tests PASS; PowerShell manifest/data/path checks PASS; 46 `.ps1` parsed. `final-project-e2e.log`. PSScriptAnalyzer chưa cài nên phần analyzer được ghi rõ là skipped. |
| UI contracts | 10 Python tests PASS: registry identity, queue/lease/camera/cache, catalog major và bounded PLY header. `final-build-tests.log`. |
| Frontend | Strict TypeScript/build PASS; 7 portable bookmark tests PASS. Initial gzip 85,589 bytes / 184,320 budget; Viewer lazy 892,621 bytes / 1,126,400 exception. Renderer exception có giải thích ở SPIKE_DECISION.md. |
| Fixture E2E | 5 tests PASS: selection/metrics/ROI/diagram, onboarding/theme/language/gallery, automated accessibility, bookmark import/merge/replace, delayed-submit scene race. `final-e2e.log`. Synthetic data, không chứng minh CUDA quality/performance. |
| Actual browsers | Brave 154.0.8037.93, Chrome 154.0.8037.95, Edge 154.0.4258.48. ANGLE / NVIDIA RTX A4500 Laptop GPU / D3D11. Brave tải đủ 5 scenes; Chrome/Edge Tea smoke và single/dual switches. `browser/results.json` cùng screenshots. |
| Worker decode | Browser instrumentation ghi `init-wasm`, `loadPackedSplats`, `nextChunk`, `sortSplats32`; point decoder dùng worker riêng. Đây là decode evidence, không chỉ thấy sorting worker. |
| Actual rendering | Nút UI đã hoàn tất paired request và từng model riêng ở 320 × 570; PNG/model identities và guard record được lưu. `ui-inference/result.json`, `pair.png`, `nerfacto-single.png`, `splatfacto-single.png`. |
| Novel camera | API render pair ở camera dịch 5 mm trong frozen model frame thành công. `inference/paired-novel-camera.json` và hai PNG. Không gán GT/metrics cho camera này. |
| HTTP/service | 11 API contract groups PASS: ranges, allowlist, CSRF/Origin, lease, pose, stale revision, malformed body, release, report. `api/result.json`. Exclusive Windows bind, strict port rejection, fallback 7017, owned stop và primary unchanged PASS: `ports.json`. |
| Export/recovery | Download PNG + JSON thực; context loss qua WEBGL_lose_context và Retry; tour controls/return-to-Garden; forced-colors emulation; PDF room/lpips giữ filters, run/config/checkpoint/split identities. `interactions/result.json` và exports. |

Actual render times ghi trong job là thời gian inference sau CUDA synchronize,
không gồm load/checks/save PNG. Không gọi số này là thời gian người dùng chờ hoặc
offline FPS. Cặp novel và cặp UI giữ cùng camera request/hash; N đóng trước khi
S nạp. Success chỉ publish sau cả hai model và final GPU guard thành công.
HTTP process không import Torch; browser drawing tạm dừng khi worker đang chạy.

## U01–U40

| ID | Status | Kiểm tra, evidence và giới hạn |
|---|---|---|
| U01 | PASS | Native PowerShell tại path tiếng Việt; setup/build/prepare/start và root health Unicode khớp. Fresh shell tìm Miniconda ổ D qua Windows registry; không cần activate shell. |
| U02 | PASS | Card Bộ trà mở đúng scene và camera; catalog binds đúng N/S run keys, cover GT, saved views và metrics. Actual browser + builder. |
| U03 | PASS | Brave load đầy đủ 5 exact paired scenes; labels/scopes/capabilities đúng. Poster có smoke label và không tạo aggregate giả. |
| U04 | PASS | S-only load full Gaussian, camera controls/reset; mode switching trên 3 browser. Representation label rõ. |
| U05 | PASS | N-only load RGB cloud, point-size control; proxy label rõ. Neural images được tạo qua checkpoint riêng. |
| U06 | PASS | Dual mặc định dùng cùng frozen pose; camera matrix round-trip dưới 1e-6; input/target copy giữa adapters, không fit riêng từng model. Actual rotation và dual screenshots. |
| U07 | PASS | Non-default camera giữ khi dual → N → S → dual; browser test assert mọi matrix component sai lệch dưới 1e-4. |
| U08 | PARTIAL | Sync toggle và re-enable chạy trên cả 3 browser; active-pane restore đã triển khai. Chưa đo tự động hai independent rigs sau một chuỗi kéo dài từ mỗi pane. |
| U09 | PASS | Builder kiểm cùng frozen index/GT/pred/hash/dimensions; selector và saved group qua fixture/actual browser. |
| U10 | PASS | Wipe keyboard slider, shared source-pixel ROI, zoom và viewport clipping; fixture + actual screenshot. Không trộn saved và novel groups. |
| U11 | PASS | Bộ trà portrait giữ aspect ratio; screenshot thật và 320 × 570 live output. ROI caption dùng dimensions nguồn. |
| U12 | PASS | 6 metrics, units, method/scopes và exact run rows lấy từ validated JSON; fixture table + actual report. Không tính aggregate có Poster. |
| U13 | PASS | Ba Mermaid diagram tabs render từ local bundle; zoom và SVG download thật. Node text có giải thích/source section; actual config fields và provenance có thể mở. |
| U14 | PASS | Gallery có geometry, khung ảnh GT, plaques/labels; chỉ tải covers trong phòng. DOM exhibit choices vẫn có khi WebGL không dùng được. Actual gallery screenshot. |
| U15 | PASS | Guided tour start/stop, speed control, reset/map hoạt động; actual interaction test. Collision bounds và normalized diagonal movement được kiểm trong code. Không gọi slider test là đo vật lý tốc độ bằng thiết bị ngoài. |
| U16 | PASS | Map Garden → Open reconstruction → return giữ focus/vị trí Garden qua actual browser. Frame raycast click và E/Enter có cùng scene dispatch trong code. |
| U17 | PARTIAL | DOM keyboard controls, Esc modal, reduced-motion/forced-colors emulation đã kiểm. Pointer-lock Esc có code cleanup; chưa chạy bài thao tác pointer lock thủ công bằng chuột thật. |
| U18 | PASS | N-only và S-only đều render thành công từ nút UI; status results chỉ chứa method đã chọn. Exact run/checkpoint/config SHA trong `ui-inference/result.json`. |
| U19 | PASS | Paired UI và paired translated camera thực thành công; chỉ công bố cặp sau final guard. Source identities và PNG SHA nằm trong immutable job status. |
| U20 | PASS | Fixture trì hoãn POST jobs rồi đổi scene xác nhận cancel và không chuyển cảnh mới sang ảnh cũ. Backend latest-pending/stale-revision và frontend sequence contracts được kiểm. Không gọi fixture race là CUDA preemption test. |
| U21 | PASS | HTTP/static tách worker process; status/error/profile reason có action rõ. Artifacts profile, invalid-camera và worker lỗi integer intrinsics đã được quan sát trong quá trình sửa; bản cuối render thành công. |
| U22 | PASS | Garden full 1,656,903 Gaussians; actual download cancellation với delayed transport và Retry thành công. Không đổi ngầm sang reduced tier. |
| U23 | PARTIAL | Five-scene switching, mode recreation, gallery round trip và context-loss retry không có uncaught page errors; explicit dispose/abort/worker cleanup. Chưa chạy memory soak hàng giờ hoặc đo peak toàn bộ worker/WASM/native RSS. |
| U24 | PASS | Bookmark camera round-trip; backup/import/merge/replace; PNG và JSON screenshot sidecar download thật với scene/mode/camera/run/catalog metadata. |
| U25 | PASS | Native Stop/restart sạch khi idle; PID cũ mất, port mở lại. Fallback service HTTP shutdown + process exit thật, primary còn nguyên. Không kiểm forced termination giữa CUDA kernel bị treo. |
| U26 | PASS | Three-browser native GPU matrix có version/renderer; actual WebGL context loss/recovery qua Brave. Brave full, Chrome/Edge smoke đúng phạm vi đã ghi. |
| U27 | PASS | Worker decode call được ghi cùng SDK source audit, typed arrays/transfer cho points. Actual Garden cancel/retry; không clone per-vertex JS objects. Không có claim peak memory từ main-heap sample. |
| U28 | PASS | First-run skip trên real browsers; help reopen/Esc, language/theme trong fixture. Không tự bật pointer lock, tour hoặc inference. |
| U29 | PARTIAL | Desktop 1366 × 900 và viewport 390 × 844, DPR cap/ResizeObserver/source-pixel ROI đã kiểm. Windows OS scaling 125%/150% và browser zoom matrix chưa thao tác thủ công. |
| U30 | NOT TESTED | OrbitControls touch gestures và gallery touch arrows đã triển khai; không có physical touch device để xác nhận pinch/pan/scroll ergonomics. Mobile screenshot không được coi là touch test. |
| U31 | PARTIAL | Axe collection và workspace trên 3 real browsers đều 0 violations; fixture collection cũng 0. Focus trap/skip/keyboard và forced colors có code/evidence. NVDA và complete manual contrast audit chưa chạy. |
| U32 | PASS | CPU cache-pressure contract chỉ xóa UI jobs, bảo vệ active/pending/latest và original export. Server reserve/pixel/body limits; originals/derived referenced assets không bị eviction. |
| U33 | PASS | Windows exclusive socket bind; strict occupied-port fails đúng message, auto range chọn 7017, actual URL và stop xác minh PID. Native launcher reuse đúng root/revision/profile. Dev Vite 5176/exact backend/Origin lease proxy cũng đã chạy smoke. |
| U34 | PASS | 7 backup unit cases, real camera serialization và fixture download/import/merge/replace/unknown-schema. Missing-scene references có preview/restore notice; không tự map sang scene khác. |
| U35 | PASS (local) | Build/typecheck/Vitest/5 fixture E2E/bundle budgets PASS native. GitHub Actions UI job đã có source; hosted CI chưa chạy cho working tree này. Không gọi fixture software rendering là A4500 evidence. |
| U36 | PASS | Actual room/lpips PDF: print-visible filter, units, matrices, both run keys/configs/checkpoint/split hashes được assert trước xuất. SVG/PNG/source report links còn đúng. |
| U37 | PASS | Unknown major catalog rejects, source bytes giữ nguyên; builder publish validated atomic copy. Old revision jobs rejected. Không triển khai generic unreviewed schema conversion. |
| U38 | PASS | API single lease owner/second-owner refusal; CPU latest-pending và expiry/cancel code; pagehide/hidden release, heartbeat không renew tab ẩn. Chưa đo timing tab-close timeout bằng thiết bị ngoài. |
| U39 | PARTIAL | Code publish sau loop + guard, failure không có results, previous completed UI pair không bị ghi đè; stale/cancel status không expose success images. Chưa cố tình làm hỏng checkpoint hoặc ép GPU fail ở method thứ hai trên laptop. |
| U40 | PARTIAL | ExtraMatrix workflow và duplicate/contract/budget/atomic checks đã có; 5 existing scenes prepare thực thành công. Không có sixth completed paired scene để chạy trọn workflow mới. |

## Phạm vi bàn giao

Code của collection/workspace/gallery/inference/research đã hoàn thiện và được
build/chạy local. Các status PARTIAL/NOT TESTED trên là giới hạn nghiệm thu mở
rộng, không phải placeholder UI hay các nút chưa được code. Source immutable của
thí nghiệm và original review không bị sửa; migration chỉ bỏ phần Ui hợp lệ ra
khỏi experiment hash. Không mở rộng phép tương thích sang training/data/runtime/
safety fields.

Chạy lại bằng [README.md](README.md). Renderer evidence ở
[SPIKE_DECISION.md](SPIKE_DECISION.md); các bước đã hoàn tất ở
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Những phép đo unavailable vẫn
có thể bổ sung bằng test tools đã bàn giao, không phải hỏi lại thiết kế từng bước.
