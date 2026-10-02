# Static tea-set video — main custom/demo scene

`tea_sets_2.mp4`: 64,066667 s, 720×1280, 30 FPS, 1.922 decoded frames.
Camera đi quanh bộ trà đứng yên. Video không vào Git.

Native extraction chọn 120 timestamps → 105 train/15 eval ở
`data/raw/custom/tea_sets_2/`; `video.json` lưu source/frame hashes và timestamps.
CPU COLMAP connected model 1 đăng ký đủ 120 ảnh; canonical data ở
`data/processed/canonical/custom-tea_sets_2/`.
Review evidence: `reports/custom_capture/tea_sets_2/{poses.png,projections.png,pose_evidence.json}`.
Agent visual audit đã ghi rõ reviewer/notes/hashes; human research/replay và
full GPU quality acceptance vẫn phải thực hiện.

Video đầu `tea_sets.mp4`: 66,533333 s, 1.996 frames; extracted 105 train/15 eval.
Có tay xoay khay trong nền tĩnh, giữ nguyên làm attempt cũ và không dùng làm
rigid-scene benchmark. Single-video held-out views có tương quan thời gian;
không diễn giải chúng thành independent multi-session generalization test.
