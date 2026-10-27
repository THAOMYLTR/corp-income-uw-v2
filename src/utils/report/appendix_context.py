"""Cells of "Thẩm định nguồn thu doanh nghiệp" (Appendix - Corp income) filled in code.

Rule of thumb: a FACT read off a document, a NUMBER, a CHECK or a GROUP is filled
here (same input → same report). Only what needs reading free text and judging
it — products / services, addresses, the business-activity comment and the
wording of the conclusion — is left to the report writer LLM, which sees every
value below so its text cannot contradict them.

Sections follow the BRD of 27/10/2026 (tag [BRD 27/10]; older rules [BRD 16/10]):
  1. a: source priority per field (ĐKKD → Điều lệ / Sổ cổ đông → thực địa), T24 ID,
        "Đăng ký lần đầu … thay đổi lần thứ …", status bold red when not operating.
     b: members table; one legal comment (years operating, borrower %, NĐDPL, warnings).
  2. Mô hình HĐKD — 5-tier diagram (calculator/business_model.py).
  3. Tài chính: table in triệu đồng, VAT update, comment draft, finance group.
  4. Dư nợ tại TCTD: one row per TCTD, credit quality, bureau group (cic_metrics.py).
  5. Kết luận: business-plan table (hidden without a plan), corp group, income value.
"""

from __future__ import annotations

import html
import os
import re
from datetime import date
from typing import Any

from src.agents.calculator import business_model, cic_metrics
from src.agents.calculator import financial_metrics as fm
from src.agents.calculator.legal_checks import norm_person, parse_date, within_lookback

NO_INFO = "Chưa có thông tin"

# [BRD 16/10] Phân nhóm finance / bureau / corp is "chỉ hiển thị khi POC, không khuyến
# khích hiển thị tại credit memo ver final". Set CORP_INCOME_SHOW_GROUPS=0 to hide.
SHOW_GROUPS = os.getenv("CORP_INCOME_SHOW_GROUPS", "1") != "0"

# [BRD 16/10] 1.1: "ưu tiên ĐKKD, sau đó Điều lệ / Sổ cổ đông / Báo cáo khảo sát thực địa".
LEGAL_DOC_PRIORITY = ("gcn_dkdn", "dieu_le", "so_dang_ky_co_dong", "bao_cao_thuc_dia",
                      "bao_cao_thuc_dia_phap_ly")
NOT_OPERATING = ("tam_ngung", "ngung_hoat_dong", "giai_the", "pha_san")
NOT_OPERATING_LABELS = ("Tạm ngừng hoạt động", "Ngừng hoạt động", "Giải thể", "Phá sản")
# Finding codes (legal_checks.py) that mean "thông tin pháp lý không phù hợp".
LEGAL_MISMATCH_CODES = ("tax_code_mismatch", "name_mismatch", "address_mismatch",
                        "establishment_mismatch", "rep_mismatch")

# Template prefix → field of financial_metrics (figures) or ratio name.
FIGURE_PREFIXES = {
    "TongTaiSan": "total_assets", "TSNH": "current_assets", "TSDH": "non_current_assets",
    "TongNguonVon": "total_capital", "NoPhaiTra": "total_liabilities", "VCSH": "equity",
    "DTT": "net_revenue", "GVHB": "cogs", "LNG": "gross_profit", "DTTC": "financial_income",
    "CPTC": "financial_expenses", "CPQL": "admin_expenses", "CPBH": "selling_expenses",
    "LNThuan": "operating_profit", "LNTT": "profit_before_tax", "LNST": "profit_after_tax",
}
RATIO_PREFIXES = {"BienDongDT": "revenue_growth", "ROS": "ros", "CurrentRatio": "current_ratio"}
FINANCIAL_NAME = re.compile(
    r"^(" + "|".join(sorted({**FIGURE_PREFIXES, **RATIO_PREFIXES}, key=len, reverse=True))
    + r")(\d{4}|Current|N-1|N-2|N1|N2)$"
)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _summary_value(items: dict, field: str) -> Any:
    for entry in items[1]["summary"].values():
        if entry.get("field") == field:
            return entry.get("value")
    return None


def _pick_by_document(records: list[dict], field: str) -> tuple[Any, str]:
    """[BRD 16/10] First non-empty value following LEGAL_DOC_PRIORITY, then any other document."""

    order = {t: i for i, t in enumerate(LEGAL_DOC_PRIORITY)}
    legal = [r for r in records if r.get("pass") == "legal_basic"]
    for record in sorted(legal, key=lambda r: order.get(r.get("document_type"), 50)):
        value = record["data"].get(field)
        if value not in (None, "", [], {}):
            if isinstance(value, list):
                value = ", ".join(str(v.get("name") if isinstance(v, dict) else v) for v in value)
            return value, record.get("document", "")
    return None, ""


def _codes(items: dict, *numbers: int) -> dict[str, dict]:
    return {f["code"]: f for n in numbers for f in items[n]["findings"]}


def _relations(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Relations between members; [BRD 16/10] the field report (thực địa) first."""

    found: dict[str, list[str]] = {}
    shareholders = [r for r in records if r.get("pass") == "shareholders"]
    shareholders.sort(key=lambda r: 0 if r.get("source") == "field" else 1)
    for record in shareholders:
        for rel in record["data"].get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            relation = rel.get("relation") or "có quan hệ"
            a, b = rel.get("member_a"), rel.get("member_b")
            # "member_a is <relation> of member_b": each row reads from its own person.
            for me, text in ((a, f"{relation} của {b or '?'}"), (b, f"{a or '?'} là {relation}")):
                if me and text not in found.setdefault(norm_person(me), []):
                    found[norm_person(me)].append(text)
    return found


def _ratio_text(name: str, value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}".replace(".", ",") if name == "current_ratio" else fm.pct(value)


def _age(founded: date | None, as_of: date) -> str:
    if not founded:
        return ""
    months = (as_of.year - founded.year) * 12 + as_of.month - founded.month - (as_of.day < founded.day)
    return f"{months // 12} năm {months % 12} tháng" if months >= 0 else ""


def borrower_ownership(items: dict, borrower_names: list[str]) -> float | None:
    """Total % the individual borrower(s) hold, when printed or computed."""

    total, found = 0.0, False
    for row in items[2]["summary"].get("borrowers") or []:
        if row.get("ownership_pct") is not None:
            total += float(row["ownership_pct"])
            found = True
    return total if found else None


def business_type(records: list[dict]) -> tuple[str, str]:
    """[BRD 16/10] Loại hình chính (field report / internal first) for the bureau threshold."""

    ranked = sorted((r for r in records if r.get("pass") == "legal_basic"),
                    key=lambda r: {"field": 0, "internal": 1}.get(r.get("source"), 2))
    for record in ranked:
        if record["data"].get("business_type"):
            return record["data"]["business_type"], record["data"].get("business_type_note") or ""
    return "", ""


# --------------------------------------------------------------------------- #
# corp group — mục 5 "Phân nhóm doanh nghiệp"
# --------------------------------------------------------------------------- #
def corp_group(items: dict, financials: dict, cic: dict, as_of: date) -> dict[str, Any]:
    """Bad corp if ANY criterion; Good corp if Good finance AND Good bureau; else Normal."""

    codes = _codes(items, 1)
    bad: list[str] = []
    if "status_not_active" in codes:
        bad.append("Pháp lý: " + codes["status_not_active"]["message"])
    for code in LEGAL_MISMATCH_CODES:
        if code in codes and codes[code]["severity"] == "alert":
            bad.append("Pháp lý: " + codes[code]["message"])
    founded = parse_date(_summary_value(items, "establishment_date"))
    if founded and (as_of - founded).days < 365:
        bad.append(f"Pháp lý: thời gian thành lập dưới 12 tháng (thành lập {founded:%d/%m/%Y})")
    if "site_not_operating" in codes:
        bad.append("Hoạt động kinh doanh: " + codes["site_not_operating"]["message"])
    if financials["group"] == "Bad finance":
        bad.append("Tài chính: thuộc nhóm Bad finance — " + financials["group_reason"])
    if cic["group"] == "Bad bureau":
        bad.append("Tín dụng: thuộc nhóm Bad bureau — " + cic["group_reason"])
    if bad:
        group = "Bad corp"
    elif financials["group"] == "Good finance" and cic["group"] == "Good bureau":
        group = "Good corp"
    else:
        group = "Normal corp"
    return {"group": group, "bad_reasons": bad,
            "finance": f"{financials['group']} ({financials['group_reason']})",
            "bureau": f"{cic['group']} ({cic['group_reason']})"}


# --------------------------------------------------------------------------- #
# small table builders
# --------------------------------------------------------------------------- #
def _pipe_row(values: list[Any]) -> str:
    """One row of a Markdown table: no "|" or line break inside a cell."""

    def cell(value: Any) -> str:
        return str("—" if value is None else value).replace("|", "/").replace("\n", "<br>")
    return "| " + " | ".join(cell(v) for v in values) + " |"


def _html_row(values: list[Any]) -> str:
    def cell(value: Any) -> str:
        return html.escape(str("—" if value is None else value)).replace("\n", "<br>")
    return "<tr>" + "".join(f"<td>{cell(v)}</td>" for v in values) + "</tr>"


def _group_marks(prefix: str, groups: tuple[str, str, str], chosen: str, reason: str) -> dict[str, str]:
    """"Kết quả" column of a POC table: ✔ + basis on the group that applies, empty elsewhere."""

    marks = {f"{prefix}_{i}": "" for i in (1, 2, 3)}
    if chosen in groups:
        marks[f"{prefix}_{groups.index(chosen) + 1}"] = f"✔ {reason}"
    elif chosen:
        marks[f"{prefix}_2"] = f"Chưa phân nhóm — {chosen}: {reason}"
    return marks


def pick_plan(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The customer's business plan: the first document with planned revenue."""

    plans = [r["data"] for r in records if r.get("pass") == "plan" and r["data"].get("has_plan")]
    plans.sort(key=lambda p: 0 if p.get("plan_revenue") else 1)
    return plans[0] if plans else None


# --------------------------------------------------------------------------- #
# main builder
# --------------------------------------------------------------------------- #
def build_appendix_context(result: dict[str, Any], records: list[dict[str, Any]],
                           financials: dict[str, Any], as_of: date,
                           cic: dict[str, Any] | None = None,
                           corp: dict[str, Any] | None = None,
                           income: dict[str, Any] | None = None) -> dict[str, str]:
    items = result["items"]
    borrower_names = result["meta"]["borrower_names"]
    borrowers = {norm_person(n) for n in borrower_names}
    codes = _codes(items, 1, 2, 3)
    ctx: dict[str, str] = {}

    # ---- 1a. Thông tin cơ bản ----------------------------------------------------
    def legal_cell(field: str, mismatch_code: str = "") -> str:
        value, _ = _pick_by_document(records, field)
        value = value or _summary_value(items, field)
        if not value:
            return NO_INFO
        mark = " ⚠ không khớp giữa các nguồn" if mismatch_code in codes else ""
        return f"{value}{mark}"

    company, _ = _pick_by_document(records, "company_name")
    company = company or _summary_value(items, "company_name") or "Doanh nghiệp"
    ctx["TenDoanhNghiep"] = legal_cell("company_name", "name_mismatch")
    ctx["MST"] = legal_cell("tax_code", "tax_code_mismatch")
    ctx["NguoiDaiDien"] = legal_cell("legal_representatives", "rep_mismatch")
    t24, _ = _pick_by_document(records, "t24_id")
    ctx["T24ID"] = str(t24) if t24 else "Chưa có thông tin (tra cứu MST trên T24)"
    founded_text, _ = _pick_by_document(records, "establishment_date")
    founded_text = founded_text or _summary_value(items, "establishment_date")
    founded = parse_date(founded_text)
    number, _ = _pick_by_document(records, "registration_change_number")
    latest, _ = _pick_by_document(records, "latest_change_date")
    note = "; ".join(x for x in (
        f"Đăng ký lần đầu {founded_text}" if founded_text else "",
        "thay đổi lần thứ " + " ".join(y for y in (str(number) if number not in (None, "") else "",
                                                   f"ngày {latest}" if latest else "") if y)
        if number not in (None, "") or latest else "") if x)
    ctx["NamThanhLap"] = (f"{founded.year} ({note})" if founded else note or NO_INFO) + (
        " ⚠ không khớp giữa các nguồn" if "establishment_mismatch" in codes else "")
    status = _summary_value(items, "operating_status")
    if not status:
        ctx["TinhTrangHoatDong"] = "Chưa có kết quả tra cứu (masothue.com / Cổng ĐKDN)"
    elif status in NOT_OPERATING_LABELS or "status_not_active" in codes:
        # "Bôi đỏ, đậm nếu doanh nghiệp không hoạt động / tạm dừng hoạt động"
        ctx["TinhTrangHoatDong"] = f'<b><span style="color:#C00000">{status}</span></b>'
    else:
        ctx["TinhTrangHoatDong"] = str(status)

    # ---- 1b. Thành viên góp vốn & người đại diện theo pháp luật ---------------------
    reps = {norm_person(r.get("name")): r for r in items[3]["summary"].get("legal_representatives", [])}
    relations = _relations(records)
    member_rows = []
    for member in items[2]["summary"].get("members", []):
        key = norm_person(member.get("name"))
        relation = ["Khách hàng vay vốn"] if key in borrowers else []
        if key in reps:
            relation.append("Người đại diện theo pháp luật")
        relation += relations.get(key, [])
        pct = member.get("ownership_pct")
        changes = []
        if within_lookback(member.get("acquisition_date"), as_of):
            changes.append(f"Có — nhận vốn góp ngày {member['acquisition_date']}")
        rep = reps.get(key)
        if rep and within_lookback(rep.get("appointed_date"), as_of):
            changes.append(f"Có — bổ nhiệm NĐDPL ngày {rep['appointed_date']}")
        member_rows.append([
            member.get("name") or NO_INFO,
            "; ".join(relation) or "—",
            "—" if pct is None else f"{float(pct):.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%",
            "; ".join(changes) or "Không",
        ])
    # A legal representative who holds no capital is still listed (the table is "… & NĐDPL").
    member_keys = {norm_person(row[0]) for row in member_rows}
    for key, rep in reps.items():
        if key and key not in member_keys:
            changed = within_lookback(rep.get("appointed_date"), as_of)
            member_rows.append([rep.get("name"), "Người đại diện theo pháp luật (không góp vốn)", "—",
                                f"Có — bổ nhiệm NĐDPL ngày {rep['appointed_date']}" if changed else "Không"])
    # Data rows under the table header written in the template.
    ctx["RowsThanhVien"] = "\n".join(_pipe_row(r) for r in member_rows or [[NO_INFO, "—", "—", "—"]])

    # ---- Nhận xét về pháp lý Khách hàng (one cell in the BRD of 27/10) --------------
    lines = []
    age = _age(founded, as_of)
    if age:
        lines.append(f"Doanh nghiệp đã hoạt động {age} (đăng ký lần đầu {founded:%d/%m/%Y}).")
    if borrower_names:
        pct = borrower_ownership(items, borrower_names)
        is_rep = any(norm_person(n) in reps for n in borrower_names)
        lines.append(f"KH cá nhân vay vốn {', '.join(borrower_names)} nắm giữ "
                     + (f"{pct:g}% vốn góp".replace(".", ",") if pct is not None else "tỷ lệ vốn góp chưa xác định")
                     + f"; {'là' if is_rep else 'không phải là'} người đại diện theo pháp luật của doanh nghiệp"
                     + (f" ({result['meta']['borrower_source']})." if result["meta"].get("borrower_source") else "."))
    else:
        lines.append("Chưa xác định được KH cá nhân vay vốn: hồ sơ vay vốn (giấy đề nghị vay / tờ trình) không nêu tên "
                     "thành viên góp vốn hoặc người đại diện nào — kiểm tra lại hồ sơ, hoặc khai báo BORROWER_NAMES.")
    warn = [codes[c]["message"] for c in LEGAL_MISMATCH_CODES if c in codes]
    warn += [codes[c]["message"] for c in ("status_not_active", "status_unknown") if c in codes]
    warn += [f["message"] for f in items[2]["findings"]
             if f["code"] in ("ownership_not_100", "ownership_incomplete", "capital_sum_mismatch")]
    warn += [f["message"] for n in (1, 2, 3) for f in items[n]["findings"]
             if f["severity"] == "alert" and f["message"] not in warn]
    if warn:
        lines.append("Cảnh báo pháp lý cần đánh giá lại:")
        lines += [f"  + {w}" for w in warn]
    ctx["NhanXet"] = "\n".join(line if line.startswith(" ") else f"- {line}" for line in lines) or NO_INFO

    # ---- 2. Mô hình HĐKD [BRD 27/10] ------------------------------------------------
    ctx["MoHinhHDKD"] = (business_model.diagram(str(company), records)
                         or "Chưa có thông tin đối tác đầu vào / đầu ra trong hồ sơ")

    # ---- 3. Tài chính ---------------------------------------------------------------
    ctx["NguonTaiChinh"] = fm.sources_text(financials)
    interim = financials.get("interim") or {}
    vat = financials.get("vat") or {}
    ctx["NamHienTai"] = (str(vat["current_year"]) if vat.get("current_year")
                         else interim.get("period") or str(as_of.year))
    for name, field in FIGURE_PREFIXES.items():
        for label, fig in financials["years"].items():
            ctx[f"{name}{label}"] = fm.fmt(fig.get(field))
    for name, ratio in RATIO_PREFIXES.items():
        for label, values in financials["ratios"].items():
            ctx[f"{name}{label}"] = _ratio_text(ratio, values.get(ratio))
    # "Cập nhật các tháng năm N": Nguyên tắc 2 — doanh thu theo tờ khai VAT, % doanh thu năm N-1.
    if vat.get("text"):
        ctx["DTTCurrent"] = vat["text"]
    elif interim.get("net_revenue") is not None:
        ctx["DTTCurrent"] = f"{fm.fmt(interim['net_revenue'])} (BCTC {interim.get('period') or 'giữa niên độ'})"
    else:
        ctx["DTTCurrent"] = "—"

    # Relative years: N-1 = latest full year with a BCTC (else the year before the loan
    # date), N-2 = the year before it. Cells: {{DTTN-1}}, {{TongTaiSanN-2}}, {{ROSN-1}} …
    n1 = financials.get("latest_year") or str(as_of.year - 1)
    n2 = str(int(n1) - 1)
    ctx["Nam-1"], ctx["Nam-2"] = n1, n2
    for prefix in (*FIGURE_PREFIXES, *RATIO_PREFIXES):
        for alias, year in (("N-1", n1), ("N-2", n2), ("N1", n1), ("N2", n2)):
            ctx[f"{prefix}{alias}"] = ctx.get(f"{prefix}{year}", "—")

    cic = cic or {"available": False}
    fin_lines = ["**Cảnh báo dấu hiệu bất thường của BCTC**"]
    fin_lines += [f"- ⚠ {w}" for w in financials["material_warnings"]] or ["- Không ghi nhận mâu thuẫn trọng yếu"]
    fin_lines += [f"- {w}" for w in financials["other_warnings"]]
    interest = fm.interest_vs_cic(financials, cic.get("avg_balance_12m"))
    if interest:                      # "tương quan chi phí lãi vay và diễn biến dư nợ theo CIC"
        fin_lines.append(f"- ⚠ {interest}")
    derived = {f for fig in financials["years"].values() for f in fig.get("_derived", [])}
    if {"current_assets", "current_liabilities"} & derived:   # only the TT133 derivation
        fin_lines.append("- Ghi chú: BCTC không chia ngắn hạn/dài hạn (TT133) — TSNH/TSDH/nợ ngắn hạn được tính "
                         "theo Nguyên tắc 1")
    fin_lines.append("\n**Nhận xét về trạng thái tài chính của KH**")
    fin_lines += [f"- {x}" for x in financials["status_remarks"]] or ["- Chưa có BCTC để đánh giá"]
    if vat.get("text"):
        fin_lines.append(f"- {vat['text']}")
    ctx["NhanXetTaiChinh"] = "\n".join(fin_lines)
    ctx.update(_group_marks("KQ_TaiChinh", ("Bad finance", "Normal finance", "Good finance"),
                            financials["group"], financials["group_reason"]))

    # ---- 4. Dư nợ tại TCTD ----------------------------------------------------------
    if cic.get("available"):
        ctx["NgayDuLieuCIC"] = cic["query_dates"] + "".join(f"\n\n⚠ {w}" for w in cic["warnings"])
        rows = []
        for lender in cic.get("lenders") or []:
            rows.append([lender["name"], fm.fmt(lender["short_term"]), fm.fmt(lender["long_term"]),
                         fm.fmt(lender["other"]), fm.fmt(lender["total"]),
                         "; ".join(lender["collaterals"]) or "—",
                         fm.fmt(lender["collateral_value"]) if lender["collaterals"] or lender["collateral_value"]
                         else "—",
                         ", ".join(lender["owners"]) or "—"])
        total = cic["rows"]["Total"]
        rows.append(["Tổng tại các TCTD", fm.fmt(total["short_term"]), fm.fmt(total["long_term"]),
                     fm.fmt(total["other"] + total["off_balance"]), fm.fmt(total["total"]), "",
                     fm.fmt(total["collateral"]) if cic.get("has_r20") else "—", ""])  # no R20 → unknown, not 0
        ctx["RowsDuNoTCTD"] = "\n".join(_html_row(r) for r in rows)
        ctx["SpecialMention"] = cic_metrics.describe_items(cic["special_mention"],
                                                           "nợ cần chú ý trong 12 tháng gần nhất")
        ctx["BadDebt"] = cic_metrics.describe_items(cic["bad_debt"], "nợ xấu trong 05 năm gần nhất")
        reason = cic["group_reason"]
        if cic.get("leverage") is not None and "Dư nợ BQ" not in reason and "dư nợ BQ" not in reason:
            reason += f" (dư nợ BQ 12 tháng / doanh thu BQ tháng = {cic['leverage']:.1f}, ngưỡng {cic['limit']})" \
                .replace(".", ",")
    else:
        missing = "Chưa có bản tin CIC S10A/R20 trong hồ sơ"
        reason = cic.get("group_reason", missing)
        ctx.update({"NgayDuLieuCIC": missing, "SpecialMention": missing, "BadDebt": missing,
                    "RowsDuNoTCTD": _html_row([missing, "—", "—", "—", "—", "—", "—", "—"])})
    ctx.update(_group_marks("KQ_Bureau", ("Bad bureau", "Normal bureau", "Good bureau"),
                            cic.get("group", "Chưa có CIC"), reason))

    # ---- 5. Kết luận: phương án kinh doanh, phân nhóm, giá trị nguồn thu ------------
    plan = pick_plan(records)
    ctx.update(plan_cells(plan, financials, n1))
    if corp:
        ctx.update(_group_marks(
            "KQ_DoanhNghiep", ("Bad corp", "Normal corp", "Good corp"), corp["group"],
            "; ".join(corp["bad_reasons"]) if corp["bad_reasons"]
            else f"tài chính: {corp['finance']}; tín dụng: {corp['bureau']}"))
    if corp and income is not None:
        ctx["KetLuan"] = income_block(corp, income)
    return ctx


def plan_cells(plan: dict[str, Any] | None, financials: dict[str, Any], n1: str) -> dict[str, str]:
    """[BRD 27/10] Cells of the table "Phương án kinh doanh (nếu có)" that are not history.

    History columns (N-2, N-1) reuse the cells of mục 3 ("= giá trị cùng kỳ tại phần 3").
    "Cập nhật năm T" = doanh thu theo tờ khai VAT; "Năm kế hoạch" = the plan; growth of the
    plan = DT kế hoạch / DT năm N-1 − 1; ROS of the plan = LNST kế hoạch / DT kế hoạch.
    ``_has_plan`` / ``_plan_basis`` drive apply_output_conditions (hide table / column).
    """

    if not plan:
        return {"_has_plan": "", "_plan_basis": "", "PAKD_NamKeHoach": "", "PAKD_DTT_CapNhat": "",
                "PAKD_DTT_KeHoach": "", "PAKD_TangTruong_KeHoach": "", "PAKD_LNST_KeHoach": "",
                "PAKD_ROS_KeHoach": "", "PAKD_DTT_CoSo": ""}
    vat = financials.get("vat") or {}
    vat_now = (vat.get("by_year") or {}).get(vat.get("current_year")) if vat.get("current_year") else None
    prev_revenue = (financials["years"].get(n1) or {}).get("net_revenue")
    revenue, profit = plan.get("plan_revenue"), plan.get("plan_profit_after_tax")
    basis = " ".join(str(plan.get("basis") or "").split())
    return {
        "_has_plan": "1",
        "_plan_basis": "1" if basis else "",
        "PAKD_NamKeHoach": str(plan.get("plan_year") or ""),
        "PAKD_DTT_CapNhat": (f"{fm.fmt(vat_now['revenue'])} (tờ khai VAT đến T{max(vat_now['months']):02d}/"
                             f"{vat['current_year']})" if vat_now else ""),
        "PAKD_DTT_KeHoach": fm.fmt(revenue),
        "PAKD_TangTruong_KeHoach": fm.pct(revenue / prev_revenue - 1) if revenue and prev_revenue else "—",
        "PAKD_LNST_KeHoach": fm.fmt(profit),
        "PAKD_ROS_KeHoach": fm.pct(profit / revenue) if profit is not None and revenue else "—",
        "PAKD_DTT_CoSo": basis,
    }


def income_block(corp: dict[str, Any], income: dict[str, Any]) -> str:
    """"Giá trị nguồn thu doanh nghiệp để đánh giá năng lực trả nợ" (formulas of the BRD)."""

    lines = ["**Giá trị nguồn thu doanh nghiệp để đánh giá năng lực trả nợ**", ""]
    if corp["group"] == "Bad corp":
        lines += ["Không sử dụng nguồn thu doanh nghiệp, không thực hiện đánh giá dự phóng. Cơ sở:"]
        lines += [f"- {r}" for r in corp["bad_reasons"]]
        return "\n".join(lines)
    year = income.get("year") or "N-1"
    proj = income.get("projection")
    if proj:
        k = f" × {proj['growth_factor']:g}".replace(".", ",") if proj["growth_factor"] != 1 else ""
        lines += [
            "_Sử dụng phương án kinh doanh (ngành TCB: "
            f"{proj['industry']}, tăng trưởng ngành {fm.pct(proj['industry_growth'])}, ROS ngành "
            f"{fm.pct(proj['industry_ros'])})_",
            f"- Doanh thu dự phóng khả thi = min[DT theo PAKD; DT {year} × (1 + tăng trưởng ngành{k})] = "
            f"min[{fm.fmt(proj['plan_revenue'])}; {fm.fmt(proj['revenue_n'])} × (1 + "
            f"{fm.pct(proj['industry_growth'])}{k})] = **{fm.fmt(proj['feasible_revenue'])}** triệu đồng",
            f"- Tỷ suất lợi nhuận dự phóng khả thi = min{{ROS PAKD; max[ROS {year}; ROS ngành]}} = "
            f"min{{{fm.pct(proj['plan_ros'])}; max[{fm.pct(proj['ros_hist'])}; {fm.pct(proj['industry_ros'])}]}} = "
            f"**{fm.pct(proj['feasible_ros'])}**",
            f"- Lợi nhuận dự phóng khả thi = {fm.pct(proj['feasible_ros'])} × {fm.fmt(proj['feasible_revenue'])} = "
            f"**{fm.fmt(proj['lnst'])}** triệu đồng",
        ]
    else:
        lines += [
            f"- LNST hợp lý của doanh nghiệp = LNST {year} − DT tài chính − Thu nhập khác = "
            f"{fm.fmt(income['lnst'])} − {fm.fmt(income['financial_income'] or 0)} − "
            f"{fm.fmt(income['other_income'] or 0)} = **{fm.fmt(income['reasonable_lnst'])}** triệu đồng",
        ]
    lines += [
        f"- LNST sử dụng để trả nghĩa vụ TDH doanh nghiệp = Nghĩa vụ trả gốc TDH hằng năm − Khấu hao trong năm = "
        f"{fm.fmt(income['annual_lt_principal'] or 0)} − {fm.fmt(income['depreciation'] or 0)} → "
        f"**{fm.fmt(income['lnst_for_lt_debt'])}** triệu đồng (không âm)",
        "- Lợi tức / cổ tức tối đa chia được cho KHCN = (LNST hợp lý − LNST trả nợ TDH) × tỷ lệ góp vốn"
        + (f" = ({fm.fmt(income['reasonable_lnst'])} − {fm.fmt(income['lnst_for_lt_debt'])}) × "
           + f"{income['ownership_pct']:g}%".replace(".", ",") + f" = **{fm.fmt(income['value'])}** triệu đồng"
           if income["value"] is not None else ": chưa tính được"),
    ]
    lines += [f"- ⚠ {w}" for w in income.get("warnings") or []]
    if income["missing"]:
        lines.append(f"- Thiếu dữ liệu: {'; '.join(income['missing'])}")
    return "\n".join(lines)


def fill_missing_financial_names(names: set[str], ctx: dict[str, str]) -> None:
    """A financial cell for a year with no statement is "—", not a question for the LLM."""

    for name in names:
        if name not in ctx and FINANCIAL_NAME.match(name):
            ctx[name] = "—"


# --------------------------------------------------------------------------- #
# "Hiển thị khi …" rules, applied to the rendered report
# --------------------------------------------------------------------------- #
_PAKD_TABLE = re.compile(r'<table id="pakd">.*?</table>\n?', re.S)
_COSO_CELL = re.compile(r'<t[hd] class="coso">.*?</t[hd]>')
_POC_TABLE = re.compile(r'<table class="poc">.*?</table>\n?', re.S)


def apply_output_conditions(markdown: str, ctx: dict[str, str]) -> str:
    """- No business plan → hide the plan table ("TH không có PAKD, ẩn đi bảng tính này").
    - The plan states no basis → hide the "Cơ sở của Khách hàng" column.
    - CORP_INCOME_SHOW_GROUPS=0 → hide the "Phân nhóm … (POC)" tables.
    """

    if not ctx.get("_has_plan"):
        markdown = _PAKD_TABLE.sub("", markdown)
    elif not ctx.get("_plan_basis"):
        markdown = _COSO_CELL.sub("", markdown)
    if not SHOW_GROUPS:
        markdown = _POC_TABLE.sub("", markdown)
    return markdown
