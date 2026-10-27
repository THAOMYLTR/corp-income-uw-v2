"""Shared types and small helpers for the corp-income workflow."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict


AgentName = Literal[
    "CORP_INCOME_AGENT",
]
WorkflowMode = Literal[
    "single_corp_income",
]
DocumentAgentName = Literal[
    "CORP_INCOME_AGENT",
    "GENERAL_CONTEXT",
]
SPECIALIST_DOCUMENT_AGENTS = frozenset({
    "CORP_INCOME_AGENT",
})
VALID_DOCUMENT_AGENTS = SPECIALIST_DOCUMENT_AGENTS | {"GENERAL_CONTEXT"}


@dataclass
class ClassifiedDocument:
    """Extracted document text plus its target agent classification."""

    path: str
    filename: str
    content: str
    agent: DocumentAgentName
    reasoning: str
    confidence: float
    file_hash: str = ""
    source_description: str = ""
    declared_group: str = ""
    # How the text was obtained: pdf_text_layer | ocr_pdf | ocr_image | docx |
    # spreadsheet | text. Written to the run log so a wrong field can be traced
    # back to how the file was read.
    read_method: str = ""
    extraction_status: str = "success"
    extraction_error: str = ""
    classifier_error_type: str = ""
    classifier_error: str = ""
    document_type: str = ""
    document_group: str = ""
    # customer = KH cung cấp | field = báo cáo thực địa | external = tra cứu
    # Cổng ĐKDN/thuế/BHXH | internal = hệ thống nội bộ. The BRD checks compare
    # facts BETWEEN sources, so every record carries this.
    source: str = "customer"
    type_scores: dict[str, float] = field(default_factory=dict)
    agent_relevance: dict[str, str] = field(default_factory=dict)
    loan_program: str = ""
    agent_scores: dict[str, float] = field(default_factory=dict)
    relevant_agents: list[str] = field(default_factory=list)
    # BRD Corp Income items 1-4 — one structured-extraction pass each.
    is_legal_basic: bool = False
    is_shareholders: bool = False
    is_legal_rep: bool = False
    is_liabilities: bool = False
    is_financial: bool = False
    # [BRD 16/10] new passes M6-M8
    is_vat: bool = False
    is_cic: bool = False
    is_plan: bool = False
    # [BRD 27/10] pass M9 — mô hình HĐKD
    is_business_model: bool = False
    legal_basic_extraction: dict[str, Any] | None = None
    legal_basic_extraction_error: str = ""
    shareholders_extraction: dict[str, Any] | None = None
    shareholders_extraction_error: str = ""
    legal_rep_extraction: dict[str, Any] | None = None
    legal_rep_extraction_error: str = ""
    liabilities_extraction: dict[str, Any] | None = None
    liabilities_extraction_error: str = ""
    financial_extraction: dict[str, Any] | None = None
    financial_extraction_error: str = ""
    vat_extraction: dict[str, Any] | None = None
    vat_extraction_error: str = ""
    cic_extraction: dict[str, Any] | None = None
    cic_extraction_error: str = ""
    plan_extraction: dict[str, Any] | None = None
    plan_extraction_error: str = ""
    business_model_extraction: dict[str, Any] | None = None
    business_model_extraction_error: str = ""


class UnderwritingGraphState(TypedDict, total=False):
    """State passed between LangGraph workflow nodes."""

    input_paths: list[str]
    files: list[str]
    skipped_outside_box: list[str]
    loan_program: str
    loan_date: str
    borrower_names: list[str]
    documents: list[ClassifiedDocument]
    document_routes: set[str]
    document_summary: str
    decision: dict[str, Any]
    workflow_mode: WorkflowMode
    gap_analysis: dict[str, Any]
    # internal_data / external_data / watchlist handed in by the caller
    # (BRD steps B2, B3, B4).
    reference_data: dict[str, Any]
    execution_plan: dict[str, Any]
    steps: list[str]
    output_state: dict[str, Any]


def to_dict_list(items: list[Any]) -> list[dict[str, Any]]:
    """Convert dataclasses to JSON-friendly dictionaries."""

    return [
        asdict(item) if hasattr(item, "__dataclass_fields__") else item
        for item in items
    ]


def extract_text_from_agent_output(output: Any) -> str:
    """Normalize LangChain agent or chain output into plain text."""

    if output is None:
        return ""
    if isinstance(output, str):
        return output
    if hasattr(output, "content"):
        return str(output.content)
    if isinstance(output, dict):
        for key in ["response", "output", "content"]:
            if key in output:
                return extract_text_from_agent_output(output[key])
        messages = output.get("messages")
        if messages:
            return extract_text_from_agent_output(messages[-1])
    return str(output)


def truncate_text(text: str, limit: int) -> str:
    """Truncate long prompt/evidence blocks."""

    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"
