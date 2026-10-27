"""The whole graph on a small dossier, with fake extraction chains (no API key).

Covers: upload boxes, files outside every box, duplicate files, classification,
which BRD passes run on which document, the evidence-gap stop, unit scaling,
internal data and the watchlist, every BRD B6 check that has a clear verdict,
and the output state the notebook saves.

    python -m unittest testing.test_corp_income_workflow
"""

import copy
import json
import tempfile
from unittest import mock
import unittest
from pathlib import Path

from src.agents.supervisor import EXTRACTION_PASSES, Supervisor
from src.config import Config

GCN = {"company_name": "CÔNG TY TNHH THƯƠNG MẠI ABC", "tax_code": "0101234567",
       "legal_form": "tnhh_hai_thanh_vien_tro_len", "establishment_date": "12/05/2015",
       "registration_change_number": 6, "latest_change_date": "20/03/2026",
       "charter_capital": 10, "source_unit": "ty dong",
       "head_office_address": "Số 1 Láng Hạ, Đống Đa, Hà Nội", "legal_representatives": ["Trần Thị B"],
       "operating_status": "", "change_history": [{"date": "20/03/2026", "fields_changed": ["legal_rep", "members"]}]}
LOOKUP = {**GCN, "tax_code": "0101234568", "operating_status": "dang_hoat_dong", "change_history": []}
SITE = {"company_name": "", "tax_code": "", "legal_representatives": [], "source_unit": "dong",
        "change_history": [], "site_visit": {"actual_operation_confirmed": True}}
MEMBERS = {"source_unit": "trieu dong", "charter_capital": 10000, "document_date": "20/03/2026",
           "members": [
               {"name": "Nguyễn Văn A", "member_type": "ca_nhan", "capital_amount": 6000, "ownership_pct": 60,
                "acquisition_date": "20/03/2026", "acquisition_method": "nhan_chuyen_nhuong"},
               {"name": "Công ty CP Đầu tư XYZ", "member_type": "phap_nhan", "id_number": "0109999999",
                "capital_amount": 3000, "ownership_pct": 30, "acquisition_date": "12/05/2015",
                "acquisition_method": "gop_von_thanh_lap"}],
           "transfers": [{"date": "20/03/2026", "transferor": "Lê Văn C", "transferee": "Nguyễn Văn A"}]}
REP = {"legal_representatives": [{"name": "Trần Thị B", "title": "Giám đốc", "appointed_date": "20/03/2026"}],
       "previous_representatives": [{"name": "Lê Văn C", "until_date": "20/03/2026"}]}
REP_SITE = {"legal_representatives": [], "actual_operator": {"name": "Nguyễn Văn A", "role": "Chủ tịch HĐTV"}}
TAX = {"source_unit": "dong", "tax_debts": [{"authority": "Chi cục Thuế Đống Đa", "amount": 125000000,
                                              "overdue_days": 120, "status": "con_no"}],
       "social_insurance_debts": [], "administrative_penalties": [], "disputes": []}
FIN = {"audited": True, "source_unit": "trieu dong", "unusual_items": [],
       "periods": [
           {"period": "2025", "period_type": "year", "total_assets": 50000, "current_assets": 30000,
            "non_current_assets": 20000, "total_liabilities": 30000, "current_liabilities": 32000,
            "equity": 20000, "total_capital": 50000, "net_revenue": 70000, "cogs": 60000,
            "gross_profit": 10000, "profit_before_tax": 2500, "profit_after_tax": 2000, "depreciation": 500},
           {"period": "2024", "period_type": "year", "total_assets": 45000, "current_assets": 28000,
            "total_liabilities": 26000, "current_liabilities": 20000, "equity": 19000, "total_capital": 45000,
            "net_revenue": 100000, "profit_after_tax": 3000},
       ]}
EMPTY = {
    "legal_basic": {"company_name": "", "tax_code": "", "legal_representatives": [], "source_unit": "dong"},
    "shareholders": {"members": [], "source_unit": "dong"},
    "legal_rep": {"legal_representatives": []},
    "liabilities": {"tax_debts": [], "social_insurance_debts": [], "administrative_penalties": [],
                    "disputes": [], "source_unit": "dong"},
    "financial": {"periods": [], "source_unit": "dong"},
}
ANSWERS = {
    ("GCN_DKDN_ABC.txt", "legal_basic"): GCN, ("GCN_DKDN_ABC.txt", "shareholders"): MEMBERS,
    ("GCN_DKDN_ABC.txt", "legal_rep"): REP,
    ("masothue_0101234568.txt", "legal_basic"): LOOKUP, ("masothue_0101234568.txt", "legal_rep"): REP,
    ("BCTD_ABC.txt", "legal_basic"): SITE, ("BCTD_ABC.txt", "legal_rep"): REP_SITE,
    ("thong_bao_no_thue.txt", "liabilities"): TAX,
    ("BCTC_2025.txt", "financial"): FIN,
}


class FakeChain:
    """Stands in for prompt | llm | JsonOutputParser for one BRD pass."""

    def __init__(self, pass_name: str, calls: list):
        self.pass_name, self.calls = pass_name, calls

    def invoke(self, payload):
        self.calls.append((payload["filename"], self.pass_name))
        return copy.deepcopy(ANSWERS.get((payload["filename"], self.pass_name), EMPTY[self.pass_name]))


class FakeWriterChain:
    """Stands in for the report-writer chain; answers every requested cell."""

    def __init__(self, seen: list):
        self.seen = seen

    def invoke(self, payload):
        self.seen.append(payload)
        names = [json.loads(line)["o"] for line in payload["fields"].splitlines()]
        return {name: f"LLM:{name}" for name in names if name != "KetLuanNguonThuDoanhNghiep"}


def supervisor_with_fakes(calls: list) -> Supervisor:
    sup = Supervisor(Config())
    for pass_ in EXTRACTION_PASSES:
        setattr(sup, pass_.chain_attr, FakeChain(pass_.result_attr.removesuffix("_extraction"), calls))
    return sup


def write_dossier(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")


DOSSIER = {
    "ho_so_phap_ly/GCN_DKDN_ABC.txt": "GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP",
    "ho_so_phap_ly/GCN_DKDN_ABC_copy.txt": "GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP",
    "ho_so_noi_bo/masothue_0101234568.txt": "Thông tin người nộp thuế",
    "ho_so_soan_thao_noi_bo/BCTD_ABC.txt": "Báo cáo khảo sát thực địa",
    "ho_so_tai_chinh/thong_bao_no_thue.txt": "THÔNG BÁO TIỀN THUẾ NỢ",
    "ho_so_tai_chinh/BCTC_2025.txt": "BẢNG CÂN ĐỐI KẾ TOÁN tại ngày 31/12/2025",
    "ho_so_tai_chinh/VAT01.2025.txt": "TỜ KHAI THUẾ GIÁ TRỊ GIA TĂNG — khách hàng chính: Công ty Minh Phát",
    "loose_file.txt": "file đặt ngoài mọi thư mục",
}


class CorpIncomeWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name) / "khdn_abc"
        write_dossier(root, DOSSIER)
        cls.calls: list = []
        cls.writer_payloads: list = []
        sup = supervisor_with_fakes(cls.calls)
        sup.config.report_writer_llm = object()
        with mock.patch("src.agents.report_writer.build_writer_chain",
                        lambda llm: FakeWriterChain(cls.writer_payloads)):
            cls.result = sup.process(
                [str(root)],
                agent="CORP_INCOME_AGENT",
                loan_program="KHDN",
                loan_date="13/10/2026",
                borrower_names=["Nguyễn Văn A"],
                internal_data={"legal_basic": {**GCN, "head_office_address": "Số 5 Cầu Giấy, Hà Nội"}},
                watchlist=[{"name": "Công ty CP Đầu tư XYZ", "tax_code": "0109999999", "list": "WL"}],
            )
        cls.codes = {
            int(n): {f["code"]: f for f in item["findings"]}
            for n, item in cls.result["corp_income"]["items"].items()
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs_to_the_corp_agent(self):
        self.assertEqual(self.result["agent_name"], "CORP_INCOME_AGENT")
        self.assertTrue(self.result["response"].startswith("## PHỤ LỤC 01 - THẨM ĐỊNH NGUỒN THU DOANH NGHIỆP"))

    def test_upload_boxes_duplicates_and_loose_files(self):
        steps = "\n".join(self.result["steps"])
        self.assertIn("skipped 1 file(s) under no upload box: loose_file.txt", steps)
        self.assertIn("Skipped duplicate document: GCN_DKDN_ABC_copy.txt", steps)
        types = {d["filename"]: d["document_type"] for d in self.result["document_classifications"]}
        self.assertEqual(types, {"GCN_DKDN_ABC.txt": "gcn_dkdn", "masothue_0101234568.txt": "tra_cuu_dkdn",
                                 "BCTD_ABC.txt": "bao_cao_thuc_dia", "thong_bao_no_thue.txt": "thong_bao_no_thue",
                                 "BCTC_2025.txt": "bao_cao_tai_chinh", "VAT01.2025.txt": "to_khai_vat"})

    def test_each_document_runs_only_its_brd_items(self):
        by_file: dict[str, set] = {}
        for filename, pass_name in self.calls:
            by_file.setdefault(filename, set()).add(pass_name)
        self.assertEqual(by_file["GCN_DKDN_ABC.txt"], {"legal_basic", "shareholders", "legal_rep"})
        self.assertEqual(by_file["thong_bao_no_thue.txt"], {"liabilities"})
        self.assertEqual(by_file["BCTD_ABC.txt"], {"legal_basic", "shareholders", "legal_rep", "liabilities",
                                                   "business_model"})

    def test_item_1_checks(self):
        self.assertEqual(self.codes[1]["tax_code_mismatch"]["severity"], "alert")
        self.assertIn("status_active", self.codes[1])
        self.assertIn("changes_12m", self.codes[1])
        self.assertIn("internal_stale", self.codes[1])
        self.assertIn("site_operating", self.codes[1])

    def test_item_2_checks_and_units(self):
        self.assertEqual(self.codes[2]["borrower_new_member"]["severity"], "alert")
        self.assertEqual(self.codes[2]["watchlist_member"]["severity"], "alert")
        self.assertIn("transfer_12m", self.codes[2])
        members = self.result["corp_income"]["items"]["2"]["summary"]["members"]
        self.assertEqual(members[0]["capital_amount"], 6_000_000_000)  # 6.000 triệu đồng

    def test_item_3_and_4_checks(self):
        self.assertEqual(self.codes[3]["rep_changed_12m"]["severity"], "alert")
        self.assertIn("operator_differs", self.codes[3])
        self.assertEqual(self.codes[4]["thue_debt"]["severity"], "alert")
        self.assertIn("bhxh_unverified", self.codes[4])

    def test_outputs_the_notebook_saves(self):
        self.assertEqual(set(self.result["ocr_text"]), {d["filename"] for d in self.result["document_classifications"]})
        self.assertIn("records", self.result["corp_income"])
        self.assertEqual(self.result["corp_income"]["meta"]["unknown_placeholders"], [])
        self.assertIn("financials", self.result["corp_income"])


class AppendixTemplateTest(CorpIncomeWorkflowTest):
    """Phụ lục 01: code fills facts and figures, the writer only the rest."""

    def test_legal_cells_come_from_the_documents(self):
        report = self.result["response"]
        # [BRD 16/10] ĐKKD first, and the mismatch with the tax lookup is marked
        self.assertIn("| Mã số thuế | 0101234567 ⚠ không khớp giữa các nguồn |", report)
        self.assertIn("| Năm thành lập | 2015 (Đăng ký lần đầu 12/05/2015; thay đổi lần thứ 6 ngày 20/03/2026) |",
                      report)
        self.assertIn("| Nguyễn Văn A | Khách hàng vay vốn | 60% | Có — nhận vốn góp ngày 20/03/2026 |", report)
        self.assertNotIn("{{", report)

    def test_financial_table_and_ratios_are_computed_in_code(self):
        report = self.result["response"]
        self.assertIn("<td>{}</td>".format("70.000"), report)          # DTT 2025, triệu đồng
        self.assertIn("<th>2025</th>", report)                   # {{Nam-1}} = latest BCTC year
        self.assertIn("<td>-30,0%</td>", report)                       # 70.000 / 100.000 - 1
        self.assertIn("<td>0,94</td>", report)                         # 30.000 / 32.000
        remarks = self.result["corp_income"]["financials"]["status_remarks"]
        self.assertTrue(any("HĐKD của KH suy giảm" in r for r in remarks))
        self.assertTrue(any("< 1" in r for r in remarks))
        # [BRD 16/10] LNST hợp lý = LNST - DT tài chính - thu nhập khác (none printed → 0);
        # no TDH principal given → 0; x 60%.
        income = self.result["corp_income"]["income_estimate"]
        self.assertEqual(income["value"], 2_000e6 * 60 / 100)

    def test_writer_gets_only_the_narrative_cells_and_the_evidence(self):
        meta = self.result["corp_income"]["meta"]
        self.assertIn("NhanXetHDKD", meta["llm_placeholders"])
        self.assertIn("KetLuanNguonThuDoanhNghiep", meta["llm_placeholders"])
        for code_cell in ("MST", "ThanhVien1", "DTT2025", "ROS2024", "TongTaiSanCurrent",
                          "KetLuan", "TCB_ST"):
            self.assertNotIn(code_cell, meta["llm_placeholders"])
        evidence = json.loads(self.writer_payloads[0]["evidence"])
        self.assertEqual(evidence["phan_nhom_doanh_nghiep"]["group"], "Bad corp")   # MST mismatch
        self.assertIn("VAT01.2025.txt", {e["file"] for e in evidence["trich_doan_ho_so"]})
        report = self.result["response"]
        self.assertIn("LLM:NhanXetHDKD", report)
        self.assertIn("1 cell(s) empty", meta["writer_error"])           # fake leaves one cell empty
        # [BRD 16/10] the fake rewrite "LLM:NhanXet" drops every number → the code draft is kept
        self.assertIn("NhanXet", evidence["ban_nhap_code"])
        self.assertIn("kept the code draft", meta["writer_error"])
        self.assertIn("Doanh nghiệp đã hoạt động", report)
        self.assertNotIn("LLM:NhanXetTaiChinh", report)


class OcrFallbackTest(unittest.TestCase):
    """A noisy scanned GCN: the LLM left MST and dates empty, the text has them."""

    OCR = ("GIAY CHUNG NHAN DANG KY DOANH NGHIEP\nMA so doanh nghiép: 0108977425\n"
           "Dang ky lan dau: ngay 07 thang 11 naém 2019\n"
           "Dang ky thay déi lan thir: 4, ngay 26 thang 09 nadm 2025")

    def test_empty_fields_are_filled_from_the_text(self):
        from src.agents.extraction.legal_basic_extraction import fill_from_text
        result = fill_from_text({"tax_code": "", "establishment_date": ""}, self.OCR)
        self.assertEqual(result["tax_code"], "0108977425")
        self.assertEqual(result["establishment_date"], "07/11/2019")
        self.assertEqual((result["registration_change_number"], result["latest_change_date"]), (4, "26/09/2025"))

    def test_llm_values_are_kept_except_a_wrong_first_registration_date(self):
        from src.agents.extraction.legal_basic_extraction import fill_from_text
        result = fill_from_text({"tax_code": "0101234567", "establishment_date": "01/01/2015",
                                 "registration_change_number": 2, "latest_change_date": "02/02/2020"}, self.OCR)
        self.assertEqual(result["tax_code"], "0101234567")
        self.assertEqual(result["latest_change_date"], "02/02/2020")
        # [Sửa 20/10] "Đăng ký lần đầu: ngày …" printed on the GCN wins over the LLM's year.
        self.assertEqual(result["establishment_date"], "07/11/2019")
        same = fill_from_text({"tax_code": "0101234567", "establishment_date": "07/11/2019",
                               "registration_change_number": 2, "latest_change_date": "02/02/2020"}, self.OCR)
        self.assertNotIn("extraction_notes", same)


class GuidanceTest(unittest.TestCase):
    def test_guidance_sits_next_to_the_template_and_is_read(self):
        from src.agents.report_writer import GUIDANCE_PATH, load_guidance
        self.assertEqual(GUIDANCE_PATH.parent.name, "templates")
        text = load_guidance()
        self.assertIn("PHÁP LÝ DOANH NGHIỆP", text)
        self.assertIn("Bad Corp", text)


class EvidenceGapTest(unittest.TestCase):
    def test_no_legal_document_stops_before_any_llm_call(self):
        calls: list = []
        with tempfile.TemporaryDirectory() as tmp:
            write_dossier(Path(tmp), {"ho_so_tai_chinh/thong_bao_no_thue.txt": "THÔNG BÁO TIỀN THUẾ NỢ"})
            result = supervisor_with_fakes(calls).process([tmp], loan_date="13/10/2026")
        self.assertEqual(result["agent_name"], "EVIDENCE_GAP_CHECK")
        self.assertEqual(calls, [])
        self.assertIn("legal_documents", result["response"])

    def test_external_data_alone_is_enough_for_item_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_dossier(Path(tmp), {"ho_so_tai_chinh/thong_bao_no_thue.txt": "THÔNG BÁO TIỀN THUẾ NỢ"})
            result = supervisor_with_fakes([]).process([tmp], external_data={"legal_basic": LOOKUP})
        self.assertEqual(result["agent_name"], "CORP_INCOME_AGENT")

    def test_files_outside_every_box_are_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_dossier(Path(tmp), {"GCN_DKDN.txt": "GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP"})
            result = supervisor_with_fakes([]).process([tmp])
        self.assertEqual(result["agent_name"], "EVIDENCE_GAP_CHECK")
        self.assertIn("chưa được gắn loại tài liệu", result["response"])

    def test_malformed_internal_data_is_an_error_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_dossier(Path(tmp), DOSSIER)
            result = supervisor_with_fakes([]).process([tmp], internal_data={"not_an_item": {}})
        self.assertEqual(result["status"], "error")

    def test_unknown_agent_is_refused(self):
        with self.assertRaises(ValueError):
            Supervisor(Config()).process([], agent="FINANCIAL_ANALYSIS_AGENT")


if __name__ == "__main__":
    unittest.main()
