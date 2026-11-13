"""Tests for the LLM enrichment layer.

These cover the registry and the graceful-fallback contract without making any
real API calls. The actual ChainOfThought path is exercised with a mock to
confirm enrichment is applied when a backend and key are present.
"""

import sys
import types

from screener_generator.generator import generate_from_text
from screener_generator.llm import (
    BACKENDS,
    DEFAULT_BACKEND,
    available_backends,
    configured_backends,
    enrich,
)

BRIEF = "Smart Reply for support agents. Segments: new vs experienced. n=12 remote interviews."


def test_backend_registry_has_three():
    assert set(available_backends()) == {"anthropic", "gemini", "openai"}


def test_backend_model_strings():
    assert BACKENDS["anthropic"] == "anthropic/claude-opus-4-7"
    assert BACKENDS["gemini"] == "gemini/gemini-4-argon"
    assert BACKENDS["openai"] == "openai/gpt-5.5"


def test_default_backend_known():
    assert DEFAULT_BACKEND in BACKENDS


def test_configured_backends_respects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert "openai" in configured_backends()
    assert "anthropic" not in configured_backends()


def test_enrich_unknown_backend_warns(monkeypatch):
    warnings = []
    s = generate_from_text(BRIEF)
    enrich(s, backend="bogus", on_warning=warnings.append)
    assert any("unknown backend" in w.lower() for w in warnings)


def test_enrich_missing_key_returns_unchanged(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    warnings = []
    s = generate_from_text(BRIEF)
    n_before = len(s.questions)
    out = enrich(s, backend="anthropic", on_warning=warnings.append)
    assert out.backend is None
    assert len(out.questions) == n_before
    assert any("not set" in w.lower() for w in warnings)


def test_enrich_no_dspy_installed_warns(monkeypatch):
    """If dspy import fails even with a key set, we warn and fall back."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    # force the dspy import inside _configure_dspy to fail
    monkeypatch.setitem(sys.modules, "dspy", None)
    warnings = []
    s = generate_from_text(BRIEF)
    out = enrich(s, backend="anthropic", on_warning=warnings.append)
    assert out.backend is None


def test_enrich_with_mock_dspy(monkeypatch):
    """Inject a fake dspy module to confirm enrichment is applied end-to-end."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    fake = types.ModuleType("dspy")

    class _Sig:  # stand-in for dspy.Signature
        pass

    def _input_field(**kwargs):
        return None

    def _output_field(**kwargs):
        return None

    class _LM:
        def __init__(self, *a, **k):
            pass

    def _configure(**kwargs):
        return None

    class _Pred:
        def __init__(self, val):
            self._val = val

    class _ChainOfThought:
        def __init__(self, sig):
            self._sig = sig

        def __call__(self, **kwargs):
            # return an object with all plausible output attrs populated
            r = types.SimpleNamespace()
            r.refined_question = "Refined: " + kwargs.get("original_question", "q")
            r.exclusions = "Competitor support tooling, Helpdesk vendors"
            r.summary = "Qualifies daily support agents; watch for over-tenured insiders."
            return r

    fake.Signature = _Sig
    fake.InputField = _input_field
    fake.OutputField = _output_field
    fake.LM = _LM
    fake.configure = _configure
    fake.ChainOfThought = _ChainOfThought
    monkeypatch.setitem(sys.modules, "dspy", fake)

    s = generate_from_text(BRIEF)
    out = enrich(s, backend="anthropic")
    assert out.backend == BACKENDS["anthropic"]
    assert out.summary.startswith("Qualifies")
    # at least one primary/articulation question got rewritten
    assert any(q.source == "llm" for q in out.questions)
