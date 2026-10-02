# Nerfacto vs Splatfacto on one RTX A4500 Laptop

Nguồn cho báo cáo 6–8 trang; các phần kết quả chỉ điền sau measured primary runs.
Không dùng diagnostic 100-step numbers hay planning estimate thay baseline.

## Abstract (khoảng 150–200 từ)

Nêu research question, dataset/method/runtime/hardware, protocol và kết quả thực đo.
Chưa có full primary evidence thì viết proposal/status, không viết abstract kết luận.

## 1. Introduction (khoảng 1 trang)

Novel-view reconstruction từ ảnh điện thoại; trade-off quality/time/VRAM/model size.
Phạm vi là Nerfacto và Splatfacto ở pinned release trên một laptop, không mọi NeRF/3DGS.
Đóng góp: common pinhole GT/split, evidence-backed measurement, real capture và failure analysis.

## 2. Background / Related work (khoảng 1 trang)

Volume compositing, proposal sampling/hash fields/contraction; Gaussian covariance
projection, alpha blending/densification. Dẫn papers trong docs/research; phân biệt
paper claims với kết quả project. Không coi runtime Nerfacto là NeRF 2020 reproduction.

## 3. Experimental setup (khoảng 1–1.5 trang)

Trích exact registry và run manifests: version/SHA, A4500/driver, AC/thermal conditions,
30k iterations/seed42/downscale2/interval8, source counts và custom pose acceptance.
Mô tả shared pinhole preprocessing từ pinned undistorter, intrinsics/crops/sparse points,
explicit train/test membership. Giữ ray-vs-image batch defaults và report wall time.
Metrics lấy upstream held-out implementation. Checkpoint bytes khác derived PLY bytes.
FPS đo cùng camera/resolution, warm-up, synchronization, IO excluded; VRAM sampling10s.

## 4. Results (khoảng 1–1.5 trang)

Chèn `results.md/csv`, link mỗi row về exact run key/hash. Official three scenes và
custom có nhóm riêng; poster chỉ smoke. Chèn paired throughput nếu thực sự có chung
trajectory. Không suy winner từ diagnostic, không nhập half-pair hoặc tuned result
khác protocol vào primary. Repeated seeds nếu có lập bảng riêng và tính variance.

## 5. Qualitative analysis (khoảng 1–1.5 trang)

Chọn identical held-out camera/crop coordinates, dẫn `crops.json` và frame artifacts.
Phân tích ít nhất ba cases: foliage/thin structures, specular/fine texture, low-overlap.
Mỗi case ghi observation → giả thuyết pose/coverage/appearance/density/densification
→ evidence/limitation. Không coi center crops tự động là expert-selected failures.

## 6. Limitations / Conclusion (khoảng 0.5–1 trang)

Single laptop, primary seed, Windows, sampled VRAM, thermal/power và different batch
semantics; preprocessing khác published protocols. Nêu kết luận trong measured scope,
không khái quát representation mọi dataset/hardware. Ghi failures/exclusions thật.

## Reproducibility appendix / References

Link source archive/Git diff, dependency snapshot, data/source citations, primary matrix,
config/checkpoint hashes và independent reviewer evidence. Không bundle private data/model
lớn trong Git. G-Core/release checklist phải phản ánh trạng thái thật.
