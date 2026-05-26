"""Screener-hygiene validation.

Runs cheap, deterministic checks over an assembled screener and emits Flags.
These are probe signals to support an analyst's review, never a pass/fail
verdict — the messages say what to look at and why, and the analyst decides.

Checks:
  • leading / loaded wording in question text
  • double-barrelled questions (two asks in one)
  • over-screening (so many terminates that incidence will be punishingly low)
  • missing essentials (security screen, articulation, consent)
  • a rough incidence estimate from the terminating questions
"""

from __future__ import annotations

import re

from .models import (
    Flag,
    QuestionType,
    Screener,
    Section,
    Severity,
)

# Phrases that genuinely lead or load a respondent. Kept deliberately narrow:
# bare adjectives like "best"/"great" fire constantly on neutral wording
# ("which best describes you") and produce noise, so they are excluded.
_LEADING_TERMS = (
    "obviously",
    "everyone",
    "of course",
    "wouldn't you",
    "don't you agree",
    "isn't it",
    "agree that",
    "as you know",
    "surely",
    "needless to say",
)


def _leading_hits(text: str) -> list[str]:
    """Return leading phrases present in text, matched on word boundaries."""
    low = text.lower()
    hits = []
    for term in _LEADING_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", low):
            hits.append(term)
    return hits


# Interrogative stems used to decide whether an ' and ' joins two real asks.
_INTERROGATIVES = ("how", "what", "which", "do you", "would you", "are you", "have you")


def _is_double_barrelled(text: str) -> bool:
    """Heuristic: the interrogative clause contains ' and ' joining two asks.

    Only the question clause is inspected (text after the last full stop and up
    to the final '?'), so descriptive logistics preamble — e.g. a remote-session
    note before "Are you comfortable…?" — does not trip the check.
    """
    low = text.lower()
    if "?" not in low:
        return False
    clause = low.rsplit(".", 1)[-1].split("?", 1)[0]
    if " and " not in clause:
        return False
    asks = sum(1 for stem in _INTERROGATIVES if stem in clause)
    return asks >= 2


def _estimate_incidence(screener: Screener) -> float:
    """Rough order-of-magnitude qualifying rate (0–1).

    Incidence here means the share of the general population that *qualifies*,
    so logistics and consent (post-qualification conversion) are excluded. The
    model is deliberately crude and conservative:

      • single-select qualifiers  → surviving options / total (floored)
      • multi-select exclusion/qualifier screens → most respondents land on the
        safe side, so a high fixed pass rate is assumed
      • open-ends and logistics/consent → not counted toward incidence
    """
    rate = 1.0
    for q in screener.questions:
        if q.qtype is QuestionType.OPEN_END:
            continue
        if q.section is Section.LOGISTICS:
            continue
        term = len(q.terminating_codes)
        total = len(q.options)
        if total == 0 or term == 0:
            continue
        if q.qtype is QuestionType.MULTI_SELECT:
            # exclusion / "select all that apply" screens disqualify a minority
            pass_frac = 0.8
        else:
            pass_frac = max(0.15, (total - term) / total)
        rate *= pass_frac
    return round(rate, 3)


def validate(screener: Screener) -> list[Flag]:
    """Return hygiene flags for the screener (does not mutate it)."""
    flags: list[Flag] = []

    # — wording checks per question —
    for q in screener.questions:
        hits = _leading_hits(q.text)
        if hits:
            flags.append(
                Flag(
                    severity=Severity.WARNING,
                    qid=q.qid,
                    message=f"Possible leading wording ({', '.join(hits[:3])}). Neutralise before fielding.",
                )
            )
        if _is_double_barrelled(q.text):
            flags.append(
                Flag(
                    severity=Severity.WARNING,
                    qid=q.qid,
                    message="Reads as double-barrelled — consider splitting into separate questions.",
                )
            )

    # — essentials present? —
    sections = {q.section for q in screener.questions}
    if Section.SECURITY not in sections:
        flags.append(Flag(Severity.CRITICAL, "No security / exclusion screen present.", None))
    if Section.ARTICULATION not in sections:
        flags.append(
            Flag(Severity.INFO, "No articulation question — consider one for moderated qual.", None)
        )
    has_consent = any(q.qid == "L2" for q in screener.questions)
    if not has_consent:
        flags.append(Flag(Severity.WARNING, "No explicit consent question detected.", None))

    # — over-screening —
    incidence = _estimate_incidence(screener)
    screener.incidence_estimate = incidence
    if incidence < 0.10:
        flags.append(
            Flag(
                severity=Severity.WARNING,
                message=(
                    f"Estimated incidence ≈ {incidence:.0%}. Recruitment may be slow and costly; "
                    "consider relaxing the tightest qualifier."
                ),
            )
        )

    # — quota sanity —
    quota_q = [q for q in screener.questions if q.section is Section.QUOTA]
    if screener.quota and screener.quota.cells and len(screener.quota.cells) > 1 and not quota_q:
        flags.append(
            Flag(
                severity=Severity.INFO,
                message="Quota cells defined but no quota-routing question found.",
            )
        )

    return flags
