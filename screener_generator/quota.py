"""Quota planning.

Turns the parsed segments and target sample size into an explicit quota plan
(named cells with target counts) and a matching quota-screening question whose
options route respondents into those cells.

The split is deterministic: completes are distributed as evenly as possible
across cells, with any remainder pushed to the earliest cells. This is a
planning aid — real fieldwork quotas are negotiated with incidence and budget,
which the notes call out explicitly.
"""

from __future__ import annotations

from .models import (
    AnswerOption,
    BriefSpec,
    Disposition,
    QuestionType,
    QuotaCell,
    QuotaPlan,
    ScreenerQuestion,
    Section,
)

DEFAULT_SAMPLE = 12  # a sensible default total for a moderated qual study


def _even_split(total: int, n_cells: int) -> list[int]:
    """Distribute `total` across `n_cells`, remainder to the earliest cells."""
    if n_cells <= 0:
        return []
    base, rem = divmod(total, n_cells)
    return [base + (1 if i < rem else 0) for i in range(n_cells)]


def build_quota_plan(spec: BriefSpec) -> QuotaPlan:
    """Build a QuotaPlan from the brief's segments and sample size."""
    total = spec.sample_size or DEFAULT_SAMPLE
    segments = [s for s in spec.segments if s]

    notes: list[str] = []
    if spec.sample_size is None:
        notes.append(
            f"No sample size found in the brief — defaulted to n={DEFAULT_SAMPLE}. Adjust to your study."
        )

    if not segments:
        notes.append("No segments detected — a single open cell is used. Add segments to split quotas.")
        return QuotaPlan(
            total_completes=total,
            cells=[QuotaCell(group="All", label="All qualified participants", target=total)],
            notes=notes,
        )

    splits = _even_split(total, len(segments))
    cells = [
        QuotaCell(group="Segment", label=seg, target=count)
        for seg, count in zip(segments, splits, strict=False)
    ]
    notes.append(
        "Cells are an even split of the target sample. Re-weight by expected incidence and priority before fielding."
    )
    return QuotaPlan(total_completes=total, cells=cells, notes=notes)


def quota_question(plan: QuotaPlan) -> ScreenerQuestion | None:
    """A single-select that routes a respondent into one of the quota cells.

    Returns None when there is only a single 'All' cell (nothing to route).
    """
    segment_cells = [c for c in plan.cells if c.group != "All"]
    if not segment_cells:
        return None

    options = [
        AnswerOption(
            code=str(i + 1),
            label=cell.label,
            disposition=Disposition.QUOTA,
            quota_cell=cell.label,
        )
        for i, cell in enumerate(segment_cells)
    ]
    options.append(
        AnswerOption(
            code=str(len(segment_cells) + 1),
            label="None of these / prefer not to say",
            disposition=Disposition.TERMINATE,
        )
    )
    targets = ", ".join(f"{c.label}: n={c.target}" for c in segment_cells)
    return ScreenerQuestion(
        qid="Q1",
        section=Section.QUOTA,
        qtype=QuestionType.SINGLE_SELECT,
        text="Which of the following best describes you?",
        options=options,
        logic=f"Assign to quota cell by selection. Targets — {targets}. "
        f"TERMINATE on the final option (no segment fit).",
        rationale=(
            "Routes qualified respondents into the segment quotas defined for this study, "
            "so the sample is balanced by design rather than by whoever signs up first."
        ),
    )
