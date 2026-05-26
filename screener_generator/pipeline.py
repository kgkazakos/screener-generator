"""Pipeline orchestration.

One entry point that takes raw brief text and returns a finished Screener,
optionally enriched by an LLM backend. Also holds the markdown renderer used by
the CLI and the Streamlit app so the field-document format lives in one place.
"""

from __future__ import annotations

from collections.abc import Callable

from .generator import generate
from .llm import DEFAULT_BACKEND, enrich
from .models import SECTION_LABELS, SECTION_ORDER, Disposition, Screener
from .parser import parse_brief

OnWarning = Callable[[str], None] | None


def build_screener(
    brief_text: str,
    use_llm: bool = True,
    backend: str = DEFAULT_BACKEND,
    on_warning: OnWarning = None,
) -> Screener:
    """Parse a brief, generate a screener, and (by default) enrich it.

    LLM enrichment is ON by default but always degrades to the rule-based
    screener if a backend/key is unavailable — set use_llm=False to force the
    offline path.
    """
    spec = parse_brief(brief_text)
    screener = generate(spec)
    if use_llm:
        screener = enrich(screener, backend=backend, on_warning=on_warning)
    return screener


_DISPOSITION_TAG = {
    Disposition.TERMINATE: "**[TERMINATE]**",
    Disposition.QUOTA: "**[QUOTA]**",
    Disposition.CONTINUE: "",
}


def to_markdown(screener: Screener) -> str:
    """Render a screener as a clean, recruiter-ready markdown document."""
    spec = screener.spec
    lines: list[str] = []
    title = spec.product or "Research study"
    lines.append(f"# Recruitment screener — {title}")
    lines.append("")
    if screener.summary:
        lines.append(f"> {screener.summary}")
        lines.append("")

    meta = []
    if spec.audience:
        meta.append(f"**Audience:** {spec.audience}")
    if screener.quota:
        meta.append(f"**Target completes:** n={screener.quota.total_completes}")
    meta.append(f"**Modality:** {spec.modality.replace('_', ' ')}")
    if screener.incidence_estimate is not None:
        meta.append(f"**Est. incidence:** ~{screener.incidence_estimate:.0%}")
    if screener.backend:
        meta.append(f"**Enriched by:** `{screener.backend}`")
    lines.append("  ·  ".join(meta))
    lines.append("")

    by_section: dict = {}
    for q in screener.questions_in_order():
        by_section.setdefault(q.section, []).append(q)

    for section in SECTION_ORDER:
        qs = by_section.get(section)
        if not qs:
            continue
        lines.append(f"## {SECTION_LABELS[section]}")
        lines.append("")
        for q in qs:
            lines.append(f"**{q.qid}. {q.text}**  _({q.qtype.value.replace('_', ' ')})_")
            for opt in q.options:
                tag = _DISPOSITION_TAG.get(opt.disposition, "")
                tag = f" {tag}" if tag else ""
                cell = f" → {opt.quota_cell}" if opt.quota_cell else ""
                lines.append(f"- `{opt.code}` {opt.label}{tag}{cell}")
            if q.logic:
                lines.append(f"  - _Logic:_ {q.logic}")
            if q.rationale:
                lines.append(f"  - _Why:_ {q.rationale}")
            lines.append("")

    # Quota plan
    if screener.quota and screener.quota.cells:
        lines.append("## Quota plan")
        lines.append("")
        lines.append("| Group | Cell | Target |")
        lines.append("|---|---|---|")
        for c in screener.quota.cells:
            lines.append(f"| {c.group} | {c.label} | {c.target} |")
        lines.append("")
        for note in screener.quota.notes:
            lines.append(f"> {note}")
        if screener.quota.notes:
            lines.append("")

    # Flags
    if screener.flags:
        lines.append("## Hygiene flags")
        lines.append("")
        lines.append("_Probe signals to review before fielding — not pass/fail verdicts._")
        lines.append("")
        for f in screener.flags:
            where = f" ({f.qid})" if f.qid else ""
            lines.append(f"- **{f.severity.value.upper()}**{where}: {f.message}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
