"""Tests for the data models."""

from screener_generator.models import (
    SECTION_ORDER,
    AnswerOption,
    BriefSpec,
    Disposition,
    QuestionType,
    QuotaCell,
    QuotaPlan,
    Screener,
    ScreenerQuestion,
    Section,
)


def _q(qid, section, term=False):
    opts = [
        AnswerOption("1", "Yes", Disposition.TERMINATE if term else Disposition.CONTINUE),
        AnswerOption("2", "No"),
    ]
    return ScreenerQuestion(qid=qid, section=section, qtype=QuestionType.SINGLE_SELECT, text="t", options=opts)


def test_answer_option_to_dict():
    o = AnswerOption("1", "Yes", Disposition.QUOTA, quota_cell="New")
    d = o.to_dict()
    assert d["disposition"] == "quota"
    assert d["quota_cell"] == "New"


def test_terminating_codes_property():
    q = _q("S1", Section.SECURITY, term=True)
    assert q.terminating_codes == ["1"]


def test_questions_in_order_sorts_by_section():
    s = Screener(
        spec=BriefSpec(),
        questions=[_q("L1", Section.LOGISTICS), _q("S1", Section.SECURITY)],
    )
    ordered = s.questions_in_order()
    assert ordered[0].section is Section.SECURITY
    assert ordered[-1].section is Section.LOGISTICS


def test_section_order_complete():
    # every section listed exactly once
    assert len(SECTION_ORDER) == len(set(SECTION_ORDER))


def test_quota_plan_to_dict():
    plan = QuotaPlan(total_completes=12, cells=[QuotaCell("Segment", "New", 6)], notes=["n"])
    d = plan.to_dict()
    assert d["total_completes"] == 12
    assert d["cells"][0]["target"] == 6


def test_screener_to_dict_counts():
    s = Screener(spec=BriefSpec(product="X"), questions=[_q("S1", Section.SECURITY, term=True)])
    d = s.to_dict()
    assert d["counts"]["questions"] == 1
    assert d["counts"]["terminating"] == 1


def test_brief_spec_to_dict_keys():
    d = BriefSpec(product="X", sample_size=10).to_dict()
    assert d["product"] == "X"
    assert d["sample_size"] == 10
    assert d["modality"] == "remote"
