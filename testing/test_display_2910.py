"""[Sửa 29/10] Fine-tune of the final output: 1a, 1b, 2b, 3a, 3b, 4a."""

import unittest

from src.agents.calculator import cic_metrics, legal_checks
from src.agents.calculator import financial_metrics as fm
from src.utils.report.appendix_context import debt_table, drop_repeated_warnings
from testing.test_brd_2710 import AS_OF, M, Y2024, Y2025, fin


def legal(*rows):
    return [{"pass": "legal_basic", "source": "customer", "document": f"doc{i}.pdf", "document_type": "gcn_dkdn",
             "data": data} for i, data in enumerate(rows)]


def codes(records):
    return {f["code"] for f in legal_checks.run_all_checks(records, AS_OF)[1]["findings"]}


class LegalTest(unittest.TestCase):
    def test_company_abbreviations_are_not_a_mismatch(self):
        for a, b in (("Công ty TNHH Đức Phúc", "CT TNHH Đức Phúc"),
                     ("Công ty Cổ phần Đức Phúc", "CTCP Đức Phúc"),
                     ("CÔNG TY CP ĐỨC PHÚC", "Cty CP Đức Phúc")):
            self.assertNotIn("name_mismatch", codes(legal({"company_name": a}, {"company_name": b})), (a, b))
        self.assertIn("name_mismatch", codes(legal({"company_name": "CTCP Đức Phúc"},
                                                   {"company_name": "CTCP Việt Phúc"})))

    def test_year_only_matches_a_full_date_of_that_year(self):
        found = lambda a, b: "establishment_mismatch" in codes(
            legal({"establishment_date": a}, {"establishment_date": b}))
        self.assertFalse(found("2025", "06/02/2025"))
        self.assertTrue(found("2024", "06/02/2025"))
        self.assertTrue(found("05/02/2025", "06/02/2025"))       # both full dates → compared in full
        self.assertFalse(found("06/02/2025", "2025-02-06"))


class RepeatTest(unittest.TestCase):
    def test_2b_drops_mismatches_already_in_1b(self):
        legal_text = ("**Cảnh báo pháp lý:**\n\n- Địa chỉ trụ sở chính ghi khác nhau giữa các nguồn: A (ĐKKD) ≠ B")
        hdkd = "- Địa chỉ báo cáo thực địa ≠ ĐKKD<br>- Ảnh thực địa không có biển hiệu"
        self.assertEqual(drop_repeated_warnings(hdkd, legal_text), "- Ảnh thực địa không có biển hiệu")
        self.assertEqual(drop_repeated_warnings("- Địa chỉ báo cáo thực địa ≠ ĐKKD", legal_text), "—")
        self.assertEqual(drop_repeated_warnings(hdkd, ""), hdkd)


class FinanceTest(unittest.TestCase):
    def test_ros_positive_means_efficient(self):
        f = fm.compute([fin([Y2025, Y2024])], AS_OF)
        self.assertTrue(any("> 0 — KH là doanh nghiệp có hoạt động kinh doanh hiệu quả" in r
                            for r in f["status_remarks"]))


class CicTest(unittest.TestCase):
    def cic(self, **data):
        base = {"report_type": "S10A", "query_date": "20/10/2026",
                "lenders": [{"name": "Vietcombank", "short_term": 20 * M}], "collaterals": [{"name": "Nhà"}],
                "monthly_balances_12m": []}
        return {"pass": "cic", "document": "CIC.pdf", "data": {**base, **data}}

    def test_one_validity_line(self):
        old = [self.cic(query_date="01/08/2026"), self.cic(query_date="01/08/2026")]   # two prints
        table = debt_table(cic_metrics.compute(old, AS_OF, revenue_prev_year=900 * M))
        self.assertEqual(table.count("CIC chưa hợp lệ"), 1)
        self.assertEqual(table.count("quá 1 tháng"), 1)
        self.assertNotIn("Bản tin: ", table)
        ok = debt_table(cic_metrics.compute([self.cic()], AS_OF, revenue_prev_year=900 * M))
        self.assertIn("Bản tin CIC hợp lệ (S10A: 20/10/2026) — tra cứu trong vòng 1 tháng", ok)

    def test_no_debt_is_good_bureau(self):
        for lenders in ([], [{"name": "Vietcombank", "short_term": 0}]):
            r = cic_metrics.compute([self.cic(lenders=lenders)], AS_OF, revenue_prev_year=None)
            self.assertEqual(r["group"], "Good bureau", lenders)
            self.assertEqual(r["avg_balance_12m"], 0)
        with_debt = cic_metrics.compute([self.cic()], AS_OF, revenue_prev_year=900 * M)
        self.assertEqual(with_debt["group"], "Normal bureau")              # no monthly balances → unchanged

    def test_bad_debt_still_wins(self):
        r = cic_metrics.compute([self.cic(lenders=[], bad_debt_5y=[{"date": "01/2026", "lender": "X"}])], AS_OF, None)
        self.assertEqual(r["group"], "Bad bureau")


class TemplateTest(unittest.TestCase):
    def test_no_t24_row(self):
        with open("src/templates/corp-income-structure.md", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("T24", text)


if __name__ == "__main__":
    unittest.main()
