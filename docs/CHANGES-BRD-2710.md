# BRD 27/10/2026 + Document Matrix — what changed and where

Every change in the code carries the tag `[BRD 27/10]` (`grep -rn "BRD 27/10" src config testing`).
Rules of the BRD of 16/10 that did not change are still in place ([CHANGES-BRD-1610.md](CHANGES-BRD-1610.md)).
Each rule has a test in `testing/test_brd_2710.py`.

## Document matrix → folders and agents

| Change | File |
|---|---|
| Types carry the matrix **code** (100, 101, 200, 205, 208, 301, 302, 400, 401, 701, 706, 708), **matrix_agents** (CIA, LA, BA, FS, RA, CP, CR) and the matrix **validation** rules | `document_matrix.yaml`, `document_matrix.py` |
| CIA reads a type exactly when the matrix lists CIA — the loader refuses a mismatch; 400 / 401 (RA, CP) are listed, not read | `document_matrix.py` (`_load`) |
| New types: 101 giấy phép ngành nghề · hồ sơ quyền sử dụng nhà xưởng · báo cáo thực địa in folder I · sao kê, phần mềm bán hàng (205 alternatives) · tồn kho / TK 131 / 331 · tiến độ hợp đồng · 401 chứng thư định giá · CIC liên quan · 708 blacklist · 706 giới hạn tín dụng | `document_matrix.yaml` |
| Contracts / invoices moved to **III. Hồ sơ vay vốn** (301); the old "chung_tu_kinh_doanh" is split into 301, sao kê and TK 131/331 | `document_matrix.yaml` |
| Folder numbering: soạn thảo nội bộ = VII, khác = VIII; VIRAC added to internal data | `document_matrix.yaml` |
| Excel "Hồ sơ": matrix code, matrix agents, validation checklist | `excel_export.py`, `specialist.py` |

## Output template (sheet "Appendix - Corp income")

| Change | File |
|---|---|
| Every BRD table is written out in the template (headers, columns, row labels): members (1b), financial summary (3), CIC table with the two-row header TCTD → Số dư cấp tín dụng [NH, TDH, khác, tổng] → Tên / Giá trị / Chủ sở hữu TSBĐ (4b), business-plan table N-2 / N-1 / Cập nhật năm T / Năm kế hoạch / Cơ sở (5), and the three "Phân nhóm (POC)" tables with their criteria | `src/templates/corp-income-structure.md` |
| Code fills only cells and data rows: `{{RowsThanhVien}}` (one per member, + a legal rep without capital), `{{RowsDuNoTCTD}}` (one per TCTD + total), `PAKD_*`, `KQ_TaiChinh_*` / `KQ_Bureau_*` / `KQ_DoanhNghiep_*` (✔ on the group that applies) | `appendix_context.py` |
| Sections: 1 a-b, 2, 3, 4 a-c, **5. Kết luận nguồn thu doanh nghiệp** (the business-plan table sits in mục 5); one legal comment instead of two; no "Nhận xét dư nợ" cell (the interest-vs-CIC warning moved to the finance comment) | template, `appendix_context.py` |
| Mục 2: "Nguồn" row and the two partner tables removed → **Mô hình HĐKD** 5-tier diagram | `calculator/business_model.py` (new), pass **M9** `business_model_extraction` (new) |
| Mục 3: year headers show the year (2024, 2025); "Cập nhật các tháng năm N" only on the revenue row, as the VAT sentence | `appendix_context.py` |
| Hide rules: no plan → plan table removed; no basis → "Cơ sở" column removed; `CORP_INCOME_SHOW_GROUPS=0` → POC tables removed | `appendix_context.apply_output_conditions` |
| "Mối quan hệ" reads from each person's side ("vợ của …" / "… là vợ"); the prompt states the direction | `appendix_context._relations`, `shareholders_extraction.md` |

## Rules

| BRD line | Code |
|---|---|
| Mô hình HĐKD: thực địa → hợp đồng / hóa đơn → TK 131 / 331; ≤ 5 per side by value; suppliers left, buyers right; fewer than 5 → only real rows, no "khác"; no share → names and products only; partner without product → empty product block | `business_model.partners`, `business_model.diagram` |
| Tên ngành theo bảng ngành TCB | M9 prompt lists the names; `industry.lookup` |
| Good finance: biến động DT năm N **> 0%**, ROS > 0, HSTT ≥ 1 | `financial_metrics.GOOD_FINANCE_MIN_GROWTH` |
| DT BQ tháng năm N (VAT) / DT BQ tháng N-1 − 1 < −20% → warning | `financial_metrics.vat_summary`, `compute` [TT] |
| Good bureau also needs no card late payment in 3 years | `cic_extraction.md` (`card_late_payment_3y`), `cic_metrics.compute` |
| With PAKD: DT khả thi = min[PAKD; DT N × (1 + tăng trưởng ngành × k)], k = 1,5 Good corp; ROS khả thi = min{PAKD; max[ROS N; ROS ngành]}; LN = ROS × DT; Bad corp → no projection | `financial_metrics.income_estimate` [DP] |
| PAKD revenue > 20% above year N without a basis → warning | `financial_metrics.PLAN_GROWTH_NEEDS_BASIS` |
| Without PAKD: LNST hợp lý = LNST N-1 − DT tài chính − thu nhập khác; LNST trả nợ TDH = gốc TDH − khấu hao; lợi tức = (LNST hợp lý − LNST trả nợ TDH) × tỷ lệ góp vốn | unchanged, `income_estimate` |

## Decisions to confirm with the business owner

| Point | Chosen | Where to change |
|---|---|---|
| Good finance growth: Appendix "> 0%" vs detail sheet "> −20%" | 0% (Appendix = output template) | `GOOD_FINANCE_MIN_GROWTH` |
| Good corp growth factor: Appendix "× 1,5" vs detail sheet "× 2" | 1,5 | `GOOD_CORP_GROWTH_FACTOR` |
| "DT năm N × tốc độ tăng trưởng ngành" read as DT × (1 + tăng trưởng) | — | `income_estimate` |
| "Năm N" for the projection and the finance group = latest full year with a BCTC | — | `income_estimate`, `compute` |
| Biến động DT per column = that year vs the year before (first column only when data exist) | — | unchanged |
| Report title kept "PHỤ LỤC 01 - THẨM ĐỊNH NGUỒN THU DOANH NGHIỆP" so existing copies keep working | — | template first line |

## Bảng ngành tại TCB (PL1)

- `src/templates/bang-nganh-tcb.csv`: the full main table, 4 segments (SME, USME, MM, LC) × 110
  industries. ROS and growth differ by segment, so `industry.lookup(name, segment, sector)` reads the
  row of the company's segment — SME < 200 tỷ, USME < 600 tỷ, MM < 2000 tỷ, LC ≥ 2000 tỷ of net
  revenue in the latest year (`financial_metrics.segment_code`). The LLM picks "Ngành — Lĩnh vực"
  from the list ("Khác" exists in several sectors).
- `src/templates/bang-nganh-tcb-b2b-b2c.csv`: the second PL1 table (MSME / SME by B2B / B2C,
  30 groups each) — saved, **not used**: confirm with the business owner whether it replaces the
  main table for SME. Note: SME "Thương mại khác (B2C)" has ROS 0.8 where MSME has 0.08.
- Values to check in the main table: ROS > 50% (LC "Thương mại Nhựa" 0.94, LC "Dịch vụ Xuất bản
  khác" 1.10, MM "Khai thác dầu thô" 0.81, LC "Nhà phát triển BĐS xây dựng hạ tầng" 0.89) — they
  only raise the ROS floor max[ROS lịch sử; ROS ngành], the plan's ROS still caps it.
