"""Tests for quota planning."""

from screener_generator.models import BriefSpec, Disposition
from screener_generator.quota import (
    DEFAULT_SAMPLE,
    _even_split,
    build_quota_plan,
    quota_question,
)


def test_even_split_basic():
    assert _even_split(12, 3) == [4, 4, 4]


def test_even_split_with_remainder():
    assert _even_split(10, 3) == [4, 3, 3]


def test_even_split_zero_cells():
    assert _even_split(10, 0) == []


def test_default_sample_when_missing():
    plan = build_quota_plan(BriefSpec())
    assert plan.total_completes == DEFAULT_SAMPLE
    assert any("defaulted" in n.lower() for n in plan.notes)


def test_single_cell_without_segments():
    plan = build_quota_plan(BriefSpec(sample_size=10))
    assert len(plan.cells) == 1
    assert plan.cells[0].group == "All"
    assert plan.cells[0].target == 10


def test_segments_split_sample():
    spec = BriefSpec(sample_size=12, segments=["New", "Experienced"])
    plan = build_quota_plan(spec)
    assert len(plan.cells) == 2
    assert sum(c.target for c in plan.cells) == 12


def test_quota_question_none_for_single_cell():
    plan = build_quota_plan(BriefSpec(sample_size=8))
    assert quota_question(plan) is None


def test_quota_question_routes_segments():
    spec = BriefSpec(sample_size=12, segments=["New", "Experienced"])
    plan = build_quota_plan(spec)
    q = quota_question(plan)
    assert q is not None
    quota_opts = [o for o in q.options if o.disposition is Disposition.QUOTA]
    assert len(quota_opts) == 2
    # final option terminates (no segment fit)
    assert q.options[-1].disposition is Disposition.TERMINATE


def test_quota_cells_carry_targets_into_logic():
    spec = BriefSpec(sample_size=12, segments=["A", "B"])
    q = quota_question(build_quota_plan(spec))
    assert "n=" in q.logic
