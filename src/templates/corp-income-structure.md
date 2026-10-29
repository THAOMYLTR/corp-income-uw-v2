<!--
Template — Thẩm định nguồn thu doanh nghiệp, BRD 29/10/2026 (more compact than 27/10).
This note is not part of the report.

Who fills what:
- CODE (src/utils/report/appendix_context.py): every fact, number, table row and warning.
  {{RowsThanhVien}}, {{RowsCoCau}}, {{RowsTangTruong}} are data rows under a header written here;
  {{BangDuNoTCTD}} is a whole table (one column per credit institution, so it cannot be fixed here);
  {{BieuDoDuNo}} is the monthly debt chart (SVG image) shown to the right of it.
- LLM (src/templates/corp-income-cell-specs.md): SanPhamDichVu, TruSoChinh, NhaXuong, KhoHang,
  NhanXetHDKD, KetLuanNguonThuDoanhNghiep.
- Years: {{Nam-2}}, {{Nam-1}} = the two latest full years with a BCTC; {{PAKD_NamKeHoach}} = plan year.
- Shown only when (appendix_context.apply_output_conditions):
  "- Nhà xưởng: …" / "- Kho hàng: …" lines — only when the dossier has that address;
  {{CanhBaoPhapLy}}, {{NhanXetHDKD}} lines — only when there is something to warn about;
  class="pakd" tables — only with a business plan, else the class="no-pakd" sentence.
-->
## PHỤ LỤC 01 - THẨM ĐỊNH NGUỒN THU DOANH NGHIỆP

| Nội dung | Thông tin |
|---|---|
| Tên doanh nghiệp | {{TenDoanhNghiep}} |

### 1. Pháp lý doanh nghiệp

#### a. Thông tin cơ bản về pháp lý doanh nghiệp

| Nội dung | Thông tin |
|---|---|
| ID T24 (nếu có) | {{T24ID}} |
| Mã số thuế | {{MST}} |
| Năm thành lập | {{NamThanhLap}} |
| Người đại diện theo PL | {{NguoiDaiDien}} |
| Tình trạng hoạt động | {{TinhTrangHoatDong}} |

#### b. Thành viên góp vốn & người đại diện theo pháp luật

| Tên thành viên góp vốn/ ban lãnh đạo | Tỷ lệ vốn góp (%) | Chức vụ | Mối quan hệ | Mức độ ảnh hưởng tới Khách hàng | Đánh giá về năng lực, uy tín và kinh nghiệm |
|---|---|---|---|---|---|
{{RowsThanhVien}}

{{CanhBaoPhapLy}}

---

### 2. Hoạt động kinh doanh

#### a. Ngành nghề hoạt động kinh doanh

| Nội dung | Thông tin |
|---|---|
| Sản phẩm/ dịch vụ | {{SanPhamDichVu}} |

#### b. Mô tả hoạt động kinh doanh

| Nội dung | Thông tin |
|---|---|
| Địa chỉ | - TSC: {{TruSoChinh}}<br>- Nhà xưởng: {{NhaXuong}}<br>- Kho hàng: {{KhoHang}} |
| Mô hình hoạt động kinh doanh | {{MoHinhHDKD}} |

**Cảnh báo HĐKD:** {{NhanXetHDKD}}

---

### 3. Tài chính

| Nội dung | Thông tin |
|---|---|
| Nguồn | {{NguonTaiChinh}} |

**Tóm tắt tài chính (triệu đồng)**

#### a. Cơ cấu tài sản, nguồn vốn

<table>
<tr><th>Chỉ tiêu</th><th>{{Nam-2}}</th><th>% Tỷ trọng</th><th>{{Nam-1}}</th><th>% Tỷ trọng</th><th>Nhận xét</th></tr>
{{RowsCoCau}}
</table>

#### b. Quy mô & tăng trưởng & chỉ số

<table>
<tr><th>Chỉ tiêu</th><th>{{Nam-2}}</th><th>{{Nam-1}}</th><th>Tăng trưởng</th><th>Nhận xét</th></tr>
{{RowsTangTruong}}
</table>

---

### 4. Dư nợ tại TCTD

#### a. Tổng thông tin dư nợ doanh nghiệp (Đvt: triệu VNĐ)

<table class="layout"><tr><td class="layout-main">{{BangDuNoTCTD}}</td><td class="layout-side">{{BieuDoDuNo}}</td></tr></table>

#### b. Chất lượng tín dụng

| Nội dung | Thông tin |
|---|---|
| Thông tin nợ cần chú ý | {{SpecialMention}} |
| Thông tin nợ xấu | {{BadDebt}} |

---

### 5. Kết luận nguồn thu doanh nghiệp

#### a. Dự phóng kinh doanh {{PAKD_NamKeHoach}} (nếu có)

<p class="no-pakd">Khách hàng không cung cấp phương án kinh doanh.</p>

<table class="pakd">
<tr><th>Chỉ tiêu</th><th>TH {{Nam-1}}</th><th>KH {{PAKD_NamKeHoach}}</th><th>Tăng/ giảm</th><th>Cơ sở dự phóng</th></tr>
<tr><td>Doanh thu thuần</td><td>{{DTTN-1}}</td><td>{{PAKD_DTT_KeHoach}}</td><td>{{PAKD_DTT_TangGiam}}</td><td rowspan="3">{{PAKD_CoSo}}</td></tr>
<tr><td>Giá vốn</td><td>{{GVHBN-1}}</td><td>{{PAKD_GV_KeHoach}}</td><td>{{PAKD_GV_TangGiam}}</td></tr>
<tr><td>LNST</td><td>{{LNSTN-1}}</td><td>{{PAKD_LNST_KeHoach}}</td><td>{{PAKD_LNST_TangGiam}}</td></tr>
</table>

<table class="pakd">
<tr><th>Chỉ tiêu</th><th>Theo am hiểu ngành TCB</th><th>Theo dự phóng</th><th>Cơ sở dự phóng</th></tr>
<tr><td>ROS</td><td>{{Nganh_ROS}}</td><td>{{PAKD_ROS}}</td><td rowspan="2">{{Nganh_CoSo}}</td></tr>
<tr><td>Tăng trưởng ngành</td><td>{{Nganh_TangTruong}}</td><td>{{PAKD_TangTruong}}</td></tr>
</table>

#### b. Đề xuất

{{KetLuanNguonThuDoanhNghiep}}

{{KetLuan}}
