"""Evidence of the history view: compact per-sample records of every stored sample up to the endpoint.

Only SQL-compacted projections are streamed (never whole raw snapshots); the selected endpoint is the
one full snapshot already hydrated in the context. Entity membership (lines, vehicles) is kept per
sample because consecutive-sample turnover and purchase cohorts need it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..game_time import calendar_ordinal
from .models import EvaluationContext, SampleRef
from .reader import EvidenceReader

TICK_LIMIT = 2**63 - 1


@dataclass(frozen=True)
class HistorySample:
    """One stored sample reduced to the facts the history analysis consumes."""

    tick: int
    year_duration: int
    ymd: tuple[int, int, int] | None
    ordinal: int | None
    label: str
    reason: str | None
    balance: int | None
    loan: int | None
    earnings: int | None
    score: int | None
    track: int | None
    passengers: int | None
    cargo: int | None
    lines: tuple[tuple[int, str], ...]  # (id, name)
    vehicles: tuple[tuple[int, str, str, int | None, int | None], ...]  # (id, name, carrier, value, purchase tick)
    stations: int
    rolling_profit: int | None
    lines_losing: int
    lines_with_profit: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class EndpointFacts:
    """Raw company facts of the selected endpoint, kept even when the timeline cannot be used."""

    label: str
    balance: Any
    loan: Any
    company_name: str | None


@dataclass(frozen=True)
class HistoryEvidence:
    samples: tuple[HistorySample, ...]
    endpoint: SampleRef
    endpoint_facts: EndpointFacts
    eligible: int
    later_samples: int
    hydrated: int
    hydration_limit: int


def _sample(row: dict[str, Any]) -> HistorySample:
    date = row["date"] or None
    ordinal = calendar_ordinal(date)
    ymd = (date["year"], date["month"], date["day"]) if ordinal is not None else None
    lines = tuple((line["id"], line["name"] or f"Line #{line['id']}") for line in row["lines"] or ())
    vehicles = tuple(
        (v["id"], v["name"] or f"Vehicle #{v['id']}", v["carrier"] or "UNKNOWN", v["value"], v["purchase"])
        for v in row["vehicles"] or ()
    )
    profits = [line["profit"] for line in row["lines"] or () if line["profit"] is not None]
    errors = row["errors"]
    return HistorySample(
        tick=row["game_time"],
        year_duration=row["year_duration"] or 0,
        ymd=ymd,
        ordinal=ordinal,
        label=row["date_label"],
        reason=row["reason"],
        balance=row["balance"],
        loan=row["loan"],
        earnings=row["earnings"],
        score=row["score"],
        track=row["track"],
        passengers=row["passengers"],
        cargo=row["cargo"],
        lines=lines,
        vehicles=vehicles,
        stations=row["stations"],
        rolling_profit=sum(profits) if profits else None,
        lines_losing=sum(1 for p in profits if p < 0),
        lines_with_profit=len(profits),
        errors=tuple(errors.values() if isinstance(errors, dict) else errors or ()),
    )


def load(reader: EvidenceReader, context: EvaluationContext) -> HistoryEvidence:
    snapshot = context.snapshot
    samples = tuple(_sample(row) for row in reader.store.iter_history_points(reader.endpoint))
    eligible = reader.count_samples()
    later = reader.store.count_samples(TICK_LIMIT) - eligible
    company = snapshot.company
    facts = EndpointFacts(snapshot.date_label, company.get("balance"), company.get("loan"), company.get("name"))
    return HistoryEvidence(samples, reader.ref(snapshot), facts, eligible, later, reader.hydrated, 1)
