"""Evidence for the lines-history view: compact per-line series plus at most 12 sampled full snapshots.

Per-line series and the sample index are streamed from endpoint-bounded SQL projections, keeping one
retained tick (the newest) per distinct date label. Instantaneous occupancy hydrates at most
`OCCUPANCY_SAMPLES` of those ticks (the selected endpoint is already in memory); no other snapshot is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby

from .. import analysis
from .lines_history import OCCUPANCY_SAMPLES, LinePoint, spread
from .models import EvaluationContext, SampleRef
from .reader import EvidenceReader


@dataclass(frozen=True)
class LineSeries:
    line_id: int
    name: str | None  # newest non-empty stored name
    points: tuple[LinePoint, ...]  # one point per retained sample date, oldest first


@dataclass(frozen=True)
class CurrentLine:
    """What the endpoint snapshot says about one line."""

    id: int
    has_vehicles: bool
    carrier: str | None
    issues: tuple[str, ...]
    oldest_purchase: int | None  # oldest purchase tick among the line's currently assigned vehicles


@dataclass(frozen=True)
class OccupancySample:
    tick: int
    date: str
    loads: tuple[tuple[int, float], ...]  # (line id, instantaneous used/capacity ratio) where defined


@dataclass(frozen=True)
class LinesHistoryEvidence:
    endpoint: SampleRef
    samples: tuple[SampleRef, ...]
    series: tuple[LineSeries, ...]
    current: tuple[CurrentLine, ...]
    occupancy: tuple[OccupancySample, ...]
    eligible: int
    read: int
    hydrated: int


def load(reader: EvidenceReader, context: EvaluationContext) -> LinesHistoryEvidence:
    endpoint = context.snapshot
    newest: dict[str, int] = {}
    read = 0
    for tick, date, _meta in reader.sample_index():
        read += 1
        newest[date] = max(newest.get(date, -1), tick)
    kept = {tick: date for date, tick in newest.items()}
    samples = tuple(SampleRef(tick, kept[tick]) for tick in sorted(kept))

    series: list[LineSeries] = []
    for line_id, rows in groupby(reader.line_points(), key=lambda row: row["line_id"]):
        points = []
        name = None
        for row in rows:
            read += 1
            if row["game_time"] not in kept:
                continue
            points.append(
                LinePoint(
                    row["game_time"],
                    kept[row["game_time"]],
                    row["profit_year"],
                    row["transported_year"],
                    row["rate"],
                    row["vehicles"],
                )
            )
            if row["name"]:
                name = row["name"]
        if points:
            series.append(LineSeries(line_id, name, tuple(points)))

    current = []
    for raw in endpoint.lines:
        bought = [v["purchaseTime"] for v in endpoint.line_vehicles(raw) if v.get("purchaseTime") is not None]
        current.append(
            CurrentLine(
                raw["id"],
                bool(raw.get("vehicles")),
                analysis.line_carrier(endpoint, raw),
                tuple(sorted({str(i.get("type")) for i in raw.get("issues") or [] if i.get("type")})),
                min(bought) if bought else None,
            )
        )

    occupancy = []
    for tick in spread([s.tick for s in samples], OCCUPANCY_SAMPLES):
        snap = reader.hydrate(tick)
        if snap is None:
            continue
        occupancy.append(
            OccupancySample(
                snap.game_time,
                snap.date_label,
                tuple((raw["id"], load) for raw in snap.lines if (load := analysis.line_load(raw)) is not None),
            )
        )

    return LinesHistoryEvidence(
        endpoint=reader.ref(endpoint),
        samples=samples,
        series=tuple(series),
        current=tuple(current),
        occupancy=tuple(occupancy),
        eligible=reader.count_samples(),
        read=read,
        hydrated=reader.hydrated,
    )
