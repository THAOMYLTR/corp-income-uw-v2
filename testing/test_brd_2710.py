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
from src.utils.report.appendix_context import apply_output_conditions, plan_cells
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
        import base64, re
        records = [model("hop_dong_dau_vao_dau_ra", "HD.pdf",
                         suppliers=[{"name": "Nhà cung cấp X", "product": "Xi măng", "value": 5 * M}],
                         customers=[{"name": "Khách Y", "product": "", "value": 9 * M},
                                    {"name": "Khách Z", "product": "Gạch", "value": 3 * M}])]
        html = business_model.diagram("CÔNG TY ABC", records)
        self.assertNotIn("\n", html)                               # fits one table cell
        self.assertIn("không có tỷ trọng", html)
        svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", html).group(1)).decode("utf-8")
        x = {t: float(re.search(r'<tspan x="([\d.]+)"[^>]*>' + re.escape(t), svg).group(1))
             for t in ("Xi măng", "Nhà cung cấp X", "CÔNG TY ABC", "Gạch", "Khách Z", "Khách Y")}
        # 5 tiers: sản phẩm đầu vào < đối tác đầu vào < DN < sản phẩm đầu ra < đối tác đầu ra
        self.assertLess(x["Xi măng"], x["Nhà cung cấp X"])
        self.assertLess(x["Nhà cung cấp X"], x["CÔNG TY ABC"])
        self.assertLess(x["CÔNG TY ABC"], x["Gạch"])
        self.assertLess(x["Gạch"], x["Khách Z"])
        self.assertEqual(x["Khách Y"], x["Khách Z"])                # no product → no product box
        self.assertEqual(svg.count("<rect x"), 6)                    # 2 left + 3 right (Y has no product) + DN
        self.assertNotIn("không rõ", svg)
        self.assertNotIn("khác", svg.lower().replace("khách", ""))

    def test_share_labels_only_when_given(self):
        import base64, re
        records = [model("bao_cao_thuc_dia", "BCTD.pdf",
                         suppliers=[{"name": "A", "product": "", "value": 1 * M, "share_pct": 45}])]
        svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)",
                                         business_model.diagram("DN", records)).group(1)).decode("utf-8")
        self.assertIn(">45%<", svg)

    def test_no_partner_no_diagram(self):
        self.assertEqual(business_model.diagram("ABC", []), "")


class IndustryTest(unittest.TestCase):
    def test_full_table_four_segments(self):
        rows = industry.industries()
        self.assertEqual(len(rows), 440)
        self.assertEqual({r["segment"] for r in rows}, {"SME", "USME", "MM", "LC"})

    def test_lookup_by_segment_ignores_accents(self):
        sme = industry.lookup("xay dung dan dung", "SME")
        self.assertEqual((sme["ros"], sme["growth"]), (0.12, 0.07))
        lc = industry.lookup("Xây dựng dân dụng", "LC")
        self.assertAlmostEqual(lc["ros"], 0.06773796195417427)
        self.assertEqual(industry.lookup("Xây dựng dân dụng")["segment"], "SME")   # unknown segment
        self.assertIsNone(industry.lookup("Ngành không có"))

    def test_sector_breaks_ties_and_prompt_lists_each_industry_once(self):
        self.assertEqual(industry.lookup("Khác", "SME", "Recom")["bizline"], "SME-Recom-Others")
        listed = industry.prompt_list().splitlines()
        self.assertEqual(len(listed), len(set(listed)))
        self.assertIn("- Xây dựng dân dụng — Recom", listed)

    def test_segment_from_revenue(self):
        for revenue, code in ((150e9, "SME"), (200e9, "USME"), (700e9, "MM"), (2500e9, "LC")):
            f = fm.compute([fin([year(2025, net_revenue=revenue / M)])], AS_OF)
            self.assertEqual(fm.segment_code(f), code)


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
    TABLE = ('<table id="pakd">\n<tr><th>Phương án kinh doanh (nếu có)</th><th class="coso">Cơ sở của Khách hàng</th>'
             '</tr>\n<tr><td>Doanh thu thuần</td><td class="coso">x</td></tr>\n</table>\nsau')

    def test_plan_cells(self):
        f = fm.compute([fin([Y2025, Y2024])], AS_OF)
        cells = plan_cells({"plan_year": 2026, "plan_revenue": 1200 * M, "plan_profit_after_tax": 60 * M,
                            "basis": "HĐ mới"}, f, "2025")
        self.assertEqual((cells["PAKD_TangTruong_KeHoach"], cells["PAKD_ROS_KeHoach"]), ("20,0%", "5,0%"))
        self.assertEqual(cells["PAKD_NamKeHoach"], "2026")

    def test_table_hidden_without_plan_and_basis_column_without_basis(self):
        self.assertEqual(apply_output_conditions(self.TABLE, {"_has_plan": ""}), "sau")
        out = apply_output_conditions(self.TABLE, {"_has_plan": "1", "_plan_basis": ""})
        self.assertIn("Doanh thu thuần", out)
        self.assertNotIn("Cơ sở của Khách hàng", out)
        self.assertNotIn('class="coso"', out)


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
    TEXT = load_template()[0]

    def test_template_has_the_appendix_sections(self):
        for heading in ("### 1. Pháp lý doanh nghiệp", "#### a. Thông tin cơ bản về pháp lý doanh nghiệp",
                        "#### b. Thành viên góp vốn & người đại diện theo pháp luật",
                        "### 2. Hoạt động kinh doanh", "Mô hình HĐKD (nếu có)", "### 3. Tài chính",
                        "Cập nhật các tháng năm", "### 4. Dư nợ tại TCTD", "#### c. Chất lượng tín dụng",
                        "### 5. Kết luận nguồn thu doanh nghiệp"):
            self.assertIn(heading, self.TEXT)
        names = set(template_placeholders(self.TEXT))
        self.assertFalse({"NhanXetPhapLyDN", "NhanXetDuNo", "NhanXetPAKD", "Nguon", "DoanhNghiepA"} & names)

    def test_tables_are_written_out_like_the_brd(self):
        # Every column header of the BRD tables is in the template itself, not built by code.
        for header in ("| Họ và tên | Mối quan hệ | Tỷ lệ góp vốn |",
                       '<th rowspan="2">TCTD</th><th colspan="4">Số dư cấp tín dụng</th>',
                       "<th>Dư nợ ngắn hạn</th><th>Dư nợ TDH</th><th>Dư nợ khác</th><th>Tổng số dư CTD</th>",
                       '<th rowspan="2">Tên TSBĐ</th><th rowspan="2">Giá trị TSBĐ</th><th rowspan="2">Chủ sở hữu TSBĐ</th>',
                       "<th>Phương án kinh doanh (nếu có)</th><th>{{Nam-2}}</th><th>{{Nam-1}}</th><th>Cập nhật năm T</th>",
                       '<th class="coso">Cơ sở của Khách hàng</th>',
                       "<th>Phân nhóm tài chính doanh nghiệp (POC)</th>", "<th>Phân nhóm bureau (POC)</th>",
                       "<th>Phân nhóm doanh nghiệp (POC)</th>"):
            self.assertIn(header, self.TEXT)
        for row in ("Doanh thu thuần", "Biến động doanh thu thuần", "Lợi nhuận sau thuế", "ROS (LNST/DTT)"):
            self.assertIn(f"<tr><td>{row}</td>", self.TEXT)


if __name__ == "__main__":
    unittest.main()
