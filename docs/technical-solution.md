# Corp Income — Technical Solution

## 0. Scope

BRD *Corp Income Assessment*, sheet **Corp income (detail)**, use case **Pháp lý doanh
nghiệp**, items 1–4 (rows transcribed in `docs/BRD_corp_income_items_1-4.xlsx`). The
structure follows the SME repo's `refactor/ui-driven-inputs` branch so the two can share
infrastructure and, later, one upload screen.

| | SME repo | This repo |
|---|---|---|
| Graph | discover → classify → gap check → extract → reference data → specialist | same nodes, one branch (`single_corp_income`) |
| Agents | 4 LLM specialists | `CORP_INCOME_AGENT`, no LLM (checks + template in code) |
| Extraction passes | BCTC, proposal, CIC S10A/R20, site visit, ledger | M1–M4, one per BRD item |
| Upload boxes | 7 | the same 7 |
| Deterministic step | financial ratios, credit need | `legal_checks.py` (BRD B6) |
| Reading | PDF OCR, Excel, CSV, XML, PPTX | + PDF text layer, photos, Word |
| LLM | ChatOpenAI | + `LLM_PROVIDER` = anthropic / databricks |

## 0b. The report — "Appendix - Corp income" (BRD 27/10/2026)

Template: `src/templates/corp-income-structure.md`. Guidance: `src/templates/corp-income-guidance.md`;
frames of the LLM cells: `src/templates/corp-income-cell-specs.md`. What changed: `docs/CHANGES-BRD-2710.md`.

| Template part | Filled by | Where |
|---|---|---|
| 1 a-b (T24, MST, năm TL, NĐDPL, tình trạng, thành viên, tỷ lệ, thay đổi 12 tháng), legal comment draft | code, from M1–M3 + checks | `src/utils/report/appendix_context.py` |
| 2. Mô hình HĐKD (5 tầng), ngành TCB | code, from M9 (`business_model_extraction`) | `calculator/business_model.py`, `calculator/industry.py` |
| 3. Bảng tài chính, chỉ số, cảnh báo, phân nhóm tài chính | code, from M5 / M6 | `calculator/financial_metrics.py` |
| 4. Bảng dư nợ theo TCTD, nợ cần chú ý / nợ xấu, phân nhóm bureau | code, from M7 | `calculator/cic_metrics.py` |
| 5. Bảng PAKD, phân nhóm DN, giá trị nguồn thu (lịch sử hoặc dự phóng) | code, from M8 + groups | `appendix_context.plan_table`, `financial_metrics.income_estimate` |
| Sản phẩm/dịch vụ, địa chỉ, nhận xét HĐKD, kết luận; rewrite of the legal and finance comments | one LLM call (`report_writer_llm`) with the guidance, every code value and document excerpts | `src/agents/report_writer.py`, `config/prompts/report_writer.md` |

The LLM returns `{placeholder: text}` only for cells code left empty, so it can neither move
the layout nor change a number; a rewrite of a code draft that drops a number is rejected.

## 0c. Document matrix

`src/agents/documents/document_matrix.yaml` — 7 folders = matrix sections I, II, III, IV, V, VII,
VIII. Each type: `code`, `matrix_agents` (CIA, LA, BA, FS, RA, CP, CR), `validation`, keywords,
`source`, and the pass flags. CIA (this repo's `CORP_INCOME_AGENT`) reads a type exactly when
`matrix_agents` lists CIA.

## 1. BRD steps → code

| BRD step | Meaning | Where |
|---|---|---|
| B1 OCR output | read the customer's papers | `src/utils/reading/` + `config/prompts/*_extraction.md` |
| B2 Internal data | BCDE/BEP/DBX (KHDN ETC TCB) | `ho_so_noi_bo/` printouts (type `du_lieu_noi_bo`) or `process(internal_data=…)` |
| B3 External data | Cổng ĐKDN, cơ quan thuế, BHXH | `ho_so_noi_bo/` lookups (`tra_cuu_dkdn`, `tra_cuu_no_thue_bhxh`) or `process(external_data=…)` |
| B4 Fraud detection | AML/BL/WL | `process(watchlist=…)`; tamper detection out of scope |
| B5 Site visit / RBO | field report | `ho_so_soan_thao_noi_bo/` (701, type `bao_cao_thuc_dia`) or `ho_so_phap_ly/` (`bao_cao_thuc_dia_phap_ly`) |
| B6 Kiểm tra cụ thể | the checks | `src/agents/calculator/legal_checks.py` |

Each record carries its **source** (customer / field / external / internal). When sources
disagree, the summary shows external > customer > field > internal, and the finding lists all.

## 2. Checks (finding codes)

**Mục 1** — `tax_code_match` / `tax_code_mismatch` 🔴 · `name_mismatch` · `address_mismatch` ·
`establishment_mismatch` · `capital_mismatch` · `rep_mismatch` · `status_active` /
`status_not_active` 🔴 / `status_unknown` · `changes_12m` · `internal_current` / `internal_stale` /
`internal_absent` · `site_operating` / `site_not_operating` 🔴 / `site_unconfirmed` ·
`watchlist_company` 🔴.

**Mục 2** — `ownership_100` / `ownership_not_100` / `ownership_incomplete` ·
`capital_sum_mismatch` · `member_mismatch` · `transfer_12m` · `borrower_member` /
`borrower_not_member` / `borrower_new_member` 🔴 · `corporate_members` · `relationships` ·
`watchlist_member` 🔴.

**Mục 3** — `rep_match` / `rep_mismatch` / `no_rep` 🔴 · `rep_changed_12m` 🔴 ·
`operator_is_rep` / `operator_differs` / `operator_unknown` · `people_met` · `watchlist_rep` 🔴.
Leadership-capability assessment: removed per the BRD dependency note.

**Mục 4** — `thue_debt` / `bhxh_debt` 🔴 (count > 90 days) · `thue_clear` / `bhxh_clear` ·
`thue_unverified` / `bhxh_unverified` · `thue_conflict` / `bhxh_conflict` 🔴 · `penalty_open` /
`penalty_remediated` · `enforcement` 🔴 · `dispute` (🔴 when it affects operations/collateral) ·
`site_risk` · `inspection`.

A 12-month window ends at `loan_date`. Dates printed as month or year only count as the end of
that period (the conservative reading for "changed in the last 12 months").

## 3. Changing behaviour

| To change | Edit |
|---|---|
| Which documents are recognised, in which folder, which matrix agents / passes read them | `src/agents/documents/document_matrix.yaml` |
| Industry list (ROS, tăng trưởng ngành) | `src/templates/bang-nganh-tcb.csv` |
| A threshold of the BRD | the named constant at the top of `financial_metrics.py` / `cic_metrics.py` |
| What a pass extracts | `config/prompts/<item>_extraction.md` (keep the keys `legal_checks.py` reads) |
| A check | `src/agents/calculator/legal_checks.py` (one function per item) |
| The report layout | `src/templates/corp-income-structure.md` |
| The Excel layout | `src/utils/report/excel_export.py` |

Run the tests after any change (README, "Tests").

## 4. Cost

LLM calls per run = classification tie-breaks (only unsure documents) + Σ over documents of the
BRD items each feeds. A typical dossier of 8–12 files ≈ 15–25 calls. Digital PDFs skip OCR;
with `OCR_CACHE_DIR` on a Volume, re-runs do not OCR again.
