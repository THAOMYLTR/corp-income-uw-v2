"""Loader for the document routing matrix (src/agents/documents/document_matrix.yaml)."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.types import SPECIALIST_DOCUMENT_AGENTS
from src.utils.common import normalize_text


MATRIX_PATH = Path(__file__).resolve().parent / "document_matrix.yaml"

RELEVANCE_LEVELS = ("R", "O")
# Named only for the error message below; the scorer owns the real constant.
FILENAME_KEYWORD_WEIGHT = 3
DEFAULT_LOAN_PROGRAM = "KHDN"

PRIMARY_AGENT_PRECEDENCE = (
    "CORP_INCOME_AGENT",
)

# Where a document's facts come from. The BRD checks compare facts BETWEEN
# sources (a GCN against the national register, the register against the
# bank's own system), so every type declares one.
SOURCES = ("customer", "field", "external", "internal")

# [BRD 27/10] Agents of the document matrix. CIA (Corp Income Agent) is the one
# this repo runs, as CORP_INCOME_AGENT; the others name the report section that
# uses a document (LA mục 1, BA mục 2, FS mục 3, CR/RA mục 4, CP mục 5).
MATRIX_AGENTS = {
    "CIA": "Corp Income Agent",
    "LA": "Legal Assessment",
    "BA": "Business Activity",
    "FS": "Financial Statement",
    "RA": "Risk Assessment",
    "CP": "Credit Proposal",
    "CR": "Credit Relationship",
}
CIA_AGENT = "CORP_INCOME_AGENT"

_LEVEL_RANK = {"O": 1, "R": 2}

class DocumentMatrixError(RuntimeError):
    """Raised when the matrix file is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class DocumentType:
    """One row of the matrix: a kind of document and who consumes it."""

    id: str
    stt: str
    label: str
    short_label: str
    group_id: str
    group_stt: str
    group_label: str
    keywords: tuple[str, ...]
    filename_keywords: tuple[str, ...]
    agents: dict[str, dict[str, str]]
    primary_agent: str
    requirement: dict[str, str] = field(default_factory=dict)
    source: str = "customer"
    # [BRD 27/10] number on the document matrix, its agents, its validation rules.
    code: str = ""
    matrix_agents: tuple[str, ...] = ()
    validation: tuple[str, ...] = ()
    # BRD Corp Income items 1-4: which extraction passes run on this type.
    legal_basic_extraction: bool = False
    shareholders_extraction: bool = False
    legal_rep_extraction: bool = False
    liabilities_extraction: bool = False
    # Báo cáo tài chính → Phụ lục 01 mục 3 (tài chính doanh nghiệp).
    financial_extraction: bool = False
    # [BRD 16/10] tờ khai VAT (mục 3/5), bản tin CIC (mục 4), phương án kinh doanh (mục 5).
    vat_extraction: bool = False
    cic_extraction: bool = False
    plan_extraction: bool = False
    # [BRD 27/10] mục 2 — ngành TCB, đối tác đầu vào / đầu ra (mô hình HĐKD).
    business_model_extraction: bool = False

    @property
    def routing_signature(self) -> frozenset[str]:
        """The set of agents this type feeds, ignoring R/O and loan program."""
        return frozenset(self.agents)


@dataclass(frozen=True)
class DocumentMatrix:
    version: int
    loan_programs: tuple[str, ...]
    loan_program_labels: dict[str, str]
    types: dict[str, DocumentType]
    boxes: tuple[str, ...]
    box_labels: dict[str, str]
    catch_all_boxes: frozenset[str]


def _fail(message: str) -> None:
    raise DocumentMatrixError(f"{MATRIX_PATH.name}: {message}")


def _need(value: Any, kind: type, message: str) -> Any:
    """Return `value`, or refuse it for being absent, wrong-typed, or empty."""

    if not isinstance(value, kind) or not value:
        _fail(message)
    return value


def _parse_agents(
    raw: Any,
    programs: tuple[str, ...],
    where: str,
) -> dict[str, dict[str, str]]:
    """Expand the `agents` block into {agent: {program: level}}.

    Accepts a scalar level (same across every loan program) or an explicit
    per-program map. A partial map is rejected rather than back-filled: the
    whole point of splitting the four programs is that a future divergence must
    be stated, not guessed.

    An EMPTY mapping is allowed and means "no specialist consumes this type".
    That is not the same as deleting the type: the document is still recognised,
    still named correctly in the source list, and still counts toward the upload
    box it was filed in — it simply is not fed to anyone. Collateral documents
    sit here now that risk assessment is gone.
    """

    if raw is None or raw == {}:
        return {}
    if not isinstance(raw, dict):
        _fail(f"{where}: 'agents' must be a mapping")

    agents: dict[str, dict[str, str]] = {}
    for agent, value in raw.items():
        if agent not in SPECIALIST_DOCUMENT_AGENTS:
            _fail(
                f"{where}: unknown agent {agent!r}; expected one of "
                f"{sorted(SPECIALIST_DOCUMENT_AGENTS)}"
            )
        if isinstance(value, str):
            level = value.strip().upper()
            if level not in RELEVANCE_LEVELS:
                _fail(f"{where}/{agent}: level {value!r} must be R or O")
            agents[agent] = {program: level for program in programs}
            continue
        if isinstance(value, dict):
            missing = [p for p in programs if p not in value]
            extra = [p for p in value if p not in programs]
            if missing or extra:
                _fail(
                    f"{where}/{agent}: per-program map must list exactly "
                    f"{list(programs)}"
                    + (f"; missing {missing}" if missing else "")
                    + (f"; unknown {extra}" if extra else "")
                )
            levels = {}
            for program in programs:
                level = str(value[program]).strip().upper()
                if level not in RELEVANCE_LEVELS:
                    _fail(
                        f"{where}/{agent}/{program}: level "
                        f"{value[program]!r} must be R or O"
                    )
                levels[program] = level
            agents[agent] = levels
            continue
        _fail(f"{where}/{agent}: expected 'R'/'O' or a per-program mapping")
    return agents


def _parse_keywords(
    raw: Any,
    where: str,
    field: str,
    required: bool = True,
) -> list[str]:
    """One keyword list: non-empty strings, no duplicates.

    Duplicates are judged AFTER normalisation, because that is the form that
    gets scored. "tai khoan: 131" and "tai khoan 131" are different strings and
    the same keyword, and the pair sat in the matrix for all seven accounts —
    every hit on one counted twice.
    """

    if not required and not raw:
        return []
    raw = _need(raw, list, f"{where}: {field!r} must be a non-empty list")
    keywords: list[str] = []
    seen: dict[str, str] = {}
    for keyword in raw:
        text = str(keyword).strip()
        normalized = normalize_text(text)
        if not normalized:
            _fail(f"{where}: empty keyword in {field!r}")
        if normalized in seen:
            _fail(
                f"{where}: {text!r} and {seen[normalized]!r} in {field!r} are "
                f"the same keyword once normalised ({normalized!r})"
            )
        seen[normalized] = text
        keywords.append(text)
    return keywords


def _resolve_primary_agent(
    declared: str | None,
    agents: dict[str, dict[str, str]],
    where: str,
) -> str:
    """Pick the agent this document type is displayed as belonging to."""

    if declared:
        if declared not in SPECIALIST_DOCUMENT_AGENTS:
            _fail(f"{where}: unknown primary_agent {declared!r}")
        if declared in agents:
            return declared

    def _pick(level: str) -> str | None:
        for agent in PRIMARY_AGENT_PRECEDENCE:
            levels = agents.get(agent)
            if levels and level in levels.values():
                return agent
        return None

    # "" when nothing consumes the type. The caller turns that into
    # GENERAL_CONTEXT, which is where an unconsumed document belongs.
    return _pick("R") or _pick("O") or (sorted(agents)[0] if agents else "")


def _load(path: Path) -> DocumentMatrix:
    if not path.exists():
        _fail(f"matrix file not found at {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DocumentMatrixError(f"{path.name}: invalid YAML: {exc}") from exc
    _need(raw, dict, "top level must be a mapping")

    version = raw.get("version")
    if not isinstance(version, int):
        _fail("'version' must be an integer")

    raw_programs = _need(raw.get("loan_programs"), list,
                         "'loan_programs' must be a non-empty list")
    programs: list[str] = []
    program_labels: dict[str, str] = {}
    for entry in raw_programs:
        _need(entry, dict, "each loan_programs entry must be a mapping")
        _need(entry.get("id"), str, "each loan_programs entry needs an 'id'")
        program_id = str(entry["id"])
        if program_id in program_labels:
            _fail(f"duplicate loan program id {program_id!r}")
        programs.append(program_id)
        program_labels[program_id] = str(entry.get("label") or program_id)

    if DEFAULT_LOAN_PROGRAM not in programs:
        # A constant naming a programme the matrix no longer declares would
        # route every case against a column that does not exist.
        _fail(
            f"DEFAULT_LOAN_PROGRAM {DEFAULT_LOAN_PROGRAM!r} is not one of "
            f"{programs}"
        )

    raw_groups = _need(raw.get("groups"), list,
                       "'groups' must be a non-empty list")

    types: dict[str, DocumentType] = {}
    group_ids: set[str] = set()
    boxes: list[str] = []
    box_labels: dict[str, str] = {}
    catch_all_boxes: set[str] = set()
    for group in raw_groups:
        _need(group, dict, "each group must be a mapping")
        group_id = str(_need(group.get("id"), str, "each group needs an 'id'"))
        if group_id in group_ids:
            _fail(f"duplicate group id {group_id!r}")
        group_ids.add(group_id)

        boxes.append(group_id)
        box_labels[group_id] = str(group.get("label") or group_id)

        if group.get("catch_all"):
            if group.get("types"):
                _fail(
                    f"group {group_id!r}: a catch-all box classifies nothing, so "
                    f"it cannot declare 'types'"
                )
            catch_all_boxes.add(group_id)
            continue

        raw_types = _need(group.get("types"), list,
                          f"group {group_id!r}: 'types' must be a non-empty list")

        for entry in raw_types:
            _need(entry, dict, f"group {group_id!r}: each type must be a mapping")
            type_id = str(_need(entry.get("id"), str,
                                f"group {group_id!r}: a type is missing 'id'"))
            if type_id in types:
                _fail(f"duplicate document type id {type_id!r}")
            where = f"type {type_id!r}"

            label = str(_need(entry.get("label"), str,
                              f"{where}: 'label' is required")).strip()
            short_label = str(entry.get("short_label") or "").strip() or label

            keywords = _parse_keywords(entry.get("keywords"), where, "keywords")

            filename_keywords = _parse_keywords(
                entry.get("filename_keywords") or [],
                where,
                "filename_keywords",
                required=False,
            )
            both = sorted(
                {normalize_text(k) for k in keywords}
                & {normalize_text(k) for k in filename_keywords}
            )
            if both:
                _fail(
                    f"{where}: {both} appear in both 'keywords' and "
                    f"'filename_keywords'; a term in 'keywords' is already "
                    f"scored against the filename at {FILENAME_KEYWORD_WEIGHT}x"
                )

            agents = _parse_agents(entry.get("agents"), tuple(programs), where)
            source = str(entry.get("source") or "customer")
            if source not in SOURCES:
                _fail(f"{where}: source {source!r} must be one of {list(SOURCES)}")
            requirement = entry.get("requirement") or {}
            if not isinstance(requirement, dict):
                _fail(f"{where}: 'requirement' must be a mapping")
            # [BRD 27/10] matrix agents; CIA reads the type exactly when it is listed.
            matrix_agents = tuple(str(a) for a in entry.get("matrix_agents") or [])
            unknown = [a for a in matrix_agents if a not in MATRIX_AGENTS]
            if unknown:
                _fail(f"{where}: unknown matrix_agents {unknown}; expected {list(MATRIX_AGENTS)}")
            if ("CIA" in matrix_agents) != (CIA_AGENT in agents):
                _fail(f"{where}: 'agents' must list {CIA_AGENT} exactly when matrix_agents has CIA")

            types[type_id] = DocumentType(
                id=type_id,
                stt=str(entry.get("stt") or ""),
                label=label,
                short_label=short_label,
                group_id=group_id,
                group_stt=str(group.get("stt") or ""),
                group_label=str(group.get("label") or group_id),
                keywords=tuple(keywords),
                filename_keywords=tuple(filename_keywords),
                agents=agents,
                primary_agent=_resolve_primary_agent(
                    entry.get("primary_agent") or group.get("primary_agent"),
                    agents,
                    where,
                ),
                requirement={
                    str(key): str(value or "")
                    for key, value in requirement.items()
                },
                source=source,
                code=str(entry.get("code") or ""),
                matrix_agents=matrix_agents,
                validation=tuple(str(v) for v in entry.get("validation") or []),
                legal_basic_extraction=bool(entry.get("legal_basic_extraction", False)),
                shareholders_extraction=bool(entry.get("shareholders_extraction", False)),
                legal_rep_extraction=bool(entry.get("legal_rep_extraction", False)),
                liabilities_extraction=bool(entry.get("liabilities_extraction", False)),
                financial_extraction=bool(entry.get("financial_extraction", False)),
                vat_extraction=bool(entry.get("vat_extraction", False)),
                cic_extraction=bool(entry.get("cic_extraction", False)),
                plan_extraction=bool(entry.get("plan_extraction", False)),
                business_model_extraction=bool(entry.get("business_model_extraction", False)),
            )

    if not types:
        _fail("no document types defined")
    return DocumentMatrix(
        version=version,
        loan_programs=tuple(programs),
        loan_program_labels=program_labels,
        types=types,
        boxes=tuple(boxes),
        box_labels=box_labels,
        catch_all_boxes=frozenset(catch_all_boxes),
    )


@lru_cache(maxsize=1)
def load_matrix() -> DocumentMatrix:
    """Load and validate the matrix once per process."""

    return _load(MATRIX_PATH)


def get_type(type_id: str) -> DocumentType | None:
    return load_matrix().types.get(type_id)


def is_catch_all_box(group_id: str) -> bool:
    """True for an upload box that declares no document types."""

    return group_id in load_matrix().catch_all_boxes


def document_type_keywords() -> dict[str, tuple[str, ...]]:
    """{document_type_id: keywords} — the input to rule-based classification."""

    return {type_id: doc.keywords for type_id, doc in load_matrix().types.items()}


def document_type_filename_keywords() -> dict[str, tuple[str, ...]]:
    """{document_type_id: keywords scored against the FILENAME only}."""

    return {
        type_id: doc.filename_keywords
        for type_id, doc in load_matrix().types.items()
    }


def resolve_loan_program(loan_program: str = "") -> str:
    """The programme whose column of the matrix a case is read against."""

    if not loan_program:
        return DEFAULT_LOAN_PROGRAM
    if loan_program not in load_matrix().loan_programs:
        raise DocumentMatrixError(
            f"unknown loan program {loan_program!r}; expected one of "
            f"{list(load_matrix().loan_programs)}"
        )
    return loan_program


def agent_relevance_for_type(
    type_id: str,
    loan_program: str | None = None,
) -> dict[str, str]:
    """Return {agent: "R"|"O"} for a document type."""

    doc = get_type(type_id)
    if doc is None:
        return {}
    if loan_program is not None:
        if loan_program not in load_matrix().loan_programs:
            raise DocumentMatrixError(
                f"unknown loan program {loan_program!r}; expected one of "
                f"{list(load_matrix().loan_programs)}"
            )
        return {
            agent: levels[loan_program] for agent, levels in doc.agents.items()
        }
    return {
        agent: max(levels.values(), key=lambda level: _LEVEL_RANK[level])
        for agent, levels in doc.agents.items()
    }


def primary_agent_for_type(type_id: str) -> str | None:
    doc = get_type(type_id)
    return doc.primary_agent if doc else None


def source_for_type(type_id: str) -> str:
    """customer | field | external | internal — "customer" when unknown."""

    doc = get_type(type_id)
    return doc.source if doc else "customer"


def is_legal_basic_type(type_id: str) -> bool:
    """True when BRD item 1 (thông tin pháp lý cơ bản) is extracted from this type."""

    doc = get_type(type_id)
    return bool(doc and doc.legal_basic_extraction)


def is_shareholders_type(type_id: str) -> bool:
    """True when BRD item 2 (cổ đông, thành viên góp vốn) is extracted from this type."""

    doc = get_type(type_id)
    return bool(doc and doc.shareholders_extraction)


def is_legal_rep_type(type_id: str) -> bool:
    """True when BRD item 3 (người đại diện pháp luật) is extracted from this type."""

    doc = get_type(type_id)
    return bool(doc and doc.legal_rep_extraction)


def is_liabilities_type(type_id: str) -> bool:
    """True when BRD item 4 (nợ thuế, BHXH, xử phạt, tranh chấp) is extracted from this type."""

    doc = get_type(type_id)
    return bool(doc and doc.liabilities_extraction)


def is_financial_type(type_id: str) -> bool:
    """True when the financial-statement figures are extracted from this type."""

    doc = get_type(type_id)
    return bool(doc and doc.financial_extraction)


# [BRD 16/10] one lookup per new pass, same shape as the ones above.
def is_vat_type(type_id: str) -> bool:
    doc = get_type(type_id)
    return bool(doc and doc.vat_extraction)


def is_cic_type(type_id: str) -> bool:
    doc = get_type(type_id)
    return bool(doc and doc.cic_extraction)


def is_plan_type(type_id: str) -> bool:
    doc = get_type(type_id)
    return bool(doc and doc.plan_extraction)


# [BRD 27/10]
def is_business_model_type(type_id: str) -> bool:
    doc = get_type(type_id)
    return bool(doc and doc.business_model_extraction)


def describe_types_for_prompt(group_id: str = "") -> str:
    """Render the type catalogue for the classifier LLM prompt.

    Built from the matrix so the prompt can never list a type the matrix does
    not define (or miss one it does).
    """

    lines: list[str] = []
    current_group: str | None = None
    for doc in load_matrix().types.values():
        if group_id and doc.group_id != group_id:
            continue
        if doc.group_id != current_group:
            current_group = doc.group_id
            lines.append(f"\n{doc.group_stt}. {doc.group_label}")
        label = " ".join(doc.label.split())
        if len(label) > 180:
            label = label[:180].rstrip() + "..."
        lines.append(f'- "{doc.id}" ({doc.stt}): {label}')
    return "\n".join(lines).strip()
