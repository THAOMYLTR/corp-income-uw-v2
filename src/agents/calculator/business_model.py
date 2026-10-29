"""[BRD 27/10] Phụ lục mục 2 — "Mô hình HĐKD" and the industry, in code.

Input: records of pass "business_model" (one per document). The BRD rules:

  - Nguồn ưu tiên: báo cáo khảo sát thực địa → hợp đồng / hóa đơn đầu vào, đầu ra
    → sổ chi tiết TK 131 / 331 (→ sao kê, then internal data).
  - Đầu vào xếp theo giá trị mua lớn nhất, đầu ra theo giá trị bán lớn nhất;
    NHIỀU NHẤT 5 đối tác mỗi bên. Ít hơn 5 → chỉ những đối tác có thật.
  - [Sửa 29/10] Tỷ trọng = giá trị đối tác / tổng giá trị các đối tác nhận diện được (cùng bên).
    Không có giá trị nào → dùng tỷ trọng hồ sơ ghi; cũng không có → bỏ tỷ trọng.
  - Sơ đồ 5 tầng: sản phẩm đầu vào → đối tác đầu vào → doanh nghiệp → đối tác
    đầu ra → sản phẩm đầu ra. Nhà cung cấp luôn bên TRÁI, khách mua bên PHẢI.
    Đối tác không có mặt hàng → không có khối sản phẩm (ô trống, không "không rõ").
"""

from __future__ import annotations

import base64
import html
from typing import Any

from src.agents.calculator import industry as industry_table
from src.utils.common import normalize_text

MAX_PARTNERS = 5
# Lower = read first (BRD source priority for the diagram).
SOURCE_PRIORITY = {
    "bao_cao_thuc_dia": 0, "bao_cao_thuc_dia_phap_ly": 0,
    "hop_dong_dau_vao_dau_ra": 1,
    "so_chi_tiet_cong_no": 2,
    "sao_ke_tai_khoan": 3,
    "du_lieu_noi_bo": 4,
}


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = [r for r in records if r.get("pass") == "business_model" and isinstance(r.get("data"), dict)]
    return sorted(found, key=lambda r: SOURCE_PRIORITY.get(r.get("document_type"), 9))


def partners(records: list[dict[str, Any]], side: str, limit: int | None = MAX_PARTNERS) -> list[dict[str, Any]]:
    """Top 5 suppliers ("suppliers") or customers ("customers"), merged across documents.

    The same partner named by several documents is one row; the first (highest
    priority) document that gives a product, value or share keeps it.
    """

    merged: dict[str, dict[str, Any]] = {}
    for record in _records(records):
        for p in record["data"].get(side) or []:
            name = str(p.get("name") or "").strip()
            key = normalize_text(name)
            if not key:
                continue
            row = merged.setdefault(key, {"name": name, "product": "", "value": None, "share_pct": None,
                                          "source": record.get("document", "")})
            if not row["product"] and p.get("product"):
                row["product"] = str(p["product"]).strip()
            if row["value"] is None:
                row["value"] = _num(p.get("value"))
            if row["share_pct"] is None:
                row["share_pct"] = _num(p.get("share_pct"))
    rows = list(merged.values())
    # [Sửa 29/10] Tỷ trọng tính trong code: giá trị hợp đồng của đối tác / tổng giá trị hợp đồng
    # của mọi đối tác nhận diện được cùng bên (đầu vào hoặc đầu ra). Vd Dược Hậu Giang 135tr,
    # Nam Phùng 45tr → 75% và 25%. Không có giá trị nào thì giữ tỷ trọng hồ sơ ghi (nếu có).
    total = sum(r["value"] for r in rows if r["value"])
    if total:
        for r in rows:
            r["share_pct"] = round(r["value"] / total * 100, 1) if r["value"] else None
    # Largest value first; partners without a value keep their document order after them.
    rows.sort(key=lambda r: -(r["value"] if r["value"] is not None else -1))
    return rows[:limit]


def industry(records: list[dict[str, Any]], segment: str = "") -> dict[str, Any] | None:
    """The TCB industry row named by the highest-priority document that names one,
    in the company's segment (SME / USME / MM / LC — ROS and growth differ by segment)."""

    for record in _records(records):
        row = industry_table.lookup(record["data"].get("industry"), segment,
                                    record["data"].get("industry_sector"))
        if row:
            return {**row, "document": record.get("document", "")}
    return None


def product_service(records: list[dict[str, Any]]) -> str:
    """[Sửa 29/10] "Sản phẩm/ dịch vụ" as the site-visit report writes it ('' if none).

    Read by the business_model pass over the WHOLE report — the writer LLM only sees the first
    6.000 characters of it, and in the MB form this row comes after the long checklist (mục A).
    """

    for record in _records(records):
        text = " ".join(str(record["data"].get("product_service") or "").split())
        if text:
            return text
    return ""


def _cell(text: str) -> str:
    # The diagram sits inside a Markdown table cell: one line, no "|".
    return html.escape(" ".join(str(text or "").split())).replace("|", "/")


# --------------------------------------------------------------------------- #
# [BRD 27/10] The diagram, drawn as an SVG (same look as the BRD's Excel shape):
#   sản phẩm đầu vào → đối tác đầu vào ─%─┐                ┌─%→ sản phẩm đầu ra → đối tác đầu ra
#                                          ├→ DOANH NGHIỆP ─┤
#   sản phẩm đầu vào → đối tác đầu vào ─%─┘                └─%→ sản phẩm đầu ra → đối tác đầu ra
# Embedded as <img src="data:image/svg+xml;base64,…">: one line (fits the table cell) and
# shown the same in the PDF (WeasyPrint), HTML and the .md file. No library needed.
# --------------------------------------------------------------------------- #
BOX_W, BOX_H, COL_GAP, ROW_GAP, MARGIN = 150, 58, 90, 22, 16
FILL, STROKE, TEXT, LINE = "#dcdcf5", "#8f8fcf", "#1f1f3d", "#555555"
FONT = "Arial, Helvetica, sans-serif"
CHARS_PER_LINE, MAX_LINES = 22, 3
WIDTH = 2 * MARGIN + 5 * BOX_W + 4 * COL_GAP


def _wrap(text: str) -> list[str]:
    """Split a label into at most MAX_LINES lines of about CHARS_PER_LINE characters."""

    lines, line = [], ""
    for word in " ".join(str(text or "").split()).split(" "):
        if line and len(line) + 1 + len(word) > CHARS_PER_LINE:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1][: CHARS_PER_LINE - 1].rstrip() + "…"
    return lines


def _money(value: Any) -> str:
    """[BRD 29/10] Contract value in the partner box, compact: "135tr", "1,5tỷ", "180tỷ".

    Below 1 tỷ in triệu đồng; from 1 tỷ in tỷ đồng (one decimal, dropped when ,0) — so
    180 tỷ never reads as "180tr".
    """

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    if abs(value) < 1e9:
        return f"{value / 1e6:,.0f}".replace(",", ".") + "tr"
    text = f"{value / 1e9:,.1f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return text.removesuffix(",0") + "tỷ"


def _box(x: float, y: float, text: str, bold: bool = False, value: str = "") -> str:
    """A box with its label; ``value`` (e.g. "135 tr") is a bold line right under the name."""

    lines = _wrap(text)
    if value and len(lines) > 2:                   # name keeps 2 lines when a value is shown
        lines = lines[:2]
        lines[-1] = lines[-1][: CHARS_PER_LINE - 1].rstrip() + "…"
    rows = [(t, False) for t in lines] + ([(value, True)] if value else [])
    first = y + BOX_H / 2 - (len(rows) - 1) * 7 + 4
    spans = "".join(f'<tspan x="{x + BOX_W / 2}" y="{first + i * 14}"'
                    + (' font-weight="bold"' if strong else "") + f'>{html.escape(t)}</tspan>'
                    for i, (t, strong) in enumerate(rows))
    weight = ' font-weight="bold"' if bold else ""
    return (f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="3" fill="{FILL}" '
            f'stroke="{STROKE}"/><text text-anchor="middle" font-size="11"{weight}>{spans}</text>')


def _label(x: float, y: float, text: str) -> str:
    """A % on a line, on a white patch so the line does not cross the digits."""

    w = 7 * len(text) + 6
    return (f'<rect x="{x - w / 2}" y="{y - 8}" width="{w}" height="14" fill="#ffffff"/>'
            f'<text x="{x}" y="{y + 3}" text-anchor="middle" font-size="10">{html.escape(text)}</text>')


def _share(p: dict[str, Any]) -> str:
    return f"{p['share_pct']:g}%".replace(".", ",") if p.get("share_pct") is not None else ""


def diagram_svg(company: str, left: list[dict[str, Any]], right: list[dict[str, Any]]) -> str:
    """The SVG text. Suppliers always on the LEFT (arrows into the company), buyers on the
    RIGHT (arrows out). A partner with no product has no product box (BRD: xóa khối đó)."""

    rows = max(len(left), len(right), 1)
    col = [MARGIN + i * (BOX_W + COL_GAP) for i in range(5)]
    height = 2 * MARGIN + rows * BOX_H + (rows - 1) * ROW_GAP
    row_y = lambda i, n: MARGIN + (height - 2 * MARGIN - (n * BOX_H + (n - 1) * ROW_GAP)) / 2 + i * (BOX_H + ROW_GAP)
    mid = height / 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" font-family="{FONT}" fill="{TEXT}">',
        f'<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 z" fill="{LINE}"/></marker></defs>',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    line = f'fill="none" stroke="{LINE}" stroke-width="1.2"'
    trunk_l = col[1] + BOX_W + COL_GAP / 2          # where the left branches merge
    trunk_r = col[2] + BOX_W + COL_GAP / 2          # where the right branches split

    for i, p in enumerate(left):                    # [sản phẩm] → [đối tác] ─%─ → công ty
        y = row_y(i, len(left))
        cy = y + BOX_H / 2
        if p.get("product"):
            parts.append(_box(col[0], y, p["product"]))
            parts.append(f'<path d="M{col[0] + BOX_W},{cy} H{col[1] - 2}" {line} marker-end="url(#a)"/>')
        parts.append(_box(col[1], y, p["name"], value=_money(p.get("value"))))
        parts.append(f'<path d="M{col[1] + BOX_W},{cy} H{trunk_l} V{mid} H{col[2] - 2}" {line} '
                     'marker-end="url(#a)"/>')
        if _share(p):
            parts.append(_label(col[1] + BOX_W + COL_GAP / 4, cy, _share(p)))

    for i, p in enumerate(right):                   # công ty ─%→ [sản phẩm] → [đối tác]
        y = row_y(i, len(right))
        cy = y + BOX_H / 2
        target = col[3] if p.get("product") else col[4]
        parts.append(f'<path d="M{col[2] + BOX_W},{mid} H{trunk_r} V{cy} H{target - 2}" {line} '
                     'marker-end="url(#a)"/>')
        if _share(p):
            parts.append(_label(trunk_r + COL_GAP / 4, cy, _share(p)))
        if p.get("product"):
            parts.append(_box(col[3], y, p["product"]))
            parts.append(f'<path d="M{col[3] + BOX_W},{cy} H{col[4] - 2}" {line} marker-end="url(#a)"/>')
        parts.append(_box(col[4], y, p["name"], value=_money(p.get("value"))))

    parts.append(_box(col[2], mid - BOX_H / 2, company, bold=True))
    parts.append("</svg>")
    return "".join(parts)


def diagram(company: str, records: list[dict[str, Any]]) -> str:
    """The 5-tier diagram, as a one-line <img> with the SVG inside (data URI).

    Returns "" when no document names a partner (the template then says so).
    """

    every_left, every_right = partners(records, "suppliers", None), partners(records, "customers", None)
    left, right = every_left[:MAX_PARTNERS], every_right[:MAX_PARTNERS]
    if not left and not right:
        return ""
    svg = diagram_svg(company, left, right)
    alt = _cell("Đầu vào: " + ", ".join(p["name"] for p in left)
                + " → " + company + " → Đầu ra: " + ", ".join(p["name"] for p in right))
    image = (f'<img alt="{alt}" style="width:100%;max-width:{WIDTH}px" '
             f'src="data:image/svg+xml;base64,{base64.b64encode(svg.encode("utf-8")).decode("ascii")}">')
    with_share = any(p["share_pct"] is not None for p in left + right)
    note = "" if with_share else "<br><i>Hồ sơ không có tỷ trọng — chỉ ghi tên đối tác và sản phẩm.</i>"
    # [Sửa 29/10] more than 5 partners on a side: % are over all of them, so the 5 shown add to < 100%
    if max(len(every_left), len(every_right)) > MAX_PARTNERS:
        note += f"<br><i>(*) Hiển thị {MAX_PARTNERS} đối tác tối đa.</i>"
    return image + note
