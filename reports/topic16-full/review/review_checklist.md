# Phiếu review selection topic16-full

Phiếu dành cho người thực sự đọc kết quả. Không tự chuyển checkbox thành approval.
Tác giả phân tích hiện tại là AI; reviewer tự ghi danh tính và quyết định.

## Hồ sơ cần đọc

1. [research_review.md](research_review.md): câu hỏi, protocol, kết quả, trade-off và limitations.
2. [paired-comparisons.csv](paired-comparisons.csv): delta/tỷ lệ từ số gốc.
3. [case-selection.json](case-selection.json): camera, tọa độ crop, nguồn/checksum.
4. [artifact-audit.json](artifact-audit.json): phạm vi CPU audit và các checks thực sự chạy.
5. [replay_runbook.md](replay_runbook.md): evidence replay đang thiếu.

## Nhận xét cần xác nhận

| Câu hỏi | Reviewer ghi nhận xét / correction |
|---|---|
| Có đúng 30k/seed42/downscale2, defaults mỗi method và cùng input/camera không? | |
| Có tách poster/custom khỏi kết luận official benchmark không? | |
| Có phân biệt FPS synchronized, upstream FPS, checkpoint và PLY không? | |
| Nhận xét hình có khớp cả worst/median views, gồm failure của Splatfacto không? | |
| Kết luận có giữ single-seed, single-host, clock-cap, custom video/SfM limitations không? | |
| Có tránh claim 100% 3D accuracy, model học nhiều scene để thông minh hơn, hoặc thuật toán tự nghĩ ra không? | |
| Có nói rõ CPU replay chưa phải clean-machine GPU replay không? | |
| Source snapshots/provenance có đủ để người khác kiểm tra source thực sự đã chạy không? | |

Reviewer: __________. Vai trò: __________. Ngày: __________.
Quyết định research review: approve / request changes / reject.
Notes và evidence đã đọc: __________.
Quyết định independent replay: chưa có evidence / scoped replay reviewed / full replay reviewed.
Máy, người chạy, môi trường và phạm vi replay thực tế: __________.

## Ghi approval sau khi có xác nhận thật

Sao chép `review.pending.json` thành một file endorsement mới; giữ nguyên exact
`settings_hash` và sorted `run_keys`. Chỉ set `research_review.approved=true`
sau quyết định review; ghi `reviewer`, `notes`, evidence có thật.
`clean_machine_replay.approved` giữ false cho đến khi có actual setup/data/train/eval
replay với scope được người chịu trách nhiệm chấp nhận. Không dùng fixture hay CPU
audit thay bằng chứng GPU. Có thể approve research riêng trong khi replay còn thiếu;
G-Core vẫn BLOCKED, đó là trạng thái đúng.

Chạy lại analysis trước để xem gate, không tự Resume session sang demo/release:

```powershell
$matrixPaths = @(
    '.\artifacts\logs\matrices\topic16-full-poster.json',
    '.\artifacts\logs\matrices\topic16-full-calibration.json',
    '.\artifacts\logs\matrices\topic16-full-benchmark.json',
    '.\artifacts\logs\matrices\topic16-full-custom.json'
)
.\scripts\Analyze-Results.ps1 -MatrixPaths $matrixPaths `
    -OutputDirectory .\reports\topic16-full `
    -ReviewPath .\reports\topic16-full\review\review.endorsed.json
```

File endorsed chưa tồn tại hiện tại. Command này chỉ dành cho endorsement thực tế,
không phải một bước đã chạy hoặc instruction sửa gate bằng tay.
