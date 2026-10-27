# BRD 16/10/2026 — what changed and where

The BRD **adds** to the guidance and the Phụ lục 01 template; nothing was replaced and no
template placeholder was renamed. In the code every change carries the tag `[BRD 16/10]`
(`grep -rn "BRD 16/10" src config`).

## Design rule

| What the BRD asks | Who does it | Why |
|---|---|---|
| A fact on a document, a number, a ratio, a threshold, a date check, a group | **Code** | Same input → same report; no invented numbers |
| Reading free text and comparing it (business activity, addresses, partners), wording a conclusion | **LLM** (one call, `report_writer.py`) | Needs judgment; it sees every code result and must not contradict it |

## BRD line → code

| BRD section | Rule | File / function |
|---|---|---|
| 1a | ID T24 from internal printouts | prompt `legal_basic_extraction.md` (`t24_id`) → `appendix_context.build_appendix_context` |
| 1a | MST / NĐDPL / năm thành lập: ĐKKD → Điều lệ / Sổ cổ đông → thực địa; mark mismatch | `appendix_context.LEGAL_DOC_PRIORITY`, `_pick_by_document`, `legal_cell` |
| 1a | "Đăng ký lần đầu … thay đổi lần thứ …" | `build_appendix_context` (`NamThanhLap`, `DKKD`) |
| 1a | Status bold red when not operating | `build_appendix_context` (`TinhTrangHoatDong`) |
| 1b | Members: Sổ cổ đông / Sổ chứng nhận lưu ký / DS thành viên → Điều lệ | `legal_checks._MEMBER_DOC_PRIORITY` (+ matrix keywords "luu ky") |
| 1b | Relation: NĐDPL; relations from the field report first | `appendix_context._relations` |
| 1 | Nhận xét pháp lý (years operating, borrower %, NĐDPL, warnings, ownership ≠ 100%) | `build_appendix_context` (`NhanXetPhapLyDN`, `NhanXet`) |
| 2 | Loại hình / tên ngành / diễn giải; photo, internal data, contract comparisons; addresses (≥ 1 of 3, đi thuê / sở hữu); top-5 partners | **LLM** — guidance "BỔ SUNG … mục 2", `report_writer.md` rules 10-11 |
| 2 | "< 5 đối tác thì xóa hẳn dòng thừa" | `appendix_context.apply_output_conditions` |
| 2 | Tên ngành theo bảng ngành TCB | optional file `src/templates/bang-nganh-tcb.md` (add it) |
| 3 | Nguồn: BCTC thuế / kiểm toán, tờ khai VAT periods | `financial_metrics.sources_text` |
| 3 | Nguyên tắc 1 (TT200 / TT133) | `financial_metrics._derive_tt133` |
| 3 | Nguyên tắc 2 (tờ khai VAT, các tháng năm N) | new pass M6 `vat_extraction` → `financial_metrics.vat_summary` |
| 3 | Nguyên tắc 3 (biến động DT, ROS, HSTT) | `financial_metrics.compute` [N3] |
| 3 | Dấu hiệu bất thường BCTC | `financial_metrics.compute` [BT]; excluded auditors: optional file `src/templates/danh-sach-kiem-toan-loai-tru.txt` |
| 3 | Trạng thái tài chính (phân khúc, suy giảm, hiệu quả, thanh khoản) | `financial_metrics.compute` [TT] |
| 3 | Bad / Normal / Good finance | `financial_metrics.compute` [NF] |
| 4 | CIC S10A / R20 within 1 month; table per TCB / other; TSBĐ; nợ cần chú ý; nợ xấu | new pass M7 `cic_extraction` → `cic_metrics.compute` |
| 4 | Bad / Normal / Good bureau (thresholds 6 / 9 / 9 / 6) | `cic_metrics.compute` [NB]; loại hình from prompt `business_type` |
| 3-4 | Chi phí lãi vay vs dư nợ BQ CIC × 10% | `financial_metrics.interest_vs_cic` |
| 5 | Plan numbers, growth and ROS of the plan; hide the table without a plan | new pass M8 `plan_extraction` → `build_appendix_context`, `apply_output_conditions` |
| 6 | Bad / Normal / Good corp | `appendix_context.corp_group` |
| 6 | LNST hợp lý, LNST trả nợ TDH, lợi tức tối đa cho KHCN | `financial_metrics.income_estimate`, `appendix_context.income_block`; input `annual_lt_principal` (notebook `ANNUAL_LT_PRINCIPAL`) |
| 6 | Wording of the conclusion (examples in the BRD) | **LLM** — `KetLuanNguonThuDoanhNghiep` |
| 3-6 | Groups shown "chỉ khi POC" | env `CORP_INCOME_SHOW_GROUPS=0` hides them |

## Decisions to confirm with the business owner

The BRD gives no number for these. Each one is a named constant you can change in one line.

| Constant | Placeholder | File |
|---|---|---|
| `VAT_BCTC_DIFF_ALERT` | DTT on BCTC vs VAT full year: alert above 20% | `financial_metrics.py` |
| `INTEREST_BAND`, `ASSUMED_INTEREST_RATE` | Interest outside 50%–200% of dư nợ BQ × 10% | `financial_metrics.py` |
| `CIT_TOLERANCE` | Thuế TNDN / LNTT outside 18%–22% (a warning, not "trọng yếu") | `financial_metrics.py` |
| `DEFAULT_LIMIT` | Business type unknown → bureau threshold 6 (the stricter one) | `cic_metrics.py` |
| Material warnings | Bad finance = TS ≠ NV, opening ≠ previous closing, LN chưa PP jump, BCTC vs VAT gap, excluded auditor | `financial_metrics.compute` |
| `lnst_for_lt_debt` floored at 0 | When khấu hao exceeds the principal, the surplus is not added to income | `financial_metrics.income_estimate` |
| HSTT wording | The BRD writes "> 1" under thanh khoản; the code warns on **< 1** (the meaning given) | `financial_metrics.compute` |

## Not done (needs data the dossier does not carry yet)

- Photo **content** (products, machines, people): only the text OCR reads from the photo is used.
- Revenue vs bank statements / sales software: the writer mentions them only when the documents are in the dossier.
- "Mô hình HĐKD" diagram: replaced by the two partner tables already in the template (the BRD marks the diagram optional).

## Sửa sau BRD (tìm tag trong code: `[Sửa 16/10]`, `[Sửa 20/10]`)

| Ngày | Vấn đề | Sửa | File |
|---|---|---|---|
| 16/10 | Biến động DT ra 390,9% khi năm trước là năm đầu thành lập (không đủ 12 tháng) | LLM đọc thêm `months`; hai năm khác số tháng → không tính, hiện "—" và có cảnh báo | `config/prompts/financial_extraction.md`, `financial_metrics.py` (merge_periods, [N3]) |
| 16/10 | Số doanh thu đọc nhầm dòng/cột không ai phát hiện | Cảnh báo khi DTT − Giá vốn ≠ LN gộp; cảnh báo khi biến động DT ngoài −80%…+200% (`REVENUE_GROWTH_CHECK`) | `financial_metrics.py` ([BT]) |
| 20/10 | GCN ĐKDN font VNI/TCVN3 không được OCR (lớp text "Ñaêng kyù…" bị coi là sạch) → năm thành lập sai | `_looks_like_legacy_font`: phát hiện font cũ → OCR ảnh trang | `src/utils/reading/extractors.py` |
| 20/10 | LLM ghi ngày "thay đổi lần thứ N" vào ngày thành lập | Dòng "Đăng ký lần đầu: ngày …" trên giấy thắng giá trị LLM (ghi chú "LLM ghi …, giấy ghi …"); nhận cả dạng `12/05/2015` | `legal_basic_extraction.py` (`_DATE`, `fill_from_text`) |
| 20/10 | Phải điền tay `BORROWER_NAMES` cho từng hồ sơ | Để trống → tự tìm tên thành viên góp vốn cá nhân / NĐDPL trong hồ sơ vay vốn (`ho_so_vay_von`, rồi `ho_so_soan_thao_noi_bo`); báo cáo ghi "tự nhận diện từ <file>". Điền tay vẫn được ưu tiên | `src/agents/calculator/borrowers.py` (mới), `specialist.py`, `appendix_context.py`, notebook |
| 20/10 | OCR lỗi "[Errno 13] Permission denied" trên cluster dùng chung (thư mục cache OCR do user khác tạo) | Thư mục cache riêng theo user; không ghi/đọc được thì dùng thư mục tạm mới | `src/utils/reading/ocr.py` (`_cache_dir`, `_read_cache`) |
| 20/10 | 49 file chạy 34 phút (đọc + phân loại + trích xuất lần lượt từng file) | Đọc/phân loại nhiều file song song (`FILE_WORKERS`, mặc định 3); các bước trích xuất gọi LLM song song (`LLM_WORKERS`, mặc định 4); Tesseract 1 luồng/tiến trình (`OMP_THREAD_LIMIT=1`); thu nhỏ ảnh chụp điện thoại về cạnh dài 3500px (`OCR_MAX_IMAGE_SIDE`) | `supervisor.py` (`_prepare_documents`, `_prepare_one`, `_run_structured_extraction`), `ocr.py` |
| 20/10 | Báo "Chưa có bản tin R20" khi một file PDF CIC gộp cả S10A + R20 | Bản tin có danh sách TSBĐ cũng tính là R20; có dư nợ theo TCTD cũng tính là S10A | `src/agents/calculator/cic_metrics.py` |
| 27/10 | Databricks báo "Fatal error: Python kernel is unresponsive" — driver hết RAM vì đọc 3 file × OCR 8 trang cùng lúc | Mặc định giảm: `FILE_WORKERS` 3 → 1, `OCR_MAX_WORKERS` min(8, CPU) → 2, `LLM_WORKERS` 4 → 2 (DPI giữ 300 để không giảm chất lượng OCR). Driver lớn thì tăng lại trong `.env`. Dòng `OCR_MAX_WORKERS=` để trống trong `.env` không còn gây lỗi | `supervisor.py` (`_prepare_documents`, `_run_structured_extraction`), `ocr.py`, `.env.example` |
