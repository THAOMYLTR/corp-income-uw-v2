"""[BRD 16/10] LLM extraction of the customer's business plan — Phụ lục 01 mục 5.

Only the plan year, planned revenue / profit and the customer's stated basis;
growth and ROS of the plan are computed in code (appendix_context.py).
"""

from typing import Any

from src.agents.extraction.structured_extraction import (
    build_extraction_chain,
    resolve_money_multiplier,
    run_extraction,
    scale_amount,
)
from src.prompts import system_prompt

REQUIRED_TOP_LEVEL_KEYS = {"has_plan"}


def normalize_amounts(result: dict[str, Any]) -> dict[str, Any]:
    multiplier = resolve_money_multiplier(result.get("source_unit"))
    for field in ("plan_revenue", "plan_cogs", "plan_profit_after_tax"):
        result[field] = scale_amount(result.get(field), multiplier)
    result["source_unit"] = "dong"
    return result


def build_plan_extraction_chain(llm: Any):
    return build_extraction_chain(system_prompt("plan_extraction"), llm)


def extract_plan_structured_data(chain: Any, filename: str, content: str, path: str = ""):
    return run_extraction(chain, filename, content, REQUIRED_TOP_LEVEL_KEYS,
                          "No plan_extraction_llm configured.", normalize_amounts)
