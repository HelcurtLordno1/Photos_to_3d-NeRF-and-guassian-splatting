# Report workspace

Nguồn LaTeX/Word, bảng và figure của báo cáo cuối kỳ. Không đặt checkpoint hoặc
dataset trong thư mục này.

`topic16-full/` là full primary selection đã hoàn tất ngày 2026-10-02. Đọc
[báo cáo nghiên cứu](topic16-full/review/research_review.md), hoặc mở
`topic16-full/review/research_review.html` để đọc offline/in PDF bằng browser.
`case-gallery.html` có 14 góc camera, cùng crop/error map và nguồn/checksum.
Source replay bundle và runbook ở cùng folder; approval hiện vẫn pending,
không gọi clean-Python artifact audit là independent GPU replay.

`diagnostic/` có kết quả **100 steps** chạy thật trên poster/bonsai, không là
primary benchmark. `custom_capture/` có contact sheets, camera frustums và sparse projections
của static scene tea_sets_2; video tea_sets đầu giữ làm attempt cũ. `report_template.md` là outline báo cáo, không tự sinh kết luận thực nghiệm.
Reports mới tạo bằng `Analyze-Results.ps1` từ explicit matrix paths; selection/
release manifests chỉ tạo khi G-Core thật sự PASS.
