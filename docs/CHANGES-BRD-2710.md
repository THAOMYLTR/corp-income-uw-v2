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
| Same sections / rows / columns as the Appendix: 1 a-b, 2, 3, 4 a-c, **5. Kết luận nguồn thu doanh nghiệp** (the business-plan table now sits in mục 5) | `src/templates/corp-income-structure.md` |
| One legal comment ("Nhận xét về pháp lý Khách hàng") instead of two; the members table lists every member and a legal rep without capital | `appendix_context.py` |
| Mục 2: "Nguồn" row and the two partner tables removed → **Mô hình HĐKD** 5-tier diagram | `calculator/business_model.py` (new), pass **M9** `business_model_extraction` (new) |
| Mục 3: year headers show the year (2024, 2025); "Cập nhật các tháng năm N" only on the revenue row, as the VAT sentence | `appendix_context.py` |
| Mục 4: one row per TCTD with Tên / Giá trị / Chủ sở hữu TSBĐ; cam kết ngoại bảng in "Dư nợ khác"; no "Nhận xét dư nợ" cell (the interest-vs-CIC warning moved to the finance comment) | `cic_metrics.py`, `appendix_context.py` |
| "Phân nhóm tài chính / bureau / doanh nghiệp (POC)" are their own cells (`CORP_INCOME_SHOW_GROUPS=0` empties them) | template, `appendix_context._group_line` |
| Business-plan table: hidden without a plan; "Cơ sở của Khách hàng" column hidden when the plan gives none | `appendix_context.plan_table` |

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

## Data still needed

- **PL1 Bảng ngành tại TCB**: only 13 rows (SME / Recom) reached the repo. Paste the remaining rows
  into `src/templates/bang-nganh-tcb.csv` (same columns).
