"""The corp-income agent (CIA): "Thẩm định nguồn thu doanh nghiệp" (Appendix - Corp income).

Same place and shape as the SME repo's specialists (``SPECIALIST_BY_AGENT``).
Two layers, so a figure in the report can only come from a document:

1. Code — BRD legal checks (legal_checks.py), financial figures and ratios
   (financial_metrics.py), and every template cell that is a fact or a number
   (appendix_context.py).
2. One LLM call (report_writer.py) — only the cells code cannot write: the
   "Nhận xét…" paragraphs, business activity, CIC and the conclusion, written
   from the guidance (src/templates/corp-income-guidance.md) and the evidence.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from src.agents.calculator.legal_checks import parse_date, run_all_checks
from src.agents.calculator import financial_metrics
from src.agents.extraction import (
    business_model_extraction,
    cic_extraction,
    financial_extraction,
    plan_extraction,
    vat_extraction,
    legal_basic_extraction,
    legal_rep_extraction,
    liabilities_extraction,
    shareholders_extraction,
)
from src.agents.report_writer import NO_INFO, assess_credit, keeps_every_number, write_placeholders
from src.types import ClassifiedDocument
from src.agents.calculator import cic_metrics
from src.agents.calculator.borrowers import detect_borrowers
from src.agents.calculator import business_model
from src.agents.documents.document_matrix import get_type
from src.utils.report.appendix_context import (
    apply_output_conditions,
    borrower_ownership,
    build_appendix_context,
    business_type,
    corp_group,
    fill_missing_financial_names,
    pick_plan,
)
from src.utils.report.report_template import (
    HTML_COMMENT,
    build_context,
    load_template,
    render_markdown,
    template_placeholders,
)

# pass name → (ClassifiedDocument result attribute, normaliser for provided data)
PASSES: dict[str, tuple[str, Any]] = {
    "legal_basic": ("legal_basic_extraction", legal_basic_extraction.normalize_amounts),
    "shareholders": ("shareholders_extraction", shareholders_extraction.normalize_amounts),
    "legal_rep": ("legal_rep_extraction", legal_rep_extraction.normalize_amounts),
    "liabilities": ("liabilities_extraction", liabilities_extraction.normalize_amounts),
    "financial": ("financial_extraction", financial_extraction.normalize_amounts),
    # [BRD 16/10]
    "vat": ("vat_extraction", vat_extraction.normalize_amounts),
    "cic": ("cic_extraction", cic_extraction.normalize_amounts),
    "plan": ("plan_extraction", plan_extraction.normalize_amounts),
    # [BRD 27/10] mục 2 — ngành TCB, đối tác đầu vào / đầu ra
    "business_model": ("business_model_extraction", business_model_extraction.normalize_amounts),
}

# Documents whose text the report writer reads first (business activity, CIC,
# business plan); then everything else. Characters per document.
# [BRD 16/10] + du_lieu_noi_bo (dữ liệu thẩm định KHDN nội bộ TCB, ngành nghề) and GCN
# (address of the head office) — mục 2 compares them with the field report.
# [BRD 27/10] ids of the new document matrix (contracts, permits, premises, statements…).
EXCERPT_FIRST = ("bao_cao_thuc_dia", "bao_cao_thuc_dia_phap_ly", "du_lieu_noi_bo", "hinh_anh_thuc_dia",
                 "hop_dong_dau_vao_dau_ra", "quyen_su_dung_nha_xuong", "giay_phep_nganh_nghe",
                 "so_chi_tiet_cong_no", "sao_ke_tai_khoan", "phan_mem_ban_hang", "tien_do_hop_dong",
                 "blacklist_fraud", "de_nghi_cap_tin_dung", "gcn_dkdn", "bao_cao_cic", "to_khai_vat", "")
# [BRD 16/10] Comments code writes as a fact list; the LLM rewrites them into the frame of
# corp-income-cell-specs.md. A rewrite that drops any number of the draft is rejected and
# the code draft is kept. CORP_INCOME_POLISH_COMMENTS=0 keeps the code drafts as they are.
# [BRD 27/10] the template has one legal comment and no CIC comment any more.
POLISH_CELLS = ("NhanXet", "NhanXetTaiChinh")
POLISH = os.getenv("CORP_INCOME_POLISH_COMMENTS", "1") != "0"
EXCERPT_CHARS = {"first": 6_000, "other": 2_500}
EXCERPT_TOTAL = 80_000

PROVIDED_LABELS = {
    "internal": "Internal data (BCDE/BEP/DBX)",
    "external": "External data (Cổng ĐKDN/cơ quan thuế/BHXH)",
}


def records_from_documents(documents: list[ClassifiedDocument]) -> list[dict[str, Any]]:
    """One record per (document, BRD item) that came back with JSON."""

    records = []
    for doc in documents:
        for pass_name, (attr, _) in PASSES.items():
            data = getattr(doc, attr, None)
            if isinstance(data, dict):
                records.append({
                    "source": doc.source,
                    "document": doc.filename,
                    "document_type": doc.document_type,
                    "pass": pass_name,
                    "data": data,
                })
    return records


def records_from_reference_data(reference_data: dict[str, Any]) -> list[dict[str, Any]]:
    """internal_data / external_data handed in by the caller (BRD B2/B3)."""

    records = []
    for kind in ("internal", "external"):
        for pass_name, data in (reference_data.get(f"{kind}_data") or {}).items():
            if pass_name not in PASSES or not isinstance(data, dict):
                raise ValueError(
                    f"{kind}_data keys must be among {list(PASSES)}; got {pass_name!r}"
                )
            records.append({
                "source": kind,
                "document": PROVIDED_LABELS[kind],
                "document_type": f"{kind}_data",
                "pass": pass_name,
                "data": PASSES[pass_name][1](json.loads(json.dumps(data))),
            })
    return records


def _excerpts(documents: list[ClassifiedDocument]) -> list[dict[str, Any]]:
    ordered = sorted(documents, key=lambda d: 0 if (d.document_type or "") in EXCERPT_FIRST else 1)
    out, budget = [], EXCERPT_TOTAL
    for doc in ordered:
        limit = EXCERPT_CHARS["first" if (doc.document_type or "") in EXCERPT_FIRST else "other"]
        text = (doc.content or "")[: min(limit, budget)]
        if not text:
            continue
        budget -= len(text)
        out.append({"file": doc.filename, "loai": doc.source_description or doc.document_type or "Chưa phân loại",
                    "nguon": doc.source, "noi_dung": text})
        if budget <= 0:
            break
    return out


def _compact_items(items: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        str(n): {
            "tieu_de": item["title"],
            "ket_luan": item["conclusion"],
            "kiem_tra": [{"muc_do": f["severity"], "noi_dung": f["message"], "can_cu": f.get("evidence") or []}
                         for f in item["findings"]],
            "tom_tat": item["summary"],
        }
        for n, item in items.items()
    }


class CorpIncomeAnalysis:
    """Phụ lục 01. ``llm`` writes the narrative cells; everything else is code."""

    agent_name = "CORP_INCOME_AGENT"

    def __init__(self, llm: Any = None):
        self.llm = llm

    def analyze(
        self,
        documents: list[ClassifiedDocument],
        reference_data: dict[str, Any] | None = None,
        loan_date: str | date | None = None,
        borrower_names: list[str] | None = None,
        template_path: str | None = None,
    ) -> dict[str, Any]:
        reference_data = reference_data or {}
        borrower_names = list(borrower_names or [])
        as_of = loan_date if isinstance(loan_date, date) else (parse_date(loan_date) or date.today())
        records = records_from_documents(documents) + records_from_reference_data(reference_data)
        # [Sửa 20/10] BORROWER_NAMES trống → tự tìm tên KH vay trong hồ sơ vay vốn.
        borrower_source = "khai báo trong notebook" if borrower_names else ""
        if not borrower_names:
            borrower_names, borrower_files = detect_borrowers(documents, records)
            if borrower_names:
                borrower_source = "tự nhận diện từ " + ", ".join(borrower_files)
        items = run_all_checks(
            records,
            as_of=as_of,
            borrower_names=borrower_names,
            watchlist=reference_data.get("watchlist") or [],
        )
        # [BRD 16/10] all groups and values below are computed in code, then shown to the LLM.
        financials = financial_metrics.compute(records, as_of)
        latest = financials["latest_year"]
        btype, btype_note = business_type(records)
        cic = cic_metrics.compute(
            records, as_of,
            revenue_prev_year=(financials["years"].get(latest) or {}).get("net_revenue") if latest else None,
            business_type=btype)
        corp = corp_group(items, financials, cic, as_of)
        # [BRD 27/10] with a business plan and a TCB industry, the income is the projection.
        nganh = business_model.industry(records)
        income = financial_metrics.income_estimate(
            financials, borrower_ownership(items, borrower_names), reference_data.get("annual_lt_principal"),
            plan=pick_plan(records), industry=nganh, corp_group=corp["group"])

        template_text, template_source = load_template(template_path)
        template_body = HTML_COMMENT.sub("", template_text)
        meta = {
            "as_of": as_of.strftime("%d/%m/%Y"),
            "borrower_names": borrower_names,
            "borrower_source": borrower_source,
            "template": template_source,
        }
        documents_view = [
            {
                "filename": doc.filename,
                "label": doc.source_description or doc.document_type or "Chưa phân loại",
                "source": doc.source,
                "box": doc.declared_group,
                # [BRD 27/10] document-matrix number and agents of the type
                "matrix_code": getattr(get_type(doc.document_type), "code", "") if doc.document_type else "",
                "matrix_agents": list(getattr(get_type(doc.document_type), "matrix_agents", ()) or ()),
                "matrix_validation": list(getattr(get_type(doc.document_type), "validation", ()) or ()),
                "read_method": doc.read_method,
                "chars": len(doc.content or ""),
                "passes_done": [
                    name for name, (attr, _) in PASSES.items()
                    if isinstance(getattr(doc, attr, None), dict)
                ],
                "errors": {
                    name: getattr(doc, f"{attr}_error")
                    for name, (attr, _) in PASSES.items()
                    if getattr(doc, f"{attr}_error", "")
                },
            }
            for doc in documents
        ]
        base = {"meta": meta, "documents": documents_view, "items": items}

        # 1. Code fills every fact and figure.
        names = template_placeholders(template_body)
        ctx = {**build_context(base),
               **build_appendix_context(base, records, financials, as_of, cic=cic, corp=corp, income=income)}
        fill_missing_financial_names(set(names), ctx)

        # 2. The LLM writes only what is left.
        drafts = {n: ctx.pop(n) for n in POLISH_CELLS if POLISH and self.llm and n in ctx and n in names}
        remaining = [name for name in names if name not in ctx]
        evidence = {
            "ngay_tham_chieu": meta["as_of"],
            "khach_hang_vay": borrower_names,
            "gia_tri_da_dien": {name: ctx[name] for name in names if name in ctx},
            "phap_ly": _compact_items(items),
            "tai_chinh": {
                "nguon": financials["sources"],
                "so_lieu_theo_nam": {y: {k: v for k, v in fig.items() if not k.startswith("_")}
                                     for y, fig in financials["years"].items()},
                "ky_giua_nien_do": {k: v for k, v in financials["interim"].items() if not k.startswith("_")},
                "to_khai_vat": financials["vat"],
                "chi_so": financials["ratios"],
                "canh_bao_trong_yeu": financials["material_warnings"],
                "canh_bao_khac": financials["other_warnings"],
                "nhan_xet_trang_thai": financials["status_remarks"],
                "nhom_tai_chinh": financials["group"],
                "don_vi": "đồng (bảng trong báo cáo hiển thị triệu đồng)",
            },
            "tin_dung_cic": {k: v for k, v in cic.items() if k != "rows"},
            # [BRD 16/10] the group is decided in code; the LLM words the conclusion around it.
            "phan_nhom_doanh_nghiep": corp,
            "loai_hinh_kinh_doanh": {"ma": btype, "ghi_chu": btype_note},
            "thu_nhap_ghi_nhan": {
                **income,
                "gia_tri_trieu_dong": financial_metrics.fmt(income["value"]),
                "cong_thuc": "(LNST hợp lý − LNST sử dụng trả nợ TDH) × Tỷ lệ góp vốn",
            },
            "dia_chi_tsc_tren_dkkd": next((e["value"] for e in items[1]["summary"].values()
                                           if e.get("field") == "head_office_address"), None),
            # [BRD 27/10] industry chosen in code from the TCB table, and the partners of the diagram
            "nganh_tcb": nganh or "Chưa xác định ngành theo bảng ngành TCB",
            "mo_hinh_hdkd": {"dau_vao": business_model.partners(records, "suppliers"),
                             "dau_ra": business_model.partners(records, "customers")},
            "ho_so": [{"file": d["filename"], "loai": d["label"], "nguon": d["source"],
                       "doc_bang": d["read_method"]} for d in documents_view],
            "trich_doan_ho_so": _excerpts(documents),
            "du_lieu_noi_bo_ngoai": {k: v for k, v in reference_data.items() if k != "watchlist"},
        }
        evidence["ban_nhap_code"] = drafts
        # [BRD 16/10] Step 1: one overall credit view; step 2: every cell is written from it.
        assessment, assessment_note = assess_credit(self.llm, evidence, corp["group"])
        evidence["danh_gia_tin_dung"] = assessment
        written, writer_error = write_placeholders(self.llm, template_body, remaining, evidence)
        writer_error = "; ".join(x for x in (assessment_note, writer_error) if x)
        rejected = []
        for name, draft in drafts.items():
            missing = keeps_every_number(draft, written.get(name, ""))
            if missing or written.get(name) in (None, "", NO_INFO):
                written[name] = draft                       # keep the code version
                rejected.append(name)
        if rejected:
            writer_error = "; ".join(x for x in (writer_error, "kept the code draft (LLM rewrite lost numbers or "
                                                 f"was empty): {', '.join(rejected)}") if x)
        ctx.update(written)
        meta.update({
            "code_placeholders": [n for n in names if n not in remaining],
            "llm_placeholders": remaining,
            "writer_error": writer_error,
            "unknown_placeholders": [],
        })

        # "hiển thị khi …": plan table, "Cơ sở" column, POC group tables.
        markdown = apply_output_conditions(render_markdown(base, template_text, ctx), ctx)
        return {
            "response": markdown,
            "meta": meta,
            "items": {str(number): item for number, item in items.items()},
            "financials": financials,
            "income_estimate": income,
            "cic": {k: v for k, v in cic.items() if k != "rows"} | {
                "rows": {k: {f: (sorted(x) if isinstance(x, set) else x) for f, x in row.items()}
                         for k, row in cic.get("rows", {}).items()}},
            "corp_group": corp,
            # [BRD 27/10] mục 2 — ngành TCB and the ranked partners of the diagram
            "business_model": {"industry": nganh,
                               "suppliers": business_model.partners(records, "suppliers"),
                               "customers": business_model.partners(records, "customers")},
            "credit_assessment": assessment,
            "records": records,
            "documents": documents_view,
        }


SPECIALIST_BY_AGENT = {
    "CORP_INCOME_AGENT": CorpIncomeAnalysis,
}
