<!--
Template — Thẩm định nguồn thu doanh nghiệp. Same sections, rows and columns as the sheet
"Appendix - Corp income" of the BRD of 27/10/2026. This note is not part of the report.

Who fills what:
- CODE (from the documents / arithmetic, src/utils/report/appendix_context.py): mục 1 a-b,
  the comment draft of mục 1, Mô hình HĐKD, the whole of mục 3 (unit: triệu đồng), mục 4,
  the business-plan table, every "Phân nhóm" cell and the value of the income.
- LLM (src/templates/corp-income-cell-specs.md): SanPhamDichVu, the three addresses,
  NhanXetHDKD and KetLuanNguonThuDoanhNghiep; it also rewrites NhanXet and
  NhanXetTaiChinh from the code draft without losing any number.
- Years: {{Nam-1}} = the latest full year with a BCTC in the dossier, {{Nam-2}} the year
  before; {{NamHienTai}} = the months of the current year covered by the VAT returns.
- "Phân nhóm …" cells are POC only: CORP_INCOME_SHOW_GROUPS=0 leaves them empty.
-->
## PHỤ LỤC 01 - THẨM ĐỊNH NGUỒN THU DOANH NGHIỆP

| Tên doanh nghiệp | {{TenDoanhNghiep}} |
|---|---|

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

{{BangThanhVien}}

**Nhận xét về pháp lý Khách hàng**

{{NhanXet}}

---

### 2. Hoạt động kinh doanh

| Nội dung | Thông tin |
|---|---|
| Sản phẩm/ dịch vụ | {{SanPhamDichVu}} |
| Địa chỉ | - TSC: {{TruSoChinh}}<br>- Nhà xưởng: {{NhaXuong}}<br>- Kho hàng: {{KhoHang}} |
| Mô hình HĐKD (nếu có) | {{MoHinhHDKD}} |

**Nhận xét về HĐKD của Khách hàng**

{{NhanXetHDKD}}

---

### 3. Tài chính

| Nguồn | {{NguonTaiChinh}} |
|---|---|

**Tóm tắt tài chính (đơn vị tính: triệu đồng)**

<table>
<tr><th>Bảng cân đối kế toán</th><th>{{Nam-2}}</th><th>{{Nam-1}}</th><th>Báo cáo kết quả hoạt động kinh doanh</th><th>{{Nam-2}}</th><th>{{Nam-1}}</th><th>Cập nhật các tháng năm {{NamHienTai}}</th></tr>
<tr><td>Tổng tài sản</td><td>{{TongTaiSanN-2}}</td><td>{{TongTaiSanN-1}}</td><td>Doanh thu thuần</td><td>{{DTTN-2}}</td><td>{{DTTN-1}}</td><td>{{DTTCurrent}}</td></tr>
<tr><td>Tài sản ngắn hạn</td><td>{{TSNHN-2}}</td><td>{{TSNHN-1}}</td><td>Giá vốn hàng bán</td><td>{{GVHBN-2}}</td><td>{{GVHBN-1}}</td><td></td></tr>
<tr><td>Tài sản dài hạn</td><td>{{TSDHN-2}}</td><td>{{TSDHN-1}}</td><td>Lợi nhuận gộp</td><td>{{LNGN-2}}</td><td>{{LNGN-1}}</td><td></td></tr>
<tr><td>Tổng nguồn vốn</td><td>{{TongNguonVonN-2}}</td><td>{{TongNguonVonN-1}}</td><td>Doanh thu tài chính</td><td>{{DTTCN-2}}</td><td>{{DTTCN-1}}</td><td></td></tr>
<tr><td>Nợ phải trả</td><td>{{NoPhaiTraN-2}}</td><td>{{NoPhaiTraN-1}}</td><td>Chi phí tài chính</td><td>{{CPTCN-2}}</td><td>{{CPTCN-1}}</td><td></td></tr>
<tr><td>Vốn chủ sở hữu</td><td>{{VCSHN-2}}</td><td>{{VCSHN-1}}</td><td>Chi phí quản lý doanh nghiệp</td><td>{{CPQLN-2}}</td><td>{{CPQLN-1}}</td><td></td></tr>
<tr><td><b>Các chỉ số tài chính</b></td><td></td><td></td><td>Chi phí bán hàng</td><td>{{CPBHN-2}}</td><td>{{CPBHN-1}}</td><td></td></tr>
<tr><td>Biến động doanh thu</td><td>{{BienDongDTN-2}}</td><td>{{BienDongDTN-1}}</td><td>Lợi nhuận thuần</td><td>{{LNThuanN-2}}</td><td>{{LNThuanN-1}}</td><td></td></tr>
<tr><td>ROS (LN sau thuế/ DTT)</td><td>{{ROSN-2}}</td><td>{{ROSN-1}}</td><td>Lợi nhuận trước thuế</td><td>{{LNTTN-2}}</td><td>{{LNTTN-1}}</td><td></td></tr>
<tr><td>Hệ số thanh toán hiện hành</td><td>{{CurrentRatioN-2}}</td><td>{{CurrentRatioN-1}}</td><td>Lợi nhuận sau thuế</td><td>{{LNSTN-2}}</td><td>{{LNSTN-1}}</td><td></td></tr>
</table>

**Nhận xét về tài chính Khách hàng**

{{NhanXetTaiChinh}}

{{PhanNhomTaiChinh}}

---

### 4. Dư nợ tại TCTD

#### a. Ngày

{{NgayDuLieuCIC}}

#### b. Số dư cấp tín dụng hiện tại (Đvt: triệu đồng)

{{BangDuNoTCTD}}

#### c. Chất lượng tín dụng

| Nội dung | Thông tin |
|---|---|
| Thông tin nợ cần chú ý | {{SpecialMention}} |
| Thông tin nợ xấu | {{BadDebt}} |

{{PhanNhomBureau}}

---

### 5. Kết luận nguồn thu doanh nghiệp

{{BangPhuongAnKinhDoanh}}

{{PhanNhomDoanhNghiep}}

**Nhận xét về nguồn thu doanh nghiệp**

{{KetLuanNguonThuDoanhNghiep}}

{{KetLuan}}
