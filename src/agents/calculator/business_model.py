"""[BRD 27/10] Phụ lục mục 2 — "Mô hình HĐKD" and the industry, in code.

Input: records of pass "business_model" (one per document). The BRD rules:

  - Nguồn ưu tiên: báo cáo khảo sát thực địa → hợp đồng / hóa đơn đầu vào, đầu ra
    → sổ chi tiết TK 131 / 331 (→ sao kê, then internal data).
  - Đầu vào xếp theo giá trị mua lớn nhất, đầu ra theo giá trị bán lớn nhất;
    NHIỀU NHẤT 5 đối tác mỗi bên. Ít hơn 5 → chỉ những đối tác có thật.
  - Không có tỷ trọng → bỏ tỷ trọng, giữ tên đối tác và sản phẩm.
  - Sơ đồ 5 tầng: sản phẩm đầu vào → đối tác đầu vào → doanh nghiệp → đối tác
    đầu ra → sản phẩm đầu ra. Nhà cung cấp luôn bên TRÁI, khách mua bên PHẢI.
    Đối tác không có mặt hàng → không có khối sản phẩm (ô trống, không "không rõ").
"""

from __future__ import annotations

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


def partners(records: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
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
    # Largest value first; partners without a value keep their document order after them.
    rows.sort(key=lambda r: -(r["value"] if r["value"] is not None else -1))
    return rows[:MAX_PARTNERS]


def industry(records: list[dict[str, Any]], segment: str = "") -> dict[str, Any] | None:
    """The TCB industry row named by the highest-priority document that names one,
    in the company's segment (SME / USME / MM / LC — ROS and growth differ by segment)."""

    for record in _records(records):
        row = industry_table.lookup(record["data"].get("industry"), segment,
                                    record["data"].get("industry_sector"))
        if row:
            return {**row, "document": record.get("document", "")}
    return None


def _cell(text: str) -> str:
    # The diagram sits inside a Markdown table cell: one line, no "|".
    return html.escape(" ".join(str(text or "").split())).replace("|", "/")


def diagram(company: str, records: list[dict[str, Any]]) -> str:
    """The 5-tier diagram as an HTML table (renders in Markdown, HTML and PDF).

    Returns "" when no document names a partner (the template then says so).
    """

    left, right = partners(records, "suppliers"), partners(records, "customers")
    if not left and not right:
        return ""
    with_share = any(p["share_pct"] is not None for p in left + right)

    def label(p: dict[str, Any] | None) -> str:
        if not p:
            return ""
        share = f" ({p['share_pct']:g}%)".replace(".", ",") if with_share and p["share_pct"] is not None else ""
        return _cell(p["name"]) + share

    rows = max(len(left), len(right))
    head = ("<tr><th>Sản phẩm đầu vào</th><th>Đối tác đầu vào<br>(nhà cung cấp)</th><th></th>"
            "<th>Doanh nghiệp</th><th></th><th>Đối tác đầu ra<br>(khách mua)</th><th>Sản phẩm đầu ra</th></tr>")
    body = []
    for i in range(rows):
        sup = left[i] if i < len(left) else None
        cus = right[i] if i < len(right) else None
        cells = [
            f"<td>{_cell(sup['product']) if sup else ''}</td>",
            f"<td>{label(sup)}</td>",
            f"<td>{'→' if sup else ''}</td>",
        ]
        if i == 0:
            cells.append(f'<td rowspan="{rows}" align="center"><b>{_cell(company)}</b></td>')
        cells += [
            f"<td>{'→' if cus else ''}</td>",
            f"<td>{label(cus)}</td>",
            f"<td>{_cell(cus['product']) if cus else ''}</td>",
        ]
        body.append("<tr>" + "".join(cells) + "</tr>")
    note = "" if with_share else "<br><i>Hồ sơ không có tỷ trọng — chỉ ghi tên đối tác và sản phẩm.</i>"
    sources = sorted({p["source"] for p in left + right if p.get("source")})
    return ("<table>" + head + "".join(body) + "</table>"
            + note + (f"<br><i>Nguồn: {_cell(', '.join(sources))}</i>" if sources else ""))
