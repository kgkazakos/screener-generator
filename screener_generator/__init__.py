"""screener-generator · CPR Orbital #34 (Season 6, Pre-study & impact)

Turn a research brief into a fieldwork-ready recruitment screener:
qualifying questions, quota logic, and disqualification criteria.

The rule-based core runs fully offline with zero API calls. LLM enrichment
(Claude Opus, Gemini 4 Argon, GPT-5.5) is on by default and rewrites
questions to be brief-specific, but degrades gracefully to the deterministic
core whenever a key or backend is unavailable.

Part of the CPR Orbital series — github.com/kgkazakos
"""

__version__ = "0.1.0"
