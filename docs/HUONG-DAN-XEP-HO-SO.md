# Hướng dẫn xếp hồ sơ vào các thư mục (theo Document Matrix 27/10/2026)

Mỗi hồ sơ là một thư mục (`INPUT_PATHS`), bên trong có 7 thư mục con — mỗi thư mục là một phần
của Document Matrix. Agent CIA (Corp Income Agent) đọc các thư mục này. Danh sách loại giấy tờ
đầy đủ, mã ma trận, agent sử dụng và từ khóa nhận diện nằm ở
[`src/agents/documents/document_matrix.yaml`](../src/agents/documents/document_matrix.yaml) —
muốn thêm loại giấy tờ mới thì sửa ở đó.

| Thư mục | Phần ma trận | Để giấy tờ gì |
|---|---|---|
| **`ho_so_phap_ly`** | I. Hồ sơ pháp lý | **100** ĐKKD / Giấy CNĐKDN / Giấy CNĐT, điều lệ, sổ cổ đông / sổ đăng ký thành viên, HĐ chuyển nhượng vốn · **101** giấy phép kinh doanh ngành nghề có điều kiện · hồ sơ quyền sử dụng nhà xưởng / kho / trụ sở (HĐ thuê, GCN QSDĐ) · báo cáo khảo sát thực địa (nếu ĐVKD để ở đây) · QĐ bổ nhiệm, nghị quyết, QĐ xử phạt, biên bản thanh tra, hồ sơ tranh chấp |
| **`ho_so_tai_chinh`** | II. Hồ sơ tài chính | **200** BCTC 2 năm gần nhất, thuyết minh / báo cáo kiểm toán · **205** tờ khai VAT; nếu không có: sao kê tài khoản DN (6 tháng), phần mềm bán hàng (12 tháng) · chi tiết tồn kho, sổ chi tiết TK 131 / 331 · thông báo nợ thuế, xác nhận BHXH |
| **`ho_so_vay_von`** | III. Hồ sơ vay vốn | **302** phương án kinh doanh, đề nghị cấp tín dụng, kế hoạch sử dụng vốn · **301** hợp đồng kinh tế, hóa đơn đầu vào – đầu ra · hồ sơ tiến độ thực hiện hợp đồng (nghiệm thu, bàn giao) |
| **`ho_so_tai_san_dam_bao`** | IV. Hồ sơ TSBĐ | **400** hồ sơ TSBĐ · **401** chứng thư định giá — CIA không đọc (agent RA, CP) |
| **`ho_so_noi_bo`** | V. Hồ sơ nội bộ | **208** CIC doanh nghiệp (S10A, R20) · CIC của ĐDPL / cổ đông ≥ 30% · **708** kết quả tra cứu blacklist / fraud · bản tra cứu tracuunnt / masothue / bocaodientu · bản in T24 / BCDE / BEP / DBX / VIRAC |
| **`ho_so_soan_thao_noi_bo`** | VII. Hồ sơ nội bộ soạn thảo | **701** báo cáo khảo sát và đề xuất tín dụng, hình ảnh khảo sát · **706** báo cáo giới hạn tín dụng |
| **`ho_so_khac`** | VIII. Hồ sơ khác | overlay CIC, báo cáo adhoc, hồ sơ bổ sung ngoài danh mục |

## Lưu ý

- **Hợp đồng / hóa đơn đầu vào – đầu ra** để ở `ho_so_vay_von` (mã 301 — đã chuyển từ
  `ho_so_tai_chinh` theo ma trận mới). Sổ chi tiết TK 131 / 331 và sao kê vẫn ở `ho_so_tai_chinh`.
  Các tài liệu này (cùng báo cáo khảo sát thực địa) là nguồn để vẽ **Mô hình HĐKD**.
- **Phương án kinh doanh** để ở `ho_so_vay_von`, tên file nên có chữ **"pakd"** hoặc
  **"phuong an"** (vd `PAKD_2026.pdf`): đây là tài liệu duy nhất được đọc số kế hoạch cho mục 5.
- **CIC**: bản tin S10A và R20 phải tra cứu trong vòng 1 tháng tính đến ngày phân tích. CIC của
  người đại diện / cổ đông để riêng (tên file có "cic ca nhan", "cic ddpl", "cic co dong") để không
  bị cộng vào dư nợ của doanh nghiệp.
- **KH cá nhân vay vốn**: để `BORROWER_NAMES = []` thì hệ thống tự tìm tên trong `ho_so_vay_von`
  (rồi `ho_so_soan_thao_noi_bo`). Điền tay thì tên điền tay được ưu tiên.
- Để nhầm thư mục không làm hỏng kết quả: hệ thống đọc nội dung và báo trong "Steps" file nào có
  nội dung khớp thư mục khác. Nhưng nên để đúng thư mục, vì việc nhận loại giấy tờ dựa trên thư mục.
- Các yêu cầu "đủ dấu, đủ trang, chữ ký…" của ma trận được liệt kê ở sheet **Hồ sơ** của file
  Excel để người dùng xác nhận.
