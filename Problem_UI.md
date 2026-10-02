1. browser/hardware matrix dùng brave với chrome hay microsoft edge

2. Chiến lược CSS/styling implementation
Thiếu: Design tokens có, nhưng không nói dùng CSS Modules, Tailwind, styled-components, hay plain CSS. Điều này ảnh hưởng lớn đến cấu trúc code frontend.

3. Web Worker cho PLY parsing
Thiếu: Parse PLY 392 MiB (Garden) trên main thread sẽ block UI. Không có mention về Web Worker hay streaming parser.

Đề xuất: Thêm mục "Parsing strategy" — dùng Web Worker cho PLY decode, transferable ArrayBuffers, progress callback.

4. Loading sequence chi tiết cho workspace
Thiếu: Khi mở workspace, thứ tự load gì trước? Catalog → thumbnail → presets → Gaussian? Có skeleton screen không? Điều này quan trọng cho perceived performance.

5. Onboarding lần đầu
Thiếu: Người dùng mới mở UI lần đầu sẽ thấy gì? Có tooltip/hướng dẫn không? Không nên bắt họ đọc tài liệu.

Đề xuất: Thêm "First-run experience" — overlay ngắn 3 bước: chọn cảnh → xem 3D → so sánh.

6. Xử lý Windows display scaling và DPI
Thiếu: Windows thường scale 125%/150%. Canvas 3D và pixel coordinates (đặc biệt crop/wipe) có thể bị lệch nếu không xử lý devicePixelRatio đúng. Document có mention DPR cap nhưng không nói về OS scaling.

7. Color blindness / High contrast mode
Thiếu: Method colors (xanh lam vs xanh ngọc) có thể khó phân biệt với người mù màu. Không có mention Windows High Contrast mode hay forced-colors.

Đề xuất: Thêm pattern/icon khác biệt ngoài màu; test với simulated deuteranopia.

8. Touch/mobile 3D controls
Thiếu: Viewport <768px nói "single viewer mặc định" nhưng không nói rõ touch gestures cho orbit/pan/zoom trên tablet. Pinch zoom? Two-finger rotate?

9. i18n strategy
Thiếu: UI mặc định tiếng Việt, giữ tên Nerfacto/Splatfacto. Nhưng nếu sau này muốn English? Không có mention về i18n framework hay tách strings.

10. New scene addition workflow
Thiếu: Document nói "Thêm scene mới bằng catalog, không phải sửa component" nhưng không mô tả workflow cụ thể: ai chạy gì, validate ra sao, cập nhật catalog thế nào.

11. Error boundary strategy (React)
Thiếu: Nếu một component 3D crash, có error boundary để không sập toàn app không?

12. Print/export report
Thiếu: Có export CSV/JSON/SVG/PNG cho chart, nhưng không có "export toàn bộ benchmark thành PDF/report" — có thể cần cho mục đích trình bày.

13. Cache eviction policy chi tiết
Thiếu: Max disk 2 GiB, LRU — nhưng ai trigger eviction? Khi nào? Có background job không?

14. Server port conflict handling
Có mention "Launcher báo port và process/service conflict; không kill process lạ" — nhưng không nói có auto-retry port khác không.

15. Backup/restore bookmarks
Thiếu: Bookmarks lưu localStorage hoặc server. Nếu user xóa cache, mất hết. Có export/import bookmarks không?

16. Testing trên CI
Thiếu: Không có mention về CI pipeline cho frontend tests. Chỉ có Test-UI.ps1 local.

17. Bundle size budget
Thiếu: Vite build ra bao nhiêu? Có code splitting không? Gallery vs Workspace vs Benchmark nên lazy load.

18. Accessibility audit cụ thể
Có mention accessibility trong 11.4 nhưng không có:

WCAG level target (A/AA/AAA)

Screen reader testing plan (NVDA/JAWS?)

Keyboard navigation map đầy đủ

19. Performance measurement methodology
Có targets nhưng không nói đo thế nào: Chrome DevTools? Lighthouse? Custom instrumentation?

20. Phiên bản hóa catalog và migration
Có mention schema_version và catalog_revision, nhưng không nói khi nào bump version, migration path giữa các version.

Những câu hỏi thiết kế chưa được trả lời
Khi user resize cửa sổ browser, canvas 3D có re-render không? Có debounce không?

Khi user mở nhiều tab cùng lúc? Có giới hạn session không?

Nếu user tắt browser giữa chừng khi đang render? Job có bị orphan không?

Làm sao để user biết một scene có inference available? Badge trên card? Tooltip?

Có keyboard shortcut nào để chuyển tab không? (1/2/3 cho 3 tab?)

Khi so sánh 2 methods, nếu một method lỗi, UI hiển thị gì? (Có mention trong error table nhưng chưa rõ UX)

Đánh giá tổng thể
Tiêu chí	Điểm (1-10)	Nhận xét
Độ đầy đủ	8.5	Rất chi tiết, thiếu vài practical details
Tính khả thi	9	Lộ trình thực tế, có spike phase
Chất lượng kỹ thuật	9.5	Contracts, alignment, lifecycle xuất sắc
UX completeness	7.5	Thiếu onboarding, mobile touch, a11y details
Testing strategy	8	Có acceptance matrix, thiếu CI/automation
Documentation	9	Rõ ràng, có ví dụ, có nguồn
Kết luận: Tài liệu đủ để bắt đầu triển khai Phase 0, nhưng nên bổ sung một "Appendix: Practical Details" trước Phase 1 để tránh phải quyết định ad-hoc trong lúc code. Những thiếu sót chính không phải về kiến trúc (đã rất tốt) mà là về chi tiết vận hành UI (loading, onboarding, touch, browser support, styling approach).

Ưu tiên bổ sung:

Browser/hardware matrix (cao)

Web Worker PLY parsing (cao)

CSS/styling approach (cao)

Loading sequence + skeleton (trung bình)

Touch controls cho tablet (trung bình)

Color blindness/a11y testing (trung bình)

i18n strategy (thấp — có thể để sau)

CI pipeline (thấp — có thể để Phase 4)