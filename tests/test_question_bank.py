"""Tests for the standard question bank."""

from screener_generator import question_bank as qb
from screener_generator.models import (
    BriefSpec,
    Disposition,
    QuestionType,
    Section,
)


def test_security_question_terminates_industries():
    q = qb.security_question()
    assert q.section is Section.SECURITY
    assert q.qtype is QuestionType.MULTI_SELECT
    # all but the final "None" option terminate
    assert len(q.terminating_codes) == len(q.options) - 1
    assert "none" in q.options[-1].label.lower()


def test_recent_participation_terminates_recent():
    q = qb.recent_participation_question()
    assert q.options[0].disposition is Disposition.TERMINATE
    assert "month" in q.options[0].label.lower()


def test_category_usage_uses_product_name():
    spec = BriefSpec(product="Smart Reply")
    q = qb.category_usage_question(spec)
    assert "Smart Reply" in q.text
    # the two lowest-frequency options terminate
    assert len(q.terminating_codes) == 2


def test_category_usage_falls_back_without_product():
    q = qb.category_usage_question(BriefSpec())
    assert "this type of product" in q.text


def test_must_have_question_none_when_empty():
    assert qb.must_have_question(BriefSpec()) is None


def test_must_have_question_builds_options():
    spec = BriefSpec(must_have=["uses a team inbox", "handles 20+ tickets/week"])
    q = qb.must_have_question(spec)
    assert q is not None
    assert q.qtype is QuestionType.MULTI_SELECT
    # last option ("none apply") terminates
    assert q.options[-1].disposition is Disposition.TERMINATE


def test_articulation_is_open_end():
    q = qb.articulation_question(BriefSpec(product="X"))
    assert q.qtype is QuestionType.OPEN_END
    assert q.options == []


def test_logistics_text_varies_by_modality():
    remote = qb.logistics_question(BriefSpec(modality="remote"))
    inperson = qb.logistics_question(BriefSpec(modality="in_person"))
    assert remote.text != inperson.text


def test_consent_adds_sensitive_note():
    sensitive = qb.consent_question(BriefSpec(sensitive=True))
    plain = qb.consent_question(BriefSpec(sensitive=False))
    assert "sensitive" in sensitive.text.lower()
    assert "sensitive" not in plain.text.lower()


def test_consent_terminates_on_no():
    q = qb.consent_question(BriefSpec())
    assert q.options[-1].disposition is Disposition.TERMINATE
