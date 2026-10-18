"""Behavior regression tests for agent experience prompts, resources and instructions."""
from __future__ import annotations

import json
import os
import sys

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from tf3companion.agent_experience import (
    annual_review,
    cargo_opportunities,
    decision_review,
    fleet_renewal,
    line_triage,
)

ANALYSIS_PROMPTS = {"monthly-review", "annual-review", "line-triage", "fleet-renewal", "cargo-opportunities", "decision-review",
                    "apply-methodology"}


def test_decision_review_validates_status_choices():
    with pytest.raises(ValueError, match="Invalid decision status"):
        decision_review("invalid_status")  # type: ignore[arg-type]


def test_annual_review_rejects_negative_or_zero_years():
    with pytest.raises(ValueError, match="Invalid game year"):
        annual_review(-1)
    with pytest.raises(ValueError, match="Invalid game year"):
        annual_review(0)


@pytest.mark.parametrize("invalid_ref", ["", "   ", "\n", "line\x00one"])
def test_prompts_reject_blank_or_control_references(invalid_ref: str):
    with pytest.raises(ValueError, match="Invalid line reference"):
        line_triage(invalid_ref)
    with pytest.raises(ValueError, match="Invalid line reference"):
        fleet_renewal(invalid_ref)
    with pytest.raises(ValueError, match="Invalid cargo reference"):
        cargo_opportunities(invalid_ref)


def test_onboarding_over_stdio_without_game_or_storage(tmp_path):
    """A first-time player's client gets setup guidance; nothing pretends analysis data exists or creates storage."""
    data = tmp_path / "data"
    (tmp_path / "home").mkdir()
    env = {**os.environ, "HOME": str(tmp_path / "home"), "USERPROFILE": str(tmp_path / "home"),
           "TF3C_USERDATA_DIR": str(tmp_path / "missing-game"), "TF3C_DATA_DIR": str(data)}
    params = StdioServerParameters(command=sys.executable, args=["-c", "from tf3companion.cli import main; main(['mcp'])"],
                                   env=env, cwd=str(tmp_path))

    async def session_run():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            prompts = {p.name for p in (await session.list_prompts()).prompts}
            prompt = await session.get_prompt("setup-check")
            guide = (await session.read_resource("tf3c://setup")).contents[0]
            doctor = await session.call_tool("doctor", {})
            return prompts, prompt, guide, doctor

    prompts, prompt, guide, doctor = anyio.run(session_run)

    assert prompts == ANALYSIS_PROMPTS | {"setup-check"}
    assert prompt.messages and prompt.messages[0].content.text.strip()
    assert guide.mime_type == "text/markdown" and guide.text.strip()
    report = doctor.structured_content or json.loads(doctor.content[0].text)
    report = report.get("result", report)
    assert report["ok"] is False
    assert any(c["name"] == "userdata" and c["status"] == "error" for c in report["checks"])
    assert not data.exists()

