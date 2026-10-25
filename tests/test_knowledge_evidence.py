"""Structural invariants of packaged knowledge that readers rely on (not wording)."""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

LEGEND_PREFIX = "> **Evidence legend"
NEW_TOPICS = ("engine", "api_catalog")
ADOPTED_TAG = re.compile(r"\[ADOPTED(?::\s*([a-z]+))?\]")
VALID_CLASSES = {"observed", "code", "assumed", "claim"}
HEX_LITERAL = re.compile(r"\b0x[0-9a-fA-F]{5,}\b")


def check_topic(text: str, *, new_topic: bool = False) -> list[str]:
    """Return one message per violated invariant; empty when the topic is sound."""
    problems: list[str] = []
    lines = text.splitlines()
    has_legend = any(line.startswith(LEGEND_PREFIX) for line in lines)
    uses_evidence = False
    for number, line in enumerate(lines, 1):
        if line.startswith(LEGEND_PREFIX):
            continue
        for match in ADOPTED_TAG.finditer(line):
            uses_evidence = True
            if match.group(1) not in VALID_CLASSES:
                problems.append(f"line {number}: [ADOPTED] needs an author class from {sorted(VALID_CLASSES)}")
            if "MPF:" not in line:
                problems.append(f"line {number}: [ADOPTED] without an MPF: citation on the same line")
        if "MPF:" in line:
            uses_evidence = True
        if HEX_LITERAL.search(line):
            problems.append(f"line {number}: executable-address-like hex literal")
    if uses_evidence and not has_legend:
        problems.append("topic uses [ADOPTED]/MPF: but has no evidence legend")
    if new_topic:
        summary = next((ln for ln in lines if ln.strip() and not ln.startswith("#")), "")
        if not summary or summary.startswith(">"):
            problems.append("first non-heading line must be a scope summary, not a legend or empty")
    return problems


def _topics() -> dict[str, str]:
    directory = files("tf3companion").joinpath("knowledge")
    return {
        entry.name[:-3]: entry.read_text(encoding="utf-8")
        for entry in directory.iterdir()
        if entry.name.endswith(".md")
    }


def test_new_topics_are_packaged():
    assert set(NEW_TOPICS) <= set(_topics())


@pytest.mark.parametrize("topic", sorted(_topics()))
def test_packaged_topic_keeps_evidence_invariants(topic):
    assert check_topic(_topics()[topic], new_topic=topic in NEW_TOPICS) == []


@pytest.mark.parametrize(
    "sample",
    [
        "# T\n\nsummary\n\n- fact [ADOPTED: observed]\n",
        "# T\n\nsummary\n\n- fact [ADOPTED: guess] (MPF:docs/RESEARCH.md:1)\n",
        "# T\n\nsummary\n\n- fact [ADOPTED] (MPF:docs/RESEARCH.md:1)\n",
        "# T\n\nsummary\n\n- fact at 0x2fc8fe0\n",
        "# T\n\nsummary\n\n- fact [ADOPTED: code] (MPF:docs/RESEARCH.md:1)\n",
    ],
)
def test_checker_rejects_violations(sample):
    assert check_topic(sample), sample


def test_checker_accepts_a_sound_topic():
    sound = (
        "# T\n\nWhat this covers.\n\n"
        f"{LEGEND_PREFIX} (imported research).** text\n\n"
        "- fact [ADOPTED: code] (MPF:docs/RESEARCH.md:1)\n"
    )
    assert check_topic(sound, new_topic=True) == []


def test_checker_rejects_legend_as_summary_of_new_topic():
    assert check_topic(f"# T\n\n{LEGEND_PREFIX} (imported research).** text\n", new_topic=True)
