"""Core data models for screener-generator.

These dataclasses and enums are the shared vocabulary between the rule-based
core (parser, question_bank, generator, quota, validate) and the optional LLM
enrichment layer (llm). Everything serialises cleanly to JSON so the CLI can
emit machine-readable output for CI and downstream tooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuestionType(str, Enum):
    """The shape of a screener question."""

    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    NUMERIC = "numeric"
    OPEN_END = "open_end"


class Disposition(str, Enum):
    """What happens when a respondent picks an option.

    CONTINUE  — option keeps the respondent in the funnel.
    TERMINATE — option disqualifies the respondent (a security / quality / fit screen).
    QUOTA     — option keeps the respondent but counts toward a quota cell.
    """

    CONTINUE = "continue"
    TERMINATE = "terminate"
    QUOTA = "quota"


class Section(str, Enum):
    """The standard sections of a recruitment screener, in field order."""

    SECURITY = "security"
    PRIMARY = "primary"
    QUOTA = "quota"
    BEHAVIORAL = "behavioral"
    ARTICULATION = "articulation"
    LOGISTICS = "logistics"


# Field order for rendering — keeps a generated screener in a sensible sequence.
SECTION_ORDER = [
    Section.SECURITY,
    Section.PRIMARY,
    Section.QUOTA,
    Section.BEHAVIORAL,
    Section.ARTICULATION,
    Section.LOGISTICS,
]

SECTION_LABELS = {
    Section.SECURITY: "Security & exclusions",
    Section.PRIMARY: "Primary qualification",
    Section.QUOTA: "Quota & segmentation",
    Section.BEHAVIORAL: "Behavioural & frequency",
    Section.ARTICULATION: "Articulation",
    Section.LOGISTICS: "Logistics & consent",
}


class Severity(str, Enum):
    """Severity of a screener-hygiene flag."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AnswerOption:
    """A single answer option on a closed question.

    `code` is the punch code a panel/scripting tool would use. `disposition`
    drives skip logic. `quota_cell` links an option to a named quota cell when
    its disposition is QUOTA.
    """

    code: str
    label: str
    disposition: Disposition = Disposition.CONTINUE
    quota_cell: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "disposition": self.disposition.value,
            "quota_cell": self.quota_cell,
        }


@dataclass
class ScreenerQuestion:
    """One question in the screener."""

    qid: str
    section: Section
    qtype: QuestionType
    text: str
    options: list[AnswerOption] = field(default_factory=list)
    logic: str = ""           # human-readable skip/terminate logic, e.g. "TERMINATE if code 1–3"
    rationale: str = ""       # why this question earns its place in the screener
    source: str = "rule"      # "rule" or "llm" — provenance, so enrichment is auditable

    @property
    def terminating_codes(self) -> list[str]:
        return [o.code for o in self.options if o.disposition is Disposition.TERMINATE]

    def to_dict(self) -> dict[str, Any]:
        return {
            "qid": self.qid,
            "section": self.section.value,
            "qtype": self.qtype.value,
            "text": self.text,
            "options": [o.to_dict() for o in self.options],
            "logic": self.logic,
            "rationale": self.rationale,
            "source": self.source,
        }


@dataclass
class QuotaCell:
    """A target count within a quota group."""

    group: str        # e.g. "Role" or "Tenure"
    label: str        # e.g. "Frontline agent"
    target: int       # how many completes we want in this cell

    def to_dict(self) -> dict[str, Any]:
        return {"group": self.group, "label": self.label, "target": self.target}


@dataclass
class QuotaPlan:
    """The full quota plan: total completes and the cells that make it up."""

    total_completes: int
    cells: list[QuotaCell] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_completes": self.total_completes,
            "cells": [c.to_dict() for c in self.cells],
            "notes": self.notes,
        }


@dataclass
class Flag:
    """A screener-hygiene observation — a probe signal, not a verdict."""

    severity: Severity
    message: str
    qid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity.value, "message": self.message, "qid": self.qid}


@dataclass
class BriefSpec:
    """Structured extraction of the inputs a screener depends on.

    Produced by the parser from free-text or markdown brief. The generator
    reads only from this object, never from the raw brief, so the rule-based
    path and the LLM path share one contract.
    """

    product: str = ""
    category: str = ""
    audience: str = ""
    segments: list[str] = field(default_factory=list)
    must_have: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    sample_size: int | None = None
    modality: str = "remote"          # remote | in_person | unmoderated
    sensitive: bool = False           # touches health, finance, children, etc.

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "category": self.category,
            "audience": self.audience,
            "segments": self.segments,
            "must_have": self.must_have,
            "exclude": self.exclude,
            "sample_size": self.sample_size,
            "modality": self.modality,
            "sensitive": self.sensitive,
        }


@dataclass
class Screener:
    """The complete generated screener."""

    spec: BriefSpec
    questions: list[ScreenerQuestion] = field(default_factory=list)
    quota: QuotaPlan | None = None
    flags: list[Flag] = field(default_factory=list)
    incidence_estimate: float | None = None    # rough qualifying rate, 0–1
    summary: str = ""                              # optional LLM-written framing
    backend: str | None = None                  # which LLM backend enriched, if any

    def questions_in_order(self) -> list[ScreenerQuestion]:
        rank = {s: i for i, s in enumerate(SECTION_ORDER)}
        return sorted(self.questions, key=lambda q: (rank.get(q.section, 99), q.qid))

    @property
    def terminate_count(self) -> int:
        return sum(1 for q in self.questions if q.terminating_codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec.to_dict(),
            "questions": [q.to_dict() for q in self.questions_in_order()],
            "quota": self.quota.to_dict() if self.quota else None,
            "flags": [f.to_dict() for f in self.flags],
            "incidence_estimate": self.incidence_estimate,
            "summary": self.summary,
            "backend": self.backend,
            "counts": {
                "questions": len(self.questions),
                "terminating": self.terminate_count,
                "flags": len(self.flags),
            },
        }
