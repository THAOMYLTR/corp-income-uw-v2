<!--
Khung viết cho từng ô do LLM viết (report writer). Sửa file này để đổi cách viết,
không cần sửa code.

Cách dùng: mỗi ô là một mục "## TenO" (đúng tên biến trong template, không có {{ }}).
Nội dung bên dưới là khung LLM PHẢI theo — thứ tự các phần, số câu, cách mở đầu.
Ô không có mục ở đây thì LLM viết theo quy tắc chung (config/prompts/report_writer.md).
Ghi chú trong khối này không gửi cho LLM.
-->

## NhanXet
[BRD 27/10] Ô nhận xét DUY NHẤT của mục 1 (pháp lý DN và pháp lý KH vay). Viết đúng khung:
**Kết luận:** <Phù hợp / Cần làm rõ / Rủi ro cao> — 1 câu: DN hoạt động bao lâu, KH vay sở hữu bao nhiêu %, có là NĐDPL không.
**Căn cứ:** số năm DN hoạt động; % vốn góp KH vay nắm giữ; vai trò NĐDPL; MST / tình trạng hoạt động đã đối chiếu — mỗi ý một gạch đầu dòng, ngắn gọn.
**Cảnh báo pháp lý cần đánh giá lại:** liệt kê nguyên văn các cảnh báo (tên/TSC/NĐDPL/năm thành lập không khớp, DN không hoạt động/tạm ngưng, tổng tỷ lệ sở hữu ≠ 100%, thay đổi thành viên/NĐDPL trong 12 tháng). Thông tin không khớp thì giữ nguyên phần "giá trị (bộ hồ sơ) ≠ giá trị (bộ hồ sơ)" của bản nháp.
Ô này KHÔNG ghi tên file, tên thư mục hay nguồn (KH cung cấp / thực địa / tra cứu…) — kể cả khi quy tắc chung yêu cầu nêu cơ sở. Chỉ nêu bộ hồ sơ (ĐKKD, Điều lệ, Tra cứu thuế…) ở chỗ thông tin không khớp.
**Ảnh hưởng tới quyết định:** 1 câu lấy từ "danh_gia_tin_dung.anh_huong_theo_muc.phap_ly" — làm quyết định mạnh lên hay yếu đi, vì sao.

## SanPhamDichVu
Đúng 3 dòng nối bằng "<br>":
Loại hình: <sản xuất / thương mại / dịch vụ> (<tỷ trọng nếu đa loại hình>) — <nguồn>
Tên ngành: <tên theo bảng ngành TCB, hoặc như hồ sơ + "chưa đối chiếu bảng ngành TCB">
Diễn giải chi tiết: <sản phẩm chính, quy mô, theo báo cáo thực địa — hoặc "Báo cáo thực địa chưa có thông tin">

## NhanXetHDKD
Viết đúng khung:
**Kết luận:** <Phù hợp / Cần làm rõ / Rủi ro cao> — 1 câu: DN làm gì, ở đâu, đã xác minh qua tài liệu nào.
**Đối chiếu:** 2–4 gạch đầu dòng, mỗi dòng: <nguồn A> vs <nguồn B> → khớp / không khớp (ngành nghề, sản phẩm, địa chỉ, đối tác).
**Cảnh báo:** các cảnh báo của mục 2 trong guidance (thiếu loại hình/ngành nghề, ảnh thiếu biển hiệu, sản phẩm/địa chỉ không khớp…).
**Cảnh báo bắt buộc kiểm tra:** báo cáo thực địa thiếu loại hình / ngành nghề; ảnh thực địa thiếu biển hiệu hoặc biển hiệu không có tên DN; không có người làm việc / số người / máy móc không phù hợp ngành nghề, loại hình; sản phẩm dịch vụ, địa chỉ không khớp giữa báo cáo thực địa và tài liệu đối chiếu.
**Đề xuất:** tài liệu cần bổ sung (hợp đồng đầu ra/đầu vào, hóa đơn, sổ TK 131/331, hợp đồng thuê…).
**Ảnh hưởng tới quyết định:** 1 câu lấy từ "danh_gia_tin_dung.anh_huong_theo_muc.hoat_dong_kinh_doanh" — làm quyết định mạnh lên hay yếu đi, vì sao.

## NhanXetTaiChinh
Giữ NGUYÊN mọi con số, tỷ lệ, năm trong bản nháp của hệ thống. Viết đúng khung:
**Kết luận:** <Tài chính ổn định / Có dấu hiệu suy giảm / BCTC có mâu thuẫn trọng yếu> — 1 câu.
**Cảnh báo dấu hiệu bất thường của BCTC:** gạch đầu dòng, nguyên văn số liệu.
**Trạng thái tài chính:** phân khúc; biến động doanh thu; hiệu quả (ROS, chất lượng lợi nhuận, lãi vay); thanh khoản — mỗi ý một dòng, có số.
**Doanh thu năm hiện tại:** theo tờ khai VAT (nếu có).
Dòng "Phân nhóm tài chính (POC)" giữ nguyên ở cuối nếu bản nháp có.
**Ảnh hưởng tới quyết định:** 1 câu lấy từ "danh_gia_tin_dung.anh_huong_theo_muc.tai_chinh" — làm quyết định mạnh lên hay yếu đi, vì sao.

## KetLuanNguonThuDoanhNghiep
[BRD 27/10] Mục 5 không còn ô nhận xét riêng cho phương án kinh doanh: nếu có PAKD, nêu trong
"Lý do chính" / "Rủi ro còn lại" việc doanh thu kế hoạch có cơ sở hay không (so với số lịch sử
và báo cáo thực địa) — KHÔNG tự đánh giá khả thi ngoài quy tắc (giá trị dự phóng hệ thống in bên dưới).
Viết đúng khung, theo "danh_gia_tin_dung" (quyết định đã chốt, KHÔNG đổi):
**Đề xuất: <Sử dụng / Sử dụng có điều kiện / Không sử dụng> nguồn thu doanh nghiệp để đánh giá năng lực trả nợ lần này.**
**Lý do chính:** 2–3 gạch đầu dòng mạnh nhất (rủi ro hoặc điểm mạnh), mỗi dòng có số liệu + nguồn.
**Rủi ro còn lại & biện pháp giảm thiểu:** chỉ rủi ro mức cao / trung bình.
**Điều kiện:** (khi "Sử dụng có điều kiện") điều kiện trước giải ngân / trong thời gian vay.
**Hồ sơ cần bổ sung / câu hỏi cho ĐVKD:** gạch đầu dòng cụ thể.
Không nhắc lại công thức / giá trị thu nhập — hệ thống in ngay bên dưới.
