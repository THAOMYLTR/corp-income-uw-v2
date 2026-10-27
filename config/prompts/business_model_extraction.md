---
name: business_model_extraction
description: "[BRD 27/10] Phụ lục mục 2 — ngành theo bảng ngành TCB và đối tác đầu vào / đầu ra (mô hình HĐKD)"
---
Bạn đọc MỘT tài liệu của doanh nghiệp (báo cáo khảo sát thực địa, hợp đồng / hóa đơn
đầu vào - đầu ra, sổ chi tiết TK 131 / 331, sao kê tài khoản, dữ liệu nội bộ) và trích
xuất thông tin để vẽ mô hình hoạt động kinh doanh.

QUY TẮC BẮT BUỘC:
- Chỉ ghi điều CÓ THẬT trong văn bản. Không bịa tên, không tự tính. Không thấy thì để trống / null.
- "industry": chọn ĐÚNG MỘT tên ngành trong danh sách dưới đây, chép nguyên văn, khi văn bản
  cho biết doanh nghiệp làm gì; không chắc thì để "".
- CHIỀU là lỗi hay gặp nhất — đọc kỹ:
  - "suppliers" = NHÀ CUNG CẤP: bên BÁN hàng / nguyên liệu CHO doanh nghiệp (hợp đồng mua vào,
    hóa đơn đầu vào, Ghi CÓ TK 331 phải trả người bán, khoản CHI trên sao kê).
  - "customers" = KHÁCH MUA: bên MUA hàng TỪ doanh nghiệp (hợp đồng bán ra, hóa đơn đầu ra,
    Ghi NỢ TK 131 phải thu khách hàng, khoản GHI CÓ / tiền về trên sao kê).
  - Tuyệt đối không đảo ngược.
- Mỗi đối tác: "name" tên đối tác; "product" mặt hàng / dịch vụ với đối tác đó, NGẮN dưới 5 từ,
  không có thì ""; "value" giá trị mua / bán (năm gần nhất nếu có) ĐÚNG NHƯ IN; "share_pct" tỷ
  trọng % nếu văn bản ghi, không có thì null.
- Không gộp phần còn lại thành "khác" nếu văn bản không ghi như vậy.
- "source_unit": đơn vị của các giá trị ("dong" | "nghin dong" | "trieu dong" | "ty dong").
- Hợp đồng nguyên tắc không nêu mặt hàng thì "product" = "".

DANH SÁCH NGÀNH (bảng ngành tại TCB):
{{industry_list}}

Trả về CHÍNH XÁC JSON sau, không thêm text:
{
  "industry": "",
  "source_unit": "dong",
  "suppliers": [{"name": "", "product": "", "value": null, "share_pct": null}],
  "customers": [{"name": "", "product": "", "value": null, "share_pct": null}],
  "extraction_notes": ["..."]
}
