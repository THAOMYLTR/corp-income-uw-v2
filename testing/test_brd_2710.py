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
from src.utils.report.appendix_context import apply_output_conditions, debt_table, plan_cells
from src.utils.report.visualization.debt_chart import debt_chart
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
        self.assertNotIn("không có tỷ trọng", html)                # [Sửa 29/10] % computed from values
        svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", html).group(1)).decode("utf-8")
        x = {t: float(re.search(r'<tspan x="([\d.]+)"[^>]*>' + re.escape(t), svg).group(1))
             for t in ("Xi măng", "Nhà cung cấp X", "CÔNG TY ABC", "Gạch", "Khách Z", "Khách Y")}
        # 5 tiers: sản phẩm đầu vào < đối tác đầu vào < DN < sản phẩm đầu ra < đối tác đầu ra
        self.assertLess(x["Xi măng"], x["Nhà cung cấp X"])
        self.assertLess(x["Nhà cung cấp X"], x["CÔNG TY ABC"])
        self.assertLess(x["CÔNG TY ABC"], x["Gạch"])
        self.assertLess(x["Gạch"], x["Khách Z"])
        self.assertEqual(x["Khách Y"], x["Khách Z"])                # no product → no product box
        self.assertEqual(svg.count('width="150"'), 6)               # 2 left + 3 right (Y has no product) + DN
        self.assertNotIn("không rõ", svg)
        self.assertNotIn("khác", svg.lower().replace("khách", ""))

    def test_contract_value_under_the_partner_name(self):
        import base64, re
        records = [model("hop_dong_dau_vao_dau_ra", "HD.pdf",
                         suppliers=[{"name": "Dược Hậu Giang", "product": "Thuốc", "value": 135 * M}],
                         customers=[{"name": "BHXH Hà Nội", "product": "", "value": None}])]
        svg = base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)",
                                         business_model.diagram("DN", records)).group(1)).decode("utf-8")
        name_y = float(re.search(r'y="([\d.]+)">Dược Hậu Giang<', svg).group(1))
        value_y = float(re.search(r'y="([\d.]+)" font-weight="bold">135tr<', svg).group(1))
        self.assertGreater(value_y, name_y)                       # right under the name, same box
        self.assertNotIn("tr<", svg.split("BHXH Hà Nội")[1][:80])   # no value → no value line
        self.assertEqual([business_model._money(v) for v in (135 * M, 950 * M, 1.5e9, 180e9, 2_345e9)],
                         ["135tr", "950tr", "1,5tỷ", "180tỷ", "2.345tỷ"])

    def test_share_computed_from_values_else_as_given(self):
        import base64, re
        svg = lambda recs: base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)",
                                                      business_model.diagram("DN", recs)).group(1)).decode("utf-8")
        # [Sửa 29/10] 135tr / (135tr + 45tr) = 75% — the document's own 45% is not used
        with_values = [model("hop_dong_dau_vao_dau_ra", "HD.pdf",
                             suppliers=[{"name": "Dược Hậu Giang", "value": 135 * M, "share_pct": 45},
                                        {"name": "Nam Phùng", "value": 45 * M}])]
        self.assertIn(">75%<", svg(with_values))
        self.assertIn(">25%<", svg(with_values))
        # no value at all → the share the document writes
        no_values = [model("bao_cao_thuc_dia", "BCTD.pdf",
                           suppliers=[{"name": "A", "product": "", "value": None, "share_pct": 45}])]
        self.assertIn(">45%<", svg(no_values))

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


class RelationTest(unittest.TestCase):
    def test_one_phrase_per_pair(self):
        from src.utils.report.appendix_context import _relations
        rel = lambda a, b, r: {"member_a": a, "member_b": b, "relation": r}
        records = [{"pass": "shareholders", "source": "customer",
                    "data": {"relationships": [rel("Lê Thị Hoa", "Vũ Hoàng Nguyên", "vợ")]}},
                   {"pass": "shareholders", "source": "field",
                    "data": {"relationships": [rel("Vũ Hoàng Nguyên", "Lê Thị Hoa", "chồng"),
                                               rel("Vũ Minh", "Vũ Hoàng Nguyên", "con")]}}]
        found = _relations(records)
        self.assertEqual(found["le thi hoa"], ["vợ của Vũ Hoàng Nguyên"])
        self.assertEqual(sorted(found["vu hoang nguyen"]), ["Vũ Minh là con", "chồng của Lê Thị Hoa"])


class BorrowerFromSiteVisitTest(unittest.TestCase):
    """[BRD 29/10] Đại diện KH trong báo cáo thực địa = người đứng ra vay (trước hồ sơ vay vốn)."""

    MEMBERS = {"pass": "shareholders", "source": "customer", "document": "So co dong.pdf",
               "data": {"members": [{"name": "Vũ Hoàng Nguyên", "member_type": "ca_nhan"},
                                    {"name": "Nguyễn Huệ Chi", "member_type": "ca_nhan"}]}}
    LOAN_REQUEST = None

    def setUp(self):
        from types import SimpleNamespace as Doc
        self.Doc = Doc
        self.loan = Doc(declared_group="ho_so_vay_von", source="customer", filename="De nghi vay.pdf",
                        content="GIẤY ĐỀ NGHỊ VAY VỐN — Ông Vũ Hoàng Nguyên và Bà Nguyễn Huệ Chi")

    def detect(self, docs, records):
        from src.agents.calculator.borrowers import detect_borrowers
        return detect_borrowers(docs, records)

    def test_llm_field_customer_representative(self):
        field = {"pass": "shareholders", "source": "field", "document": "BCTD.pdf",
                 "data": {"customer_representative": "Bà Nguyễn Huệ Chi"}}
        self.assertEqual(self.detect([self.loan], [self.MEMBERS, field]),
                         (["Nguyễn Huệ Chi"], ["BCTD.pdf (đại diện KH)"]))

    def report(self, text):
        return self.Doc(declared_group="ho_so_soan_thao_noi_bo", source="field", filename="BCTD.pdf",
                        content="BÁO CÁO KHẢO SÁT THỰC ĐỊA\n" + text)

    def test_representative_line_in_the_report_text(self):
        names, files = self.detect([self.report("Đại diện khách hàng: Bà Nguyễn Huệ Chi - Phó giám đốc\n"
                                                "Thành viên góp vốn: Vũ Hoàng Nguyên, Nguyễn Huệ Chi"),
                                    self.loan], [self.MEMBERS])
        self.assertEqual(names, ["Nguyễn Huệ Chi"])
        self.assertTrue(files[0].startswith("BCTD.pdf (dòng: Đại diện khách hàng"))

    def test_only_the_name_right_after_the_label(self):
        """The mix-up seen in a real run: the husband named on the same line was taken too."""
        doc = self.report("Đại diện KH: Bà Nguyễn Huệ Chi (vợ ông Vũ Hoàng Nguyên, người quyết định chính)")
        self.assertEqual(self.detect([doc], [self.MEMBERS])[0], ["Nguyễn Huệ Chi"])

    def test_label_after_a_relation_word_is_ignored(self):
        doc = self.report("Chồng khách hàng vay vốn là ông Vũ Hoàng Nguyên\nTên khách hàng: Nguyễn Huệ Chi")
        self.assertEqual(self.detect([doc], [self.MEMBERS])[0], ["Nguyễn Huệ Chi"])

    def test_people_marked_kh_vay(self):
        field = {"pass": "shareholders", "source": "field", "document": "BCTD.pdf",
                 "data": {"people": [{"name": "Vũ Hoàng Nguyên", "relation_to_borrower": "Chồng KH vay"},
                                     {"name": "Nguyễn Huệ Chi", "relation_to_borrower": "KH vay"}]}}
        self.assertEqual(self.detect([], [self.MEMBERS, field])[0], ["Nguyễn Huệ Chi"])

    def test_falls_back_to_the_loan_request(self):
        self.assertEqual(self.detect([self.loan], [self.MEMBERS])[0], ["Vũ Hoàng Nguyên", "Nguyễn Huệ Chi"])


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
    """[BRD 29/10] Dự phóng kinh doanh: TH vs KH, ROS / tăng trưởng theo ngành TCB vs theo dự phóng."""

    def test_plan_cells(self):
        f = fm.compute([fin([dict(Y2025, cogs=600 * M), Y2024])], AS_OF)
        nganh = {"name": "Xây dựng dân dụng", "segment": "SME", "ros": 0.12, "growth": 0.07}
        cells = plan_cells({"plan_year": 2026, "plan_revenue": 1200 * M, "plan_cogs": 690 * M,
                            "plan_profit_after_tax": 60 * M, "basis": "HĐ mới"}, f, "2025", nganh)
        self.assertEqual(cells["PAKD_DTT_TangGiam"], "+20,0%")             # 1200 / 1000 − 1
        self.assertEqual(cells["PAKD_GV_TangGiam"], "+15,0%")              # 690 / 600 − 1
        self.assertEqual(cells["PAKD_LNST_TangGiam"], "+20,0%")            # 60 / 50 − 1
        self.assertEqual((cells["PAKD_ROS"], cells["PAKD_TangTruong"]), ("5,0%", "+20,0%"))
        self.assertEqual((cells["Nganh_ROS"], cells["Nganh_TangTruong"]), ("12,0%", "7,0%"))
        self.assertIn("phân khúc SME", cells["Nganh_CoSo"])

    def test_tables_hidden_without_plan(self):
        md = ('<p class="no-pakd">Khách hàng không cung cấp phương án kinh doanh.</p>\n'
              '<table class="pakd">\n<tr><td>Doanh thu thuần</td></tr>\n</table>\nsau')
        self.assertEqual(apply_output_conditions(md, {"_has_plan": ""}),
                         '<p class="no-pakd">Khách hàng không cung cấp phương án kinh doanh.</p>\nsau')
        self.assertNotIn("no-pakd", apply_output_conditions(md, {"_has_plan": "1"}))


class AddressLinesTest(unittest.TestCase):
    def test_missing_factory_and_warehouse_are_skipped(self):
        row = "| Địa chỉ | - TSC: Số 1 Lê Lợi<br>- Nhà xưởng: —<br>- Kho hàng: Chưa có thông tin trong hồ sơ |"
        out = apply_output_conditions(row + "\n**Cảnh báo HĐKD:** —\n",
                                      {"NhaXuong": "—", "KhoHang": "Chưa có thông tin trong hồ sơ", "NhanXetHDKD": "—"})
        self.assertEqual(out, "| Địa chỉ | - TSC: Số 1 Lê Lợi |\n")
        kept = apply_output_conditions(row.replace("Nhà xưởng: —", "Nhà xưởng: KCN Quang Minh (đi thuê)"),
                                       {"NhaXuong": "KCN Quang Minh (đi thuê)", "KhoHang": "—"})
        self.assertIn("Nhà xưởng: KCN Quang Minh", kept)


class FinanceTablesTest(unittest.TestCase):
    """[BRD 29/10] a. lines ≥ 20% of total assets; b. growth = năm sau / năm trước − 1, signed."""

    def test_only_lines_of_20_percent_or_more(self):
        y25 = dict(Y2025, cash=25 * M, receivables=10 * M, fixed_assets=30 * M, inventory=5 * M)
        y24 = dict(Y2024, cash=5 * M, receivables=30 * M, fixed_assets=50 * M, inventory=5 * M)
        f = fm.compute([fin([y25, y24])], AS_OF)
        shown = [label for label, _ in fm.asset_lines(f, ("2024", "2025"))]
        self.assertEqual(shown, ["Tiền và tương đương tiền", "Phải thu & trả trước", "TSCĐ ròng"])

    def test_signed_growth(self):
        self.assertEqual((fm.signed_pct(2.426), fm.signed_pct(-0.014), fm.signed_pct(None)),
                         ("+242,6%", "-1,4%", "—"))

    def test_interest_band_6_to_14_percent(self):
        f = fm.compute([fin([dict(Y2025, interest_expense=1 * M), Y2024])], AS_OF)
        self.assertIn("ngoài khoảng 6%–14%", fm.interest_vs_cic(f, 100 * M))      # 1%/năm
        self.assertEqual(fm.interest_vs_cic(f, 10 * M), "")                         # 10%/năm

    def test_remarks_keep_numbers_but_no_file_names(self):
        a = fin([dict(Y2025, total_assets=101 * M), Y2024]); a["document"] = "BCTC_2025.pdf"
        b = fin([year(2025, total_assets=120)]); b["document"] = "BCTC_2026.pdf"
        a["data"]["unusual_items"] = ["Thu nhập khác lớn từ thanh lý TSCĐ"]
        f = fm.compute([a, b], AS_OF)
        text = " ".join(f["bs_warnings"] + f["pl_warnings"] + f["status_remarks"])
        self.assertNotIn(".pdf", text)
        self.assertIn("101 ≠ 120", text)                                     # the numbers stay
        self.assertIn("Doanh thu thuần năm 2025 đạt 1.000 triệu đồng", text)

    def test_structure_remarks(self):
        f = fm.compute([fin([dict(Y2025, non_current_assets=60 * M), Y2024])], AS_OF)
        remarks = fm.structure_remarks(f, "thuong_mai")
        self.assertTrue(any("thương mại có tài sản dài hạn" in r for r in remarks))
        self.assertTrue(any("Vốn lưu động ròng năm 2025 = 30" in r for r in remarks))     # 60 − 30


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
        self.assertEqual(rows["Vietcombank"]["off_balance"], 5 * M)     # [BRD 29/10] ngoại bảng apart
        self.assertEqual(rows["Vietcombank"]["total"], 20 * M)          # not in Tổng dư nợ
        self.assertEqual(r["group"], "Good bureau")

    def test_card_late_payment_blocks_good_bureau(self):
        r = cic_metrics.compute([self.s10a(card_late_payment_3y=[{"lender": "VCB", "date": "05/2025"}])],
                                AS_OF, revenue_prev_year=900 * M, business_type="thuong_mai")
        self.assertEqual(r["group"], "Normal bureau")


class DebtTableTest(unittest.TestCase):
    def test_columns_per_lender_and_chart(self):
        data = {"report_type": "S10A", "query_date": "20/10/2026",
                "lenders": [{"name": "Vietinbank", "short_term": 60 * M, "long_term": 20 * M},
                            {"name": "VCB", "short_term": 10 * M, "finance_lease": 10 * M, "off_balance": 7 * M}],
                "monthly_balances_12m": [{"month": f"{m:02d}/2026", "balance": (90 + m) * M} for m in range(1, 13)]}
        cic = cic_metrics.compute([{"pass": "cic", "document": "CIC.pdf", "data": data}], AS_OF, 1200 * M)
        table = debt_table(cic)
        self.assertNotIn("\n", table)                                  # one line: sits in a table cell
        self.assertIn("<th>Vietinbank</th><th>VCB</th><th>Tổng</th>", table)
        self.assertIn("<td>Cho thuê TC</td><td>0</td><td>10</td><td>10</td>", table)
        self.assertIn("<td>%</td><td>80,0%</td><td>20,0%</td><td>100%</td>", table)
        self.assertIn("Cam kết ngoại bảng tại: VCB (*)", table)
        self.assertEqual([m for m, _ in cic["monthly"]][:2], ["01/2026", "02/2026"])
        chart = debt_chart(cic["monthly"], cic["avg_balance_12m"])
        self.assertTrue(chart.startswith("<img") and "\n" not in chart)
        self.assertEqual(debt_chart([]), "")


class TemplateTest(unittest.TestCase):
    TEXT = load_template()[0]

    def test_template_follows_the_brd_of_29_10(self):
        for text in ("#### a. Thông tin cơ bản về pháp lý doanh nghiệp",
                     "| Tên thành viên góp vốn/ ban lãnh đạo | Tỷ lệ vốn góp (%) | Chức vụ | Mối quan hệ | "
                     "Mức độ ảnh hưởng tới Khách hàng | Đánh giá về năng lực, uy tín và kinh nghiệm |",
                     "#### a. Ngành nghề hoạt động kinh doanh", "#### b. Mô tả hoạt động kinh doanh",
                     "| Mô hình hoạt động kinh doanh | {{MoHinhHDKD}} |",
                     "#### a. Cơ cấu tài sản, nguồn vốn",
                     "<th>Chỉ tiêu</th><th>{{Nam-2}}</th><th>% Tỷ trọng</th><th>{{Nam-1}}</th><th>% Tỷ trọng</th>"
                     "<th>Nhận xét</th>",
                     "#### b. Quy mô & tăng trưởng & chỉ số", "<th>Tăng trưởng</th>",
                     "{{BangDuNoTCTD}}", "{{BieuDoDuNo}}", "#### b. Chất lượng tín dụng",
                     "<th>Chỉ tiêu</th><th>TH {{Nam-1}}</th><th>KH {{PAKD_NamKeHoach}}</th><th>Tăng/ giảm</th>"
                     "<th>Cơ sở dự phóng</th>",
                     "<th>Theo am hiểu ngành TCB</th><th>Theo dự phóng</th>", "#### b. Đề xuất"):
            self.assertIn(text, self.TEXT)
        names = set(template_placeholders(self.TEXT))
        self.assertFalse({"NhanXet", "NhanXetTaiChinh", "KQ_TaiChinh_1", "DTTCurrent"} & names)
        self.assertNotIn('class="poc"', self.TEXT)                      # no "Phân nhóm" tables any more


if __name__ == "__main__":
    unittest.main()
