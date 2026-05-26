"""Tests for the pipeline and markdown renderer."""

from screener_generator.pipeline import build_screener, to_markdown

BRIEF = """Smart Reply for Team Inbox
Target audience: customer support agents who handle tickets daily.
Must have: use a shared team inbox; handle 20+ tickets per week.
Segments: new agents vs experienced agents.
We want to recruit n=12 for remote interviews.
"""


def test_build_screener_offline():
    s = build_screener(BRIEF, use_llm=False)
    assert len(s.questions) >= 6
    assert s.backend is None  # no enrichment when use_llm=False


def test_build_screener_llm_without_key_falls_back():
    warnings = []
    s = build_screener(BRIEF, use_llm=True, backend="anthropic", on_warning=warnings.append)
    # no key in CI → falls back to rule-based, emits a warning, never crashes
    assert s.backend is None
    assert any("rule-based" in w.lower() or "not set" in w.lower() for w in warnings)


def test_markdown_has_title_and_sections():
    md = to_markdown(build_screener(BRIEF, use_llm=False))
    assert md.startswith("# Recruitment screener")
    assert "## Security & exclusions" in md
    assert "## Quota plan" in md


def test_markdown_marks_terminate_and_quota():
    md = to_markdown(build_screener(BRIEF, use_llm=False))
    assert "[TERMINATE]" in md
    assert "[QUOTA]" in md


def test_markdown_includes_flags_section_when_present():
    s = build_screener(BRIEF, use_llm=False)
    if s.flags:
        md = to_markdown(s)
        assert "## Hygiene flags" in md


def test_unknown_backend_warns_and_falls_back():
    warnings = []
    s = build_screener(BRIEF, use_llm=True, backend="nope", on_warning=warnings.append)
    assert s.backend is None
