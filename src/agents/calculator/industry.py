"""[BRD 27/10] Bảng ngành tại TCB (PL1): (phân khúc, ngành) → ROS ngành, tăng trưởng ngành.

The table is src/templates/bang-nganh-tcb.csv (lines starting with "#" are notes): four
segments — SME, USME, MM, LC — with the same 110 industries and their own ROS / growth.
Used twice: the business_model prompt lists the industry names (with their sector, since
"Khác" exists in several sectors) so the LLM picks one, and the business-plan projection
(mục 5) reads ROS / growth of that industry in the company's segment.

Segment = by revenue of the latest year, as in the BRD: SME < 200 tỷ, USME < 600 tỷ,
MM < 2000 tỷ, LC ≥ 2000 tỷ (financial_metrics.segment_code).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

from src.utils.common import normalize_text
from src.utils.paths import PROJECT_ROOT

INDUSTRY_FILE = PROJECT_ROOT / "src" / "templates" / "bang-nganh-tcb.csv"
DEFAULT_SEGMENT = "SME"          # segment unknown (no revenue) → SME rows


def _number(text: str) -> float | None:
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def industries() -> tuple[dict[str, Any], ...]:
    """Every row: {segment, sector, sub_segment, bizline, name, ros, growth}."""

    if not INDUSTRY_FILE.is_file():
        return ()
    lines = [line for line in INDUSTRY_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    return tuple({
        "segment": row.get("Phân khúc", ""),
        "sector": row.get("Lĩnh vực kinh tế", ""),
        "sub_segment": row.get("Sub-segment_ENG", ""),
        "bizline": row.get("Bizline - Sub-segment", ""),
        "name": row.get("Ngành", ""),
        "ros": _number(row.get("ROS", "")),
        "growth": _number(row.get("Tăng trưởng ngành", "")),
    } for row in csv.DictReader(lines))


def prompt_list() -> str:
    """One "Ngành — Lĩnh vực" per line (each industry once), for the business_model prompt."""

    seen, lines = set(), []
    for row in industries():
        key = (row["name"], row["sector"])
        if key not in seen:
            seen.add(key)
            lines.append(f"- {row['name']} — {row['sector']}")
    return "\n".join(lines) or "(chưa có bảng ngành TCB)"


def lookup(name: Any, segment: str = "", sector: Any = "") -> dict[str, Any] | None:
    """The row of ``name`` (Ngành, Sub-segment_ENG or Bizline; accents and case ignored)
    in ``segment``; ``sector`` breaks ties ("Khác" exists in every sector)."""

    key = normalize_text(str(name or ""))
    if not key:
        return None
    segment = segment or DEFAULT_SEGMENT
    found = [row for row in industries()
             if key in (normalize_text(row["name"]), normalize_text(row["sub_segment"]),
                        normalize_text(row["bizline"]))]
    in_segment = [row for row in found if row["segment"] == segment] or found
    wanted = normalize_text(str(sector or ""))
    return next((row for row in in_segment if wanted and normalize_text(row["sector"]) == wanted),
                in_segment[0] if in_segment else None)
