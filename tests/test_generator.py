"""Tests for the rule-based generator and hygiene validation."""

from screener_generator.generator import generate, generate_from_text
from screener_generator.models import (
    BriefSpec,
    Flag,
    Screener,
    Section,
    Severity,
)
from screener_generator.validate import _estimate_incidence, validate

BRIEF = """Smart Reply for Team Inbox
Target audience: customer support agents who handle tickets daily.
Must have: use a shared team inbox; handle 20+ tickets per week.
Segments: new agents vs experienced agents.
We want to recruit n=12 for remote interviews.
"""


def test_generate_includes_security_first():
    s = generate_from_text(BRIEF)
    first = s.questions_in_order()[0]
    assert first.section is Section.SECURITY


def test_generate_has_all_core_sections():
    s = generate_from_text(BRIEF)
    sections = {q.section for q in s.questions}
    assert Section.SECURITY in sections
    assert Section.PRIMARY in sections
    assert Section.ARTICULATION in sections
    assert Section.LOGISTICS in sections


def test_generate_with_segments_adds_quota_question():
    s = generate_from_text(BRIEF)
    assert any(q.section is Section.QUOTA for q in s.questions)


def test_generate_without_segments_skips_quota_question():
    s = generate(BriefSpec(product="X", sample_size=8))
    assert not any(q.section is Section.QUOTA for q in s.questions)


def test_incidence_estimate_set():
    s = generate_from_text(BRIEF)
    assert s.incidence_estimate is not None
    assert 0.0 < s.incidence_estimate <= 1.0


def test_terminate_count_positive():
    s = generate_from_text(BRIEF)
    assert s.terminate_count >= 2


def test_validate_flags_leading_question():
    s = generate(BriefSpec(product="X"))
    s.questions[0].text = "Obviously you love this product, don't you?"
    flags = validate(s)
    assert any(f.severity is Severity.WARNING and "leading" in f.message.lower() for f in flags)


def test_validate_flags_missing_security():
    s = Screener(spec=BriefSpec(product="X"), questions=[])
    flags = validate(s)
    assert any(f.severity is Severity.CRITICAL for f in flags)


def test_estimate_incidence_in_range():
    s = generate_from_text(BRIEF)
    inc = _estimate_incidence(s)
    assert 0.0 < inc <= 1.0


def test_flag_to_dict_roundtrip():
    f = Flag(Severity.WARNING, "msg", "S1")
    d = f.to_dict()
    assert d["severity"] == "warning"
    assert d["qid"] == "S1"
