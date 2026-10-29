"""[BRD 16/10] One test per rule added by the BRD of 16/10/2026 (no LLM needed).

    python -m unittest testing.test_brd_1610
"""

import unittest
from datetime import date

from src.agents.calculator import cic_metrics
from src.agents.calculator import financial_metrics as fm

AS_OF = date(2026, 10, 16)
M = 1e6  # triệu đồng → đồng


def fin(document, periods, audited=True, **extra):
    return {"pass": "financial", "document": document, "source": "customer",
            "data": {"audited": audited, "periods": periods, **extra}}


def year(y, **values):
    return {"period": str(y), "period_type": "year", **{k: v * M for k, v in values.items()}}


GOOD_2025 = year(2025, total_assets=100, total_capital=100, total_liabilities=40, equity=60,
                 current_assets=60, current_liabilities=30, net_revenue=900, profit_before_tax=50,
                 profit_after_tax=40, retained_earnings=70)
GOOD_2024 = year(2024, total_assets=90, total_capital=90, net_revenue=800, retained_earnings=30,
                 profit_after_tax=35)


class FinancialRulesTest(unittest.TestCase):
    def test_tt133_statement_is_split_by_rule_1(self):
        r = fm.compute([fin("BCTC_TT133.pdf", [year(2025, total_assets=100, cash=10, receivables=20,
                                                         inventory=30, other_assets=5, total_liabilities=40,
                                                         equity=60, net_revenue=50, profit_after_tax=2)])], AS_OF)
        fig = r["years"]["2025"]
        self.assertEqual((fig["current_assets"], fig["non_current_assets"]), (65 * M, 35 * M))
        self.assertEqual((fig["current_liabilities"], fig["long_term_liabilities"]), (40 * M, 0))
        self.assertAlmostEqual(r["ratios"]["2025"]["current_ratio"], 65 / 40)

    def test_good_finance_needs_all_three_criteria(self):
        r = fm.compute([fin("BCTC_2025.pdf", [GOOD_2025, GOOD_2024])], AS_OF)
        self.assertEqual(r["group"], "Good finance")
        self.assertEqual(r["material_warnings"], [])

    def test_opening_balance_differs_from_previous_closing(self):
        r = fm.compute([fin("BCTC_2025.pdf", [GOOD_2025, GOOD_2024]),
                        fin("BCTC_2024.pdf", [year(2024, total_assets=95)])], AS_OF)
        self.assertTrue(any("cuối kỳ năm trước ≠ đầu kỳ năm sau" in w for w in r["material_warnings"]))
        self.assertEqual(r["group"], "Bad finance")

    def test_retained_earnings_jump_above_profit(self):
        bad = dict(GOOD_2025, retained_earnings=200 * M)     # +170 vs LNST 40
        r = fm.compute([fin("BCTC_2025.pdf", [bad, GOOD_2024])], AS_OF)
        self.assertTrue(any("LNST chưa phân phối" in w for w in r["material_warnings"]))

    def test_cit_rate_off_20_percent_is_a_warning_not_material(self):
        low_tax = dict(GOOD_2025, profit_after_tax=49 * M)    # tax 2%
        r = fm.compute([fin("BCTC_2025.pdf", [low_tax, GOOD_2024])], AS_OF)
        self.assertTrue(any("Thuế TNDN" in w for w in r["other_warnings"]))
        self.assertFalse(any("Thuế TNDN" in w for w in r["material_warnings"]))

    def test_status_remarks_segment_and_efficiency(self):
        weak = dict(GOOD_2025, other_income=15 * M, financial_income=5 * M, gross_profit=100 * M,
                    interest_expense=60 * M)
        r = fm.compute([fin("BCTC_2025.pdf", [weak, GOOD_2024])], AS_OF)
        text = " ".join(r["status_remarks"])
        self.assertIn("phân khúc SME", text)                   # 900 triệu < 200 tỷ
        self.assertIn("(Thu nhập khác + DT tài chính) / LNTT", text)
        self.assertIn("Chi phí lãi vay / LN gộp", text)

    def test_vat_months_of_year_n_and_full_year_check(self):
        vat_rows = [{"period_type": "month", "month": m, "year": 2026, "revenue": 100 * M} for m in range(1, 10)]
        vat_rows += [{"period_type": "quarter", "quarter": q, "year": 2025, "revenue": 100 * M} for q in range(1, 5)]
        records = [fin("BCTC_2025.pdf", [GOOD_2025, GOOD_2024]),
                   {"pass": "vat", "document": "VAT.pdf", "data": {"returns": vat_rows}}]
        r = fm.compute(records, AS_OF)
        self.assertEqual(r["vat"]["current_year"], 2026)
        self.assertIn("đến tháng 09/2026 là 900 triệu đồng, bằng 100,0% doanh thu năm 2025", r["vat"]["text"])
        # 2025: VAT 400 vs BCTC 900 → -55,6% → material
        self.assertTrue(any("tờ khai VAT cùng kỳ" in w for w in r["material_warnings"]))

    def test_income_formula(self):
        r = fm.compute([fin("BCTC_2025.pdf", [dict(GOOD_2025, financial_income=5 * M, other_income=3 * M,
                                                    depreciation=10 * M)])], AS_OF)
        income = fm.income_estimate(r, ownership_pct=50, annual_lt_principal=25 * M)
        self.assertEqual(income["reasonable_lnst"], 32 * M)     # 40 - 5 - 3
        self.assertEqual(income["lnst_for_lt_debt"], 15 * M)    # 25 - 10
        self.assertEqual(income["value"], 8.5 * M)              # (32 - 15) x 50%


    def test_segments_by_revenue(self):
        for revenue_ty, segment in ((2500, "Large corp"), (700, "MM"), (300, "USME"), (50, "SME")):
            r = fm.compute([fin("B.pdf", [year(2025, net_revenue=revenue_ty * 1000)])], AS_OF)
            self.assertIn(f"phân khúc {segment}", r["status_remarks"][0])


class CicRulesTest(unittest.TestCase):
    def s10a(self, **data):
        base = {"report_type": "S10A", "query_date": "10/10/2026", "lenders": [
            {"name": "Techcombank CN Hà Nội", "short_term": 100 * M, "long_term": 50 * M},
            {"name": "Vietcombank", "short_term": 20 * M, "off_balance": 5 * M}],
            "special_mention_12m": [], "bad_debt_5y": [],
            "monthly_balances_12m": [{"month": f"{m:02d}/2026", "balance": 150 * M} for m in range(1, 13)]}
        return {"pass": "cic", "document": "S10A.pdf", "data": {**base, **data}}

    def test_table_split_and_good_bureau(self):
        r = cic_metrics.compute([self.s10a()], AS_OF, revenue_prev_year=900 * M, business_type="thuong_mai")
        self.assertEqual(r["rows"]["TCB"]["total"], 150 * M)
        self.assertEqual(r["rows"]["OtherBank"]["total"], 25 * M)      # incl. ngoại bảng
        self.assertAlmostEqual(r["leverage"], 150 / 75)                 # 150 / (900/12)
        self.assertEqual(r["group"], "Good bureau")

    def test_special_mention_in_12_months_is_bad_bureau(self):
        r = cic_metrics.compute([self.s10a(special_mention_12m=[{"lender": "VCB", "date": "05/2026"}])],
                                AS_OF, revenue_prev_year=900 * M)
        self.assertEqual(r["group"], "Bad bureau")

    def test_old_report_is_flagged(self):
        r = cic_metrics.compute([self.s10a(query_date="01/08/2026")], AS_OF, revenue_prev_year=900 * M)
        self.assertTrue(any("quá 1 tháng" in w for w in r["warnings"]))


class NumberTextTest(unittest.TestCase):
    def test_figures_returned_as_text_are_read(self):
        from src.agents.extraction.structured_extraction import to_number
        for text, number in (("1.234.567", 1234567), ("(1.234)", -1234), ("12,5", 12.5),
                             ("1,234,567", 1234567), ("1.234,5", 1234.5), ("-500", -500), ("n/a", "n/a")):
            self.assertEqual(to_number(text), number, text)


class WriterFramesTest(unittest.TestCase):
    def test_cell_frames_are_read_from_the_templates_folder(self):
        from src.agents.report_writer import load_cell_specs
        specs = load_cell_specs()
        self.assertIn("NhanXetHDKD", specs)
        self.assertIn("Không có cảnh báo nào thì ghi đúng", specs["NhanXetHDKD"])      # [BRD 29/10]

    def test_number_guard(self):
        from src.agents.report_writer import keeps_every_number
        draft = "- Biến động doanh thu năm 2025: -30,0%\n- HSTT 0,94 < 1"
        self.assertEqual(keeps_every_number(draft, "**Kết luận:** suy giảm. DT 2025 giảm -30,0%; HSTT 0,94 < 1"), [])
        self.assertEqual(keeps_every_number(draft, "**Kết luận:** suy giảm mạnh, HSTT 0,94 < 1"), ["2025", "-30,0%"])
        # a sentence-final period is not part of the number
        self.assertEqual(keeps_every_number("HSTT 0,94.", "HSTT là 0,94 (thấp)"), [])


class CreditAssessmentTest(unittest.TestCase):
    """[BRD 16/10] The overall decision can never contradict the code's corp group."""

    def run_with(self, decision, group):
        from unittest import mock
        from src.agents import report_writer as rw

        class Fake:
            def invoke(self, payload):
                return {"quyet_dinh": decision, "tom_tat": "x"}

        with mock.patch.object(rw, "build_assessment_chain", lambda llm: Fake()):
            return rw.assess_credit(object(), {"a": 1}, group)

    def test_bad_corp_is_always_not_used(self):
        answer, note = self.run_with("Sử dụng", "Bad corp")
        self.assertEqual(answer["quyet_dinh"], "Không sử dụng")
        self.assertIn("set to 'Không sử dụng'", note)

    def test_normal_corp_is_at_most_conditional(self):
        answer, _ = self.run_with("Sử dụng", "Normal corp")
        self.assertEqual(answer["quyet_dinh"], "Sử dụng có điều kiện")

    def test_good_corp_keeps_the_llm_decision(self):
        answer, note = self.run_with("Sử dụng", "Good corp")
        self.assertEqual((answer["quyet_dinh"], note), ("Sử dụng", ""))

    def test_payload_shrinks_excerpts_not_the_rest(self):
        from src.agents.report_writer import fit_payload
        evidence = {"phan_nhom": "Normal corp", "trich_doan_ho_so": [{"file": f"f{i}", "noi_dung": "x" * 5000}
                                                                    for i in range(10)]}
        payload = fit_payload(evidence, limit=20_000)
        self.assertLessEqual(len(payload), 20_000)
        self.assertIn('"phan_nhom": "Normal corp"', payload)
        self.assertIn('"file": "f9"', payload)                  # every document still there


class RelativeYearsTest(unittest.TestCase):
    """[BRD 16/10] {{Nam-1}} / {{DTTN-1}}: the table follows the BCTC years, not 2024/2025."""

    def test_template_follows_the_latest_bctc_year(self):
        from src.utils.report.appendix_context import build_appendix_context
        from src.utils.report.report_template import fill_template
        items = {n: {"summary": {}, "findings": []} for n in (1, 2, 3, 4)}
        items[2]["summary"] = {"members": []}
        items[3]["summary"] = {"legal_representatives": []}
        financials = fm.compute([fin("BCTC_2023.pdf", [year(2023, net_revenue=500, profit_after_tax=20),
                                                         year(2022, net_revenue=400)])], AS_OF)
        ctx = build_appendix_context({"items": items, "meta": {"borrower_names": []}}, [], financials, AS_OF)
        out = fill_template("<th>{{Nam-2}}</th><th>{{Nam-1}}</th>|{{DTTN-2}}|{{DTTN-1}}|{{BienDongDTN-1}}|"
                            "{{TongTaiSanN-1}}", ctx)
        self.assertEqual(out, "<th>2022</th><th>2023</th>|400|500|25,0%|—")


# OutputConditionsTest moved to test_brd_2710 (the tables are now built in code).


class RevenueGrowthGuardTest(unittest.TestCase):
    """[Sửa 16/10] Biến động DT: không so năm thiếu tháng; cảnh báo số bất thường."""

    @staticmethod
    def _records(months_prev):
        from src.agents.calculator import financial_metrics as fm  # noqa: F401
        periods = [
            {"period": "2024", "period_type": "year", "months": 12, "net_revenue": 49.09e9,
             "cogs": 44.09e9, "gross_profit": 5e9},
            {"period": "2023", "period_type": "year", "months": months_prev, "net_revenue": 10e9,
             "cogs": 9e9, "gross_profit": 1e9},
        ]
        return [{"pass": "financial", "document": "BCTC.pdf", "data": {"audited": False, "periods": periods}}]

    def test_partial_first_year_is_not_compared(self):
        from src.agents.calculator import financial_metrics as fm
        result = fm.compute(self._records(5))
        self.assertIsNone(result["ratios"]["2024"]["revenue_growth"])
        self.assertTrue(any("chỉ có 5 tháng" in w for w in result["other_warnings"]))

    def test_extreme_growth_is_flagged(self):
        from src.agents.calculator import financial_metrics as fm
        result = fm.compute(self._records(12))
        self.assertAlmostEqual(result["ratios"]["2024"]["revenue_growth"], 3.909, places=3)
        self.assertTrue(any("bất thường, kiểm tra lại" in w for w in result["other_warnings"]))
        self.assertFalse(any("≠ LN gộp" in w for w in result["other_warnings"]))


class DkkdReadingTest(unittest.TestCase):
    """[Sửa 20/10] GCN ĐKDN: lớp text font VNI phải đi OCR; ngày lần đầu trên giấy thắng LLM."""

    def test_vni_text_layer_is_rejected(self):
        from src.utils.reading.extractors import _looks_like_legacy_font
        self.assertTrue(_looks_like_legacy_font(
            "GIAÁY CHÖÙNG NHAÄN ÑAÊNG KYÙ DOANH NGHIEÄP. Ñaêng kyù laàn ñaàu: ngaøy 12 thaùng 05 naêm 2015"))
        self.assertFalse(_looks_like_legacy_font(
            "GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP. Đăng ký lần đầu: ngày 12 tháng 05 năm 2015, "
            "Địa chỉ trụ sở chính: số 5 phố Hàng Bài, quận Hoàn Kiếm"))

    def test_first_registration_date_overrides_llm_change_date(self):
        from src.agents.extraction.legal_basic_extraction import fill_from_text
        text = "Đăng ký lần đầu: ngày 12 tháng 05 năm 2015\nĐăng ký thay đổi lần thứ 7: ngày 03/08/2024"
        result = fill_from_text({"establishment_date": "03/08/2024"}, text)
        self.assertEqual(result["establishment_date"], "12/05/2015")
        self.assertEqual(result["registration_change_number"], 7)
        self.assertEqual(fill_from_text({}, "Đăng ký lần đầu: 12/05/2015")["establishment_date"], "12/05/2015")


class BorrowerDetectionTest(unittest.TestCase):
    """[Sửa 20/10] BORROWER_NAMES trống → tìm tên thành viên góp vốn trong hồ sơ vay vốn."""

    def test_borrower_found_in_loan_request(self):
        from types import SimpleNamespace as Doc
        from src.agents.calculator.borrowers import detect_borrowers
        records = [{"pass": "shareholders", "data": {"members": [
            {"name": "NGUYEN DUY XUAT", "member_type": "ca_nhan"},
            {"name": "LE NGOC HOA", "member_type": "ca_nhan"},
            {"name": "Công ty ABC", "member_type": "phap_nhan"}]}}]
        docs = [
            Doc(declared_group="ho_so_vay_von", filename="De nghi vay.pdf",
                content="GIẤY ĐỀ NGHỊ VAY VỐN\nHọ và tên: Ông Nguyễn Duy Xuất, CCCD 0010..."),
            Doc(declared_group="ho_so_soan_thao_noi_bo", filename="To trinh.docx",
                content="Thành viên: Nguyễn Duy Xuất, Lê Ngọc Hoa"),
        ]
        self.assertEqual(detect_borrowers(docs, records), (["NGUYEN DUY XUAT"], ["De nghi vay.pdf"]))
        self.assertEqual(detect_borrowers(docs[1:], records)[0], ["NGUYEN DUY XUAT", "LE NGOC HOA"])
        self.assertEqual(detect_borrowers([], records), ([], []))


if __name__ == "__main__":
    unittest.main()
