"""Rule-based screener generator (the deterministic core).

Assembles a complete, field-ordered screener from a parsed BriefSpec by drawing
on the question bank and the quota planner, then runs hygiene validation. This
path uses zero API calls and is fully reproducible — the llm layer enriches the
output of this function rather than replacing it.
"""

from __future__ import annotations

from . import question_bank as qb
from .models import BriefSpec, Screener
from .quota import build_quota_plan, quota_question
from .validate import validate


def generate(spec: BriefSpec) -> Screener:
    """Build a Screener from a BriefSpec using rule-based logic only."""
    questions = []

    # Security & exclusions — always present, always first.
    questions.append(qb.security_question())
    questions.append(qb.recent_participation_question())

    # Primary qualification.
    questions.append(qb.category_usage_question(spec))
    mh = qb.must_have_question(spec)
    if mh is not None:
        questions.append(mh)

    # Quota & segmentation.
    plan = build_quota_plan(spec)
    qq = quota_question(plan)
    if qq is not None:
        questions.append(qq)

    # Articulation (qual quality screen).
    questions.append(qb.articulation_question(spec))

    # Logistics & consent.
    questions.append(qb.logistics_question(spec))
    questions.append(qb.consent_question(spec))

    screener = Screener(spec=spec, questions=questions, quota=plan)
    screener.flags = validate(screener)  # also sets incidence_estimate
    return screener


def generate_from_text(text: str) -> Screener:
    """Convenience: parse a raw brief and generate a screener in one call."""
    from .parser import parse_brief

    return generate(parse_brief(text))
