"""[BRD 27/10] Bảng ngành tại TCB (PL1): ngành → ROS ngành, tăng trưởng ngành.

The table is src/templates/bang-nganh-tcb.csv (lines starting with "#" are notes).
Used twice: the business_model prompt lists the industry names so the LLM picks one,
and the business-plan projection (mục 5) reads ROS / growth of that industry.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

from src.utils.common import normalize_text
from src.utils.paths import PROJECT_ROOT

INDUSTRY_FILE = PROJECT_ROOT / "src" / "templates" / "bang-nganh-tcb.csv"


def _number(text: str) -> float | None:
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def industries() -> tuple[dict[str, Any], ...]:
    """Every row: {segment, sector, bizline, name, ros, growth}."""

    if not INDUSTRY_FILE.is_file():
        return ()
    lines = [line for line in INDUSTRY_FILE.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    rows = []
    for row in csv.DictReader(lines):
        rows.append({
            "segment": row.get("Phân khúc", ""),
            "sector": row.get("Lĩnh vực kinh tế", ""),
            "bizline": row.get("Bizline - Sub-segment", ""),
            "name": row.get("Ngành", ""),
            "ros": _number(row.get("ROS", "")),
            "growth": _number(row.get("Tăng trưởng ngành", "")),
        })
    return tuple(rows)


def prompt_list() -> str:
    """One industry name per line, for the business_model prompt."""

    return "\n".join(f"- {row['name']}" for row in industries()) or "(chưa có bảng ngành TCB)"


def lookup(name: Any) -> dict[str, Any] | None:
    """The row whose Ngành (or Bizline) matches ``name``, ignoring accents and case."""

    key = normalize_text(str(name or ""))
    if not key:
        return None
    for row in industries():
        if key in (normalize_text(row["name"]), normalize_text(row["bizline"])):
            return row
    return None
