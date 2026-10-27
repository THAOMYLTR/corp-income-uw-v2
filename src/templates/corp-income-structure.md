<!--
Template — Thẩm định nguồn thu doanh nghiệp. Same sections, tables, rows and columns as the
sheet "Appendix - Corp income" of the BRD of 27/10/2026. This note is not part of the report.

Who fills what:
- CODE (src/utils/report/appendix_context.py): every fact, number, table row and group.
  {{RowsThanhVien}} and {{RowsDuNoTCTD}} are the data rows of their table (one per member /
  per TCTD); every other cell is one placeholder.
- LLM (src/templates/corp-income-cell-specs.md): SanPhamDichVu, TruSoChinh, NhaXuong, KhoHang,
  NhanXetHDKD, KetLuanNguonThuDoanhNghiep; it also rewrites NhanXet and NhanXetTaiChinh from the
  code draft without losing any number.
- Years: {{Nam-2}}, {{Nam-1}} = the two latest full years with a BCTC; {{NamHienTai}} = year N
  (months covered by the VAT returns); {{PAKD_NamKeHoach}} = the plan year.
- Shown only when (applied after filling, appendix_context.apply_output_conditions):
  table id="pakd"   — only when the customer gives a business plan (BRD: "ẩn đi bảng tính này");
  class="coso"      — the "Cơ sở của Khách hàng" column, only when the plan states a basis;
  class="poc"       — the three "Phân nhóm … (POC)" tables; CORP_INCOME_SHOW_GROUPS=0 hides them.
  In a "Kết quả" column the group that applies is marked "✔" with its basis.
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

| Họ và tên | Mối quan hệ | Tỷ lệ góp vốn | Các thông tin về thay đổi thành viên góp vốn và người đại diện theo pháp luật trong 12 tháng gần nhất (nếu có) |
|---|---|---|---|
{{RowsThanhVien}}

| Nội dung | Thông tin |
|---|---|
| Nhận xét về pháp lý Khách hàng | {{NhanXet}} |

---

### 2. Hoạt động kinh doanh

| Nội dung | Thông tin |
|---|---|
| Sản phẩm/ dịch vụ | {{SanPhamDichVu}} |
| Địa chỉ | - TSC: {{TruSoChinh}}<br>- Nhà xưởng: {{NhaXuong}}<br>- Kho hàng: {{KhoHang}} |
| Mô hình HĐKD (nếu có) | {{MoHinhHDKD}} |
| Nhận xét về HĐKD của Khách hàng | {{NhanXetHDKD}} |

---

### 3. Tài chính

| Nội dung | Thông tin |
|---|---|
| Nguồn | {{NguonTaiChinh}} |

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

| Nội dung | Thông tin |
|---|---|
| Nhận xét về tài chính Khách hàng | {{NhanXetTaiChinh}} |

<table class="poc">
<tr><th>Phân nhóm tài chính doanh nghiệp (POC)</th><th>Phân loại</th><th>Tiêu chí</th><th>Kết quả</th></tr>
<tr><td>Nhóm 1</td><td>Tài chính có vấn đề</td><td>BCTC mâu thuẫn trọng yếu theo bộ dấu hiệu cảnh báo bất thường nêu trên</td><td>{{KQ_TaiChinh_1}}</td></tr>
<tr><td>Nhóm 2</td><td>Tài chính bình thường</td><td>Không thuộc nhóm 1 và nhóm 3</td><td>{{KQ_TaiChinh_2}}</td></tr>
<tr><td>Nhóm 3</td><td>Tài chính tốt</td><td>Biến động doanh thu năm N &gt; 0%, và LNST/ doanh thu thuần năm N &gt; 0%, và hệ số thanh toán hiện hành ≥ 1</td><td>{{KQ_TaiChinh_3}}</td></tr>
</table>

---

### 4. Dư nợ tại TCTD

#### a. Ngày

| Nội dung | Thông tin |
|---|---|
| Ngày tra cứu CIC | {{NgayDuLieuCIC}} |

#### b. Số dư cấp tín dụng hiện tại (Đvt: triệu đồng)

<table>
<tr><th rowspan="2">TCTD</th><th colspan="4">Số dư cấp tín dụng</th><th rowspan="2">Tên TSBĐ</th><th rowspan="2">Giá trị TSBĐ</th><th rowspan="2">Chủ sở hữu TSBĐ</th></tr>
<tr><th>Dư nợ ngắn hạn</th><th>Dư nợ TDH</th><th>Dư nợ khác</th><th>Tổng số dư CTD</th></tr>
{{RowsDuNoTCTD}}
</table>

#### c. Chất lượng tín dụng

| Nội dung | Thông tin |
|---|---|
| Thông tin nợ cần chú ý | {{SpecialMention}} |
| Thông tin nợ xấu | {{BadDebt}} |

<table class="poc">
<tr><th>Phân nhóm bureau (POC)</th><th>Phân loại</th><th>Tiêu chí</th><th>Kết quả</th></tr>
<tr><td>Nhóm 1</td><td>Bad bureau</td><td>Hit tiêu chí lịch sử sử dụng tín dụng theo chính sách TCB: KHDN có nợ xấu trong 24 tháng gần nhất hoặc nợ cần chú ý trong 12 tháng gần nhất</td><td>{{KQ_Bureau_1}}</td></tr>
<tr><td>Nhóm 2</td><td>Normal bureau</td><td>Không thuộc nhóm 1 và nhóm 3</td><td>{{KQ_Bureau_2}}</td></tr>
<tr><td>Nhóm 3</td><td>Good bureau</td><td>Không chậm thanh toán thẻ trong 03 năm và không nợ xấu trong 05 năm gần nhất, và dư nợ BQ 12 tháng / doanh thu BQ tháng không vượt ngưỡng: thương mại 6, sản xuất 9, dịch vụ xây lắp 9, dịch vụ khác 6</td><td>{{KQ_Bureau_3}}</td></tr>
</table>

---

### 5. Kết luận nguồn thu doanh nghiệp

<table id="pakd">
<tr><th>Phương án kinh doanh (nếu có)</th><th>{{Nam-2}}</th><th>{{Nam-1}}</th><th>Cập nhật năm T</th><th>Năm kế hoạch {{PAKD_NamKeHoach}}</th><th class="coso">Cơ sở của Khách hàng</th></tr>
<tr><td>Doanh thu thuần</td><td>{{DTTN-2}}</td><td>{{DTTN-1}}</td><td>{{PAKD_DTT_CapNhat}}</td><td>{{PAKD_DTT_KeHoach}}</td><td class="coso">{{PAKD_DTT_CoSo}}</td></tr>
<tr><td>Biến động doanh thu thuần</td><td>{{BienDongDTN-2}}</td><td>{{BienDongDTN-1}}</td><td></td><td>{{PAKD_TangTruong_KeHoach}}</td><td class="coso"></td></tr>
<tr><td>Lợi nhuận sau thuế</td><td>{{LNSTN-2}}</td><td>{{LNSTN-1}}</td><td></td><td>{{PAKD_LNST_KeHoach}}</td><td class="coso"></td></tr>
<tr><td>ROS (LNST/DTT)</td><td>{{ROSN-2}}</td><td>{{ROSN-1}}</td><td></td><td>{{PAKD_ROS_KeHoach}}</td><td class="coso"></td></tr>
</table>

<table class="poc">
<tr><th>Phân nhóm doanh nghiệp (POC)</th><th>Phân loại</th><th>Tiêu chí</th><th>Kết quả</th></tr>
<tr><td>Nhóm 1</td><td>Bad corp</td><td>Thuộc 1 trong các tiêu chí: DN không hoạt động theo tra cứu thuế, thông tin pháp lý không phù hợp giữa các chứng từ, thời gian thành lập &lt; 12 tháng; DN không hoạt động theo thẩm định thực tế; Bad finance; Bad bureau → không sử dụng nguồn thu doanh nghiệp, không đánh giá dự phóng</td><td>{{KQ_DoanhNghiep_1}}</td></tr>
<tr><td>Nhóm 2</td><td>Normal corp</td><td>Không thuộc nhóm 1 và nhóm 3</td><td>{{KQ_DoanhNghiep_2}}</td></tr>
<tr><td>Nhóm 3</td><td>Good corp</td><td>Good finance và Good bureau</td><td>{{KQ_DoanhNghiep_3}}</td></tr>
</table>

| Nội dung | Thông tin |
|---|---|
| Nhận xét về nguồn thu doanh nghiệp | {{KetLuanNguonThuDoanhNghiep}}<br><br>{{KetLuan}} |
