"""[BRD 27/10] One test per rule added by the BRD / document matrix of 27/10/2026 (no LLM needed).

    python -m unittest testing.test_brd_2710
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.agents.calculator import business_model, cic_metrics, industry
from src.agents.calculator import financial_metrics as fm
from src.agents.documents import document_matrix as dm
from src.utils.report.appendix_context import plan_table
from src.utils.report.report_template import template_placeholders, load_template

AS_OF = date(2026, 10, 27)
M = 1e6


def fin(periods):
    return {"pass": "financial", "document": "BCTC_2025.pdf", "source": "customer",
            "data": {"audited": True, "periods": periods}}


def year(y, **values):
    return {"period": str(y), "period_type": "year", **{k: v * M for k, v in values.items()}}


Y2025 = year(2025, total_assets=100, total_capital=100, total_liabilities=40, equity=60, current_assets=60,
             current_liabilities=30, net_revenue=1000, profit_after_tax=50, retained_earnings=70)
Y2024 = year(2024, total_assets=90, total_capital=90, net_revenue=800, retained_earnings=20)


def model(document_type, document, suppliers=(), customers=(), nganh=""):
    return {"pass": "business_model", "document_type": document_type, "document": document,
            "data": {"industry": nganh, "suppliers": list(suppliers), "customers": list(customers)}}


class DocumentMatrixTest(unittest.TestCase):
    def test_folders_follow_the_matrix_sections(self):
        m = dm.load_matrix()
        self.assertEqual(m.boxes, ("ho_so_phap_ly", "ho_so_tai_chinh", "ho_so_vay_von", "ho_so_tai_san_dam_bao",
                                   "ho_so_noi_bo", "ho_so_soan_thao_noi_bo", "ho_so_khac"))
        where = {code: {t.group_id for t in m.types.values() if t.code == code}
                 for code in ("100", "101", "200", "205", "208", "301", "302", "400", "401", "701", "706", "708")}
        self.assertEqual(where, {"100": {"ho_so_phap_ly"}, "101": {"ho_so_phap_ly"}, "200": {"ho_so_tai_chinh"},
                                 "205": {"ho_so_tai_chinh"}, "208": {"ho_so_noi_bo"}, "301": {"ho_so_vay_von"},
                                 "302": {"ho_so_vay_von"}, "400": {"ho_so_tai_san_dam_bao"},
                                 "401": {"ho_so_tai_san_dam_bao"}, "701": {"ho_so_soan_thao_noi_bo"},
                                 "706": {"ho_so_soan_thao_noi_bo"}, "708": {"ho_so_noi_bo"}})

    def test_cia_reads_a_type_only_when_the_matrix_lists_cia(self):
        for t in dm.load_matrix().types.values():
            self.assertEqual("CIA" in t.matrix_agents, "CORP_INCOME_AGENT" in t.agents, t.id)
        self.assertEqual(dm.get_type("chung_thu_dinh_gia").matrix_agents, ("RA", "CP"))
        self.assertEqual(dm.get_type("bao_cao_cic").matrix_agents, ("CIA", "RA", "CP", "CR"))

    def test_loader_rejects_cia_without_the_agent(self):
        bad = Path(tempfile.mkdtemp()) / "m.yaml"
        bad.write_text("version: 2\nloan_programs: [{id: KHDN}]\ngroups:\n  - id: g\n    types:\n"
                       "      - id: t\n        label: T\n        keywords: [abc]\n        matrix_agents: [CIA]\n",
                       encoding="utf-8")
        with self.assertRaises(dm.DocumentMatrixError):
            dm._load(bad)

    def test_business_model_pass_runs_on_field_report_contracts_and_ledgers(self):
        flagged = {t.id for t in dm.load_matrix().types.values() if t.business_model_extraction}
        self.assertTrue({"bao_cao_thuc_dia", "hop_dong_dau_vao_dau_ra", "so_chi_tiet_cong_no"} <= flagged)


class BusinessModelTest(unittest.TestCase):
    def test_field_report_first_then_largest_value_and_at_most_five(self):
        records = [
            model("so_chi_tiet_cong_no", "TK331.xlsx",
                  suppliers=[{"name": f"NCC {i}", "product": "Thép", "value": i * M} for i in range(1, 8)]),
            model("bao_cao_thuc_dia", "BCTD.pdf", suppliers=[{"name": "NCC 2", "product": "Thép cuộn", "value": None}]),
        ]
        rows = business_model.partners(records, "suppliers")
        self.assertEqual(len(rows), 5)
        self.assertEqual([r["name"] for r in rows], ["NCC 7", "NCC 6", "NCC 5", "NCC 4", "NCC 3"])
        merged = business_model.partners(records[1:], "suppliers")
        self.assertEqual(merged[0]["product"], "Thép cuộn")      # field report wins the product

    def test_suppliers_left_customers_right_no_invented_rows(self):
        records = [model("hop_dong_dau_vao_dau_ra", "HD.pdf",
                         suppliers=[{"name": "Nhà cung cấp X", "product": "Xi măng", "value": 5 * M}],
                         customers=[{"name": "Khách Y", "product": "", "value": 9 * M},
                                    {"name": "Khách Z", "product": "Gạch", "value": 3 * M}])]
        html = business_model.diagram("CÔNG TY ABC", records)
        first_row = html.split("<tr>")[2]
        self.assertLess(first_row.index("Nhà cung cấp X"), first_row.index("CÔNG TY ABC"))
        self.assertLess(first_row.index("CÔNG TY ABC"), first_row.index("Khách Y"))
        self.assertEqual(html.count("<tr>"), 3)                    # header + 2 rows (max of the two sides)
        self.assertNotIn("khác", html.lower().replace("khách", ""))
        self.assertNotIn("không rõ", html)
        self.assertIn("không có tỷ trọng", html)
        self.assertNotIn("\n", html)

    def test_no_partner_no_diagram(self):
        self.assertEqual(business_model.diagram("ABC", []), "")


class IndustryTest(unittest.TestCase):
    def test_lookup_ignores_accents(self):
        row = industry.lookup("xay dung dan dung")
        self.assertEqual((row["ros"], row["growth"]), (0.12, 0.07))
        self.assertIsNone(industry.lookup("Ngành không có"))
        self.assertIn("Xây dựng dân dụng", industry.prompt_list())


class FinanceGroupTest(unittest.TestCase):
    def test_good_finance_needs_growth_above_zero(self):
        flat = dict(Y2025, net_revenue=800 * M, profit_after_tax=40 * M, retained_earnings=60 * M)  # growth 0%
        self.assertEqual(fm.compute([fin([flat, Y2024])], AS_OF)["group"], "Normal finance")
        self.assertEqual(fm.compute([fin([Y2025, Y2024])], AS_OF)["group"], "Good finance")

    def test_vat_monthly_average_drop_is_flagged(self):
        vat = {"pass": "vat", "document": "VAT.pdf", "data": {"returns": [
            {"year": 2026, "period_type": "quarter", "quarter": 1, "revenue": 150 * M}]}}
        r = fm.compute([fin([Y2025, Y2024]), vat], AS_OF)
        self.assertAlmostEqual(r["vat"]["monthly_growth"], (150 / 3) / (1000 / 12) - 1)
        self.assertTrue(any("suy giảm" in x for x in r["status_remarks"]))


class ProjectionTest(unittest.TestCase):
    PLAN = {"has_plan": True, "plan_year": 2026, "plan_revenue": 1300 * M, "plan_profit_after_tax": 130 * M,
            "basis": "Hợp đồng đầu ra mới"}
    NGANH = {"name": "Xây dựng dân dụng", "ros": 0.12, "growth": 0.07}

    def financials(self):
        return fm.compute([fin([Y2025, Y2024])], AS_OF)

    def test_normal_corp_caps_revenue_at_industry_growth(self):
        r = fm.income_estimate(self.financials(), 100, 0, plan=self.PLAN, industry=self.NGANH,
                               corp_group="Normal corp")
        p = r["projection"]
        self.assertAlmostEqual(p["feasible_revenue"], 1000 * M * 1.07)            # min(1300, 1070)
        self.assertAlmostEqual(p["feasible_ros"], 0.10)                          # min(10%, max(5%, 12%))
        self.assertAlmostEqual(r["reasonable_lnst"], 0.10 * 1070 * M)
        self.assertEqual(r["method"], "du_phong")

    def test_good_corp_uses_growth_times_1_5(self):
        r = fm.income_estimate(self.financials(), 100, 0, plan=self.PLAN, industry=self.NGANH,
                               corp_group="Good corp")
        self.assertAlmostEqual(r["projection"]["feasible_revenue"], 1000 * M * (1 + 0.07 * 1.5))

    def test_bad_corp_and_unknown_industry_use_history(self):
        for group, nganh in (("Bad corp", self.NGANH), ("Normal corp", None)):
            r = fm.income_estimate(self.financials(), 100, 0, plan=self.PLAN, industry=nganh, corp_group=group)
            self.assertIsNone(r["projection"])
            self.assertEqual(r["reasonable_lnst"], 50 * M)

    def test_plan_growth_without_basis_is_flagged(self):
        plan = dict(self.PLAN, basis="")
        r = fm.income_estimate(self.financials(), 100, 0, plan=plan, industry=self.NGANH, corp_group="Normal corp")
        self.assertTrue(any("không ghi cơ sở" in w for w in r["warnings"]))

    def test_dividend_formula(self):
        r = fm.income_estimate(self.financials(), 60, 20 * M)
        self.assertAlmostEqual(r["value"], (50 * M - 20 * M) * 0.6)


class PlanTableTest(unittest.TestCase):
    def test_basis_column_hidden_without_basis(self):
        f = fm.compute([fin([Y2025, Y2024])], AS_OF)
        with_basis = plan_table({"plan_revenue": 1200 * M, "plan_profit_after_tax": 60 * M, "basis": "HĐ mới"},
                                f, "2025", "2024")
        without = plan_table({"plan_revenue": 1200 * M, "plan_profit_after_tax": 60 * M}, f, "2025", "2024")
        self.assertIn("Cơ sở của Khách hàng", with_basis)
        self.assertNotIn("Cơ sở của Khách hàng", without)
        self.assertIn("20,0%", with_basis)                       # 1200 / 1000 - 1


class CicTableTest(unittest.TestCase):
    def s10a(self, **data):
        base = {"report_type": "S10A", "query_date": "20/10/2026",
                "lenders": [{"name": "Techcombank", "short_term": 100 * M, "long_term": 50 * M},
                            {"name": "Vietcombank", "short_term": 20 * M, "off_balance": 5 * M}],
                "collaterals": [{"name": "QSDĐ Hà Nội", "value": 300 * M, "owner": "Nguyễn Văn A",
                                 "lender": "Techcombank"}],
                "monthly_balances_12m": [{"month": f"{m:02d}/2026", "balance": 150 * M} for m in range(1, 13)]}
        return {"pass": "cic", "document": "CIC.pdf", "data": {**base, **data}}

    def test_one_row_per_lender_with_its_collateral(self):
        r = cic_metrics.compute([self.s10a()], AS_OF, revenue_prev_year=900 * M, business_type="thuong_mai")
        rows = {x["name"]: x for x in r["lenders"]}
        self.assertEqual(rows["Techcombank"]["collaterals"], ["QSDĐ Hà Nội"])
        self.assertEqual(rows["Vietcombank"]["other"], 5 * M)           # cam kết ngoại bảng in "dư nợ khác"
        self.assertEqual(r["group"], "Good bureau")

    def test_card_late_payment_blocks_good_bureau(self):
        r = cic_metrics.compute([self.s10a(card_late_payment_3y=[{"lender": "VCB", "date": "05/2025"}])],
                                AS_OF, revenue_prev_year=900 * M, business_type="thuong_mai")
        self.assertEqual(r["group"], "Normal bureau")


class TemplateTest(unittest.TestCase):
    def test_template_has_the_appendix_sections(self):
        text = load_template()[0]
        for heading in ("### 1. Pháp lý doanh nghiệp", "#### a. Thông tin cơ bản về pháp lý doanh nghiệp",
                        "#### b. Thành viên góp vốn & người đại diện theo pháp luật",
                        "### 2. Hoạt động kinh doanh", "Mô hình HĐKD (nếu có)", "### 3. Tài chính",
                        "Cập nhật các tháng năm", "### 4. Dư nợ tại TCTD", "#### c. Chất lượng tín dụng",
                        "### 5. Kết luận nguồn thu doanh nghiệp"):
            self.assertIn(heading, text)
        names = set(template_placeholders(text))
        self.assertFalse({"NhanXetPhapLyDN", "NhanXetDuNo", "NhanXetPAKD", "Nguon", "DoanhNghiepA"} & names)


if __name__ == "__main__":
    unittest.main()
