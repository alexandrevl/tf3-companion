"""Evidence of the industries view: compact projections of every eligible sample plus the endpoint.

Every stored sample at or before the endpoint is streamed once as a compact projection (meta,
industries, stocks, problems, errors); no whole raw snapshot is hydrated for history. The selected
endpoint is the only full snapshot (its lines, stations and cargo names feed the station-link screen).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..snapshot import Snapshot
from .models import EvaluationContext
from .reader import EvidenceReader

PROJECTION_KEYS = ("meta", "industries", "stocks", "problems", "errors")


@dataclass(frozen=True)
class SampleRows:
    """The compact rows of one stored sample, still in their stored (untrusted) shape."""

    tick: int
    label: str
    date: Any
    industries: Any
    stocks: Any
    problems: Any
    errors: Any


@dataclass(frozen=True)
class IndustriesEvidence:
    endpoint: Snapshot  # the selected endpoint, fully hydrated
    samples: tuple[SampleRows, ...]  # every eligible sample, oldest first, ending at the endpoint
    eligible: int  # stored samples at or before the endpoint
    hydrated: int  # full snapshots loaded besides the endpoint


def _rows(tick: int, label: str, parts: dict[str, Any]) -> SampleRows:
    meta = parts.get("meta")
    return SampleRows(
        tick,
        label,
        meta.get("date") if isinstance(meta, dict) else None,
        parts.get("industries"),
        parts.get("stocks"),
        parts.get("problems"),
        parts.get("errors"),
    )


def load(reader: EvidenceReader, context: EvaluationContext) -> IndustriesEvidence:
    samples = [_rows(tick, label, parts) for tick, label, parts in reader.projection(PROJECTION_KEYS)]
    endpoint = context.snapshot
    if not samples or samples[-1].tick != endpoint.game_time:
        raw = endpoint.raw
        samples.append(_rows(endpoint.game_time, endpoint.date_label, {k: raw.get(k) for k in PROJECTION_KEYS}))
    return IndustriesEvidence(endpoint, tuple(samples), reader.count_samples(), reader.hydrated)
