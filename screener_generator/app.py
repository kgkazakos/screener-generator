"""Streamlit UI for screener-generator.

Run with:  streamlit run screener_generator/app.py

Visual language matches the rest of the CPR Orbital Series: DM Sans for body,
DM Mono for codes/labels, a calm light theme with a single warm accent.
"""

from __future__ import annotations

import json

import streamlit as st

from screener_generator.llm import available_backends, configured_backends
from screener_generator.models import SECTION_LABELS, SECTION_ORDER, Disposition
from screener_generator.pipeline import build_screener, to_markdown

st.set_page_config(
    page_title="screener-generator · CPR Orbital",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', system-ui, sans-serif; }
    code, .stCode, .mono { font-family: 'DM Mono', monospace !important; }

    .app-title { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em; color: #1a1a1a; margin-bottom: 0; }
    .app-sub { font-size: 0.85rem; color: #888; margin-top: 2px; margin-bottom: 1.4rem; }

    .stat-card { background:#fafafa; border:1px solid #e5e5e5; border-radius:10px; padding:0.85rem 1rem; }
    .stat-num  { font-size:1.7rem; font-weight:700; line-height:1; color:#1a1a1a; }
    .stat-lbl  { font-size:0.72rem; color:#888; margin-top:4px; text-transform:uppercase; letter-spacing:0.04em; }

    .qcard { border:1px solid #e5e5e5; border-left:3px solid #D85A30; border-radius:10px;
             padding:0.9rem 1.1rem; margin-bottom:0.7rem; background:#fff; }
    .qhead { display:flex; align-items:baseline; gap:8px; margin-bottom:6px; flex-wrap:wrap; }
    .qid   { font-family:'DM Mono',monospace; font-size:0.78rem; font-weight:500; color:#D85A30; }
    .qtext { font-size:0.95rem; font-weight:500; color:#1a1a1a; }
    .qtype { font-size:0.68rem; color:#888; background:#f1f1f1; border-radius:4px; padding:1px 7px;
             font-family:'DM Mono',monospace; }
    .llmtag{ font-size:0.62rem; color:#7F77DD; border:1px solid #d6d2f2; background:#f3f1fc;
             border-radius:4px; padding:0px 6px; font-family:'DM Mono',monospace; }
    .opt   { font-size:0.85rem; color:#444; padding:1px 0; }
    .ocode { font-family:'DM Mono',monospace; color:#aaa; font-size:0.78rem; }
    .term  { color:#c1392b; font-size:0.72rem; font-weight:500; }
    .quotapill { color:#0f6e56; font-size:0.72rem; font-weight:500; }
    .why   { font-size:0.78rem; color:#777; line-height:1.45; margin-top:6px; border-top:1px dashed #eee; padding-top:6px; }
    .logic { font-size:0.76rem; color:#854f0b; font-family:'DM Mono',monospace; margin-top:4px; }
    .seccap{ font-size:0.72rem; font-weight:700; color:#999; text-transform:uppercase; letter-spacing:0.06em;
             margin:1.1rem 0 0.5rem; }
    .flag  { font-size:0.82rem; padding:5px 10px; border-radius:6px; margin-bottom:5px; }
    .f-critical { background:#faece7; color:#993c1d; border:1px solid #f1c6b6; }
    .f-warning  { background:#faeeda; color:#854f0b; border:1px solid #fac775; }
    .f-info     { background:#e6f1fb; color:#185fa5; border:1px solid #b5d4f4; }
    .summary { background:#fbf7f4; border:1px solid #efe1d8; border-radius:10px; padding:0.9rem 1.1rem;
               font-size:0.9rem; color:#4a4a4a; line-height:1.55; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="app-title">screener-generator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-sub">Turn a research brief into a fieldwork-ready recruitment screener — '
    "qualifying questions, quota logic, disqualification criteria · CPR Orbital #34</div>",
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    use_llm = st.toggle("LLM enrichment", value=True, help="Rewrites questions to be study-specific.")
    backend = st.selectbox(
        "Backend",
        options=available_backends(),
        index=0,
        format_func=lambda b: {
            "anthropic": "Claude Opus",
            "gemini": "Gemini 4 Argon",
            "openai": "GPT-5.5",
        }.get(b, b),
        disabled=not use_llm,
    )
    configured = set(configured_backends())
    if use_llm and backend not in configured:
        st.caption(f"⚠︎ No API key for {backend} — will fall back to the offline rule-based screener.")
    st.divider()
    st.markdown(
        "**Rule-based core** runs fully offline.\n\n"
        "LLM enrichment is **additive** — it never removes the security, articulation, "
        "or consent screens.",
    )

# ── Input ──────────────────────────────────────────────────────────────────
SAMPLE_BRIEF = """Smart Reply for Team Inbox

We are building an AI-assisted reply feature for customer support agents inside
a shared team inbox. It drafts a suggested reply the agent can send as-is or edit.

Target audience: customer support agents who handle email and chat tickets daily.
Must have: use a shared team inbox at work; handle at least 20 tickets per week.
Segments: new agents vs experienced agents.
We want to recruit n=12 for remote, moderated 60-minute interviews.
Exclude: anyone who has taken part in research in the last month.
"""

col_in, col_btn = st.columns([5, 1])
with col_in:
    brief = st.text_area(
        "Research brief",
        value=SAMPLE_BRIEF,
        height=190,
        label_visibility="collapsed",
        placeholder="Paste a PM brief, PRD excerpt, or study description…",
    )
with col_btn:
    run = st.button("Generate", type="primary", use_container_width=True)

st.divider()

if run or brief:
    warnings: list[str] = []
    screener = build_screener(brief, use_llm=use_llm, backend=backend, on_warning=warnings.append)

    for w in warnings:
        st.caption(f"⚠︎ {w}")

    # Stat cards
    cols = st.columns(4)
    stats = [
        (str(len(screener.questions)), "Questions"),
        (str(screener.terminate_count), "Terminating"),
        (f"~{screener.incidence_estimate:.0%}" if screener.incidence_estimate is not None else "—", "Est. incidence"),
        (f"n={screener.quota.total_completes}" if screener.quota else "—", "Target completes"),
    ]
    for c, (num, lbl) in zip(cols, stats, strict=False):
        c.markdown(f'<div class="stat-card"><div class="stat-num">{num}</div>'
                   f'<div class="stat-lbl">{lbl}</div></div>', unsafe_allow_html=True)

    if screener.summary:
        st.markdown(f'<div class="summary">{screener.summary}</div>', unsafe_allow_html=True)

    tab_q, tab_quota, tab_flags, tab_md, tab_json = st.tabs(
        ["Screener", "Quota plan", f"Flags ({len(screener.flags)})", "Markdown", "JSON"]
    )

    with tab_q:
        by_section: dict = {}
        for q in screener.questions_in_order():
            by_section.setdefault(q.section, []).append(q)
        for section in SECTION_ORDER:
            qs = by_section.get(section)
            if not qs:
                continue
            st.markdown(f'<div class="seccap">{SECTION_LABELS[section]}</div>', unsafe_allow_html=True)
            for q in qs:
                opts_html = ""
                for o in q.options:
                    mark = ""
                    if o.disposition is Disposition.TERMINATE:
                        mark = ' <span class="term">✕ terminate</span>'
                    elif o.disposition is Disposition.QUOTA:
                        mark = f' <span class="quotapill">→ {o.quota_cell}</span>'
                    opts_html += f'<div class="opt"><span class="ocode">{o.code}</span> {o.label}{mark}</div>'
                llm = '<span class="llmtag">llm</span>' if q.source == "llm" else ""
                logic = f'<div class="logic">{q.logic}</div>' if q.logic else ""
                why = f'<div class="why">{q.rationale}</div>' if q.rationale else ""
                st.markdown(
                    f'<div class="qcard"><div class="qhead"><span class="qid">{q.qid}</span>'
                    f'<span class="qtext">{q.text}</span>'
                    f'<span class="qtype">{q.qtype.value.replace("_", " ")}</span>{llm}</div>'
                    f"{opts_html}{logic}{why}</div>",
                    unsafe_allow_html=True,
                )

    with tab_quota:
        if screener.quota and screener.quota.cells:
            st.dataframe(
                {
                    "Group": [c.group for c in screener.quota.cells],
                    "Cell": [c.label for c in screener.quota.cells],
                    "Target": [c.target for c in screener.quota.cells],
                },
                hide_index=True,
                use_container_width=True,
            )
            for n in screener.quota.notes:
                st.caption(n)
        else:
            st.caption("No quota cells.")

    with tab_flags:
        if screener.flags:
            st.caption("Probe signals to review before fielding — not pass/fail verdicts.")
            for f in screener.flags:
                cls = {"critical": "f-critical", "warning": "f-warning", "info": "f-info"}[f.severity.value]
                where = f" · {f.qid}" if f.qid else ""
                st.markdown(
                    f'<div class="flag {cls}"><b>{f.severity.value.upper()}</b>{where} — {f.message}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No hygiene flags raised.")

    with tab_md:
        md = to_markdown(screener)
        st.code(md, language="markdown")
        st.download_button("Download screener.md", md, file_name="screener.md")

    with tab_json:
        payload = json.dumps(screener.to_dict(), indent=2)
        st.code(payload, language="json")
        st.download_button("Download screener.json", payload, file_name="screener.json")
