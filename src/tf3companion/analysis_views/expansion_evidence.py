"""Evidence for the expansion view: a bounded sample of full snapshots plus one catalog, all at or before the endpoint.

The report's current selection is preserved: the latest sample per game month for the newest 12 months
and per quarter for older history (at most 12 + 8 representatives) plus the endpoint. Only the compact
date/tick index is streamed; at most 21 full samples and one catalog are ever hydrated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..snapshot import Snapshot
from .models import EvaluationContext
from .reader import EvidenceReader

MAX_MONTHLY_SAMPLES, MAX_QUARTERLY_SAMPLES = 12, 8
HYDRATION_LIMIT = MAX_MONTHLY_SAMPLES + MAX_QUARTERLY_SAMPLES + 1  # representatives + a distinct catalog sample

_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


@dataclass(frozen=True)
class ExpansionEvidence:
    endpoint: Snapshot
    samples: tuple[Snapshot, ...]  # oldest first, always ending with the endpoint
    catalog: Snapshot | None  # newest catalog snapshot at or before the endpoint
    eligible: int  # stored samples at or before the endpoint
    read: int  # compact index rows streamed
    hydrated: int  # full snapshots loaded besides the endpoint
    missing_ticks: tuple[int, ...] = ()  # selected ticks that could not be hydrated


def select_ticks(index: list[tuple[int, str]], endpoint: int) -> list[int]:
    """Latest tick per game month for the newest 12 months, then per quarter for older history, plus the endpoint."""
    keyed: list[tuple[int, int]] = []
    for tick, label in index:
        match = _DATE.match(str(label or ""))
        if match:
            keyed.append((int(match[1]) * 12 + int(match[2]) - 1, tick))
    if not keyed:
        return [endpoint]
    newest = max(month for month, _ in keyed)
    monthly: dict[int, int] = {}
    quarterly: dict[int, int] = {}
    for month, tick in sorted(keyed, key=lambda x: x[1]):
        if newest - month < 12:
            monthly[month] = tick
        else:
            quarterly[month // 3] = tick
    ticks = [t for _, t in sorted(monthly.items())][-MAX_MONTHLY_SAMPLES:]
    ticks = [t for _, t in sorted(quarterly.items())][-MAX_QUARTERLY_SAMPLES:] + ticks
    return sorted(set(ticks) | {endpoint})


def load(reader: EvidenceReader, context: EvaluationContext) -> ExpansionEvidence:
    index = [(tick, label) for tick, label, _ in reader.sample_index()]
    samples: list[Snapshot] = []
    missing: list[int] = []
    for tick in select_ticks(index, reader.endpoint):
        snap = reader.hydrate(tick)
        if snap is None:
            missing.append(tick)
        else:
            samples.append(snap)
    catalog = reader.catalog()
    return ExpansionEvidence(
        context.snapshot, tuple(samples), catalog, len(index), len(index), reader.hydrated, tuple(missing)
    )
