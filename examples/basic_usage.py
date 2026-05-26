"""Basic usage of screener-generator.

Run:  python examples/basic_usage.py
"""

from screener_generator.pipeline import build_screener, to_markdown

BRIEF = """Smart Reply for Team Inbox

We are building an AI-assisted reply feature for customer support agents.
Target audience: customer support agents who handle tickets daily.
Must have: use a shared team inbox; handle at least 20 tickets per week.
Segments: new agents vs experienced agents.
We want to recruit n=12 for remote, moderated interviews.
"""

# use_llm=False keeps this example fully offline and reproducible.
screener = build_screener(BRIEF, use_llm=False)

print(f"Generated {len(screener.questions)} questions, "
      f"{screener.terminate_count} with terminate logic, "
      f"est. incidence ~{screener.incidence_estimate:.0%}\n")

print(to_markdown(screener))
