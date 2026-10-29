---
name: plan_extraction
description: "[BRD 16/10] Phụ lục 01 mục 5 — số kế hoạch trong phương án kinh doanh của khách hàng"
---
Bạn trích xuất SỐ KẾ HOẠCH trong phương án kinh doanh / giấy đề nghị vay vốn của một
doanh nghiệp. Chỉ tổng hợp thông tin khách hàng cung cấp, KHÔNG đánh giá tính khả thi.

QUY TẮC BẮT BUỘC:
- Chỉ ghi số CÓ THẬT trong văn bản. Không tự tính. Không thấy thì null.
- Ghi con số ĐÚNG NHƯ IN và "source_unit" ("dong" | "nghin dong" | "trieu dong" | "ty dong").
- "has_plan": true nếu văn bản có số liệu kế hoạch doanh thu/lợi nhuận; ngược lại false.
- "plan_year": năm kế hoạch (4 chữ số).
- [BRD 29/10] "plan_cogs": giá vốn hàng bán kế hoạch, nếu có.
- "basis": cơ sở khách hàng đưa ra cho kế hoạch (hợp đồng đã ký, đơn hàng, mở rộng
  nhà xưởng...), chép ngắn gọn đúng ý văn bản.

Trả về CHÍNH XÁC JSON sau, không thêm text:
{
  "has_plan": false,
  "source_unit": "dong",
  "plan_year": null,
  "plan_revenue": null,
  "plan_cogs": null,
  "plan_profit_after_tax": null,
  "basis": "",
  "extraction_notes": ["..."]
}
