# screener-generator

**Turn a research brief into a fieldwork-ready recruitment screener — qualifying questions, quota logic, and disqualification criteria.**

CPR Orbital · Tool #34 · Season 6 (Pre-study & impact)

Recruitment is where a study quietly succeeds or fails. Get the screener wrong and you either over-screen — burning incidence and budget while the panel stalls — or under-screen and end up with sessions full of people who were never really in scope. `screener-generator` takes a short brief (a PM note, a PRD excerpt, a few lines of study description) and drafts the screener you would otherwise hand-build: a security/exclusion screen, the primary qualifiers, quota routing, an articulation check, and consent — ordered the way a recruiter expects to read it.

It is a drafting partner, not an autopilot. Every screener it produces is meant to be read, edited, and signed off by the person running the study.

---

## What you get

- **A complete, ordered screener** — security & exclusions, primary qualifiers, quota routing, articulation, logistics & consent — with terminating logic and quota cells already wired in.
- **A quota plan** — segments split into target cells with a recruitable total, ready to re-weight by incidence and priority.
- **A rough incidence estimate** — an order-of-magnitude qualifying rate so you can sanity-check how slow and costly recruitment is likely to be *before* you field.
- **Hygiene flags** — probe signals (leading wording, double-barrelled phrasing, missing essentials, over-screening) to review before fielding. These are prompts for your judgement, never pass/fail verdicts.
- **Recruiter-ready output** — clean Markdown and JSON, plus a CLI, a Python API, and a Streamlit UI.

## Install

```bash
pip install -e .
# optional LLM enrichment (any one provider, or all):
pip install -e ".[anthropic]"   # Claude Opus
pip install -e ".[gemini]"      # Gemini 3.1 Pro
pip install -e ".[openai]"      # GPT-5.5
pip install -e ".[ui]"          # Streamlit UI
```

## Use it

```bash
# from a brief file
screener-gen generate brief.md

# from stdin, offline only, as JSON
cat brief.md | screener-gen generate - --no-llm --json-output

# which backends are wired up?
screener-gen backends
```

```python
from screener_generator.pipeline import build_screener, to_markdown

screener = build_screener(open("brief.md").read())   # LLM on by default
print(to_markdown(screener))
```

```bash
streamlit run screener_generator/app.py
```

## How it works

A deterministic rule-based core does the structural work: it parses the brief into a spec (product, audience, must-haves, exclusions, segments, sample size, modality, sensitivity), assembles the standard screener sections from a question bank, builds the quota plan, and runs hygiene checks. This core **runs fully offline with zero API calls** and is the automatic fallback.

LLM enrichment is **on by default** but strictly **additive** — it rewrites questions to be specific to *your* product and audience and drafts a short summary, but it never removes the security, articulation, or consent screens, and never invents qualifying logic the core didn't establish. If no API key is set, enrichment quietly steps aside and you get the rule-based screener with a warning, never a crash. Use `--no-llm` to force the offline path.

Three backends are configured in `llm.py`:

- `anthropic/claude-opus-4-7` (Claude Opus)
- `gemini/gemini-3.1-pro-preview` (Gemini 3.1 Pro)
- `openai/gpt-5.5` (GPT-5.5)

## What this is

- A fast way to get from a brief to a *first-draft* screener you can edit, so the blank page isn't the bottleneck.
- A consistency aid — the essential screens (security, articulation, consent) are always present, so they don't get forgotten under deadline.
- A pre-field sanity check — the incidence estimate and hygiene flags surface the things that quietly sink recruitment.

## What this is not

- **Not a replacement for recruiter and researcher judgement.** Quota targets, incidence assumptions, and qualifying thresholds are yours to set; the tool gives you a defensible starting point, not a final answer.
- **Not a guarantee of representativeness.** A clean screener recruits the people it describes — whether those are the right people is a sampling-design question the tool can't decide for you.
- **Not a verdict machine.** The incidence figure is an order-of-magnitude estimate, and the flags are probe signals. They tell you what to look at and why; you decide what to do.

## Where it sits

`screener-generator` is the second tool in **Season 6 (Pre-study & impact)** of the CPR Orbital series, following [`brief-to-questions`](https://github.com/kgkazakos/brief-to-questions). The two pair naturally: one turns a brief into the research questions worth asking, the other turns the same brief into the screener that recruits the people who can answer them.

The series is open-source infrastructure for **Computational Product Research** — small, composable tools that ship at an almost-daily cadence. It is distinct from the core CPR research projects (CausalTrack, Synthetic User Council, Co-Reasoning Canvas), which are maintained separately.

## License

MIT © 2026 Kostas Kazakos
