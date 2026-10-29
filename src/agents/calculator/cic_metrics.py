"""[BRD 16/10] Phụ lục 01 mục 4 — dư nợ tại TCTD, chất lượng tín dụng, nhóm bureau.

Input: records of pass "cic" (cic_extraction.py — S10A and/or R20, line by line).
Everything here is arithmetic and date checks:

  [NG]  Ngày bản tin: chỉ chấp nhận S10A / R20 tra cứu trong 1 tháng tính đến
        thời điểm phân tích; cũ hơn → cảnh báo lấy lại.
  [DN]  Số dư cấp tín dụng: cộng các dòng S10A theo từng TCTD, tách TCB / TCTD khác.
        TSBĐ: tên, giá trị, chủ sở hữu từ R20.
        [BRD 27/10] ``lenders``: one row per TCTD (the template's table), TSBĐ by TCTD.
  [CL]  Nợ cần chú ý 12 tháng (phần 2.9), nợ xấu 5 năm (phần 2.7).
  [NB]  Phân nhóm bureau: Bad / Normal / Good bureau.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from src.agents.calculator.financial_metrics import fmt
from src.agents.calculator.legal_checks import parse_date
from src.utils.common import normalize_text

MAX_REPORT_AGE_DAYS = 31                   # [NG] "trong 1 tháng"
BAD_DEBT_LOOKBACK_DAYS = 730               # [NB] chính sách TCB: không nợ xấu 24 tháng
SPECIAL_MENTION_LOOKBACK_DAYS = 366        # [NB] không nợ cần chú ý 12 tháng
# [NB] Good bureau: dư nợ BQ 12 tháng / doanh thu BQ tháng không vượt ngưỡng theo loại hình.
DEBT_TO_MONTHLY_REVENUE_LIMIT = {
    "thuong_mai": 6, "san_xuat": 9, "dich_vu_xay_lap": 9, "dich_vu_khac": 6,
}
DEFAULT_LIMIT = 6                           # loại hình chưa xác định → ngưỡng chặt hơn
TCB_NAMES = ("techcombank", "ky thuong", "tcb")
LENDER_FIELDS = ("short_term", "long_term", "finance_lease", "other", "off_balance")


def _is_tcb(name: Any) -> bool:
    text = normalize_text(str(name or ""))
    return any(key in text.split() or key in text for key in TCB_NAMES)


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def compute(records: list[dict[str, Any]], as_of: date, revenue_prev_year: float | None,
            business_type: str = "") -> dict[str, Any]:
    cic = [r for r in records if r.get("pass") == "cic" and isinstance(r.get("data"), dict)]
    if not cic:
        return {"available": False, "group": "Chưa có CIC", "group_reason": "Hồ sơ chưa có bản tin CIC S10A/R20",
                "warnings": [], "rows": {}, "lenders": [], "card_late": [], "monthly": [], "query_dates": "", "special_mention": [], "bad_debt": [],
                "avg_balance_12m": None}

    warnings: list[str] = []
    # [NG] report dates
    dates = []
    for record in cic:
        data = record["data"]
        when = parse_date(data.get("query_date"))
        dates.append(f"{data.get('report_type') or 'CIC'}: {data.get('query_date') or 'không rõ ngày'}")
        if when is None:
            warnings.append(f"Không đọc được ngày tra cứu trên {record.get('document')} — kiểm tra lại bản tin")
        elif (as_of - when).days > MAX_REPORT_AGE_DAYS:
            warnings.append(f"Bản tin {data.get('report_type') or 'CIC'} tra cứu ngày {when:%d/%m/%Y}, quá 1 tháng "
                            f"tính đến {as_of:%d/%m/%Y} — đề nghị lấy lại dữ liệu CIC")

    # [Sửa 20/10] Một file PDF thường gộp cả S10A lẫn R20, LLM chỉ ghi một report_type →
    # R20 bị báo "chưa có". Bản tin nào có danh sách TSBĐ (collaterals) cũng tính là có R20;
    # bản tin nào có dư nợ theo TCTD (lenders) cũng tính là có S10A.
    def kind(r: dict) -> str:
        return str(r["data"].get("report_type") or "").upper()

    s10a = [r for r in cic if "R20" not in kind(r) or r["data"].get("lenders")]
    r20 = [r for r in cic if "R20" in kind(r) or r["data"].get("collaterals")]
    if not s10a:
        warnings.append("Chưa có bản tin S10A (dư nợ, nợ cần chú ý, nợ xấu)")
    if not r20:
        warnings.append("Chưa có bản tin R20 (tài sản bảo đảm)")

    # [DN] sum lines per bank group — latest S10A only (several prints of the same report)
    latest = max(s10a, key=lambda r: parse_date(r["data"].get("query_date")) or date.min) if s10a else None
    rows = {key: {f: 0.0 for f in LENDER_FIELDS} | {"collateral": 0.0, "owners": set()}
            for key in ("TCB", "OtherBank")}
    for lender in (latest["data"].get("lenders") if latest else []) or []:
        bucket = rows["TCB" if _is_tcb(lender.get("name")) else "OtherBank"]
        for field in LENDER_FIELDS:
            bucket[field] += _num(lender.get(field)) or 0.0
    for record in r20:
        for col in record["data"].get("collaterals") or []:
            bucket = rows["TCB" if _is_tcb(col.get("lender")) else "OtherBank"]
            bucket["collateral"] += _num(col.get("value")) or 0.0
            if col.get("owner"):
                bucket["owners"].add(str(col["owner"]))
    total = {f: rows["TCB"][f] + rows["OtherBank"][f] for f in (*LENDER_FIELDS, "collateral")}
    for bucket in (*rows.values(), total):
        # "Tổng số dư cấp tín dụng" = dư nợ NH + TDH + khác + cam kết ngoại bảng
        bucket["total"] = sum(bucket[f] for f in LENDER_FIELDS)
    rows["Total"] = total

    # [BRD 27/10] one row per TCTD: dư nợ NH, TDH, khác (+ cam kết ngoại bảng), tổng; TSBĐ of that TCTD.
    by_lender: dict[str, dict[str, Any]] = {}

    def lender_row(name: Any) -> dict[str, Any]:
        label = str(name or "TCTD không rõ tên").strip()
        return by_lender.setdefault(normalize_text(label), {
            "name": label, "short_term": 0.0, "long_term": 0.0, "finance_lease": 0.0, "other": 0.0,
            "off_balance": 0.0, "total": 0.0, "collaterals": [], "collateral_value": 0.0, "owners": []})

    # [BRD 29/10] "total" = dư nợ nội bảng (NH + DH + cho thuê TC + khác); cam kết ngoại bảng separate.
    for lender in (latest["data"].get("lenders") if latest else []) or []:
        row = lender_row(lender.get("name"))
        for field in ("short_term", "long_term", "finance_lease", "other", "off_balance"):
            row[field] += _num(lender.get(field)) or 0.0
        row["total"] = row["short_term"] + row["long_term"] + row["finance_lease"] + row["other"]
    for record in r20:
        for col in record["data"].get("collaterals") or []:
            row = lender_row(col.get("lender"))
            if col.get("name"):
                row["collaterals"].append(str(col["name"]))
            row["collateral_value"] += _num(col.get("value")) or 0.0
            if col.get("owner") and str(col["owner"]) not in row["owners"]:
                row["owners"].append(str(col["owner"]))

    # [CL] credit quality lists
    data = latest["data"] if latest else {}
    special = [s for s in data.get("special_mention_12m") or [] if isinstance(s, dict)]
    bad = [b for b in data.get("bad_debt_5y") or [] if isinstance(b, dict)]
    card_late = [c for c in data.get("card_late_payment_3y") or [] if isinstance(c, dict)]  # [BRD 27/10]
    # [BRD 29/10] monthly balances, oldest first — the chart beside the debt table
    monthly = [(str(m.get("month") or ""), _num(m.get("balance")))
               for m in data.get("monthly_balances_12m") or [] if isinstance(m, dict)]
    monthly = [(month, value) for month, value in monthly if value is not None]
    monthly.sort(key=lambda mv: parse_date("01/" + mv[0]) or date.min)
    balances = [value for _, value in monthly]
    avg_balance = sum(balances) / len(balances) if balances else None

    # [NB] bureau group
    def within(item: dict, days: int) -> bool:
        when = parse_date(item.get("date"), end_of_period=True)
        return when is None or as_of - timedelta(days=days) <= when   # undated → counted (conservative)

    bad_recent = [b for b in bad if within(b, BAD_DEBT_LOOKBACK_DAYS)]
    special_recent = [s for s in special if within(s, SPECIAL_MENTION_LOOKBACK_DAYS)]
    limit = DEBT_TO_MONTHLY_REVENUE_LIMIT.get(business_type, DEFAULT_LIMIT)
    leverage = (avg_balance / (revenue_prev_year / 12)) if avg_balance is not None and revenue_prev_year else None
    if not s10a:
        group, reason = "Chưa có CIC", "Thiếu bản tin S10A"
    elif bad_recent or special_recent:
        group = "Bad bureau"
        reason = ("Hit tiêu chí chính sách TCB: "
                  + "; ".join(x for x in (f"{len(bad_recent)} khoản nợ xấu trong 24 tháng" if bad_recent else "",
                                          f"{len(special_recent)} khoản nợ cần chú ý trong 12 tháng"
                                          if special_recent else "") if x))
    elif not bad and not card_late and leverage is not None and leverage <= limit:
        group = "Good bureau"
        reason = (f"Không chậm thanh toán thẻ 3 năm, không nợ xấu 5 năm; dư nợ BQ 12 tháng / DT BQ tháng = "
                  f"{leverage:.1f} ≤ {limit}"
                  + ("" if business_type else " (loại hình chưa xác định, dùng ngưỡng 6)")).replace(".", ",")
    else:
        group = "Normal bureau"
        reason = "Không thuộc Bad/Good bureau" + (
            f" (dư nợ BQ 12 tháng / DT BQ tháng = {leverage:.1f}, ngưỡng {limit})".replace(".", ",")
            if leverage is not None else " (thiếu diễn biến dư nợ 12 tháng hoặc doanh thu năm N-1)")
    return {"available": True, "group": group, "group_reason": reason, "warnings": warnings,
            "rows": rows, "lenders": list(by_lender.values()), "card_late": card_late, "monthly": monthly,
            "query_dates": "; ".join(dates), "special_mention": special, "bad_debt": bad,
            "avg_balance_12m": avg_balance, "leverage": leverage, "limit": limit, "has_r20": bool(r20)}


def describe_items(items: list[dict[str, Any]], kind: str) -> str:
    """One line per debt item, or the 'none' sentence."""

    if not items:
        return f"Không có {kind}"
    lines = []
    for item in items:
        bits = [item.get("lender") or "", item.get("date") or "", item.get("debt_group") or ""]
        amount = _num(item.get("amount"))
        lines.append("- " + ", ".join(b for b in bits if b) + (f": {fmt(amount)} triệu đồng" if amount else ""))
    return "\n".join(lines)
