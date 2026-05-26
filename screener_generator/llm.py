"""Optional LLM enrichment for screener-generator.

The deterministic core in `generator.py` produces a complete, fieldable
screener with zero API calls. This layer is *additive*: when a backend and key
are available it (a) tightens the brief parse, (b) rewrites question wording to
be specific to the study, (c) proposes category-relevant security exclusions,
and (d) writes a short recruiter-facing summary. It never removes the security,
articulation, or consent screens, and it never invents a verdict.

LLM support is ON BY DEFAULT across three backends:

    anthropic  → anthropic/claude-opus-4-7      (Claude Opus)
    gemini     → gemini/gemini-3.1-pro-preview  (Gemini 3.1 Pro)
    openai     → openai/gpt-5.5                  (GPT-5.5)

If DSPy / LiteLLM is not installed, or no API key is set, enrichment is skipped
and the rule-based screener is returned unchanged (with a warning). This means
the tool *never hard-fails* on a missing key — `--no-llm` simply forces that
same offline path explicitly.

The module is intentionally import-light at module load so the core package and
its tests have no hard dependency on dspy/litellm.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from .models import Disposition, Screener

# Canonical backend → model string map. Update model strings here only.
BACKENDS: dict[str, str] = {
    "anthropic": "anthropic/claude-opus-4-7",
    "gemini": "gemini/gemini-3.1-pro-preview",
    "openai": "openai/gpt-5.5",
}

DEFAULT_BACKEND = "anthropic"

# Which env var must be present for each backend to be usable.
_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

OnWarning = Callable[[str], None] | None


def available_backends() -> list[str]:
    """All backend names the tool knows about (regardless of key presence)."""
    return list(BACKENDS.keys())


def configured_backends() -> list[str]:
    """Backends that actually have an API key set in the environment."""
    return [name for name, env in _ENV_KEYS.items() if os.getenv(env)]


def _warn(on_warning: OnWarning, msg: str) -> None:
    if on_warning is not None:
        on_warning(msg)


def _configure_dspy(backend: str):
    """Configure and return a dspy module, or None if unavailable."""
    try:
        import dspy  # type: ignore
    except ImportError:
        return None
    model = BACKENDS.get(backend, BACKENDS[DEFAULT_BACKEND])
    lm = dspy.LM(model)
    dspy.configure(lm=lm)
    return dspy


# ── DSPy signatures (only referenced when dspy is importable) ────────────────

def _build_signatures(dspy):
    class RefineQuestion(dspy.Signature):
        """Rewrite a recruitment screener question so it is specific to the study,
        neutral (not leading), and answerable, while keeping its intent and type."""

        study_context: str = dspy.InputField(desc="product / audience under study")
        original_question: str = dspy.InputField()
        refined_question: str = dspy.OutputField(desc="improved, neutral, study-specific wording")

    class ProposeExclusions(dspy.Signature):
        """Given the product category, list 2–3 additional industries or roles whose
        members would answer as insiders and should be screened out. Comma-separated."""

        category: str = dspy.InputField()
        exclusions: str = dspy.OutputField(desc="comma-separated industries/roles to exclude")

    class WriteSummary(dspy.Signature):
        """Write a 2–3 sentence recruiter-facing summary of who this screener
        qualifies and the key risks to watch during recruitment."""

        study_context: str = dspy.InputField()
        qualifies: str = dspy.InputField(desc="brief description of qualifying criteria")
        summary: str = dspy.OutputField()

    return RefineQuestion, ProposeExclusions, WriteSummary


def enrich(
    screener: Screener,
    backend: str = DEFAULT_BACKEND,
    on_warning: OnWarning = None,
) -> Screener:
    """Enrich a rule-based screener in place and return it.

    Falls back silently-but-with-a-warning to the unchanged screener whenever
    DSPy/LiteLLM is missing or the backend has no API key configured.
    """
    if backend not in BACKENDS:
        _warn(on_warning, f"Unknown backend '{backend}'; skipping enrichment.")
        return screener

    env_key = _ENV_KEYS[backend]
    if not os.getenv(env_key):
        _warn(
            on_warning,
            f"{env_key} not set — returning the rule-based screener without LLM enrichment.",
        )
        return screener

    dspy = _configure_dspy(backend)
    if dspy is None:
        _warn(on_warning, "dspy/litellm not installed — install the [llm] extra to enable enrichment.")
        return screener

    try:
        RefineQuestion, ProposeExclusions, WriteSummary = _build_signatures(dspy)
        refine = dspy.ChainOfThought(RefineQuestion)
        propose = dspy.ChainOfThought(ProposeExclusions)
        summarise = dspy.ChainOfThought(WriteSummary)

        ctx = f"{screener.spec.product or screener.spec.category or 'the product'} — {screener.spec.audience or 'general users'}"

        # (a) refine the open-ended and primary questions for specificity
        for q in screener.questions:
            if q.section.value in ("primary", "articulation"):
                out = refine(study_context=ctx, original_question=q.text)
                refined = (out.refined_question or "").strip()
                if refined and refined != q.text:
                    q.text = refined
                    q.source = "llm"

        # (b) propose extra security exclusions for the category
        if screener.spec.category or screener.spec.product:
            out = propose(category=screener.spec.category or screener.spec.product)
            extras = [e.strip() for e in (out.exclusions or "").split(",") if e.strip()][:3]
            sec = next((q for q in screener.questions if q.qid == "S1"), None)
            if sec and extras:
                none_opt = sec.options.pop() if sec.options and "none" in sec.options[-1].label.lower() else None
                start = len(sec.options) + 1
                for i, ex in enumerate(extras):
                    sec.options.append(
                        type(sec.options[0])(
                            code=str(start + i),
                            label=ex,
                            disposition=Disposition.TERMINATE,
                        )
                    )
                if none_opt is not None:
                    none_opt.code = str(len(sec.options) + 1)
                    sec.options.append(none_opt)
                sec.logic = f"TERMINATE if any of codes 1–{len(sec.options) - 1} selected."
                sec.source = "llm"

        # (c) recruiter summary
        qualifies = screener.spec.audience or screener.spec.product or "qualified users of the product"
        out = summarise(study_context=ctx, qualifies=qualifies)
        summary = (out.summary or "").strip()
        if summary:
            screener.summary = summary

        screener.backend = BACKENDS[backend]
    except Exception as exc:  # noqa: BLE001 — never let enrichment crash the run
        _warn(on_warning, f"LLM enrichment failed ({exc.__class__.__name__}); returning rule-based screener.")

    return screener
