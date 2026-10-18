"""Towns evidence: compact town projections of every eligible sample plus the endpoint's network facts.

The history is streamed through the reader (one source row parsed at a time, bounded at the endpoint in
SQL); only the endpoint snapshot is hydrated, and it is the one the context already selected. No raw
snapshot is retained: samples are reduced to immutable per-town points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..game_time import calendar_ordinal
from ..snapshot import Snapshot, _list
from .models import EvaluationContext, SampleRef
from .reader import EvidenceReader


@dataclass(frozen=True)
class TownPoint:
    """One town in one sample; unknown measurements are None, never zero."""

    id: int
    name: str
    capacities: tuple[float, ...]
    usage: float | None
    noise: float | None
    pollution: float | None
    development: bool | None
    supply: tuple[tuple[int, float, float], ...]  # (cargo id, supply, limit)


@dataclass(frozen=True)
class TownSample:
    tick: int
    label: str
    ymd: tuple[int, int, int] | None
    towns: tuple[TownPoint, ...]


@dataclass(frozen=True)
class StationFact:
    id: int
    town: int


@dataclass(frozen=True)
class LineFact:
    id: int
    name: str
    stop_groups: tuple[int | None, ...]
    capacity: tuple[tuple[Any, float | None], ...]  # (stored cargo index, vehicle capacity)


@dataclass(frozen=True)
class OutputFact:
    cargo: int
    produced_year: float | None
    shipped_year: float | None


@dataclass(frozen=True)
class TownsEvidence:
    endpoint: SampleRef
    samples: tuple[TownSample, ...]            # every eligible sample at or before the endpoint, oldest first
    eligible: int
    read: int
    passenger_cargo: int
    stations: tuple[StationFact, ...]
    lines: tuple[LineFact, ...]
    positions: tuple[tuple[int, tuple[float, float]], ...]   # stored town positions (empty when none are collected)
    cargo_names: tuple[tuple[int, str], ...]
    outputs: tuple[OutputFact, ...]
    collection_errors: tuple[str, ...] = ()
    hydrated: int = 0                           # full snapshots loaded besides the endpoint


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _point(town: dict[str, Any]) -> TownPoint:
    caps = tuple(c for c in (_num(v) for v in _list(town.get("capacities"))) if c is not None)
    supply = []
    for entry in _list(town.get("cargoSupply")):
        cargo, sup, limit = entry.get("cargo"), _num(entry.get("supply")), _num(entry.get("limit"))
        if isinstance(cargo, int) and sup is not None and limit is not None:
            supply.append((cargo, sup, limit))
    dev = town.get("developmentActive")
    return TownPoint(
        id=town["id"], name=town.get("name") or f"Town #{town.get('id')}", capacities=caps,
        usage=_num(town.get("lineUsage")), noise=_num(town.get("noise")), pollution=_num(town.get("pollution")),
        development=dev if isinstance(dev, bool) else None, supply=tuple(supply),
    )


def _sample(tick: int, meta: Any, towns: Any) -> TownSample:
    date = meta.get("date") if isinstance(meta, dict) and isinstance(meta.get("date"), dict) else None
    ymd = (date["year"], date["month"], date["day"]) if calendar_ordinal(date) is not None else None
    label = f"{ymd[0]:04d}-{ymd[1]:02d}-{ymd[2]:02d}" if ymd else f"t={tick}"
    points: dict[int, TownPoint] = {}
    for town in _list(towns):
        points[town["id"]] = _point(town)  # a repeated id keeps its last entry, as before
    return TownSample(tick, label, ymd, tuple(points.values()))


def _passenger_cargo_id(snap: Snapshot) -> int:
    for entry in _list(snap.raw.get("cargos")):
        if "passenger" in str(entry.get("res") or "").casefold() and isinstance(entry.get("id"), int):
            return entry["id"]
    return 0


def _position(town: dict[str, Any]) -> tuple[float, float] | None:
    position = town.get("position")
    if isinstance(position, dict):
        position = _list(position)
    if isinstance(position, list) and len(position) >= 2 and all(_num(v) is not None for v in position[:2]):
        return float(position[0]), float(position[1])
    return None


def load(reader: EvidenceReader, context: EvaluationContext) -> TownsEvidence:
    endpoint = context.snapshot
    eligible = reader.count_samples()
    samples: list[TownSample] = []
    for tick, _label, projected in reader.projection(("meta", "towns")):
        samples.append(_sample(tick, projected.get("meta"), projected.get("towns")))
    read = len(samples)
    if not samples:
        samples.append(_sample(endpoint.game_time, endpoint.raw.get("meta"), endpoint.raw.get("towns")))
    stations = tuple(StationFact(s["id"], s["town"]) for s in endpoint.stations if isinstance(s.get("town"), int))
    lines = tuple(
        LineFact(
            id=line["id"], name=line.get("name") or f"Line #{line['id']}",
            stop_groups=tuple(stop.get("stationGroup") for stop in _list(line.get("stops"))),
            capacity=tuple((c.get("cargo"), _num(c.get("capacity"))) for c in _list(line.get("capacity"))),
        )
        for line in endpoint.lines
    )
    positions = tuple((t["id"], pos) for t in endpoint.towns if (pos := _position(t)) is not None)
    outputs = tuple(
        OutputFact(out["cargo"], _num(out.get("producedYear")), _num(out.get("shippedYear")))
        for ind in endpoint.industries for out in _list(ind.get("outputs")) if isinstance(out.get("cargo"), int)
    )
    return TownsEvidence(
        endpoint=reader.ref(endpoint), samples=tuple(samples), eligible=eligible, read=read,
        passenger_cargo=_passenger_cargo_id(endpoint), stations=stations, lines=lines, positions=positions,
        cargo_names=tuple(sorted(endpoint.cargo_names.items())), outputs=outputs,
        collection_errors=tuple(str(e) for e in endpoint.errors), hydrated=reader.hydrated,
    )
