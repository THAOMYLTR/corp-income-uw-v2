<!--
Khung viết cho từng ô do LLM viết (report writer). Sửa file này để đổi cách viết,
không cần sửa code.

Cách dùng: mỗi ô là một mục "## TenO" (đúng tên biến trong template, không có {{ }}).
Nội dung bên dưới là khung LLM PHẢI theo — thứ tự các phần, số câu, cách mở đầu.
Ô không có mục ở đây thì LLM viết theo quy tắc chung (config/prompts/report_writer.md).
Ghi chú trong khối này không gửi cho LLM.
-->

## SanPhamDichVu
Đúng 3 dòng nối bằng "<br>":
Loại hình: <sản xuất / thương mại / dịch vụ> (<tỷ trọng nếu đa loại hình>) — <nguồn>
Tên ngành: <tên theo bảng ngành TCB, hoặc như hồ sơ + "chưa đối chiếu bảng ngành TCB">
Diễn giải chi tiết: <sản phẩm chính, quy mô, theo báo cáo thực địa — hoặc "Báo cáo thực địa chưa có thông tin">

## NhanXetHDKD
[BRD 29/10] Dòng "Cảnh báo HĐKD" dưới bảng mục 2 — CHỈ liệt kê cảnh báo, mỗi cảnh báo một gạch đầu dòng
ngắn (dưới 25 từ), không ghi tên file / thư mục / nguồn:
- báo cáo thực địa thiếu loại hình, ngành nghề;
- ảnh thực địa thiếu biển hiệu hoặc biển hiệu không có tên DN; không có người làm việc / máy móc không phù hợp ngành nghề;
- sản phẩm dịch vụ, ngành nghề, địa chỉ không khớp giữa báo cáo thực địa và tài liệu đối chiếu (ghi "<A> ≠ <B>");
- ngành nghề theo dữ liệu nội bộ TCB khác báo cáo thực địa → "rủi ro cao, đề nghị đánh giá lại".
Không có cảnh báo nào thì ghi đúng "—" (hệ thống tự ẩn dòng).

## NhaXuong
Địa chỉ nhà xưởng + "(đi thuê / sở hữu của … / chưa xác định)". Hồ sơ không có nhà xưởng thì ghi đúng "—" (hệ thống tự ẩn dòng).

## KhoHang
Địa chỉ kho hàng + "(đi thuê / sở hữu của … / chưa xác định)". Hồ sơ không có kho hàng thì ghi đúng "—" (hệ thống tự ẩn dòng).

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
