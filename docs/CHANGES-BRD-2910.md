# BRD 29/10/2026 — output template (cô đọng hơn)

Only the presentation changed; the 27/10 rules and the document matrix stay
([CHANGES-BRD-2710.md](CHANGES-BRD-2710.md)). Tag in the code: `[BRD 29/10]`. Tests: `testing/test_brd_2710.py`
(classes `PlanTableTest`, `AddressLinesTest`, `FinanceTablesTest`, `DebtTableTest`, `TemplateTest`).

| Section | Change | File |
|---|---|---|
| 1a | Unchanged | — |
| 1b | Columns: Tên thành viên góp vốn/ ban lãnh đạo · Tỷ lệ vốn góp (%) · Chức vụ · Mối quan hệ (với KH vay) · Mức độ ảnh hưởng · Đánh giá năng lực, uy tín, kinh nghiệm. % as before; the last four from the **site-visit report** (new `people` list in `shareholders_extraction.md`). Rows: members by %, then legal reps and managers without capital (0%). No "thay đổi 12 tháng" column — those changes stay as warnings | template, `appendix_context.py` (`_field_people`, `_position`, `_relation_to_borrower`) |
| 1 | No "Nhận xét pháp lý" row: a "Cảnh báo pháp lý" list appears only when there is a warning | `appendix_context.py` |
| 2a / 2b | Headings "Ngành nghề hoạt động kinh doanh" / "Mô tả hoạt động kinh doanh". Nhà xưởng / kho hàng lines are **skipped** when the dossier has none. "Cảnh báo HĐKD" only when there is one | template, `apply_output_conditions`, `corp-income-cell-specs.md` |
| 3a | **Cơ cấu tài sản, nguồn vốn**: Tổng tài sản + asset lines with **≥ 20%** of total assets in either year (tiền, ĐTTC NH, phải thu & trả trước, HTK, TSNH khác, **TSCĐ ròng** (new field `fixed_assets`), TSDH khác); one comment cell: BCĐKT anomalies, khoản mục > 50%, thương mại TSDH > 50%, sản xuất không TSDH, dịch vụ HTK > 30%, vốn lưu động ròng | `financial_metrics.asset_lines`, `structure_remarks`, `bs_warnings` |
| 3b | **Quy mô & tăng trưởng & chỉ số**: DTT, LNST, ROS, HSTT; column **"Tăng trưởng"** = năm sau / năm trước − 1, shown **+x% / -x%**; one comment cell: KQKD anomalies, phân khúc, suy giảm, hiệu quả, thanh khoản, tờ khai VAT | `financial_metrics.signed_pct`, `pl_warnings` |
| 3 | Interest check: chi phí lãi vay / dư nợ BQ 12 tháng CIC outside **6%–14%/năm** (was 50%–200% of × 10%) | `financial_metrics.interest_vs_cic` |
| 3 | The wide BCĐKT / KQKD table and "Cập nhật các tháng năm N" column are gone (the VAT sentence moved to the 3b comment) | template |
| 4a | Table: one column per TCTD + Tổng; rows Ngắn hạn, Dài hạn, Cho thuê TC (new field `finance_lease`), (Dư nợ khác), Tổng, %, Trung bình dư nợ 12 tháng, Cam kết ngoại bảng tại … (*), Tổng giá trị TSBĐ theo CIC (**). Cam kết ngoại bảng is no longer added to "Tổng". No CIC → "Không có thông tin" | `appendix_context.debt_table`, `cic_metrics.py` |
| 4a | **Chart** to the right of the table: dư nợ by month from CIC S10A (2.6), dashed line at the 12-month average | `utils/report/visualization/debt_chart.py` |
| 5a | **Dự phóng kinh doanh** (only with a PAKD): TH vs KH for DTT, giá vốn (new field `plan_cogs`), LNST, Tăng/giảm, Cơ sở dự phóng; ROS and tăng trưởng ngành **theo am hiểu ngành TCB** (bảng ngành, by segment) vs **theo dự phóng** (LNST KH / DTT KH; DTT KH / DTT TH − 1) | template, `appendix_context.plan_cells` |
| 5b | Đề xuất: unchanged logic (Bad corp → không sử dụng; projection formulas as 27/10) | `financial_metrics.income_estimate`, `appendix_context.income_block` |
| — | "Phân nhóm (POC)" tables removed; `CORP_INCOME_SHOW_GROUPS` no longer used. Groups still drive 5b | template, `appendix_context.py` |
| — | The legal / finance comments are no longer rewritten by the LLM (short code lines in the tables); diagram and chart images are not sent to the LLM | `specialist.py` (`POLISH_CELLS = ()`) |

## Sửa 29/10 — Báo cáo khảo sát thực địa (mẫu MB, file Excel)

| Lỗi | Nguyên nhân | Sửa ở |
|---|---|---|
| KH vay nhận nhầm | Nhãn "Thời gian / Địa điểm / Thành phần / Đại diện KH / Đại diện TCB" xếp chồng trong MỘT ô (Alt+Enter), giá trị ở ô bên cạnh → khi đọc ra văn bản, nhãn và tên bị tách xa nhau | `src/utils/reading/extractors.py` (`_split_form_cells`): ô xếp chồng → mỗi dòng một hàng "Đại diện KH ⇥ Nguyễn Huệ Chi"; `src/agents/calculator/borrowers.py` (`_name_in_next_cell`): lấy ô ngay sau nhãn, không bao giờ lấy "Đại diện TCB" |
| Mức độ ảnh hưởng / Đánh giá năng lực trống | Báo cáo không có hai cột này — cả hai nằm trong cột "Ghi chú"; cột "Mối quan hệ" là Vợ/Chồng/Con theo đại diện KH | `config/prompts/shareholders_extraction.md`: tách "Ghi chú" → influence / assessment, đổi quan hệ thành "Chồng KH vay", "Con KH vay"… |
| Sản phẩm/dịch vụ sai | Dòng "Sản phẩm/ dịch vụ" ở mục B.2, sau checklist dài; LLM viết báo cáo chỉ đọc 6.000 ký tự đầu | `config/prompts/business_model_extraction.md` (trường `product_service`, đọc cả file) → `business_model.product_service` → `specialist.py` → `corp-income-cell-specs.md` (dòng Diễn giải) |

Test: `testing/test_site_visit_2910.py`.
