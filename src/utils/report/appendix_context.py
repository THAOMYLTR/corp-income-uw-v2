"""Cells of "Thẩm định nguồn thu doanh nghiệp" filled in code — BRD 29/10/2026 template.

Rule of thumb: a FACT read off a document, a NUMBER, a CHECK or a GROUP is filled here
(same input → same report). Only what needs reading free text — products / services,
addresses, the business-activity warning and the wording of the conclusion — is left to the
report writer LLM, which sees every value below so its text cannot contradict them.

Sections (search the "# ---- " markers):
  1a. ĐKKD → Điều lệ / Sổ cổ đông → thực địa; T24; "Đăng ký lần đầu … thay đổi lần thứ …";
      status bold red when not operating.
  1b. Members & management: % (sổ cổ đông → điều lệ); chức vụ, quan hệ với KH vay, mức độ ảnh
      hưởng, đánh giá năng lực from the site-visit report. Warnings only when there are some.
  2.  Mô hình HĐKD diagram (calculator/business_model.py).
  3.  a. Cơ cấu tài sản (lines ≥ 20%) + one comment; b. quy mô, tăng trưởng (+x% / -x%), chỉ số.
  4.  Debt table by TCTD + monthly chart (utils/report/visualization/debt_chart.py).
  5.  Dự phóng kinh doanh (PAKD, bảng ngành TCB) and the value of the corporate income.
"""

from __future__ import annotations

import html
import os
import re
from datetime import date
from typing import Any

from src.agents.calculator import business_model, cic_metrics
from src.utils.report.visualization.debt_chart import debt_chart
from src.agents.calculator import financial_metrics as fm
from src.agents.calculator.legal_checks import norm_person, parse_date
from src.agents.documents.document_matrix import get_type
from src.utils.common import normalize_text

NO_INFO = "Chưa có thông tin"


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


# [BRD 27/10] Short names of the documents, for "không khớp ở bộ hồ sơ nào" in the legal comment.
DOC_SHORT = {
    "gcn_dkdn": "ĐKKD", "dieu_le": "Điều lệ", "so_dang_ky_co_dong": "Sổ cổ đông",
    "chuyen_nhuong_von": "HĐ chuyển nhượng vốn", "quyet_dinh_bo_nhiem": "QĐ bổ nhiệm",
    "tra_cuu_dkdn": "Tra cứu thuế/ĐKDN", "du_lieu_noi_bo": "Dữ liệu nội bộ",
    "bao_cao_thuc_dia": "Báo cáo thực địa", "bao_cao_thuc_dia_phap_ly": "Báo cáo thực địa",
    "internal_data": "Dữ liệu nội bộ", "external_data": "Tra cứu bên ngoài",
}
# mismatch code → (pass, field) whose values differ
MISMATCH_FIELDS = {
    "tax_code_mismatch": ("legal_basic", "tax_code"), "name_mismatch": ("legal_basic", "company_name"),
    "address_mismatch": ("legal_basic", "head_office_address"),
    "establishment_mismatch": ("legal_basic", "establishment_date"),
    "rep_mismatch": ("legal_basic", "legal_representatives"),
}


def _doc_short(record: dict) -> str:
    kind = record.get("document_type") or ""
    doc = get_type(kind)
    return DOC_SHORT.get(kind) or (doc.short_label if doc else "") or record.get("document") or "?"


def _where_differs(records: list[dict], code: str) -> str:
    """'0101234567 (ĐKKD, Điều lệ) ≠ 0109999999 (Tra cứu thuế/ĐKDN)' — no file names, no folders."""

    pass_name, field = MISMATCH_FIELDS[code]
    groups: dict[str, tuple[str, list[str]]] = {}
    for record in records:
        if record.get("pass") not in (pass_name, "legal_rep" if field == "legal_representatives" else ""):
            continue
        value = record["data"].get(field)
        if isinstance(value, list):
            value = ", ".join(str(v.get("name") if isinstance(v, dict) else v) for v in value if v)
        if value in (None, ""):
            continue
        key = (norm_person if field == "legal_representatives" else normalize_text)(str(value))
        shown, docs = groups.setdefault(key, (str(value), []))
        if _doc_short(record) not in docs:
            docs.append(_doc_short(record))
    return " ≠ ".join(f"{shown} ({', '.join(docs)})" for shown, docs in groups.values()) if len(groups) > 1 else ""


def _codes(items: dict, *numbers: int) -> dict[str, dict]:
    return {f["code"]: f for n in numbers for f in items[n]["findings"]}


def _relations(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Relations between members — ONE phrase per pair of people on each person's row.

    Documents often state the same pair both ways ("A là vợ của B", "B là chồng của A").
    For the row of person P and another person Q the phrase is, in this order of preference:
      1. "<quan hệ> của Q"  — a document says what P is to Q (P = member_a), e.g. "vợ của B";
      2. "Q là <quan hệ>"   — only if no document says that, e.g. "B là chồng".
    The field report (thực địa) is read first, as the BRD asks.
    """

    own: dict[tuple[str, str], str] = {}        # (P, Q) → "<quan hệ> của Q"
    other: dict[tuple[str, str], str] = {}      # (P, Q) → "Q là <quan hệ>"
    shareholders = [r for r in records if r.get("pass") == "shareholders"]
    shareholders.sort(key=lambda r: 0 if r.get("source") == "field" else 1)
    for record in shareholders:
        for rel in record["data"].get("relationships") or []:
            if not isinstance(rel, dict) or not rel.get("member_a") or not rel.get("member_b"):
                continue
            relation = rel.get("relation") or "có quan hệ"
            a, b = rel["member_a"], rel["member_b"]
            pa, pb = norm_person(a), norm_person(b)
            own.setdefault((pa, pb), f"{relation} của {b}")
            other.setdefault((pb, pa), f"{a} là {relation}")
    found: dict[str, list[str]] = {}
    for (person, partner), text in {**other, **own}.items():   # own phrase wins for the same pair
        found.setdefault(person, []).append(text)
    return found


def _html_cell(text: str, rowspan: int = 1) -> str:
    return f'<td rowspan="{rowspan}">{text}</td>' if rowspan > 1 else f"<td>{text}</td>"


def _html_cells(values: list[Any], escape: bool = True) -> str:
    return "".join(_html_cell(html.escape(str(v)) if escape else str(v)) for v in values)


def _html_lines(lines: list[str]) -> str:
    """Comment lines inside one table cell (no Markdown there)."""
    return "<br>".join("- " + html.escape(line) for line in lines)


def _field_people(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """[BRD 29/10] People described by the site-visit report (shareholders pass, "people")."""

    found: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("pass") != "shareholders" or record.get("source") != "field":
            continue
        for person in record["data"].get("people") or []:
            if isinstance(person, dict) and person.get("name"):
                entry = found.setdefault(norm_person(person["name"]), {"name": person["name"]})
                for field in ("position", "relation_to_borrower", "influence", "assessment"):
                    if not entry.get(field) and person.get(field):
                        entry[field] = " ".join(str(person[field]).split())
    return found


def _position(position: Any, rep: dict | None, pct: Any) -> str:
    """Chức vụ: as the site-visit report says, else the legal-rep title, else "Thành viên góp vốn"."""

    text = str(position or (rep or {}).get("title") or "").strip()
    if rep and "đại diện" not in text.lower():
        text = f"{text} kiêm người đại diện theo pháp luật" if text else "Người đại diện theo pháp luật"
    return text or ("Thành viên góp vốn" if pct else "—")


def _relation_to_borrower(records: list[dict[str, Any]], key: str, borrowers: set[str]) -> str:
    """When the site-visit report says nothing: "KH vay", "<quan hệ> KH vay", else the relations found."""

    if key in borrowers:
        return "KH vay (người đứng ra vay)"
    for record in records:
        if record.get("pass") != "shareholders":
            continue
        for rel in record["data"].get("relationships") or []:
            if not isinstance(rel, dict) or not rel.get("relation"):
                continue
            a, b = norm_person(rel.get("member_a")), norm_person(rel.get("member_b"))
            if a == key and b in borrowers:
                return f"{rel['relation'].strip().capitalize()} KH vay"
            if b == key and a in borrowers:
                return f"KH vay là {rel['relation'].strip()}"
    return "; ".join(_relations(records).get(key, [])) or "—"


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
                           income: dict[str, Any] | None = None,
                           industry: dict[str, Any] | None = None) -> dict[str, str]:
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

    # ---- 1b. Thành viên góp vốn & người đại diện theo pháp luật [BRD 29/10] ----------
    # Tỷ lệ góp vốn: same logic as before (sổ cổ đông → điều lệ, legal_checks.py).
    # Chức vụ, mối quan hệ, mức độ ảnh hưởng, đánh giá năng lực: from the site-visit report.
    reps = {norm_person(r.get("name")): r for r in items[3]["summary"].get("legal_representatives", [])}
    people = _field_people(records)
    rows, seen = [], set()

    def person_row(name: str, pct: Any) -> list[str]:
        key = norm_person(name)
        seen.add(key)
        info = people.get(key, {})
        return [name or NO_INFO,
                "0" if pct is None else f"{float(pct):g}".replace(".", ","),
                _position(info.get("position"), reps.get(key), pct),
                info.get("relation_to_borrower") or _relation_to_borrower(records, key, borrowers),
                info.get("influence") or "—",
                info.get("assessment") or "—"]

    members = sorted(items[2]["summary"].get("members", []),
                     key=lambda m: -(m.get("ownership_pct") or 0))
    for member in members:
        rows.append(person_row(member.get("name"), member.get("ownership_pct")))
    for key, rep in reps.items():               # legal representatives without capital
        if key and key not in seen:
            rows.append(person_row(rep.get("name"), None))
    for key, info in people.items():            # management named only in the site-visit report
        if key and key not in seen:
            rows.append(person_row(info.get("name"), None))
    ctx["RowsThanhVien"] = "\n".join(_pipe_row(r) for r in rows or [[NO_INFO, "—", "—", "—", "—", "—"]])

    # ---- Cảnh báo pháp lý: shown only when there is one (no file names, no folders) ----
    warn = []
    if not borrower_names:
        warn.append("Chưa xác định được KH cá nhân vay vốn trong hồ sơ vay vốn — kiểm tra lại hoặc khai báo "
                    "BORROWER_NAMES")
    for c in LEGAL_MISMATCH_CODES:
        if c in codes:
            where = _where_differs(records, c)
            warn.append(codes[c]["message"] + (f": {where}" if where else ""))
    warn += [codes[c]["message"] for c in ("status_not_active", "status_unknown") if c in codes]
    warn += [f["message"] for f in items[2]["findings"]
             if f["code"] in ("ownership_not_100", "ownership_incomplete", "capital_sum_mismatch")]
    listed = {*LEGAL_MISMATCH_CODES, "status_not_active", "status_unknown",
              "ownership_not_100", "ownership_incomplete", "capital_sum_mismatch"}
    warn += [f["message"] for n in (1, 2, 3) for f in items[n]["findings"]
             if f["severity"] == "alert" and f["code"] not in listed and f["message"] not in warn]
    ctx["CanhBaoPhapLy"] = ("**Cảnh báo pháp lý:**\n\n" + "\n".join(f"- {w}" for w in warn)) if warn else ""

    # ---- 2. Mô hình HĐKD ------------------------------------------------------------
    ctx["MoHinhHDKD"] = (business_model.diagram(str(company), records)
                         or "Chưa có thông tin đối tác đầu vào / đầu ra trong hồ sơ")

    # ---- 3. Tài chính [BRD 29/10] ---------------------------------------------------
    ctx["NguonTaiChinh"] = fm.sources_text(financials)
    for name, field in FIGURE_PREFIXES.items():
        for label, fig in financials["years"].items():
            ctx[f"{name}{label}"] = fm.fmt(fig.get(field))
    for name, ratio in RATIO_PREFIXES.items():
        for label, values in financials["ratios"].items():
            ctx[f"{name}{label}"] = _ratio_text(ratio, values.get(ratio))
    # Relative years: N-1 = latest full year with a BCTC (else the year before the loan
    # date), N-2 = the year before it. Cells: {{DTTN-1}}, {{TongTaiSanN-2}}, {{ROSN-1}} …
    n1 = financials.get("latest_year") or str(as_of.year - 1)
    n2 = str(int(n1) - 1)
    ctx["Nam-1"], ctx["Nam-2"] = n1, n2
    for prefix in (*FIGURE_PREFIXES, *RATIO_PREFIXES):
        for alias, year in (("N-1", n1), ("N-2", n2), ("N1", n1), ("N2", n2)):
            ctx[f"{prefix}{alias}"] = ctx.get(f"{prefix}{year}", "—")
    f1, f2 = financials["years"].get(n1) or {}, financials["years"].get(n2) or {}
    cic = cic or {"available": False}

    # a. Cơ cấu tài sản, nguồn vốn — Tổng tài sản + lines ≥ 20%; one comment cell for the table
    def share(fig: dict, value: float | None) -> str:
        total = fig.get("total_assets")
        return fm.pct(value / total) if value is not None and total else "—"

    lines = [("Tổng tài sản", "total_assets")] + fm.asset_lines(financials, (n2, n1))
    remarks = [f"⚠ {w}" for w in financials["bs_warnings"] if w in financials["material_warnings"]]
    remarks += [w for w in financials["bs_warnings"] if w not in financials["material_warnings"]]
    remarks += fm.structure_remarks(financials, business_type(records)[0])
    derived = {f for fig in financials["years"].values() for f in fig.get("_derived", [])}
    if {"current_assets", "current_liabilities"} & derived:
        remarks.append("BCTC theo TT133: TSNH / TSDH / nợ ngắn hạn tính theo Nguyên tắc 1")
    remarks = remarks or ["Không ghi nhận dấu hiệu bất thường trên bảng cân đối kế toán"]
    rows = []
    for i, (label, field) in enumerate(lines):
        v2, v1 = fm.asset_value(f2, field), fm.asset_value(f1, field)
        cells = [label, fm.fmt(v2), share(f2, v2), fm.fmt(v1), share(f1, v1)]
        rows.append(_html_cells(cells) + (_html_cell(_html_lines(remarks), rowspan=len(lines)) if i == 0 else ""))
    ctx["RowsCoCau"] = "\n".join(f"<tr>{r}</tr>" for r in rows)

    # b. Quy mô & tăng trưởng & chỉ số — "Tăng trưởng" = năm sau / năm trước − 1, signed
    r1, r2 = financials["ratios"].get(n1) or {}, financials["ratios"].get(n2) or {}
    lnst1, lnst2 = f1.get("profit_after_tax"), f2.get("profit_after_tax")
    growth_rows = [
        ["Doanh thu thuần", fm.fmt(f2.get("net_revenue")), fm.fmt(f1.get("net_revenue")),
         fm.signed_pct(r1.get("revenue_growth"))],
        ["LNST", fm.fmt(lnst2), fm.fmt(lnst1),
         fm.signed_pct(lnst1 / lnst2 - 1) if None not in (lnst1, lnst2) and lnst2 > 0 else "—"],
        ["LN sau thuế / DTT", _ratio_text("ros", r2.get("ros")), _ratio_text("ros", r1.get("ros")), ""],
        ["Hệ số TT hiện hành", _ratio_text("current_ratio", r2.get("current_ratio")),
         _ratio_text("current_ratio", r1.get("current_ratio")), ""],
    ]
    remarks = [f"⚠ {w}" for w in financials["pl_warnings"] if w in financials["material_warnings"]]
    remarks += [w for w in financials["pl_warnings"] if w not in financials["material_warnings"]]
    interest = fm.interest_vs_cic(financials, cic.get("avg_balance_12m"))
    if interest:
        remarks.append(f"⚠ {interest}")
    remarks += financials["status_remarks"]
    vat = financials.get("vat") or {}
    if vat.get("text") and vat["text"] not in remarks:
        remarks.append(vat["text"])
    remarks = remarks or ["Chưa có BCTC để đánh giá"]
    ctx["RowsTangTruong"] = "\n".join(
        "<tr>" + _html_cells(r) + (_html_cell(_html_lines(remarks), rowspan=4) if i == 0 else "") + "</tr>"
        for i, r in enumerate(growth_rows))

    # ---- 4. Dư nợ tại TCTD [BRD 29/10] ------------------------------------------------
    if cic.get("available"):
        ctx["BangDuNoTCTD"] = debt_table(cic)
        ctx["BieuDoDuNo"] = debt_chart(cic.get("monthly") or [], cic.get("avg_balance_12m"))
        ctx["SpecialMention"] = cic_metrics.describe_items(cic["special_mention"],
                                                           "nợ cần chú ý trong 12 tháng gần nhất")
        ctx["BadDebt"] = cic_metrics.describe_items(cic["bad_debt"], "nợ xấu trong 05 năm gần nhất")
    else:
        none = "Không có thông tin (hồ sơ chưa có bản tin CIC S10A/R20)"
        ctx.update({"BangDuNoTCTD": none, "BieuDoDuNo": "", "SpecialMention": none, "BadDebt": none})

    # ---- 5. Kết luận: dự phóng kinh doanh (PAKD), giá trị nguồn thu -----------------
    ctx.update(plan_cells(pick_plan(records), financials, n1, industry))
    if corp and income is not None:
        ctx["KetLuan"] = income_block(corp, income)
    return ctx


def debt_table(cic: dict[str, Any]) -> str:
    """[BRD 29/10] "Tổng thông tin dư nợ DN": one column per TCTD + Tổng (one line of HTML).

    Rows: Ngắn hạn, Dài hạn, Cho thuê TC, (Dư nợ khác if any), Tổng, %, Trung bình dư nợ 12 tháng,
    Cam kết ngoại bảng (*), Tổng giá trị TSBĐ theo CIC (**). Below: footnotes, bản tin date, warnings.
    """

    lenders = cic.get("lenders") or []
    grand = sum(l["total"] for l in lenders)
    head = "<tr><th>Chỉ tiêu</th>" + "".join(f"<th>{html.escape(l['name'])}</th>" for l in lenders) + "<th>Tổng</th></tr>"

    def money_row(label: str, field: str) -> str:
        values = [l[field] for l in lenders]
        return "<tr>" + _html_cells([label] + [fm.fmt(v) for v in values] + [fm.fmt(sum(values))]) + "</tr>"

    body = [money_row("Ngắn hạn", "short_term"), money_row("Dài hạn", "long_term"),
            money_row("Cho thuê TC", "finance_lease")]
    if any(l["other"] for l in lenders):
        body.append(money_row("Dư nợ khác", "other"))
    body.append("<tr>" + _html_cells(["<b>Tổng</b>"] + [fm.fmt(l["total"]) for l in lenders] + [fm.fmt(grand)],
                                     escape=False) + "</tr>")
    body.append("<tr>" + _html_cells(["%"] + [fm.pct(l["total"] / grand) if grand else "—" for l in lenders]
                                     + ["100%" if grand else "—"]) + "</tr>")
    body.append("<tr>" + _html_cells(["Trung bình dư nợ 12 tháng gần nhất"] + [""] * len(lenders)
                                     + [fm.fmt(cic.get("avg_balance_12m"))]) + "</tr>")
    with_commitment = [l["name"] for l in lenders if l["off_balance"]]
    body.append(money_row("Cam kết ngoại bảng" + (f" tại: {', '.join(with_commitment)}" if with_commitment else "")
                          + " (*)", "off_balance"))
    collateral = [fm.fmt(l["collateral_value"]) if cic.get("has_r20") else "—" for l in lenders]
    body.append("<tr>" + _html_cells(["Tổng giá trị TSBĐ theo CIC (**)"] + collateral
                                     + [fm.fmt(cic["rows"]["Total"]["collateral"]) if cic.get("has_r20") else "—"])
                + "</tr>")
    notes = ["(*) Không cộng vào Tổng dư nợ. (**) Theo bản tin R20.", f"Bản tin: {cic.get('query_dates') or '—'}"]
    notes += [f"⚠ {w}" for w in cic.get("warnings") or []]
    return ("<table>" + head + "".join(body) + "</table>"
            + "".join(f"<br><i>{html.escape(n)}</i>" for n in notes))


def plan_cells(plan: dict[str, Any] | None, financials: dict[str, Any], n1: str,
               industry: dict[str, Any] | None = None) -> dict[str, str]:
    """[BRD 29/10] Cells of "a. Dự phóng kinh doanh (nếu có)".

    TH = BCTC năm N-1; KH = phương án kinh doanh; Tăng/giảm = KH / TH − 1.
    Theo am hiểu ngành TCB = ROS và tăng trưởng của ngành (bảng ngành TCB, theo phân khúc);
    theo dự phóng: ROS = LNST KH / DTT KH, tăng trưởng = DTT KH / DTT TH − 1.
    """

    cells = {"PAKD_NamKeHoach": "", "_has_plan": ""}
    fig = financials["years"].get(n1) or {}
    cells["Nganh_ROS"] = fm.pct(industry.get("ros")) if industry and industry.get("ros") is not None else "—"
    cells["Nganh_TangTruong"] = fm.pct(industry.get("growth")) if industry and industry.get("growth") is not None else "—"
    cells["Nganh_CoSo"] = (f"Bảng ngành TCB: {industry['name']} — phân khúc {industry.get('segment') or 'SME'}"
                           if industry else "Chưa xác định ngành theo bảng ngành TCB")
    if not plan:
        for key in ("DTT", "GV", "LNST"):
            cells[f"PAKD_{key}_KeHoach"] = cells[f"PAKD_{key}_TangGiam"] = ""
        cells.update({"PAKD_CoSo": "", "PAKD_ROS": "", "PAKD_TangTruong": ""})
        return cells

    def change(plan_value: float | None, actual: float | None) -> str:
        return fm.signed_pct(plan_value / actual - 1) if plan_value is not None and actual else "—"

    revenue, cogs, profit = plan.get("plan_revenue"), plan.get("plan_cogs"), plan.get("plan_profit_after_tax")
    actual_cogs = abs(fig["cogs"]) if fig.get("cogs") is not None else None
    cells.update({
        "_has_plan": "1",
        "PAKD_NamKeHoach": str(plan.get("plan_year") or ""),
        "PAKD_DTT_KeHoach": fm.fmt(revenue), "PAKD_DTT_TangGiam": change(revenue, fig.get("net_revenue")),
        "PAKD_GV_KeHoach": fm.fmt(abs(cogs) if cogs is not None else None),
        "PAKD_GV_TangGiam": change(abs(cogs) if cogs is not None else None, actual_cogs),
        "PAKD_LNST_KeHoach": fm.fmt(profit), "PAKD_LNST_TangGiam": change(profit, fig.get("profit_after_tax")),
        "PAKD_CoSo": " ".join(str(plan.get("basis") or "").split()) or "—",
        "PAKD_ROS": fm.pct(profit / revenue) if profit is not None and revenue else "—",
        "PAKD_TangTruong": change(revenue, fig.get("net_revenue")),
    })
    return cells


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
            f"{proj['industry']} — phân khúc {proj.get('segment') or 'SME'}, tăng trưởng ngành {fm.pct(proj['industry_growth'])}, ROS ngành "
            f"{fm.pct(proj['industry_ros'])})_",
            "",
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
_PAKD_TABLE = re.compile(r'<table class="pakd">.*?</table>\n?', re.S)
_NO_PAKD = re.compile(r'<p class="no-pakd">.*?</p>\n?', re.S)
_EMPTY = ("", "—", "-", "không có", "không có thông tin", "chưa có thông tin", "chưa có thông tin trong hồ sơ")


def is_empty(value: Any) -> bool:
    text = str(value or "").strip().rstrip(".").lower()
    return text in _EMPTY or text.startswith(("chưa có thông tin", "không có thông tin"))


def apply_output_conditions(markdown: str, ctx: dict[str, str]) -> str:
    """[BRD 29/10]
    - No business plan → hide the "Dự phóng kinh doanh" tables, show "Khách hàng không cung cấp PAKD".
    - No factory / warehouse address → drop that line of "Địa chỉ" (instead of "không có thông tin").
    - No business-activity warning → drop the "Cảnh báo HĐKD" line.
    """

    markdown = _NO_PAKD.sub("", markdown) if ctx.get("_has_plan") else _PAKD_TABLE.sub("", markdown)
    markdown = markdown.replace("kinh doanh  (nếu có)", "kinh doanh (nếu có)")     # no plan year
    for name, label in (("NhaXuong", "Nhà xưởng"), ("KhoHang", "Kho hàng")):
        if is_empty(ctx.get(name)):
            markdown = re.sub(r"<br>- " + label + r": [^\n]*?(?=<br>| \||$)", "", markdown, count=1,
                              flags=re.M)
    if is_empty(ctx.get("NhanXetHDKD")):
        markdown = re.sub(r"^\*\*Cảnh báo HĐKD:\*\*.*\n?", "", markdown, count=1, flags=re.M)
    return markdown
