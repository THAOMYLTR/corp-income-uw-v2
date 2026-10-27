"""LangGraph orchestrator for the corp-income flow (BRD Corp Income, items 1-4).

Same graph as the SME repo, minus what corporate legal checks do not need:

    discover_documents → classify_documents → evidence_gap_check
        → extract_documents → fetch_reference_data → single_corp_income → END

No routing LLM: ``process()`` takes the agent id directly (only
CORP_INCOME_AGENT exists here). The upload box a file sits in narrows what it
can be; keyword scoring classifies it, and an LLM is asked only when the
keyword pass is genuinely unsure. Four structured-extraction passes — one per
BRD item — turn each document into JSON, and the agent applies the BRD checks
to that JSON in code.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from src.llm_errors import explain_llm_error
from src.config import Config
from src.prompts import system_prompt
from src.types import (
    AgentName,
    ClassifiedDocument,
    UnderwritingGraphState,
    WorkflowMode,
    to_dict_list,
    truncate_text,
)
from src.utils.common import normalize_text
from src.utils.reading.extractors import extract_document_text_with_method
from src.agents.documents.document_classification import (
    FILENAME_KEYWORD_WEIGHT,
    build_document_classification_prompt,
    rule_classify_document,
)
from src.agents.documents.document_discovery import (
    box_ids,
    compute_file_hash,
    discover_documents,
    group_from_path,
)
from src.agents.documents.document_matrix import (
    agent_relevance_for_type,
    get_type,
    is_catch_all_box,
    is_cic_type,
    is_financial_type,
    is_plan_type,
    is_business_model_type,
    is_vat_type,
    is_legal_basic_type,
    is_legal_rep_type,
    is_liabilities_type,
    is_shareholders_type,
    load_matrix,
    primary_agent_for_type,
    resolve_loan_program,
    source_for_type,
)
from src.agents.extraction.legal_basic_extraction import (
    build_legal_basic_extraction_chain,
    extract_legal_basic_structured_data,
)
from src.agents.extraction.shareholders_extraction import (
    build_shareholders_extraction_chain,
    extract_shareholders_structured_data,
)
from src.agents.extraction.legal_rep_extraction import (
    build_legal_rep_extraction_chain,
    extract_legal_rep_structured_data,
)
from src.agents.extraction.liabilities_extraction import (
    build_liabilities_extraction_chain,
    extract_liabilities_structured_data,
)
from src.agents.extraction.financial_extraction import (
    build_financial_extraction_chain,
    extract_financial_structured_data,
)
from src.agents.extraction.vat_extraction import build_vat_extraction_chain, extract_vat_structured_data
from src.agents.extraction.cic_extraction import build_cic_extraction_chain, extract_cic_structured_data
from src.agents.extraction.plan_extraction import build_plan_extraction_chain, extract_plan_structured_data
from src.agents.extraction.business_model_extraction import (
    build_business_model_extraction_chain,
    extract_business_model_structured_data,
)
from src.agents.specialist import SPECIALIST_BY_AGENT

DEFAULT_ROUTE: AgentName = "CORP_INCOME_AGENT"
DEFAULT_WORKFLOW_MODE: WorkflowMode = "single_corp_income"


@dataclass(frozen=True)
class ExtractionPass:
    """One structured-extraction pass (one BRD item), declared once."""

    label: str
    tag: str
    flag_attr: str
    result_attr: str
    error_attr: str
    llm_attr: str
    build_chain: Callable[[Any], Any]
    extract: Callable[..., Any]
    # A required pass that fails stops the run instead of reporting on nothing.
    required: bool = False
    # [BRD 16/10] Config attribute used when ``llm_attr`` is not set, so a notebook
    # written before a pass existed still runs it.
    fallback_llm_attr: str = ""

    def failures(
        self, docs: list[ClassifiedDocument]
    ) -> list[tuple[ClassifiedDocument, str]]:
        """Documents this pass applies to that came back with no JSON."""

        return [
            (doc, getattr(doc, self.error_attr, "") or "No reason recorded.")
            for doc in docs
            if getattr(doc, self.flag_attr) and not getattr(doc, self.result_attr)
        ]

    @property
    def chain_attr(self) -> str:
        return f"{self.result_attr}_chain"


EXTRACTION_PASSES: tuple[ExtractionPass, ...] = (
    ExtractionPass(
        label="Mục 1 - Pháp lý cơ bản",
        tag="M1",
        flag_attr="is_legal_basic",
        result_attr="legal_basic_extraction",
        error_attr="legal_basic_extraction_error",
        llm_attr="legal_basic_extraction_llm",
        build_chain=build_legal_basic_extraction_chain,
        extract=extract_legal_basic_structured_data,
    ),
    ExtractionPass(
        label="Mục 2 - Cổ đông",
        tag="M2",
        flag_attr="is_shareholders",
        result_attr="shareholders_extraction",
        error_attr="shareholders_extraction_error",
        llm_attr="shareholders_extraction_llm",
        build_chain=build_shareholders_extraction_chain,
        extract=extract_shareholders_structured_data,
    ),
    ExtractionPass(
        label="Mục 3 - Người đại diện",
        tag="M3",
        flag_attr="is_legal_rep",
        result_attr="legal_rep_extraction",
        error_attr="legal_rep_extraction_error",
        llm_attr="legal_rep_extraction_llm",
        build_chain=build_legal_rep_extraction_chain,
        extract=extract_legal_rep_structured_data,
    ),
    ExtractionPass(
        label="Mục 4 - Nợ thuế, tranh chấp",
        tag="M4",
        flag_attr="is_liabilities",
        result_attr="liabilities_extraction",
        error_attr="liabilities_extraction_error",
        llm_attr="liabilities_extraction_llm",
        build_chain=build_liabilities_extraction_chain,
        extract=extract_liabilities_structured_data,
    ),
    ExtractionPass(
        label="Tài chính - BCTC",
        tag="M5",
        flag_attr="is_financial",
        result_attr="financial_extraction",
        error_attr="financial_extraction_error",
        llm_attr="financial_extraction_llm",
        build_chain=build_financial_extraction_chain,
        extract=extract_financial_structured_data,
    ),
    # [BRD 16/10] M6-M8 — VAT returns, CIC bulletins, business plan.
    ExtractionPass(
        label="Tờ khai VAT", tag="M6", flag_attr="is_vat",
        result_attr="vat_extraction", error_attr="vat_extraction_error",
        llm_attr="vat_extraction_llm", fallback_llm_attr="financial_extraction_llm",
        build_chain=build_vat_extraction_chain, extract=extract_vat_structured_data,
    ),
    ExtractionPass(
        label="CIC S10A/R20", tag="M7", flag_attr="is_cic",
        result_attr="cic_extraction", error_attr="cic_extraction_error",
        llm_attr="cic_extraction_llm", fallback_llm_attr="financial_extraction_llm",
        build_chain=build_cic_extraction_chain, extract=extract_cic_structured_data,
    ),
    ExtractionPass(
        label="Phương án kinh doanh", tag="M8", flag_attr="is_plan",
        result_attr="plan_extraction", error_attr="plan_extraction_error",
        llm_attr="plan_extraction_llm", fallback_llm_attr="financial_extraction_llm",
        build_chain=build_plan_extraction_chain, extract=extract_plan_structured_data,
    ),
    # [BRD 27/10] M9 — ngành TCB, đối tác đầu vào / đầu ra (mô hình HĐKD, mục 2).
    ExtractionPass(
        label="Mô hình HĐKD", tag="M9", flag_attr="is_business_model",
        result_attr="business_model_extraction", error_attr="business_model_extraction_error",
        llm_attr="business_model_extraction_llm", fallback_llm_attr="financial_extraction_llm",
        build_chain=build_business_model_extraction_chain, extract=extract_business_model_structured_data,
    ),
)


class _ExtractionBudget:
    """What one run may still spend on extraction."""

    __slots__ = ("calls_left", "chars_left", "skipped", "limit_hit")

    def __init__(self, max_calls: int, max_chars: int) -> None:
        self.calls_left = max_calls
        self.chars_left = max_chars
        self.skipped: list[str] = []
        self.limit_hit = ""

    def take(self, calls: int, chars: int, names: list[str]) -> bool:
        """Charge the budget, or record the skip and return False."""

        if calls > self.calls_left:
            self.limit_hit = self.limit_hit or "max_extraction_calls"
        elif chars > self.chars_left:
            self.limit_hit = self.limit_hit or "max_extraction_input_chars"
        else:
            self.calls_left -= calls
            self.chars_left -= chars
            return True
        self.skipped.extend(names)
        return False


class Supervisor:
    """Local supervisor without API, cache, or database dependencies."""

    RELEVANCE_SCORE = {"R": 2.0, "O": 1.0}

    # ── Construction ──────────────────────────────────────────────────────

    def __init__(self, config: Config):
        self.config = config
        self.document_classifier_chain = (
            self._build_document_classifier_chain()
            if config.document_llm
            else None
        )
        self._grouped_classifier_chains: dict[str, Any] = {}
        for pass_ in EXTRACTION_PASSES:
            # getattr(..., None): an older Config without the field still works.
            llm = getattr(config, pass_.llm_attr, None) or (
                getattr(config, pass_.fallback_llm_attr, None) if pass_.fallback_llm_attr else None)
            setattr(self, pass_.chain_attr,
                    pass_.build_chain(llm) if llm else None)
        self.workflow_graph = self._build_workflow_graph()

    def _build_workflow_graph(self):
        """Build the deterministic LangGraph workflow."""

        workflow = StateGraph(UnderwritingGraphState)
        workflow.add_node("discover_documents", self._graph_discover_documents)
        workflow.add_node("classify_documents", self._graph_classify_documents)
        workflow.add_node("evidence_gap_check", self._graph_evidence_gap_check)
        workflow.add_node("extract_documents", self._graph_extract_documents)
        workflow.add_node("fetch_reference_data", self._graph_fetch_reference_data)
        workflow.add_node("single_corp_income", self._graph_run_corp_income)

        workflow.set_entry_point("discover_documents")
        workflow.add_edge("discover_documents", "classify_documents")
        workflow.add_edge("classify_documents", "evidence_gap_check")
        workflow.add_conditional_edges(
            "evidence_gap_check",
            self._graph_stop_if_answered,
            {"blocked": END, "continue": "extract_documents"},
        )
        workflow.add_conditional_edges(
            "extract_documents",
            self._graph_stop_if_answered,
            {"blocked": END, "continue": "fetch_reference_data"},
        )
        workflow.add_conditional_edges(
            "fetch_reference_data",
            self._graph_select_workflow_branch,
            {"single_corp_income": "single_corp_income"},
        )
        workflow.add_edge("single_corp_income", END)
        return workflow.compile()

    # ── Graph nodes, in the order the workflow runs them ──────────────────

    def _graph_discover_documents(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """Discover supported files from the provided input paths."""

        input_paths = state.get("input_paths") or []
        files = discover_documents(input_paths, self.config.max_files)
        steps = state.get("steps", [])
        steps.append(f"Discovered {len(files)} supported file(s)")

        in_box: list[str] = []
        outside: list[str] = []
        for path in files:
            if group_from_path(path):
                in_box.append(path)
            else:
                outside.append(os.path.basename(path))
        if outside:
            steps.append(
                f"WARNING: skipped {len(outside)} file(s) under no upload "
                f"box: {', '.join(sorted(outside)[:10])}"
                f"{' …' if len(outside) > 10 else ''}. Every file must sit in "
                f"one of the {len(box_ids())} box folders: "
                f"{', '.join(sorted(box_ids()))}."
            )

        return {
            **state,
            "files": in_box,
            "skipped_outside_box": outside,
            "steps": steps,
        }

    def _graph_classify_documents(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """Extract and classify uploaded documents."""

        steps = state.get("steps", [])
        loan_program = resolve_loan_program(state.get("loan_program", ""))
        steps.append(f"Loan program: {loan_program}")
        documents = self._prepare_documents(
            state.get("files") or [],
            steps,
            loan_program,
        )
        return {
            **state,
            "loan_program": loan_program,
            "documents": documents,
            "document_summary": self._format_document_summary(documents),
        }

    def _graph_evidence_gap_check(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """Stop before any LLM extraction when the dossier cannot answer item 1."""

        decision = state.get("decision") or {}
        documents = state.get("documents") or []
        steps = state.get("steps", [])
        gap_analysis = self._analyze_evidence_gaps(documents, state.get("reference_data") or {})
        execution_plan = self._build_execution_plan(decision, gap_analysis)
        steps.append("Built evidence gap analysis")
        steps.append("Built LangGraph execution plan")
        for item in gap_analysis["missing_evidence"]:
            steps.append(f"Missing evidence ({item['severity']}): {item['reason']}")
        if not execution_plan.get("can_answer_now", True):
            response = self._missing_evidence_response(
                gap_analysis,
                state.get("skipped_outside_box") or [] if not documents else [],
            )
            return {
                **state,
                "gap_analysis": gap_analysis,
                "execution_plan": execution_plan,
                "steps": steps,
                "output_state": self._build_state(
                    response,
                    "EVIDENCE_GAP_CHECK",
                    decision,
                    documents,
                    execution_plan,
                    gap_analysis,
                    steps + ["Stopped before extraction because required evidence is missing"],
                    loan_program=state.get("loan_program", ""),
                ),
            }
        return {
            **state,
            "gap_analysis": gap_analysis,
            "execution_plan": execution_plan,
            "steps": steps,
        }

    @staticmethod
    def _graph_stop_if_answered(
        state: UnderwritingGraphState,
    ) -> str:
        """Whether a node has already produced the run's answer."""

        return "blocked" if state.get("output_state") else "continue"

    def _graph_extract_documents(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """Run the four BRD extraction passes on the documents each applies to."""

        documents = state.get("documents") or []
        steps = state.get("steps", [])
        budget = _ExtractionBudget(
            self.config.max_extraction_calls,
            self.config.max_extraction_input_chars,
        )
        for pass_ in EXTRACTION_PASSES:
            self._run_structured_extraction(
                documents,
                steps,
                pass_=pass_,
                chain=getattr(self, pass_.chain_attr),
                budget=budget,
            )
        if budget.skipped:
            steps.append(
                f"Extraction budget {budget.limit_hit} reached — "
                f"{len(budget.skipped)} document(s) not extracted: "
                f"{', '.join(sorted(set(budget.skipped)))}. Raise the limit in "
                f"Config or submit fewer files."
            )

        failed = [
            (pass_, doc, why)
            for pass_ in EXTRACTION_PASSES
            if pass_.required
            for doc, why in pass_.failures(documents)
        ]
        if failed:
            steps.append(
                f"Stopped after extraction: {len(failed)} required extraction(s) failed"
            )
            return {
                **state,
                "documents": documents,
                "steps": steps,
                "output_state": self._build_state(
                    self._failed_extraction_response(failed),
                    "EXTRACTION_FAILED",
                    state.get("decision") or {},
                    documents,
                    state.get("execution_plan") or {},
                    state.get("gap_analysis") or {},
                    steps,
                    loan_program=state.get("loan_program", ""),
                ),
            }
        return {
            **state,
            "documents": documents,
            "document_summary": self._format_document_summary(documents),
            "steps": steps,
        }

    def _graph_fetch_reference_data(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """BRD B2/B3/B4: internal data, external data and the watchlist.

        Handed in by the caller (``process(internal_data=…, external_data=…,
        watchlist=…)``) until the BCDE/BEP, Cổng ĐKDN and AML/BL/WL systems are
        connected; this node is where those queries will go.
        """

        steps = state.get("steps", [])
        reference = state.get("reference_data") or {}
        for key, label in (("internal_data", "internal data"), ("external_data", "external data")):
            items = sorted((reference.get(key) or {}).keys())
            steps.append(f"Reference {label}: {', '.join(items) if items else 'none provided'}")
        steps.append(f"Watchlist entries: {len(reference.get('watchlist') or [])}")
        return {**state, "steps": steps}

    @staticmethod
    def _graph_select_workflow_branch(
        state: UnderwritingGraphState,
    ) -> WorkflowMode:
        """Route graph execution by deterministic workflow mode."""

        return state.get("workflow_mode", DEFAULT_WORKFLOW_MODE)

    def _graph_run_corp_income(
        self,
        state: UnderwritingGraphState,
    ) -> UnderwritingGraphState:
        """Run the corp-income agent: BRD checks and the report."""

        steps = state.get("steps", [])
        steps.append("Running CORP_INCOME_AGENT")
        agent = SPECIALIST_BY_AGENT[DEFAULT_ROUTE](getattr(self.config, "report_writer_llm", None))
        try:
            analysis = agent.analyze(
                state.get("documents") or [],
                state.get("reference_data") or {},
                loan_date=state.get("loan_date"),
                borrower_names=state.get("borrower_names") or [],
            )
        except ValueError as exc:  # malformed internal/external data
            output = self._build_state(
                f"## Không thể tạo báo cáo\n\n{exc}",
                "INPUT_ERROR",
                state.get("decision") or {},
                state.get("documents") or [],
                state.get("execution_plan") or {},
                state.get("gap_analysis") or {},
                steps + [f"Stopped: {exc}"],
                loan_program=state.get("loan_program", ""),
            )
            output["status"] = "error"
            return {**state, "output_state": output}

        for number, item in analysis["items"].items():
            steps.append(f"Mục {number}: {item['conclusion']}")
        meta = analysis["meta"]
        steps.append(
            f"Template: {len(meta['code_placeholders'])} ô điền từ hồ sơ/tính toán, "
            f"{len(meta['llm_placeholders'])} ô do LLM viết (nhận xét, HĐKD, CIC, kết luận)"
        )
        for warning in analysis["financials"]["warnings"]:
            steps.append(f"Tài chính: {warning}")
        steps.append(f"Phân nhóm: {analysis['corp_group']['group']} — {analysis['corp_group']['finance']}; "
                     f"{analysis['corp_group']['bureau']}")
        if analysis.get("credit_assessment"):
            steps.append(f"Nhận định tín dụng: {analysis['credit_assessment'].get('quyet_dinh')} — "
                         f"{analysis['credit_assessment'].get('tom_tat', '')}")
        if meta["writer_error"]:
            steps.append(f"WARNING: {meta['writer_error']}")
        output = self._build_state(
            analysis["response"],
            DEFAULT_ROUTE,
            state.get("decision") or {},
            state.get("documents") or [],
            state.get("execution_plan") or {},
            state.get("gap_analysis") or {},
            steps + ["Built final response"],
            loan_program=state.get("loan_program", ""),
            corp_income={key: analysis[key] for key in
                         ("meta", "items", "financials", "income_estimate", "cic", "corp_group",
                          "credit_assessment", "records", "documents")},
        )
        return {**state, "output_state": output}

    # ── Entry point ───────────────────────────────────────────────────────

    def process(
        self,
        input_paths: list[str] | None = None,
        agent: str = DEFAULT_ROUTE,
        loan_program: str = "",
        loan_date: str | None = None,
        borrower_names: list[str] | None = None,
        internal_data: dict[str, Any] | None = None,
        external_data: dict[str, Any] | None = None,
        watchlist: list[dict[str, Any]] | None = None,
        annual_lt_principal: float | None = None,
    ) -> dict[str, Any]:
        """Run one local notebook request through the workflow.

        loan_date      the 12-month checks end here (dd/mm/yyyy; default today)
        borrower_names individual borrower(s) of this loan (BRD item-2 warning)
        internal_data  {item: JSON} from BCDE/BEP/DBX; external_data: Cổng ĐKDN/thuế/BHXH
                       (item = legal_basic | shareholders | legal_rep | liabilities)
        watchlist      [{"name", "tax_code", "id_number", "list": "AML|BL|WL"}]
        annual_lt_principal  [BRD 16/10] nghĩa vụ trả gốc TDH hàng năm của DN (đồng), for
                       "LNST sử dụng để trả nghĩa vụ TDH"; None = chưa có (tính 0, ghi chú)
        """

        initial_state: UnderwritingGraphState = {
            "input_paths": input_paths or [],
            "loan_program": loan_program,
            "loan_date": loan_date or "",
            "borrower_names": borrower_names or [],
            "reference_data": {
                "internal_data": internal_data or {},
                "external_data": external_data or {},
                "watchlist": watchlist or [],
                "annual_lt_principal": annual_lt_principal,
            },
            "decision": self._decision_for(agent),
            "workflow_mode": self._workflow_mode_for_route(agent),
            "steps": ["Received request"],
        }
        result = self.workflow_graph.invoke(initial_state)
        output_state = result.get("output_state")
        if output_state:
            return output_state
        return self._build_state(
            "Workflow graph finished without an output state.",
            "WORKFLOW_GRAPH",
            steps=result.get("steps", []),
        )

    # ── Reading and classifying the uploaded documents ────────────────────

    # [Sửa 20/10] Files are read + classified, and extraction passes run, several at a
    # time instead of one by one (49 files took 34 min). OCR and LLM calls wait on other
    # processes / the network, so threads overlap them. Order of documents and of the step
    # log is kept. FILE_WORKERS: files read at once (each file also OCRs its pages in
    # parallel, so keep it small). LLM_WORKERS: LLM calls at once (raise only if the
    # serving endpoint does not answer 429 "rate limit").
    @staticmethod
    def _workers(env: str, default: int) -> int:
        try:
            return max(1, int(os.getenv(env, str(default))))
        except ValueError:
            return default

    def _prepare_documents(
        self,
        files: list[str],
        steps: list[str],
        loan_program: str = "",
    ) -> list[ClassifiedDocument]:
        unique: list[tuple[str, str]] = []
        seen_hashes: set[str] = set()
        for file_path in files:
            file_hash = compute_file_hash(file_path)
            if file_hash in seen_hashes:
                steps.append(f"Skipped duplicate document: {Path(file_path).name}")
                continue
            seen_hashes.add(file_hash)
            unique.append((file_path, file_hash))
        with ThreadPoolExecutor(max_workers=self._workers("FILE_WORKERS", 3)) as pool:
            results = list(pool.map(lambda item: self._prepare_one(*item, loan_program), unique))
        documents = []
        for document, file_steps in results:
            steps.extend(file_steps)
            documents.append(document)
        return documents

    def _prepare_one(
        self,
        file_path: str,
        file_hash: str,
        loan_program: str = "",
    ) -> tuple[ClassifiedDocument, list[str]]:
        """Read, classify and flag one file; its own step lines (merged in order by the caller)."""

        steps: list[str] = []
        filename = Path(file_path).name
        try:
            steps.append(f"Extracting document content: {filename}")
            content, read_method = extract_document_text_with_method(
                file_path,
                ocr_timeout_seconds=float(os.getenv("OCR_TIMEOUT_SECONDS", "120")),
            )
            extraction_status = "success"
            extraction_error = ""
        except Exception as exc:
            content = f"[Document text extraction failed for {filename}: {exc}]"
            read_method = ""
            extraction_status = "failed"
            extraction_error = f"{type(exc).__name__}: {exc}"

        content = truncate_text(content, self.config.max_chars_per_document)
        declared_group = group_from_path(file_path)
        classification = self._classify_document(filename, content, declared_group)
        document_type = classification.get("document_type", "")
        if declared_group:
            owner_type = self._cross_box_owner(filename, content, declared_group)
            if owner_type:
                steps.append(
                    f"Possible wrong upload box: {filename} was put in "
                    f"'{declared_group}' but its content matches "
                    f"'{owner_type.short_label}' from '{owner_type.group_id}'."
                )
        agent_relevance = agent_relevance_for_type(document_type, loan_program or None)
        relevant_agents = sorted(agent_relevance)
        matched = get_type(document_type)
        flags = {
            "is_legal_basic": is_legal_basic_type(document_type),
            "is_shareholders": is_shareholders_type(document_type),
            "is_legal_rep": is_legal_rep_type(document_type),
            "is_liabilities": is_liabilities_type(document_type),
            "is_financial": is_financial_type(document_type),
            "is_vat": is_vat_type(document_type),
            "is_cic": is_cic_type(document_type),
            "is_plan": is_plan_type(document_type),
            "is_business_model": is_business_model_type(document_type),
        }
        tags = [p.tag for p in EXTRACTION_PASSES if flags[p.flag_attr]]
        steps.append(
            f"Classified document: {filename} -> "
            + (f"{document_type} " if document_type else "(no type matched) ")
            + f"(read by {read_method or '—'})"
            + (f" [{', '.join(tags)}]" if tags else "")
        )
        document = (
            ClassifiedDocument(
                path=file_path,
                filename=filename,
                content=content,
                agent=primary_agent_for_type(document_type) or "GENERAL_CONTEXT",
                reasoning=classification.get("reasoning", ""),
                confidence=float(classification.get("confidence", 0.0)),
                file_hash=file_hash,
                source_description=(
                    str(classification.get("description", "")).strip()
                    or (matched.short_label if matched else "")
                ),
                declared_group=declared_group,
                read_method=read_method,
                extraction_status=extraction_status,
                extraction_error=extraction_error,
                classifier_error_type=classification.get("classifier_error_type", ""),
                classifier_error=classification.get("classifier_error", ""),
                document_type=document_type,
                document_group=matched.group_id if matched else "",
                source=source_for_type(document_type),
                type_scores=classification.get("scores", {}),
                agent_relevance=agent_relevance,
                loan_program=loan_program,
                agent_scores={
                    name: self.RELEVANCE_SCORE[level]
                    for name, level in agent_relevance.items()
                },
                relevant_agents=relevant_agents,
                **flags,
            )
        )
        return document, steps

    @staticmethod
    def _document_sample(content: str, limit: int = 2_400) -> str:
        """Sample head+middle+tail so classification is not cover-page biased."""

        text = content or ""
        if len(text) <= limit:
            return text
        chunk = limit // 3
        head = text[:chunk]
        mid_start = max(chunk, (len(text) - chunk) // 2)
        middle = text[mid_start:mid_start + chunk]
        tail = text[-chunk:]
        return f"{head}\n...\n{middle}\n...\n{tail}"

    @staticmethod
    def _cross_box_owner(filename: str, content: str, declared_group: str):
        """The type the file's own content points at, when that is another box."""

        unrestricted = rule_classify_document(filename, content, "")
        owner_type = get_type(unrestricted.get("document_type", ""))
        if not owner_type or owner_type.group_id == declared_group:
            return None
        best = max(unrestricted.get("scores", {}).values(), default=0)
        return owner_type if best >= FILENAME_KEYWORD_WEIGHT else None

    def _classify_document(
        self,
        filename: str,
        content: str,
        group_id: str = "",
    ) -> dict[str, Any]:
        rule = rule_classify_document(filename, content, group_id)
        if is_catch_all_box(group_id):
            # Nothing to break a tie between, so no LLM call: the box declares
            # that whatever lands in it is general context.
            return rule
        threshold = (
            self.config.document_classifier_grouped_confidence_threshold
            if group_id
            else self.config.document_classifier_rule_confidence_threshold
        )
        if rule["document_type"] and (
            rule["confidence"] >= threshold
            or rule["routing_unambiguous"]
            or rule["filename_decisive"]
        ):
            return rule

        chain = self._classifier_chain_for(group_id)
        if chain:
            try:
                result = chain.invoke(
                    {
                        "filename": filename,
                        "content_sample": (
                            self._document_sample(content)
                            or "No text extracted from the document."
                        ),
                    }
                )
                document_type = result.get("document_type") or ""
                if document_type and get_type(document_type) is None:
                    return rule
                result["document_type"] = document_type
                result["scores"] = rule.get("scores", {})
                return result
            except Exception as exc:
                rule["classifier_error_type"] = type(exc).__name__
                rule["classifier_error"] = explain_llm_error(exc)
                rule["reasoning"] = (
                    "Fallback keyword classification because document "
                    "classifier failed."
                )
        return rule

    def _classifier_chain_for(self, group_id: str):
        """The classifier chain whose catalogue matches this document's box."""

        if not group_id or not self.config.document_llm:
            return self.document_classifier_chain
        if group_id not in self._grouped_classifier_chains:
            self._grouped_classifier_chains[group_id] = (
                self._build_document_classifier_chain(group_id)
            )
        return self._grouped_classifier_chains[group_id]

    def _build_document_classifier_chain(self, group_id: str = ""):
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=build_document_classification_prompt(group_id)),
                ("human", system_prompt("document_classification_user")),
            ]
        )
        return prompt | self.config.document_llm | JsonOutputParser()

    @classmethod
    def _extraction_tags(cls, doc: ClassifiedDocument) -> str:
        """Mark which structured extractions ran on a document, and which failed."""

        tags = []
        for pass_ in EXTRACTION_PASSES:
            if not getattr(doc, pass_.flag_attr):
                continue
            if getattr(doc, pass_.error_attr):
                tags.append(f" [{pass_.tag}, extraction failed]")
            else:
                tags.append(f" [{pass_.tag}]")
        return "".join(tags)

    @classmethod
    def _format_document_summary(cls, documents: list[ClassifiedDocument]) -> str:
        lines = []
        for doc in documents:
            lines.append(
                f"- {doc.filename}: {doc.document_type or '-'} ({doc.source})"
                f"{cls._extraction_tags(doc)} (confidence={doc.confidence:.2f}, "
                f"read={doc.read_method or '-'}, extraction={doc.extraction_status})"
            )
        return "\n".join(lines)

    # ── Structured extraction ─────────────────────────────────────────────

    def _run_structured_extraction(
        self,
        documents: list[ClassifiedDocument],
        steps: list[str],
        *,
        pass_: ExtractionPass,
        chain: Any,
        budget: "_ExtractionBudget | None" = None,
    ) -> None:
        """Run one structured-extraction pass over the documents it applies to."""

        targets = [doc for doc in documents if getattr(doc, pass_.flag_attr)]
        if not targets:
            return
        if not chain:
            message = f"No {pass_.llm_attr} configured."
            for doc in targets:
                setattr(doc, pass_.error_attr, message)
            steps.append(
                f"Skipped {pass_.label} extraction for {len(targets)} document(s): {message}"
            )
            return
        if budget is not None:
            names = [d.filename for d in targets]
            chars = sum(len(d.content) for d in targets)
            if not budget.take(len(targets), chars, names):
                for doc in targets:
                    setattr(doc, pass_.error_attr, f"Skipped: {budget.limit_hit} reached.")
                steps.append(
                    f"Skipped {pass_.label} extraction for {len(targets)} document(s): "
                    f"{budget.limit_hit} reached."
                )
                return
        with ThreadPoolExecutor(max_workers=self._workers("LLM_WORKERS", 4)) as pool:
            answers = list(pool.map(
                lambda doc: pass_.extract(chain, doc.filename, doc.content, doc.path), targets))
        for doc, (result, error) in zip(targets, answers):
            setattr(doc, pass_.result_attr, result)
            setattr(doc, pass_.error_attr, error)
            steps.append(
                f"{pass_.label} extraction: {doc.filename} -> "
                + ("ok" if result is not None else f"failed: {error}")
            )

    # ── Routing: the screen's choice, checked ─────────────────────────────

    @classmethod
    def _decision_for(cls, agent: str) -> dict[str, Any]:
        """The decision record for an agent the screen chose."""

        if agent not in SPECIALIST_BY_AGENT:
            raise ValueError(
                f"unknown agent {agent!r}; expected one of {sorted(SPECIALIST_BY_AGENT)}"
            )
        return {
            "route": agent,
            "workflow_mode": cls._workflow_mode_for_route(agent),
            "reasoning": "Chosen on the upload screen.",
            "confidence": 1.0,
        }

    @staticmethod
    def _workflow_mode_for_route(route: str) -> WorkflowMode:
        """Map a route to the deterministic workflow branch."""

        return {"CORP_INCOME_AGENT": "single_corp_income"}.get(route, DEFAULT_WORKFLOW_MODE)

    # ── Evidence gaps: what is missing before extraction is worth paying ──

    def _analyze_evidence_gaps(
        self,
        documents: list[ClassifiedDocument],
        reference_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Item 1 needs at least one source of legal facts; mandatory types are named."""

        reference_data = reference_data or {}
        inventory: dict[str, list[str]] = {
            "legal_documents": [], "shareholder_documents": [], "legal_rep_documents": [],
            "liability_documents": [], "general_context": [],
        }
        buckets = (("is_legal_basic", "legal_documents"), ("is_shareholders", "shareholder_documents"),
                   ("is_legal_rep", "legal_rep_documents"), ("is_liabilities", "liability_documents"))
        for doc in documents:
            matched = [bucket for flag, bucket in buckets if getattr(doc, flag)]
            for bucket in matched or ["general_context"]:
                inventory[bucket].append(doc.filename)

        provided_legal = any(
            "legal_basic" in (reference_data.get(key) or {}) for key in ("internal_data", "external_data")
        )
        missing = []
        if not inventory["legal_documents"] and not provided_legal:
            missing.append({
                "type": "legal_documents",
                "severity": "high",
                "can_continue_without_it": False,
                "reason": (
                    "Không có tài liệu nào cho BRD mục 1 (GCN ĐKDN, điều lệ, sổ cổ đông, "
                    "bản tra cứu Cổng ĐKDN, báo cáo thực địa) và không có external/internal data."
                ),
            })
        for bucket, label in (("liability_documents", "mục 4 (thông báo thuế, BHXH, xử phạt, tranh chấp)"),):
            if not inventory[bucket]:
                missing.append({
                    "type": bucket, "severity": "medium", "can_continue_without_it": True,
                    "reason": f"Chưa có tài liệu cho {label} — mục 4 sẽ được báo 'cần làm rõ'.",
                })
        for group_id, group_label, absent in self._missing_required_types(documents):
            missing.append({
                "type": f"upload_box:{group_id}", "severity": "medium", "can_continue_without_it": True,
                "reason": f"Hộp \"{group_label}\" thiếu tài liệu bắt buộc: {', '.join(absent)}.",
            })
        can_proceed = not any(
            item["severity"] == "high" and not item["can_continue_without_it"] for item in missing
        )
        available = ", ".join(f"{b}: {len(f)}" for b, f in inventory.items() if f) or "none"
        return {
            "evidence_inventory": inventory,
            "missing_evidence": missing,
            "can_proceed": can_proceed,
            "summary": (
                f"Available evidence: {available}. Missing evidence: "
                f"{', '.join(item['type'] for item in missing) or 'none'}."
            ),
        }

    @staticmethod
    def _missing_required_types(
        documents: list[ClassifiedDocument],
    ) -> list[tuple[str, str, list[str]]]:
        """Per upload box: (id, label, short labels of the mandatory types absent)."""

        present = {doc.document_type for doc in documents if doc.document_type}
        boxes: dict[str, tuple[str, list[str]]] = {}
        for doc_type in load_matrix().types.values():
            if "bat buoc" not in normalize_text(doc_type.requirement.get("cap_moi", "")):
                continue
            if doc_type.id in present:
                continue
            _, absent = boxes.setdefault(doc_type.group_id, (doc_type.group_label, []))
            absent.append(doc_type.short_label)
        return [(gid, label, absent) for gid, (label, absent) in sorted(boxes.items())]

    @staticmethod
    def _failed_extraction_response(
        failed: list[tuple[Any, ClassifiedDocument, str]],
    ) -> str:
        """The answer when a required extraction produced nothing."""

        lines = [f"- **{doc.filename}** ({pass_.label}): {why}" for pass_, doc, why in failed]
        return (
            "## Không thể tạo báo cáo\n\n"
            "Việc trích xuất dữ liệu có cấu trúc không thành công với các tài liệu dưới đây.\n\n"
            "### Tài liệu trích xuất không thành công\n" + "\n".join(lines)
            + "\n\nHãy kiểm tra tài liệu đầu vào và thử lại."
        )

    @staticmethod
    def _missing_evidence_response(
        gap_analysis: dict[str, Any],
        skipped_outside_box: list[str] | None = None,
    ) -> str:
        """The answer when required evidence is missing."""

        skipped = skipped_outside_box or []
        if skipped:
            shown = ", ".join(sorted(skipped)[:10])
            return (
                "## Không thể tạo báo cáo — hồ sơ chưa được gắn loại tài liệu\n\n"
                f"Đã tìm thấy {len(skipped)} file nhưng không file nào nằm trong "
                "thư mục loại hồ sơ, vì vậy không file nào được xử lý. Đây là lỗi ở "
                "bước upload hồ sơ, **không phải do thiếu tài liệu**.\n\n"
                f"### File bị bỏ qua\n- {shown}{' …' if len(skipped) > 10 else ''}\n\n"
                "### Cách xử lý\n"
                "Đặt mỗi file vào đúng thư mục loại hồ sơ. Thư mục hợp lệ: "
                f"{', '.join(sorted(box_ids()))}."
            )
        lines = [
            f"- **{item.get('type', 'evidence')}**: {item.get('reason', 'Missing evidence.')}"
            for item in gap_analysis.get("missing_evidence", [])
        ]
        return (
            "## Cần bổ sung thêm tài liệu\n\n"
            "Chưa thể tiếp tục vì đang thiếu thông tin bắt buộc.\n\n"
            "### Tài liệu cần bổ sung\n" + ("\n".join(lines) if lines else "- Chưa xác định.")
        )

    def _build_execution_plan(
        self,
        decision: dict[str, Any],
        gap_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        route = decision["route"]
        workflow_mode = decision.get("workflow_mode", self._workflow_mode_for_route(route))
        return {
            "plan_version": "notebook-local-v1",
            "intent": workflow_mode,
            "route": route,
            "workflow_mode": workflow_mode,
            "required_agents": [route],
            "execution_order": [p.label for p in EXTRACTION_PASSES] + ["legal_checks", "report"],
            "can_answer_now": bool(gap_analysis.get("can_proceed", True)),
            "missing_information": gap_analysis.get("missing_evidence", []),
            "reasoning": decision.get("reasoning", ""),
        }

    # ── Output ────────────────────────────────────────────────────────────

    def _classifications_for_state(
        self,
        documents: list[ClassifiedDocument],
    ) -> list[dict[str, Any]]:
        """Documents as data, with the OCR text bounded (full text: ocr/ folder)."""

        limit = self.config.result_content_char_limit
        records = to_dict_list(documents)
        if limit <= 0:
            return records
        for record in records:
            content = record.get("content")
            if isinstance(content, str):
                record["content"] = truncate_text(content, limit)
        return records

    def _build_state(
        self,
        response: str,
        agent_name: str,
        decision: dict[str, Any] | None = None,
        documents: list[ClassifiedDocument] | None = None,
        execution_plan: dict[str, Any] | None = None,
        gap_analysis: dict[str, Any] | None = None,
        steps: list[str] | None = None,
        loan_program: str = "",
        corp_income: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "response": response,
            "agent_name": agent_name,
            "decision": decision or {},
            "loan_program": loan_program,
            "document_classifications": self._classifications_for_state(documents or []),
            # Full OCR / text of every file, keyed by filename — written to
            # ocr/<file>.txt by the notebook so a wrong field can be traced back.
            "ocr_text": {doc.filename: doc.content for doc in documents or []},
            "corp_income": corp_income or {},
            "execution_plan": execution_plan or {},
            "gap_analysis": gap_analysis or {},
            "steps": steps or [],
        }
