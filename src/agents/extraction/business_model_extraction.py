"""[BRD 27/10] LLM extraction for Phụ lục mục 2 — ngành TCB and the business model.

One call per document flagged business_model_extraction in the matrix (field
report, contracts / invoices, TK 131/331 ledgers, bank statements, internal data).
Ranking, top 5 and the diagram are done in code (calculator/business_model.py).
"""

from typing import Any

from src.agents.calculator import industry
from src.agents.extraction.structured_extraction import (
    build_extraction_chain,
    resolve_money_multiplier,
    run_extraction,
    scale_amount,
)
from src.prompts import system_prompt

REQUIRED_TOP_LEVEL_KEYS = {"suppliers", "customers"}


def normalize_amounts(result: dict[str, Any]) -> dict[str, Any]:
    multiplier = resolve_money_multiplier(result.get("source_unit"))
    for side in ("suppliers", "customers"):
        partners = [p for p in result.get(side) or [] if isinstance(p, dict) and p.get("name")]
        for partner in partners:
            partner["value"] = scale_amount(partner.get("value"), multiplier)
        result[side] = partners
    result["source_unit"] = "dong"
    return result


def build_business_model_extraction_chain(llm: Any):
    return build_extraction_chain(
        system_prompt("business_model_extraction", industry_list=industry.prompt_list()), llm)


def extract_business_model_structured_data(chain: Any, filename: str, content: str, path: str = ""):
    return run_extraction(chain, filename, content, REQUIRED_TOP_LEVEL_KEYS,
                          "No business_model_extraction_llm configured.", normalize_amounts)
