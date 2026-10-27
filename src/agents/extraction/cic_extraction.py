"""[BRD 16/10] LLM extraction of the CIC reports S10A / R20 — Phụ lục 01 mục 4.

The LLM copies each printed line; src/agents/calculator/cic_metrics.py sums the
lines per bank, checks the report date and decides the bureau group.
"""

from typing import Any

from src.agents.extraction.structured_extraction import (
    build_extraction_chain,
    resolve_money_multiplier,
    run_extraction,
    scale_amount,
)
from src.prompts import system_prompt

REQUIRED_TOP_LEVEL_KEYS = {"report_type", "lenders"}
_LENDER_FIELDS = ("short_term", "long_term", "other", "off_balance")


def normalize_amounts(result: dict[str, Any]) -> dict[str, Any]:
    multiplier = resolve_money_multiplier(result.get("source_unit"))
    for key, fields in (("lenders", _LENDER_FIELDS), ("collaterals", ("value",)),
                        ("special_mention_12m", ("amount",)), ("bad_debt_5y", ("amount",)),
                        ("card_late_payment_3y", ("amount",)),  # [BRD 27/10]
                        ("monthly_balances_12m", ("balance",))):
        rows = [r for r in result.get(key) or [] if isinstance(r, dict)]
        for row in rows:
            for field in fields:
                row[field] = scale_amount(row.get(field), multiplier)
        result[key] = rows
    result["source_unit"] = "dong"
    return result


def build_cic_extraction_chain(llm: Any):
    return build_extraction_chain(system_prompt("cic_extraction"), llm)


def extract_cic_structured_data(chain: Any, filename: str, content: str, path: str = ""):
    return run_extraction(chain, filename, content, REQUIRED_TOP_LEVEL_KEYS,
                          "No cic_extraction_llm configured.", normalize_amounts)
