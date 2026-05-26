"""Standard screener question bank.

These are the field-tested building blocks every well-formed recruitment
screener tends to include, regardless of topic: a security/exclusion screen,
a recent-participation screen, an articulation check, and logistics/consent.
The generator assembles a screener from these plus brief-specific questions
derived from the parsed BriefSpec.

Each builder returns a ScreenerQuestion. Builders are pure and deterministic
so the rule-based path is fully reproducible offline.
"""

from __future__ import annotations

from .models import (
    AnswerOption,
    BriefSpec,
    Disposition,
    QuestionType,
    ScreenerQuestion,
    Section,
)

# Industries we routinely screen out to avoid professional/insider bias.
_SECURITY_INDUSTRIES = [
    "Market research",
    "Advertising, marketing or PR",
    "Product design or UX research",
    "Journalism or media",
]

_MODALITY_LOGISTICS = {
    "remote": (
        "For this study you would join a 60-minute video call and share your screen. "
        "Are you able to take part on a laptop or desktop computer with a working camera and microphone?"
    ),
    "in_person": (
        "This study takes place in person at our research facility. "
        "Are you able to travel to the session location at the scheduled time?"
    ),
    "unmoderated": (
        "This study is completed on your own time using your own device. "
        "Are you comfortable recording your screen while you complete a short set of tasks?"
    ),
}


def security_question() -> ScreenerQuestion:
    """The standard industry-exclusion / insider screen. Always first."""
    industries = _SECURITY_INDUSTRIES
    opts = [
        AnswerOption(code=str(i + 1), label=name, disposition=Disposition.TERMINATE)
        for i, name in enumerate(industries)
    ]
    opts.append(AnswerOption(code=str(len(industries) + 1), label="None of the above"))
    return ScreenerQuestion(
        qid="S1",
        section=Section.SECURITY,
        qtype=QuestionType.MULTI_SELECT,
        text=(
            "Do you, or does anyone in your immediate household, currently work "
            "in any of the following industries?"
        ),
        options=opts,
        logic=f"TERMINATE if any of codes 1–{len(industries)} selected.",
        rationale=(
            "Standard insider screen. People working in research, marketing, or the "
            "product domain answer as professionals rather than as users and bias the sample."
        ),
    )


def recent_participation_question() -> ScreenerQuestion:
    """Screens out professional respondents / research fatigue."""
    return ScreenerQuestion(
        qid="S2",
        section=Section.SECURITY,
        qtype=QuestionType.SINGLE_SELECT,
        text="When did you last take part in any market or user research study (interview, survey, or focus group)?",
        options=[
            AnswerOption(code="1", label="In the past month", disposition=Disposition.TERMINATE),
            AnswerOption(code="2", label="1–3 months ago"),
            AnswerOption(code="3", label="More than 3 months ago"),
            AnswerOption(code="4", label="Never / can't recall"),
        ],
        logic="TERMINATE if code 1 (participated within the last month).",
        rationale=(
            "Guards against professional participants and recency conditioning. "
            "Recent repeat participants often give rehearsed, research-savvy answers."
        ),
    )


def category_usage_question(spec: BriefSpec) -> ScreenerQuestion:
    """Confirms the respondent actually uses the product/category under study."""
    thing = spec.product or spec.category or "this type of product"
    return ScreenerQuestion(
        qid="P1",
        section=Section.PRIMARY,
        qtype=QuestionType.SINGLE_SELECT,
        text=f"How often do you personally use {thing}?",
        options=[
            AnswerOption(code="1", label="Daily or almost daily"),
            AnswerOption(code="2", label="A few times a week"),
            AnswerOption(code="3", label="A few times a month"),
            AnswerOption(code="4", label="Less than once a month", disposition=Disposition.TERMINATE),
            AnswerOption(code="5", label="Never", disposition=Disposition.TERMINATE),
        ],
        logic="TERMINATE if code 4 or 5 (insufficient exposure to speak to the experience).",
        rationale=(
            "A relevance screen. Without genuine recent exposure, feedback is hypothetical "
            "rather than grounded in lived use."
        ),
    )


def must_have_question(spec: BriefSpec) -> ScreenerQuestion | None:
    """A single-select that turns the brief's must-have criteria into a qualifier."""
    items = [m for m in spec.must_have if m][:4]
    if not items:
        return None
    opts = [AnswerOption(code=str(i + 1), label=item) for i, item in enumerate(items)]
    opts.append(
        AnswerOption(
            code=str(len(items) + 1),
            label="None of these apply to me",
            disposition=Disposition.TERMINATE,
        )
    )
    return ScreenerQuestion(
        qid="P2",
        section=Section.PRIMARY,
        qtype=QuestionType.MULTI_SELECT,
        text="Which of the following describes you? Select all that apply.",
        options=opts,
        logic=f"TERMINATE if only code {len(items) + 1} selected (no qualifying criteria met).",
        rationale=(
            "Operationalises the brief's must-have criteria into an auditable qualifier "
            "rather than leaving fit to recruiter judgement."
        ),
    )


def articulation_question(spec: BriefSpec) -> ScreenerQuestion:
    """Open-end that doubles as a quality / articulation screen."""
    topic = spec.product or spec.category or "the topic above"
    return ScreenerQuestion(
        qid="A1",
        section=Section.ARTICULATION,
        qtype=QuestionType.OPEN_END,
        text=(
            f"In a few sentences, describe the last time you used {topic} and what was "
            "going through your mind. There are no right or wrong answers."
        ),
        options=[],
        logic="MANUAL REVIEW — terminate one-word, off-topic, or incoherent answers before scheduling.",
        rationale=(
            "Articulation screen. Qualitative sessions depend on participants who can "
            "describe their reasoning; this surfaces that before a slot is booked."
        ),
    )


def logistics_question(spec: BriefSpec) -> ScreenerQuestion:
    """Confirms the respondent can take part in the chosen modality."""
    prompt = _MODALITY_LOGISTICS.get(spec.modality, _MODALITY_LOGISTICS["remote"])
    return ScreenerQuestion(
        qid="L1",
        section=Section.LOGISTICS,
        qtype=QuestionType.SINGLE_SELECT,
        text=prompt,
        options=[
            AnswerOption(code="1", label="Yes, I can take part as described"),
            AnswerOption(code="2", label="No / not sure", disposition=Disposition.TERMINATE),
        ],
        logic="TERMINATE if code 2 (cannot meet the modality requirement).",
        rationale="Prevents booking participants who cannot complete the session as designed.",
    )


def consent_question(spec: BriefSpec) -> ScreenerQuestion:
    """Recording consent. Phrased more carefully for sensitive topics."""
    extra = (
        " This study may touch on sensitive topics; you can skip any question and stop at any time."
        if spec.sensitive
        else ""
    )
    return ScreenerQuestion(
        qid="L2",
        section=Section.LOGISTICS,
        qtype=QuestionType.SINGLE_SELECT,
        text=(
            "The session will be recorded for research purposes and kept confidential. "
            f"Do you consent to taking part on these terms?{extra}"
        ),
        options=[
            AnswerOption(code="1", label="Yes, I consent"),
            AnswerOption(code="2", label="No", disposition=Disposition.TERMINATE),
        ],
        logic="TERMINATE if code 2 (no consent to participate / be recorded).",
        rationale=(
            "Ethical baseline. Informed, recorded consent is collected before scheduling, "
            "with an explicit opt-out for sensitive subject matter."
        ),
    )
