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
# [BRD 29/10] Labels, in a site-visit report, of the person who stands for the borrower (unaccented).
# The name RIGHT AFTER the label is taken — one person per label — so
# "Đại diện khách hàng: Bà Nguyễn Huệ Chi (vợ ông Vũ Hoàng Nguyên)" gives Nguyễn Huệ Chi only.
REPRESENTATIVE_LABELS = ("dai dien khach hang", "dai dien kh", "dai dien ben vay", "dai dien lam viec",
                         "ho ten khach hang", "ten khach hang", "khach hang vay von", "nguoi vay")
# A label right after one of these words is about someone else ("chồng khách hàng vay …").
RELATION_WORDS = {"chong", "vo", "con", "bo", "me", "cha", "anh", "chi", "em", "cua"}
NAME_WINDOW = 60       # characters after the label where the name must start


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


def _name_in_next_cell(line: str, candidates: dict[str, str]) -> str:
    """[Sửa 29/10] Excel form row (mẫu MB): label cell "Đại diện KH", value in a later cell.

    The label cell must be the label itself (so "Đại diện TCB" never matches). The value is
    taken even when it is not a candidate (ĐKKD not read): it is what the report says.
    """

    cells: list[str] = []
    for cell in line.split("\t"):                     # merged cells repeat — keep each once
        cell = cell.strip()
        if cell and (not cells or cells[-1] != cell):
            cells.append(cell)
    for i, cell in enumerate(cells[:-1]):
        if normalize_text(cell).rstrip(" :") not in REPRESENTATIVE_LABELS:
            continue
        value = cells[i + 1].strip(" :")
        key = norm_person(value)                      # also drops "Ông/Bà"
        if any(ch.isdigit() for ch in value) or not 2 <= len(key.split()) <= 5:
            return ""
        if key in candidates:
            return candidates[key]
        words = value.split()
        return " ".join(words[-len(key.split()):])      # drop "Ông/Bà"
    return ""


def _name_after_label(line: str, candidates: dict[str, str]) -> str:
    """The candidate named right after a representative label on ``line``; '' if none."""

    if "\t" in line:
        name = _name_in_next_cell(line, candidates)
        if name:
            return name
    text = " " + normalize_text(line) + " "
    for label in REPRESENTATIVE_LABELS:
        start = text.find(f" {label} ")
        while start >= 0:
            before = text[:start].split()[-1:]                  # the word just before the label
            if not (before and before[0] in RELATION_WORDS):
                after = text[start + len(label) + 1:]
                hits = [(after.find(f" {key} "), shown) for key, shown in candidates.items()
                        if 0 <= after.find(f" {key} ") <= NAME_WINDOW]
                if hits:
                    return min(hits)[1]                          # the first name after the label
            start = text.find(f" {label} ", start + 1)
    return ""


def _from_site_visit(documents: list[Any], records: list[dict[str, Any]],
                     candidates: dict[str, str]) -> tuple[list[str], list[str]]:
    """[BRD 29/10] The customer's representative named by the site-visit report.

    Order: (1) the "Đại diện khách hàng: …" line in the report text (code, exact);
    (2) the LLM field customer_representative; (3) people the report marks "KH vay".
    """

    for doc in documents:                                       # 1. the labelled line
        if getattr(doc, "source", "") != "field" or not getattr(doc, "content", ""):
            continue
        for line in doc.content.splitlines():
            name = _name_after_label(line, candidates)
            if name:
                return [name], [f"{doc.filename} (dòng: {' '.join(line.split())[:80]})"]
    field = [r for r in records if r.get("source") == "field" and r.get("pass") == "shareholders"]
    for record in field:                                        # 2. LLM field
        name = str((record.get("data") or {}).get("customer_representative") or "").strip()
        if len(norm_person(name).split()) >= 2:
            return [candidates.get(norm_person(name), name)], [f"{record.get('document', '')} (đại diện KH)"]
    for record in field:                                        # 3. "KH vay" in the people list
        for person in (record.get("data") or {}).get("people") or []:
            if isinstance(person, dict) and normalize_text(person.get("relation_to_borrower") or "") in (
                    "kh vay", "khach hang vay", "kh vay von", "nguoi vay", "nguoi dung ra vay"):
                name = str(person.get("name") or "").strip()
                return [candidates.get(norm_person(name), name)], [f"{record.get('document', '')} (KH vay)"]
    return [], []


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
            hits = [shown for _, shown in sorted((text.find(f" {key} "), shown) for key, shown in candidates.items()
                                                 if f" {key} " in text)]
            found += [name for name in hits if name not in found]
            if hits:
                files.append(doc.filename)
        if found:
            return found, files
    return [], []
