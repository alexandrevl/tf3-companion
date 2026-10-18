"""Endpoint-bounded evidence for the vehicle-ROI view.

Reproduces the report's evidence selection through the operation reader: the compact sample index
(one meta projection per stored sample, never a full snapshot), at most `TREND_COLUMNS` historical
trend samples chosen by the month/quarter/year rule, the newest `LOAD_HISTORY` snapshots for sampled
line load, the endpoint, and one endpoint-bounded catalog. Every full hydration goes through the
reader, which refuses ticks after the endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..game_time import GameCalendarClock
from ..snapshot import Snapshot
from .models import EvaluationContext, SampleRef
from .reader import EvidenceReader

TREND_COLUMNS = 8
LOAD_HISTORY = 24


@dataclass(frozen=True)
class TrendSnapshot:
    snapshot: Snapshot
    clock: GameCalendarClock


@dataclass(frozen=True)
class VehicleRoiEvidence:
    endpoint: Snapshot
    clock: GameCalendarClock
    catalog: Snapshot | None
    eligible: int                      # stored samples at or before the endpoint
    read: int                          # compact index rows streamed
    first_sample: SampleRef
    last_sample: SampleRef
    trend: tuple[TrendSnapshot, ...]   # chosen historical samples, oldest first
    load_snapshots: tuple[Snapshot, ...]  # newest LOAD_HISTORY snapshots at/before the endpoint, oldest first
    hydrated: int                      # full snapshots loaded besides the endpoint


def _date_of(meta: dict[str, Any]) -> tuple[int, int, int]:
    d = meta.get("date") or {}
    return (d.get("year", meta.get("year") or 0), d.get("month", 0), d.get("day", 0))


def select_trend_ticks(entries: list[tuple[int, tuple[int, int, int]]]) -> list[int]:
    """Last sample per month; coarsened to quarters then years while more than TREND_COLUMNS remain."""
    def pick(bucket) -> list[int]:
        last: dict[Any, int] = {}
        for tick, date in entries:
            last[bucket(date)] = tick
        return sorted(last.values())

    chosen: list[int] = []
    for bucket in (lambda d: d[:2], lambda d: (d[0], (d[1] - 1) // 3), lambda d: d[0]):
        chosen = pick(bucket)
        if len(chosen) <= TREND_COLUMNS:
            return chosen
    return chosen[-TREND_COLUMNS:]


def load(reader: EvidenceReader, context: EvaluationContext) -> VehicleRoiEvidence:
    endpoint = context.snapshot
    entries: list[tuple[int, tuple[int, int, int]]] = []
    labels: dict[int, str] = {}
    for tick, label, payload in reader.projection(("meta",)):
        entries.append((tick, _date_of(payload.get("meta") or {})))
        labels[tick] = label
    loads = tuple(reader.recent(LOAD_HISTORY)) or (endpoint,)
    trend = []
    for tick in select_trend_ticks(entries):
        snap = reader.hydrate(tick)
        if snap is not None:
            trend.append(TrendSnapshot(snap, reader.clock_at(snap)))
    catalog = reader.catalog()
    first = SampleRef(entries[0][0], labels[entries[0][0]]) if entries else reader.ref(endpoint)
    last = SampleRef(entries[-1][0], labels[entries[-1][0]]) if entries else reader.ref(endpoint)
    return VehicleRoiEvidence(endpoint, context.clock, catalog, reader.count_samples(), len(entries), first, last,
                              tuple(trend), loads, reader.hydrated)
