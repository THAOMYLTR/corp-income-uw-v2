"""Tự nhận diện KH cá nhân vay vốn (người đứng ra vay) khi BORROWER_NAMES để trống.

Thứ tự (BORROWER_NAMES khai báo trong notebook luôn được ưu tiên):
  1. [BRD 29/10] BÁO CÁO KHẢO SÁT THỰC ĐỊA — "đại diện KH" là người đứng ra vay:
     a. trường "customer_representative" do LLM trích (shareholders_extraction);
     b. dòng "Đại diện khách hàng / Đại diện KH / Người đại diện làm việc…" trong văn bản
        báo cáo (code dò, không cần LLM) — lấy ứng viên có tên trên dòng đó;
     c. người được báo cáo ghi quan hệ "KH vay".
  2. [Sửa 20/10] Tên ứng viên (thành viên góp vốn cá nhân + NĐDPL) xuất hiện trong HỒ SƠ VAY
     VỐN (giấy đề nghị vay…), rồi hồ sơ soạn thảo nội bộ (tờ trình) — so khớp không dấu.
"""

from __future__ import annotations

from typing import Any

from src.agents.calculator.legal_checks import norm_person
from src.utils.common import normalize_text

# Ô upload chứa giấy tờ vay của KH (ho_so_vay_von) và tờ trình nội bộ (ho_so_soan_thao_noi_bo).
LOAN_GROUPS = ("ho_so_vay_von", "ho_so_soan_thao_noi_bo")
# [BRD 29/10] Labels of the customer's representative in a site-visit report (unaccented).
REPRESENTATIVE_LABELS = ("dai dien khach hang", "dai dien kh", "dai dien ben vay", "nguoi dai dien lam viec",
                         "dai dien lam viec", "nguoi lam viec voi", "khach hang vay")


def _candidates(records: list[dict[str, Any]]) -> dict[str, str]:
    """{tên chuẩn hóa: tên như in} của cá nhân góp vốn và người đại diện theo pháp luật."""

    names: dict[str, str] = {}

    def add(name: Any) -> None:
        key = norm_person(name)
        if len(key.split()) >= 2:          # bỏ tên một chữ — dễ khớp nhầm
            names.setdefault(key, str(name).strip())

    for record in records:
        data = record.get("data") or {}
        for member in data.get("members") or []:
            if isinstance(member, dict) and member.get("member_type") != "phap_nhan":
                add(member.get("name"))
        for rep in data.get("legal_representatives") or []:
            add(rep.get("name") if isinstance(rep, dict) else rep)
    return names


def _from_site_visit(documents: list[Any], records: list[dict[str, Any]],
                     candidates: dict[str, str]) -> tuple[list[str], list[str]]:
    """[BRD 29/10] The customer's representative named by the site-visit report."""

    found: list[str] = []
    files: list[str] = []

    def add(name: str, file: str) -> None:
        if name and norm_person(name) not in {norm_person(f) for f in found}:
            found.append(candidates.get(norm_person(name), name))
        if file and file not in files:
            files.append(file)

    for record in records:                                      # a. LLM field; c. "KH vay" in the table
        if record.get("source") != "field" or record.get("pass") != "shareholders":
            continue
        data = record.get("data") or {}
        if len(norm_person(data.get("customer_representative")).split()) >= 2:
            add(str(data["customer_representative"]).strip(), record.get("document", ""))
        for person in data.get("people") or []:
            if isinstance(person, dict) and normalize_text(person.get("relation_to_borrower") or "") in (
                    "kh vay", "khach hang vay", "kh vay von", "nguoi vay"):
                add(str(person.get("name") or "").strip(), record.get("document", ""))
    if not found:                                               # b. the line in the report text
        for doc in documents:
            if getattr(doc, "source", "") != "field" or not getattr(doc, "content", ""):
                continue
            for line in doc.content.splitlines():
                text = " " + normalize_text(line) + " "
                if any(label in text for label in REPRESENTATIVE_LABELS):
                    for key, shown in candidates.items():
                        if f" {key} " in text:
                            add(shown, doc.filename)
    return found, files


def detect_borrowers(documents: list[Any], records: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """``(tên KH vay, file làm căn cứ)``; ([], []) khi không xác định được."""

    candidates = _candidates(records)
    found, files = _from_site_visit(documents, records, candidates)      # [BRD 29/10] first
    if found:
        return found, files
    # Giấy đề nghị vay của KH trước; tờ trình nội bộ (hay liệt kê mọi thành viên) chỉ dùng khi thiếu.
    for group in LOAN_GROUPS:
        found: list[str] = []
        files: list[str] = []
        for doc in documents:
            if getattr(doc, "declared_group", "") != group or not getattr(doc, "content", ""):
                continue
            text = " " + normalize_text(doc.content) + " "
            hits = [shown for key, shown in candidates.items() if f" {key} " in text]
            found += [name for name in hits if name not in found]
            if hits:
                files.append(doc.filename)
        if found:
            return found, files
    return [], []
