"""Rule-based brief parser.

Reads a free-text or markdown research brief and extracts the handful of facts
a screener actually depends on: who we want, who we must exclude, how many,
and how the study runs. Everything is heuristic and deliberately conservative
— when the brief is vague, fields stay empty and the generator falls back to
sensible defaults rather than inventing specifics.

No LLM here. The optional llm layer refines the BriefSpec this produces.
"""

from __future__ import annotations

import re

from .models import BriefSpec

# ── Lightweight signal vocabularies ─────────────────────────────────────────

_SAMPLE_RE = re.compile(r"\bn\s*=\s*(\d{1,4})\b", re.IGNORECASE)
_SAMPLE_WORDS_RE = re.compile(
    r"\b(\d{1,4})\s+(?:participants?|respondents?|users?|people|interviews?|completes?)\b",
    re.IGNORECASE,
)

_MODALITY_HINTS = {
    "in_person": ["in person", "in-person", "lab", "on-site", "on site", "field visit", "ethnograph"],
    "unmoderated": ["unmoderated", "self-serve", "self serve", "diary study", "survey", "async"],
    "remote": ["remote", "moderated", "video call", "zoom", "interview"],
}

_SENSITIVE_HINTS = [
    "health", "medical", "clinical", "mental", "finance", "financial", "banking",
    "credit", "debt", "children", "child", "minor", "immigration", "legal",
    "disability", "addiction", "pregnan",
]

# Phrases that introduce a target audience in a brief.
_AUDIENCE_CUES = [
    "target audience", "target users", "we want to talk to", "we want to speak to",
    "recruit", "participants are", "audience:", "users:", "who:", "talk to",
    "speak with", "interview", "people who",
]

# Phrases that introduce exclusions.
_EXCLUDE_CUES = ["exclude", "not include", "screen out", "no ", "must not", "avoid recruiting"]


def _first_sentence_after(text: str, cues: list[str]) -> str:
    """Return the clause following the first matched cue, trimmed."""
    low = text.lower()
    for cue in cues:
        idx = low.find(cue)
        if idx == -1:
            continue
        tail = text[idx + len(cue):]
        # stop at sentence / line / list boundaries
        clause = re.split(r"[.\n;•\-–]| and ", tail, maxsplit=1)[0]
        clause = clause.strip(" :,-")
        if len(clause) >= 3:
            return clause
    return ""


def _extract_segments(text: str) -> list[str]:
    """Pull candidate segment labels from explicit segment cues.

    Looks for patterns like "two segments: A and B" or bulleted "Segment:" lines.
    """
    segments: list[str] = []
    low = text.lower()

    # "segments: a, b and c"  /  "split by ... a vs b"
    m = re.search(r"segments?\s*[:\-]\s*([^\n.]+)", low)
    if m:
        chunk = m.group(1)
        parts = re.split(r",| and | vs\.? | versus | or ", chunk)
        segments += [p.strip() for p in parts if 2 <= len(p.strip()) <= 40]

    # "novice vs expert", "new vs returning"
    for m in re.finditer(r"\b([a-z][a-z \-]{2,20})\s+(?:vs\.?|versus)\s+([a-z][a-z \-]{2,20})\b", low):
        segments += [m.group(1).strip(), m.group(2).strip()]

    # de-dupe, preserve order, title-case for display
    seen: set[str] = set()
    out: list[str] = []
    for s in segments:
        key = s.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(s.strip().title())
    return out[:6]


def _extract_list(text: str, header_words: list[str]) -> list[str]:
    """Extract bullet/comma items that follow a header line like 'Must have:'."""
    out: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        low = line.lower().strip()
        if any(low.startswith(h) or (h + ":") in low for h in header_words):
            after = re.split(r"[:\-]", line, maxsplit=1)
            tail = after[1] if len(after) > 1 else ""
            if tail.strip():
                out += [p.strip(" .•-") for p in re.split(r",|;| and ", tail) if p.strip(" .•-")]
            # also pull following bullet lines
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if s.startswith(("-", "•", "*")) or re.match(r"^\d+[.)]", s):
                    out.append(s.lstrip("-•* ").lstrip("0123456789.) ").strip())
                elif s == "":
                    continue
                else:
                    break
            break
    return [o for o in out if 2 <= len(o) <= 80][:8]


def _detect_modality(text: str) -> str:
    low = text.lower()
    for modality in ("in_person", "unmoderated"):
        if any(h in low for h in _MODALITY_HINTS[modality]):
            return modality
    return "remote"


def _detect_sensitive(text: str) -> bool:
    low = text.lower()
    return any(h in low for h in _SENSITIVE_HINTS)


def _extract_sample(text: str) -> int | None:
    m = _SAMPLE_RE.search(text)
    if m:
        return int(m.group(1))
    m = _SAMPLE_WORDS_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _extract_product(text: str) -> str:
    """Best-effort product/feature name.

    Priority: an explicit short title line (the most reliable signal in a brief)
    → an explicit "Product:/Feature:/Project:" label → a "we are building…" clause.
    """
    lines = [ln.strip().lstrip("#").strip() for ln in text.splitlines()]
    # 1. first non-empty, non-bullet line that reads like a title (reasonably short)
    for s in lines:
        if s and not s.startswith(("-", "•", "*")) and len(s) <= 60 and not s.lower().startswith(
            ("we ", "this ", "the goal", "our team")
        ):
            return s[:80]
    # 2. explicit label
    explicit = _first_sentence_after(text, ["product:", "feature:", "project:", "we are building", "we're building"])
    if explicit:
        return explicit[:80]
    # 3. otherwise the first non-empty line, whatever it is
    for s in lines:
        if s and not s.startswith(("-", "•", "*")):
            return s[:80]
    return ""


def parse_brief(text: str) -> BriefSpec:
    """Parse a research brief into a structured BriefSpec.

    The extraction is heuristic; missing fields stay empty so downstream
    code can supply defaults rather than guessing from thin evidence.
    """
    text = (text or "").strip()
    spec = BriefSpec()
    if not text:
        return spec

    spec.product = _extract_product(text)
    spec.audience = _first_sentence_after(text, _AUDIENCE_CUES)
    spec.category = _first_sentence_after(text, ["category:", "in the", "market:", "domain:"])
    spec.segments = _extract_segments(text)
    spec.must_have = _extract_list(text, ["must have", "must-have", "require", "criteria", "qualif"])
    spec.exclude = _extract_list(text, ["exclude", "screen out", "disqualif", "not eligible"])
    if not spec.exclude:
        clause = _first_sentence_after(text, _EXCLUDE_CUES)
        if clause:
            spec.exclude = [clause[:60]]
    spec.sample_size = _extract_sample(text)
    spec.modality = _detect_modality(text)
    spec.sensitive = _detect_sensitive(text)
    return spec
