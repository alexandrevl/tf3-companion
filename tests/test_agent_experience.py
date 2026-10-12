"""Behavior regression tests for agent experience prompts, resources and instructions."""
from __future__ import annotations

import pytest

from tf3companion.agent_experience import (
    annual_review,
    cargo_opportunities,
    decision_review,
    fleet_renewal,
    line_triage,
)


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


