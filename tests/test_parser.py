"""Tests for the rule-based brief parser."""

from screener_generator.parser import parse_brief

SUPPORT = """Smart Reply for Team Inbox

We are building an AI-assisted reply feature for customer support agents.
Target audience: customer support agents who handle email and chat tickets daily.
Must have: use a shared team inbox at work; handle at least 20 tickets per week.
Segments: new agents vs experienced agents.
We want to recruit n=12 for remote, moderated 60-minute interviews.
Exclude: anyone who has taken part in research in the last month.
"""


def test_parses_product_from_first_line():
    spec = parse_brief(SUPPORT)
    assert "Smart Reply" in spec.product


def test_extracts_sample_size_from_n_notation():
    spec = parse_brief(SUPPORT)
    assert spec.sample_size == 12


def test_extracts_sample_size_from_words():
    spec = parse_brief("We want 8 participants for this study.")
    assert spec.sample_size == 8


def test_detects_segments_from_vs():
    spec = parse_brief(SUPPORT)
    labels = " ".join(spec.segments).lower()
    assert "new agents" in labels or "experienced agents" in labels


def test_detects_modality_remote():
    spec = parse_brief(SUPPORT)
    assert spec.modality == "remote"


def test_detects_modality_in_person():
    spec = parse_brief("We will run an in-person lab study with 6 users.")
    assert spec.modality == "in_person"


def test_detects_modality_unmoderated():
    spec = parse_brief("This is an unmoderated diary study.")
    assert spec.modality == "unmoderated"


def test_detects_audience_phrase():
    spec = parse_brief(SUPPORT)
    assert "support agents" in spec.audience.lower()


def test_extracts_must_have_list():
    spec = parse_brief(SUPPORT)
    assert len(spec.must_have) >= 1


def test_sensitive_flag_for_health():
    spec = parse_brief("A medical app for people managing a chronic health condition.")
    assert spec.sensitive is True


def test_non_sensitive_default():
    spec = parse_brief(SUPPORT)
    assert spec.sensitive is False


def test_empty_brief_returns_empty_spec():
    spec = parse_brief("")
    assert spec.product == ""
    assert spec.sample_size is None
    assert spec.segments == []


def test_whitespace_brief_is_safe():
    spec = parse_brief("   \n   ")
    assert spec.sample_size is None
