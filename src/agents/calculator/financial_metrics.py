"""Phụ lục 01 mục 3 and 6 — financial figures, ratios, warnings and groups, in code.

The LLM only reads numbers off the documents (financial_extraction, vat_extraction).
Everything the BRD asks to compute is done here, so a number in the report is
always the same arithmetic on the same printed figures.

Sections (search for the tag to find the code):
  [N1]  Nguyên tắc 1 — BCTC TT200 as printed; TT133 → derive TSNH/TSDH/nợ NH.
  [N2]  Nguyên tắc 2 — tờ khai VAT: doanh thu các tháng năm N, so với năm N-1.
  [N3]  Nguyên tắc 3 — biến động DT, ROS, hệ số thanh toán hiện hành.
  [BT]  Cảnh báo dấu hiệu bất thường của BCTC (→ Bad finance when "trọng yếu").
  [TT]  Nhận xét trạng thái tài chính: phân khúc, suy giảm, hiệu quả, thanh khoản.
  [NF]  Phân nhóm tài chính: Bad / Normal / Good finance.
  [TN]  Giá trị nguồn thu doanh nghiệp (mục 5 "Kết luận nguồn thu").
  [DP]  [BRD 27/10] Dự phóng theo phương án kinh doanh (ngành TCB, Good corp × 1,5).

Every threshold is a named constant just below, so a BRD change is a one-line edit.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from src.agents.calculator.legal_checks import SOURCE_LABELS
from src.utils.common import normalize_text
from src.utils.paths import PROJECT_ROOT

FIELDS = (
    "total_assets", "current_assets", "non_current_assets", "total_liabilities",
    "current_liabilities", "long_term_liabilities", "equity", "total_capital",
    "net_revenue", "cogs", "gross_profit", "financial_income", "financial_expenses",
    "selling_expenses", "admin_expenses", "operating_profit", "other_profit",
    "profit_before_tax", "profit_after_tax", "depreciation",
    "cash", "short_term_investments", "receivables", "inventory", "other_assets",
    "retained_earnings", "other_income", "interest_expense",
)
BALANCE_SHEET_FIELDS = (
    "total_assets", "current_assets", "non_current_assets", "total_liabilities",
    "current_liabilities", "long_term_liabilities", "equity", "total_capital", "retained_earnings",
)
LABELS = {
    "total_assets": "Tổng tài sản", "current_assets": "Tài sản ngắn hạn",
    "non_current_assets": "Tài sản dài hạn", "total_liabilities": "Nợ phải trả",
    "current_liabilities": "Nợ ngắn hạn", "long_term_liabilities": "Nợ dài hạn",
    "equity": "Vốn chủ sở hữu", "total_capital": "Tổng nguồn vốn",
    "retained_earnings": "LNST chưa phân phối",
}

# ---- thresholds (BRD 16/10) ------------------------------------------------- #
REVENUE_DROP_ALERT = -0.20          # [TT] biến động DT năm N < -20% → HĐKD suy giảm
# [BRD 27/10][NF] Good finance: "Biến động doanh thu năm N > 0%" (Appendix). The detail sheet
# still writes "> -20%"; the Appendix is the output template, so 0% — change here if needed.
GOOD_FINANCE_MIN_GROWTH = 0.0
# [BRD 27/10][DP] Good corp: doanh thu dự phóng khả thi dùng tăng trưởng ngành × 1,5
# (Appendix; the detail sheet writes × 2).
GOOD_CORP_GROWTH_FACTOR = 1.5
# [BRD 27/10][DP] doanh thu kế hoạch > 20% doanh thu năm gần nhất mà không ghi cơ sở → cảnh báo.
PLAN_GROWTH_NEEDS_BASIS = 0.20
# [Sửa 16/10] Biến động DT ngoài khoảng này → nghi đọc sai số / sai cột, cảnh báo kiểm tra lại.
REVENUE_GROWTH_CHECK = (-0.80, 2.00)
BALANCE_TOLERANCE = 0.005           # [BT] 0,5% — rounding in printed statements
CIT_STANDARD_RATE = 0.20            # [BT] thuế TNDN phổ thông 20%
CIT_TOLERANCE = 0.02                # [BT] ±2 điểm % trước khi cảnh báo
NON_CORE_PROFIT_ALERT = 0.20        # [TT] (thu nhập khác + DT tài chính) / LNTT > 20%
INTEREST_TO_GROSS_ALERT = 0.50      # [TT] chi phí lãi vay / LN gộp > 50%
# [BT] BRD: "khác biệt lớn" between BCTC revenue and VAT revenue — no number given.
# Placeholder 20%; confirm with the business owner and change here.
VAT_BCTC_DIFF_ALERT = 0.20
# [BT] BRD: chi phí lãi vay vs dư nợ BQ (CIC) x lãi suất giả định 10%/năm "không phù hợp"
# — no band given. Placeholder: outside 50%-200% of the implied interest.
ASSUMED_INTEREST_RATE = 0.10
INTEREST_BAND = (0.5, 2.0)
# [TT] Phân khúc KH theo doanh thu năm gần nhất (tỷ đồng).
SEGMENTS = ((2000e9, "Large corp"), (600e9, "MM"), (200e9, "USME"), (0, "SME"))
# [BT] Optional list of excluded audit firms, one name per line (user-maintained).
EXCLUDED_AUDITORS_FILE = PROJECT_ROOT / "src" / "templates" / "danh-sach-kiem-toan-loai-tru.txt"


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    return float(value) if isinstance(value, (int, float)) else None


def _year_of(period: dict[str, Any]) -> str:
    match = re.search(r"(19|20)\d{2}", str(period.get("period") or period.get("end_date") or ""))
    return match.group(0) if match else ""


def _ratio(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def fmt(value: float | None) -> str:
    """Money in triệu đồng, the unit of the Phụ lục 01 tables."""

    if value is None:
        return "—"
    return f"{value / 1e6:,.0f}".replace(",", ".")


def pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%".replace(".", ",")


# --------------------------------------------------------------------------- #
# Merge the BCTC documents into one figure per year
# --------------------------------------------------------------------------- #
def merge_periods(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Years (and the latest interim period) with one value per field.

    Audited statements win over unaudited; within the same rank the first
    document that prints a field keeps it. [BT] A balance-sheet figure printed
    differently by two documents for the same year (cuối kỳ năm trước vs đầu kỳ
    năm sau) is reported in ``cross_document``.
    """

    fin = [r for r in records if r.get("pass") == "financial" and isinstance(r.get("data"), dict)]
    fin.sort(key=lambda r: 0 if r["data"].get("audited") else 1)
    years: dict[str, dict[str, Any]] = {}
    interim: dict[str, Any] = {}
    unusual: list[str] = []
    sources: list[str] = []
    auditors: list[str] = []
    cross_document: list[str] = []
    for record in fin:
        data = record["data"]
        label = f"{record.get('document')} ({'BCTC kiểm toán' if data.get('audited') else 'BCTC thuế/tự lập'})"
        if label not in sources:
            sources.append(label)
        if data.get("auditor_name"):
            auditors.append(str(data["auditor_name"]))
        unusual += [f"{u} — {record.get('document')}" for u in data.get("unusual_items") or [] if u]
        for period in data.get("periods") or []:
            if not isinstance(period, dict):
                continue
            if period.get("period_type") == "interim":
                if interim and str(period.get("period")) != interim.get("period"):
                    continue
                target = interim
                target.setdefault("period", str(period.get("period") or ""))
            else:
                year = _year_of(period)
                if not year:
                    continue
                target = years.setdefault(year, {"period": year})
                # [Sửa 16/10] số tháng của kỳ (năm đầu thành lập < 12) — dùng khi tính biến động DT
                if isinstance(period.get("months"), (int, float)) and "months" not in target:
                    target["months"] = int(period["months"])
            for field in FIELDS:
                value = _num(period.get(field))
                if value is None:
                    continue
                if target.get(field) is None:
                    target[field] = value
                    target.setdefault("_source", {})[field] = record.get("document")
                elif (field in BALANCE_SHEET_FIELDS and target is not interim
                      and abs(target[field] - value) > BALANCE_TOLERANCE * max(abs(target[field]), 1)):
                    # [BT] số liệu cuối kỳ năm trước <> đầu kỳ năm sau
                    cross_document.append(
                        f"{LABELS.get(field, field)} năm {target['period']}: {fmt(target[field])} "
                        f"({target['_source'][field]}) ≠ {fmt(value)} ({record.get('document')})")
    return {"years": dict(sorted(years.items())), "interim": interim, "unusual_items": unusual,
            "sources": sources, "auditors": auditors, "cross_document": cross_document}


def _derive_tt133(fig: dict[str, Any]) -> None:
    """[N1] TT133 statements have no ngắn hạn / dài hạn split: derive it.

    TSNH = Tiền + ĐTTC ngắn hạn + Phải thu + Hàng tồn kho + TS khác
    TSDH = Tổng tài sản - TSNH;  Nợ ngắn hạn = Nợ phải trả;  Nợ dài hạn = 0
    Derived fields are listed in fig["_derived"] so the report can say so.
    """

    derived = fig.setdefault("_derived", [])
    parts = [fig.get(k) for k in ("cash", "short_term_investments", "receivables", "inventory", "other_assets")]
    if fig.get("current_assets") is None and any(p is not None for p in parts):
        fig["current_assets"] = sum(p for p in parts if p is not None)
        derived.append("current_assets")
    if fig.get("non_current_assets") is None and None not in (fig.get("total_assets"), fig.get("current_assets")):
        fig["non_current_assets"] = fig["total_assets"] - fig["current_assets"]
        derived.append("non_current_assets")
    if (fig.get("current_liabilities") is None and fig.get("long_term_liabilities") is None
            and fig.get("total_liabilities") is not None):
        fig["current_liabilities"] = fig["total_liabilities"]
        fig["long_term_liabilities"] = 0.0
        derived += ["current_liabilities", "long_term_liabilities"]
    if fig.get("total_capital") is None and None not in (fig.get("total_liabilities"), fig.get("equity")):
        fig["total_capital"] = fig["total_liabilities"] + fig["equity"]
        derived.append("total_capital")


# --------------------------------------------------------------------------- #
# [N2] VAT returns
# --------------------------------------------------------------------------- #
def vat_summary(records: list[dict[str, Any]], as_of: date, years: dict[str, Any]) -> dict[str, Any]:
    """Revenue per year from the VAT returns; the "các tháng năm N" text.

    An amended return (tờ khai bổ sung) replaces the original of the same period.
    A quarter counts as its three months.
    """

    periods: dict[tuple[int, str], dict[str, Any]] = {}
    for record in records:
        if record.get("pass") != "vat":
            continue
        for row in record["data"].get("returns") or []:
            year, revenue = row.get("year"), _num(row.get("revenue"))
            if not isinstance(year, int) or revenue is None:
                continue
            if row.get("period_type") == "quarter" and row.get("quarter"):
                key, months = f"Q{row['quarter']}", [3 * int(row["quarter"]) - 2 + i for i in range(3)]
            elif row.get("month"):
                key, months = f"M{int(row['month']):02d}", [int(row["month"])]
            else:
                continue
            if (year, key) in periods and not row.get("is_amendment"):
                continue
            periods[(year, key)] = {"revenue": revenue, "months": months, "file": record.get("document")}
    by_year: dict[int, dict[str, Any]] = {}
    for (year, _), info in periods.items():
        entry = by_year.setdefault(year, {"revenue": 0.0, "months": set(), "files": set()})
        entry["revenue"] += info["revenue"]
        entry["months"].update(info["months"])
        entry["files"].add(info["file"])
    if not by_year:
        return {"by_year": {}, "current_year": None, "text": "", "coverage": "", "monthly_growth": None}
    latest_bctc = max((int(y) for y in years), default=0)
    current = as_of.year if as_of.year in by_year else max(by_year)
    if current <= latest_bctc:
        current = None  # no VAT period after the last BCTC: nothing to "update"
    coverage = "; ".join(
        f"{min(e['months']):02d}/{y}–{max(e['months']):02d}/{y}" for y, e in sorted(by_year.items()))
    text = ""
    monthly_growth = None
    if current:
        cur = by_year[current]
        prev_revenue = _num((years.get(str(current - 1)) or {}).get("net_revenue"))
        share = _ratio(cur["revenue"], prev_revenue)
        text = (f"Doanh thu theo tờ khai VAT đến tháng {max(cur['months']):02d}/{current} là "
                f"{fmt(cur['revenue'])} triệu đồng"
                + (f", bằng {pct(share)} doanh thu năm {current - 1}" if share is not None else ""))
        # [BRD 27/10] biến động DT năm N = DT BQ tháng năm N (tờ khai) / DT BQ tháng năm N-1 − 1
        if prev_revenue:
            monthly_growth = (cur["revenue"] / len(cur["months"])) / (prev_revenue / 12) - 1
    return {"by_year": {y: {"revenue": e["revenue"], "months": sorted(e["months"])} for y, e in by_year.items()},
            "current_year": current, "text": text, "coverage": coverage, "monthly_growth": monthly_growth}


def _excluded_auditors() -> list[str]:
    if not EXCLUDED_AUDITORS_FILE.is_file():
        return []
    return [normalize_text(line) for line in EXCLUDED_AUDITORS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #
def compute(records: list[dict[str, Any]], as_of: date | None = None) -> dict[str, Any]:
    """Figures, ratios, warnings (material or not), status remarks and the finance group."""

    as_of = as_of or date.today()
    merged = merge_periods(records)
    years = merged["years"]
    ordered = list(years)
    for fig in years.values():
        _derive_tt133(fig)                                            # [N1]
    if merged["interim"]:
        _derive_tt133(merged["interim"])

    # [N3] ratios per year
    ratios: dict[str, dict[str, float | None]] = {}
    for index, year in enumerate(ordered):
        fig = years[year]
        prev = years[ordered[index - 1]] if index and int(ordered[index - 1]) == int(year) - 1 else {}
        growth = _ratio(fig.get("net_revenue"), prev.get("net_revenue"))
        # [Sửa 16/10] Không so một năm đủ 12 tháng với năm không đủ (năm đầu thành lập).
        if prev and (fig.get("months") or 12) != (prev.get("months") or 12):
            growth = None
        ratios[year] = {
            "revenue_growth": None if growth is None else growth - 1,
            "ros": _ratio(fig.get("profit_after_tax"), fig.get("net_revenue")),
            "current_ratio": _ratio(fig.get("current_assets"), fig.get("current_liabilities")),
        }

    vat = vat_summary(records, as_of, years)                         # [N2]

    # [BT] Cảnh báo dấu hiệu bất thường. ``material`` = mâu thuẫn trọng yếu → Bad finance.
    material: list[str] = []
    other: list[str] = []
    excluded = _excluded_auditors()
    for auditor in merged["auditors"]:
        if any(name and name in normalize_text(auditor) for name in excluded):
            material.append(f"Công ty kiểm toán thuộc danh sách loại trừ: {auditor}")
    if merged["auditors"] and not excluded:
        other.append("Chưa có danh sách công ty kiểm toán loại trừ để đối chiếu "
                     f"({EXCLUDED_AUDITORS_FILE.name}) — kiểm toán: {', '.join(merged['auditors'])}")
    for index, year in enumerate(ordered):
        fig = years[year]
        assets, capital = fig.get("total_assets"), fig.get("total_capital")
        if assets and capital and abs(assets - capital) > BALANCE_TOLERANCE * assets:
            material.append(f"{year}: Tổng tài sản ({fmt(assets)}) ≠ Tổng nguồn vốn ({fmt(capital)})")
        prev = years.get(str(int(year) - 1)) or {}
        re_now, re_prev, lnst = fig.get("retained_earnings"), prev.get("retained_earnings"), fig.get("profit_after_tax")
        if None not in (re_now, re_prev, lnst) and (re_now - re_prev) > lnst + BALANCE_TOLERANCE * max(abs(lnst), 1):
            material.append(f"{year}: LNST chưa phân phối tăng {fmt(re_now - re_prev)} > LNST trong kỳ {fmt(lnst)} "
                            "(trừ khi có điều chỉnh hồi tố / phân phối lại)")
        vat_year = vat["by_year"].get(int(year))
        if vat_year and len(vat_year["months"]) == 12 and fig.get("net_revenue"):
            diff = vat_year["revenue"] / fig["net_revenue"] - 1
            if abs(diff) > VAT_BCTC_DIFF_ALERT:
                material.append(f"{year}: DTT trên BCTC ({fmt(fig['net_revenue'])}) lệch {pct(diff)} so với doanh thu "
                                f"tờ khai VAT cùng kỳ ({fmt(vat_year['revenue'])})")
        lntt = fig.get("profit_before_tax")
        if lntt and lntt > 0 and lnst is not None:
            rate = (lntt - lnst) / lntt
            if abs(rate - CIT_STANDARD_RATE) > CIT_TOLERANCE:
                # Not "trọng yếu" on its own: some sectors / areas have legal tax incentives.
                other.append(f"{year}: Thuế TNDN / LNTT = {pct(rate)} ≠ 20% — cần đánh giá lại "
                             "(trừ ngành nghề/địa bàn được ưu đãi thuế)")
        # [Sửa 16/10] Kiểm tra đọc số: LN gộp phải = DTT − giá vốn; lệch → nghi đọc nhầm dòng/cột.
        dtt, cogs, gross = fig.get("net_revenue"), fig.get("cogs"), fig.get("gross_profit")
        if None not in (dtt, cogs, gross) and abs((dtt - abs(cogs)) - gross) > BALANCE_TOLERANCE * max(abs(dtt), 1):
            other.append(f"{year}: DTT ({fmt(dtt)}) − Giá vốn ({fmt(abs(cogs))}) ≠ LN gộp ({fmt(gross)}) — "
                         "nghi đọc sai số liệu, kiểm tra lại BCTC trước khi dùng các chỉ số")
        if prev and (fig.get("months") or 12) != (prev.get("months") or 12):
            other.append(f"{year}: không tính biến động DT vì năm {int(year) - 1} chỉ có "
                         f"{prev.get('months') or 12} tháng (năm đầu thành lập)")
        growth = ratios[year]["revenue_growth"]
        if growth is not None and not REVENUE_GROWTH_CHECK[0] <= growth <= REVENUE_GROWTH_CHECK[1]:
            other.append(f"{year}: biến động DT {pct(growth)} (DTT {fmt(prev.get('net_revenue'))} → "
                         f"{fmt(fig.get('net_revenue'))}) — bất thường, kiểm tra lại số đọc / kỳ báo cáo")
    material += [f"Số liệu cuối kỳ năm trước ≠ đầu kỳ năm sau: {m}" for m in merged["cross_document"]]
    other += [f"Khoản mục bất thường: {u}" for u in merged["unusual_items"]]

    # [TT] Nhận xét trạng thái tài chính — on the latest full year.
    latest = ordered[-1] if ordered else ""
    status: list[str] = []
    if latest:
        fig, r = years[latest], ratios[latest]
        revenue = fig.get("net_revenue")
        if revenue is not None:
            segment = next(name for floor, name in SEGMENTS if revenue >= floor)
            status.append(f"Doanh thu thuần năm {latest} đạt {fmt(revenue)} triệu đồng, thuộc phân khúc {segment}")
        if r["revenue_growth"] is not None:
            status.append(f"Biến động doanh thu năm {latest}: {pct(r['revenue_growth'])}"
                          + (" — HĐKD của KH suy giảm" if r["revenue_growth"] < REVENUE_DROP_ALERT else ""))
        if vat.get("monthly_growth") is not None:
            # [BRD 27/10] DT BQ tháng năm N (tờ khai VAT) so với năm N-1
            status.append(f"Doanh thu BQ tháng năm {vat['current_year']} (tờ khai VAT) so với năm {latest}: "
                          f"{pct(vat['monthly_growth'])}"
                          + (" — doanh thu suy giảm, đề nghị đánh giá lại nguyên nhân"
                             if vat["monthly_growth"] < REVENUE_DROP_ALERT else ""))
        lntt = fig.get("profit_before_tax")
        non_core = sum(v for v in (fig.get("other_income"), fig.get("financial_income")) if v is not None)
        if lntt and lntt > 0 and non_core and non_core / lntt > NON_CORE_PROFIT_ALERT:
            status.append(f"(Thu nhập khác + DT tài chính) / LNTT = {pct(non_core / lntt)} > 20% — lợi nhuận phụ thuộc "
                          "hoạt động tài chính/thu nhập khác, chất lượng lợi nhuận thấp")
        gross, interest = fig.get("gross_profit"), fig.get("interest_expense")
        if gross and gross > 0 and interest is not None and interest / gross > INTEREST_TO_GROSS_ALERT:
            status.append(f"Chi phí lãi vay / LN gộp = {pct(interest / gross)} > 50% — lãi vay bào mòn phần lớn lợi nhuận gộp")
        if r["ros"] is not None and r["ros"] < 0:
            status.append(f"ROS năm {latest} = {pct(r['ros'])} < 0 — HĐKD không hiệu quả")
        if r["current_ratio"] is not None and r["current_ratio"] < 1:
            status.append(f"Hệ số thanh toán hiện hành năm {latest} = {r['current_ratio']:.2f}".replace(".", ",")
                          + " < 1 — tài sản ngắn hạn không đủ chi trả nợ ngắn hạn, bố trí nguồn vốn chưa cân đối")

    # [NF] Phân nhóm tài chính. "Năm N" = cột năm gần nhất của bảng tài chính (năm BCTC gần
    # nhất): biến động DT, ROS và HSTT của năm đó.
    r = ratios.get(latest) or {}
    growth_n = r.get("revenue_growth")
    if material:
        group, reason = "Bad finance", "BCTC mâu thuẫn trọng yếu theo dấu hiệu bất thường"
    elif (growth_n is not None and growth_n > GOOD_FINANCE_MIN_GROWTH
          and r.get("ros") is not None and r["ros"] > 0
          and r.get("current_ratio") is not None and r["current_ratio"] >= 1):
        group, reason = "Good finance", (f"Năm {latest}: biến động DT {pct(growth_n)} > "
                                         f"{pct(GOOD_FINANCE_MIN_GROWTH)}, ROS > 0%, HSTT ≥ 1")
    else:
        group, reason = "Normal finance", ("Không thuộc Bad/Good finance" if latest else "Chưa có BCTC để đánh giá")

    return {**merged, "ratios": ratios, "vat": vat, "latest_year": latest, "growth_n": growth_n,
            "material_warnings": material, "other_warnings": other,
            "warnings": material + other,               # kept for older callers (step log, Excel)
            "status_remarks": status, "group": group, "group_reason": reason}


def interest_vs_cic(financials: dict[str, Any], avg_balance_12m: float | None) -> str:
    """[BT] Chi phí lãi vay vs dư nợ BQ 12 tháng (CIC) x 10%/năm; '' when consistent or unknown."""

    year = financials.get("latest_year")
    interest = (financials["years"].get(year) or {}).get("interest_expense") if year else None
    if interest is None or not avg_balance_12m:
        return ""
    implied = avg_balance_12m * ASSUMED_INTEREST_RATE
    ratio = interest / implied
    if INTEREST_BAND[0] <= ratio <= INTEREST_BAND[1]:
        return ""
    return (f"{year}: Chi phí lãi vay {fmt(interest)} so với ước tính theo dư nợ BQ CIC x 10%/năm "
            f"({fmt(implied)}) = {pct(ratio)} — tương quan không phù hợp")


# --------------------------------------------------------------------------- #
# [TN] Giá trị nguồn thu doanh nghiệp (mục 6)
# --------------------------------------------------------------------------- #
def income_estimate(financials: dict[str, Any], ownership_pct: float | None,
                    annual_lt_principal: float | None = None,
                    plan: dict[str, Any] | None = None,
                    industry: dict[str, Any] | None = None,
                    corp_group: str = "") -> dict[str, Any]:
    """Giá trị nguồn thu doanh nghiệp để đánh giá năng lực trả nợ.

    [TN] Không sử dụng phương án kinh doanh:
        LNST hợp lý          = LNST N-1 - DT tài chính N-1 - Thu nhập khác N-1
    [DP] [BRD 27/10] Sử dụng phương án kinh doanh (có PAKD, có ngành TCB, không Bad corp):
        DT dự phóng khả thi  = min[DT theo PAKD, DT năm N × (1 + tăng trưởng ngành × k)],
                               k = 1,5 với Good corp, 1 với nhóm còn lại
        ROS dự phóng khả thi = min{ROS theo PAKD, max[ROS lịch sử năm N, ROS ngành]}
        LNST dự phóng        = ROS dự phóng khả thi × DT dự phóng khả thi
    Then, in both cases:
        LNST trả nợ TDH      = Nghĩa vụ trả gốc TDH hằng năm - Khấu hao trong năm (≥ 0)
        Lợi tức tối đa KHCN  = (LNST hợp lý - LNST trả nợ TDH) × Tỷ lệ góp vốn

    "Năm N" = the latest full year with a BCTC in the dossier.
    """

    year = financials.get("latest_year")
    fig = financials["years"].get(year, {}) if year else {}
    lnst = fig.get("profit_after_tax")
    fin_income, other_income, dep = fig.get("financial_income"), fig.get("other_income"), fig.get("depreciation")
    missing, warnings = [], []
    if lnst is None:
        missing.append(f"LNST năm {year or 'N-1'}")
    if ownership_pct is None:
        missing.append("tỷ lệ góp vốn của KH vay (khai báo BORROWER_NAMES)")
    if fin_income is None:
        missing.append("DT tài chính (tính = 0)")
    if other_income is None:
        missing.append("thu nhập khác (tính = 0)")
    if dep is None:
        missing.append("khấu hao (tính = 0)")
    if annual_lt_principal is None:
        missing.append("nghĩa vụ trả gốc TDH hằng năm của DN (tính = 0)")
    historical = None if lnst is None else lnst - (fin_income or 0) - (other_income or 0)

    # [DP] projection from the business plan
    projection = None
    revenue = fig.get("net_revenue")
    ros_hist = (financials["ratios"].get(year) or {}).get("ros") if year else None
    if plan and plan.get("plan_revenue"):
        plan_rev, plan_lnst = plan.get("plan_revenue"), plan.get("plan_profit_after_tax")
        plan_ros = plan_lnst / plan_rev if plan_lnst is not None and plan_rev else None
        if revenue and plan_rev > revenue * (1 + PLAN_GROWTH_NEEDS_BASIS) and not (plan.get("basis") or "").strip():
            warnings.append(f"Doanh thu kế hoạch {fmt(plan_rev)} cao hơn {pct(plan_rev / revenue - 1)} so với năm "
                            f"{year} nhưng PAKD không ghi cơ sở tăng doanh thu — đề nghị bổ sung")
        if corp_group == "Bad corp":
            warnings.append("Bad corp — không thực hiện đánh giá dự phóng")
        elif not industry or industry.get("growth") is None:
            warnings.append("Chưa xác định ngành theo bảng ngành TCB (hoặc ngành chưa có tăng trưởng) — "
                            "chưa dự phóng được, dùng LNST hợp lý theo số liệu lịch sử")
        elif not revenue or plan_ros is None:
            warnings.append("Thiếu doanh thu năm gần nhất hoặc LNST kế hoạch — chưa dự phóng được")
        else:
            k = GOOD_CORP_GROWTH_FACTOR if corp_group == "Good corp" else 1.0
            cap = revenue * (1 + industry["growth"] * k)
            feasible_rev = min(plan_rev, cap)
            floor = max(x for x in (ros_hist, industry.get("ros")) if x is not None) \
                if any(x is not None for x in (ros_hist, industry.get("ros"))) else None
            feasible_ros = plan_ros if floor is None else min(plan_ros, floor)
            projection = {
                "plan_year": plan.get("plan_year"), "plan_revenue": plan_rev, "plan_ros": plan_ros,
                "industry": industry.get("name"), "industry_growth": industry["growth"],
                "industry_ros": industry.get("ros"), "growth_factor": k, "revenue_n": revenue,
                "revenue_cap": cap, "feasible_revenue": feasible_rev, "ros_hist": ros_hist,
                "feasible_ros": feasible_ros, "lnst": feasible_ros * feasible_rev,
            }
    reasonable = projection["lnst"] if projection else historical
    lt_use = max(0.0, (annual_lt_principal or 0) - (dep or 0))
    value = None
    if reasonable is not None and ownership_pct is not None:
        value = (reasonable - lt_use) * ownership_pct / 100
    return {"year": year, "lnst": lnst, "historical_lnst": historical, "reasonable_lnst": reasonable,
            "method": "du_phong" if projection else "lich_su", "projection": projection,
            "financial_income": fin_income, "other_income": other_income, "depreciation": dep,
            "annual_lt_principal": annual_lt_principal, "lnst_for_lt_debt": lt_use,
            "ownership_pct": ownership_pct, "value": value, "missing": missing, "warnings": warnings}


def sources_text(financials: dict[str, Any]) -> str:
    """[BRD 16/10] Nguồn: BCTC thuế hay kiểm toán; tờ khai VAT các quãng thời gian nào."""

    parts = ["; ".join(financials.get("sources") or []) or "Chưa có BCTC trong hồ sơ"]
    if (financials.get("vat") or {}).get("coverage"):
        parts.append(f"Tờ khai VAT: {financials['vat']['coverage']}")
    return "<br>".join(parts)


__all__ = ["compute", "income_estimate", "interest_vs_cic", "fmt", "pct", "sources_text", "SOURCE_LABELS"]
