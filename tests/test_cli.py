"""Tests for the CLI."""

import json

from click.testing import CliRunner

from screener_generator.cli import cli

BRIEF = (
    "Smart Reply for support agents.\n"
    "Target audience: customer support agents who handle tickets daily.\n"
    "Segments: new vs experienced.\n"
    "We want to recruit n=12 for remote interviews.\n"
)


def test_generate_json_output():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("brief.md", "w") as fh:
            fh.write(BRIEF)
        result = runner.invoke(cli, ["generate", "brief.md", "--no-llm", "--json-output"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["counts"]["questions"] >= 6
        assert "questions" in data


def test_generate_rich_output_runs():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("brief.md", "w") as fh:
            fh.write(BRIEF)
        result = runner.invoke(cli, ["generate", "brief.md", "--no-llm"])
        assert result.exit_code == 0, result.output
        assert "Recruitment screener" in result.output


def test_generate_markdown_output():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("brief.md", "w") as fh:
            fh.write(BRIEF)
        result = runner.invoke(cli, ["generate", "brief.md", "--no-llm", "--markdown"])
        assert result.exit_code == 0, result.output
        assert result.output.startswith("# Recruitment screener")


def test_generate_from_stdin():
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-", "--no-llm", "--json-output"], input=BRIEF)
    assert result.exit_code == 0, result.output
    json.loads(result.output)


def test_empty_brief_errors():
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "-", "--no-llm"], input="   ")
    assert result.exit_code != 0


def test_batch_over_directory():
    runner = CliRunner()
    with runner.isolated_filesystem():
        import os

        os.makedirs("briefs")
        for i in range(2):
            with open(f"briefs/b{i}.md", "w") as fh:
                fh.write(BRIEF)
        result = runner.invoke(cli, ["batch", "briefs", "--no-llm"])
        assert result.exit_code == 0, result.output
        arr = json.loads(result.output)
        assert len(arr) == 2
        assert arr[0]["file"].endswith(".md")


def test_backends_command_lists_three():
    runner = CliRunner()
    result = runner.invoke(cli, ["backends"])
    assert result.exit_code == 0
    for name in ("anthropic", "gemini", "openai"):
        assert name in result.output
