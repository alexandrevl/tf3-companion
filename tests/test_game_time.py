"""Calendar arithmetic and conservative evidence bounds, independent of nominal duration."""

from datetime import date

import pytest

from tf3companion.game_time import GameCalendarClock, calendar_ordinal


def clock(samples, **context):
    return GameCalendarClock.from_samples(samples, context=context)


def test_fourfold_mismatch_and_local_rates():
    c = clock(
        [(0, "1980-01-01"), (28000, "1980-01-29"), (42000, "1980-02-12"), (70000, "1980-02-26")], selectedTick=70000
    )
    result = c.elapsed_between_ticks(14000, 28000)
    assert result.value == pytest.approx(14 / 365.25)
    assert result.method == "calendar-interpolation"
    local = c.calendar_at_tick(56000)
    assert local.ordinal == date(1980, 2, 19).toordinal()
    assert [a["gameTime"] for a in local.anchors] == [42000, 70000]
    assert any("vary" in w for w in c.time_basis["warnings"])


def test_gregorian_crossing_leap_and_zero():
    c = clock([])
    assert c.elapsed_between_dates("1979-12-31", "1980-01-01").value == 1 / 365.25
    assert c.elapsed_between_dates("1980-02-28", "1980-03-01").value == 2 / 365.25
    assert c.elapsed_between_dates("1980-01-01", "1980-01-01").value == 0
    assert c.elapsed_between_dates("1980-02-30", "1980-03-01").reason == "invalid-calendar-date"
    assert calendar_ordinal({"year": 1980, "month": 2, "day": 30}) is None


def test_unknown_never_nominal_or_clamped():
    c = clock([(100, "1980-01-01"), (200, "1980-01-01")], selectedTick=200)
    assert c.elapsed_between_ticks(100, 200).value == 0
    assert c.elapsed_between_ticks(150, 200).reason == "insufficient-calendar-span"
    assert c.elapsed_between_ticks(0, 200).reason == "outside-observed-calendar"
    assert c.elapsed_between_ticks(201, 200).reason == "future-timestamp"
    assert clock([(100, None)]).elapsed_between_ticks(100, 100).value is None
    assert clock([(100, "1980-02-30")]).calendar_at_tick(100).reason == "invalid-calendar-date"


def test_scope_reversal_conflicting_ticks_and_future_exclusion():
    for samples in ([(0, "1980-01-10"), (100, "1980-01-01")], [(0, "1980-01-01"), (0, "1980-02-01")]):
        assert clock(samples).elapsed_between_ticks(0, 100).reason == "ambiguous-timeline"
    c = clock([(0, "1980-01-01"), (100, "1980-01-10"), (200, "1980-02-01")], selectedTick=100)
    assert [t for t, _ in c.anchors] == [0, 100]
    assert c.time_basis["version"] == "game-calendar-v1"
    assert c.time_basis["isolation"] == "legacy-unverified"
    assert (
        c.time_basis["anchorHash"]
        == clock([(0, "1980-01-01"), (100, "1980-01-10")], selectedTick=100).time_basis["anchorHash"]
    )


def test_exact_zero_requires_calendar_evidence():
    assert clock([(10, "1980-01-01")], selectedTick=10).elapsed_between_ticks(10, 10).value == 0
    assert clock([(10, None)], selectedTick=10).elapsed_between_ticks(10, 10).value is None


def test_reusable_numeric_fixture():
    import json
    from pathlib import Path

    fixture = json.loads((Path(__file__).parent / "fixtures" / "game-calendar-v1.json").read_text())
    c = clock(fixture["samples"], selectedTick=fixture["evaluationTick"])
    measured = c.elapsed_between_ticks(fixture["purchaseTick"], fixture["evaluationTick"])
    assert measured.value == fixture["expectedElapsedDays"] / fixture["daysPerYear"]
    assert measured.method == fixture["expectedMethod"]
    assert (
        c.elapsed_between_ticks(fixture["unsupportedPurchaseTick"], fixture["evaluationTick"]).reason
        == fixture["unsupportedReason"]
    )
