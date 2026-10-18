"""Field registry: every fact a methodology may read, with its type, source and caveat.

The registry is built from the existing row builders in `analysis` plus a few derived
fields. A methodology can only read facts that exist here; a field it names that is not
in this registry makes the rule *unsupported*, and a registered field whose snapshot data
is absent makes the rule *skipped*. Values are `None` when unknown (never coerced to 0).
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Callable

from .. import analysis
from ..snapshot import Snapshot
from .model import ENTITIES, UNCLASSIFIED
from .safe_regex import bounded_search

NUMBER, STRING, BOOL, LIST_NUMBER, LIST_STRING = "number", "string", "bool", "list[number]", "list[string]"
TYPES = (NUMBER, STRING, BOOL, LIST_NUMBER, LIST_STRING)

POSITIONS = "stations[].position"
CARGO_OFFSET = 1  # lines[].capacity[].cargo is the cargo id plus one.
PASSENGER_CARGO_ID = 0

Getter = Callable[["Record"], Any]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    entity: str
    type: str
    sources: tuple[str, ...]
    caveat: str
    description: str
    getter: Getter = field(repr=False, compare=False)
    derived: bool = False
    # Snapshot paths the collector must emit for the field to ever have a value; flagged
    # when this release's collector does not produce them yet.
    requires: tuple[str, ...] = ()
    collected: bool = True
    label_kind: str | None = None  # "town" | "station": how group keys become names


_REGISTRY: dict[str, FieldSpec] = {}
_INHERITING = ("vehicle", "stop")  # entities that expose `<entity>.line.<line field>`


def _register(name: str, type_: str, sources: tuple[str, ...], description: str, getter: Getter, *,
              caveat: str = "", derived: bool = False, requires: tuple[str, ...] = (),
              collected: bool = True, label_kind: str | None = None) -> None:
    entity = name.split(".", 1)[0]
    assert entity in ENTITIES and type_ in TYPES and sources and description, name
    _REGISTRY[name] = FieldSpec(name, entity, type_, sources, caveat, description, getter, derived,
                                requires, collected, label_kind)


# ---------------------------------------------------------------------------
# Facts and records

class Facts:
    """Per-snapshot lookups shared by every record, built once."""

    def __init__(self, snap: Snapshot, name_patterns: tuple[tuple[str, str], ...] = ()) -> None:
        self.snap = snap
        self.name_patterns = name_patterns
        self._line_rows: dict[int, dict[str, Any]] = {}
        self._captures: dict[int, dict[str, str]] = {}
        self.line_roles: dict[Any, str] = {}

    @cached_property
    def stations(self) -> dict[Any, dict[str, Any]]:
        return {s.get("id"): s for s in self.snap.stations}

    @cached_property
    def town_names(self) -> dict[Any, str]:
        names = {t["id"]: t.get("name") for t in self.snap.towns if t.get("name")}
        for station in self.snap.stations:
            key = _town_key(station)
            if key is not None and station.get("townName"):
                names.setdefault(key, station["townName"])
        return names

    def label(self, kind: str | None, key: Any) -> str:
        if kind == "town":
            return str(self.town_names.get(key, key))
        if kind == "station":
            station = self.stations.get(key) or {}
            return str(station.get("name") or key)
        return str(key)

    def line_row(self, line: dict[str, Any]) -> dict[str, Any]:
        row = self._line_rows.get(line["id"])
        if row is None:
            row = self._line_rows[line["id"]] = analysis.line_row(self.snap, line)
        return row

    def captures(self, line: dict[str, Any]) -> dict[str, str] | None:
        """Captures of the first name pattern that matches; None when no pattern matches."""
        cached = self._captures.get(line["id"])
        if cached is not None:
            return cached or None
        name = line.get("name") or ""
        found: dict[str, str] = {}
        for _pattern_id, pattern in self.name_patterns:
            match = bounded_search(pattern, name)
            if match:
                found = {k: v for k, v in match.groupdict().items() if v is not None}
                break
        self._captures[line["id"]] = found
        return found or None

    @cached_property
    def positions(self) -> dict[Any, tuple[float, float]]:
        out = {}
        for station in self.snap.stations:
            pos = station.get("position")
            if isinstance(pos, (list, tuple)) and len(pos) >= 2 and all(_is_number(v) for v in pos[:2]):
                out[station.get("id")] = (float(pos[0]), float(pos[1]))
        return out

    def stop_station(self, stop: Any) -> dict[str, Any] | None:
        if not isinstance(stop, dict):
            return None
        return self.stations.get(stop.get("stationGroup"))

    @cached_property
    def town_centres(self) -> dict[Any, tuple[float, float]]:
        points: dict[Any, list[tuple[float, float]]] = {}
        for station in self.snap.stations:
            key, pos = _town_key(station), self.positions.get(station.get("id"))
            if key is not None and pos is not None:
                points.setdefault(key, []).append(pos)
        return {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in points.items()}

    def records(self, entity: str) -> list["Record"]:
        snap = self.snap
        if entity == "line":
            return [Record(entity, line, self) for line in snap.lines]
        if entity == "vehicle":
            return [Record(entity, v, self, line=snap.lines_by_id.get(v.get("line"))) for v in snap.vehicles]
        if entity == "stop":
            return [Record(entity, stop if isinstance(stop, dict) else {}, self, line=line)
                    for line in snap.lines for stop in line.get("stops") or []]
        if entity == "industry":
            return [Record(entity, i, self) for i in snap.industries]
        if entity == "stock":
            return [Record(entity, s, self) for s in snap.stocks]
        if entity == "town":
            return [Record(entity, t, self) for t in snap.towns]
        raise KeyError(entity)


class Record:
    """One entity instance; `get` resolves registry fields lazily and caches them."""

    __slots__ = ("entity", "raw", "facts", "line", "role", "_cache")

    def __init__(self, entity: str, raw: dict[str, Any], facts: Facts, line: dict[str, Any] | None = None) -> None:
        self.entity = entity
        self.raw = raw
        self.facts = facts
        self.line = line
        self.role: str | None = None
        self._cache: dict[str, Any] = {}

    @property
    def line_record(self) -> "Record | None":
        if self.entity == "line":
            return self
        if self.line is None:
            return None
        cached = self._cache.get("@line")
        if cached is None:
            cached = self._cache["@line"] = Record("line", self.line, self.facts)
        return cached

    def get(self, name: str) -> Any:
        if name in self._cache:
            return self._cache[name]
        spec = lookup(name)
        value = None if spec is None else spec.getter(self)
        self._cache[name] = value
        return value

    @property
    def ident(self) -> dict[str, Any]:
        raw = self.raw
        if self.entity == "stock":
            return {"type": "stock", "id": raw.get("owner"), "name": raw.get("ownerName")}
        if self.entity == "stop":
            station = self.facts.stop_station(raw) or {}
            return {"type": "stop", "id": raw.get("stationGroup"), "name": station.get("name") or raw.get("name")}
        return {"type": self.entity, "id": raw.get("id"), "name": raw.get("name")}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _town_key(station: dict[str, Any] | None) -> Any:
    if not station:
        return None
    key = station.get("town")
    return key if key is not None else station.get("townName")


# ---------------------------------------------------------------------------
# Derived value helpers

def _positive_capacity(line: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in line.get("capacity") or [] if isinstance(c, dict) and (c.get("capacity") or 0) > 0
            and isinstance(c.get("cargo"), int)]


def _cargo_ids(line: dict[str, Any]) -> list[int]:
    return list(dict.fromkeys(c["cargo"] - CARGO_OFFSET for c in _positive_capacity(line)))


def _cargo_name(snap: Snapshot, cargo_id: int) -> str:
    if cargo_id == PASSENGER_CARGO_ID and cargo_id not in snap.cargo_names:
        return "Passengers"
    return snap.cargo(cargo_id) or str(cargo_id)


def _cargo_key(snap: Snapshot, cargo_id: int) -> str | None:
    if cargo_id == PASSENGER_CARGO_ID and cargo_id not in snap.cargo_names:
        return "passengers"
    for cargo in snap.raw.get("cargos") or []:
        if isinstance(cargo, dict) and cargo.get("id") == cargo_id and cargo.get("res"):
            parts = [p for p in str(cargo["res"]).replace("::", "").split("/") if p]
            if len(parts) >= 2 and parts[0] == "cargos":
                return parts[1]
            return parts[-1].rsplit(".", 1)[0] if parts else None
    return None


def model_family(res: Any) -> str | None:
    """Segment after `vehicle` in a model resource path (`::/vehicle/<family>/...`)."""
    if not isinstance(res, str):
        return None
    parts = [p for p in res.replace("::", "").split("/") if p]
    if "vehicle" in parts:
        index = parts.index("vehicle")
        if index + 1 < len(parts) - 1:
            return parts[index + 1]
    return None


def _stop_town_keys(rec: Record) -> list[Any]:
    line = rec.line_record.raw
    keys = []
    for stop in line.get("stops") or []:
        key = _town_key(rec.facts.stop_station(stop))
        if key is not None:
            keys.append(key)
    return keys


def _route_legs_km(rec: Record) -> list[float] | None:
    stops = rec.raw.get("stops") or []
    points = []
    for stop in stops:
        station = rec.facts.stop_station(stop)
        point = rec.facts.positions.get(station.get("id")) if station else None
        if point is None:
            return None
        points.append(point)
    if len(points) < 2:
        return None
    return [math.hypot(a[0] - b[0], a[1] - b[1]) / 1000 for a, b in zip(points, points[1:])]


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    return num / den


def _present(value: Any) -> Any:
    return value if value not in ([], {}, "") else None


# ---------------------------------------------------------------------------
# line

def _line_unrounded_load(rec: Record) -> float | None:
    return analysis.line_load(rec.raw)


_register("line.id", NUMBER, ("lines[].id",), "Entity id of the line.", lambda r: r.raw.get("id"))
_register("line.name", STRING, ("lines[].name",), "Line name as typed in the game.", lambda r: _present(r.raw.get("name")))
_register("line.carrier", STRING, ("vehicles[].carrier",),
          "Transport mode of the line: ROAD, RAIL, TRAM, WATER or AIR (most common among its vehicles).",
          lambda r: r.facts.line_row(r.raw)["carrier"], caveat="Missing for lines without vehicles.")
_register("line.vehicle_count", NUMBER, ("lines[].vehicles",), "Number of vehicles assigned to the line.",
          lambda r: len(r.raw.get("vehicles") or []))
_register("line.stop_count", NUMBER, ("lines[].stops",), "Number of stops on the line.",
          lambda r: len(r.raw.get("stops") or []))
_register("line.stop_towns", LIST_NUMBER, ("lines[].stops[].stationGroup", "stations[].townName"),
          "Distinct towns of the line's stops, from each stop's station group (never from name codes).",
          lambda r: _present(list(dict.fromkeys(_stop_town_keys(r)))), derived=True, label_kind="town",
          caveat="Stops whose station group is absent from stations[] contribute no town.")
_register("line.first_stop_town", NUMBER, ("lines[].stops[].stationGroup", "stations[].townName"),
          "Town of the line's first stop.",
          lambda r: _town_key(r.facts.stop_station((r.raw.get("stops") or [None])[0])), derived=True, label_kind="town",
          caveat="Missing when the first stop's station group is absent from stations[].")
_register("line.town_count", NUMBER, ("lines[].stops[].stationGroup", "stations[].townName"),
          "Number of distinct towns the line's stops belong to.",
          lambda r: len(set(_stop_town_keys(r))) or None, derived=True,
          caveat="Missing when no stop resolves to a town.")
_register("line.profit_year", NUMBER, ("lines[].profitYear",), "Rolling game-year profit of the line.",
          lambda r: r.raw.get("profitYear"),
          caveat="Rolling game year, not calendar income; partial for lines younger than a year.")
_register("line.loss_year", NUMBER, ("lines[].profitYear",), "Loss over the rolling game year: max(0, -profit_year).",
          lambda r: None if r.raw.get("profitYear") is None else max(0, -r.raw["profitYear"]), derived=True,
          caveat="Rolling game year, not calendar income; partial for lines younger than a year.")
_register("line.transported_year", NUMBER, ("lines[].transportedYear",), "Items transported over the rolling game year.",
          lambda r: r.raw.get("transportedYear"), caveat="The accounting interpretation of transportedYear is unverified.")
_register("line.rate", NUMBER, ("lines[].rate",), "Line throughput rate reported by the game.", lambda r: r.raw.get("rate"))
_register("line.load", NUMBER, ("lines[].capacity[]",), "Occupancy of the line's vehicles, 0 to 1.",
          _line_unrounded_load, caveat="Instantaneous reading at snapshot time, not an average.")
_register("line.age_years", NUMBER, ("vehicles[].purchaseTime", "meta.yearDuration"),
          "Age of the oldest vehicle on the line, in game years.",
          lambda r: analysis.line_age_years(r.facts.snap, r.raw),
          caveat="Lower bound for the line's age (no creation date is collected); divided by meta.yearDuration, "
                 "which may differ from the calendar year.")
_register("line.is_passenger_only", BOOL, ("lines[].capacity[]",),
          "True when every positive-capacity entry of the line is passengers (cargo id 0).",
          lambda r: (lambda ids: None if not ids else all(i == PASSENGER_CARGO_ID for i in ids))(_cargo_ids(r.raw)),
          derived=True, caveat="capacity[].cargo is the cargo id plus one. Missing when the line has no positive capacity "
                               "(for example no vehicles).")
_register("line.cargo_ids", LIST_NUMBER, ("lines[].capacity[]",), "Cargo ids with positive capacity on the line.",
          lambda r: _present(_cargo_ids(r.raw)), derived=True, caveat="capacity[].cargo minus one.")
_register("line.cargo_names", LIST_STRING, ("lines[].capacity[]",),
          "Cargo names with positive capacity, as the game shows them.",
          lambda r: _present([_cargo_name(r.facts.snap, i) for i in _cargo_ids(r.raw)]), derived=True,
          caveat="Names follow the game language; use line.cargo_keys for language-neutral matching.")
_register("line.cargo_keys", LIST_STRING, ("lines[].capacity[]", "cargos[].res"),
          "Language-neutral cargo keys (segment of the cargo resource path, for example `grain`).",
          lambda r: _present([k for i in _cargo_ids(r.raw) if (k := _cargo_key(r.facts.snap, i))]), derived=True)
_register("line.issue_types", LIST_STRING, ("lines[].issues[]",), "Configuration issue types reported for the line.",
          lambda r: _present([i.get("type") for i in r.raw.get("issues") or []
                              if isinstance(i, dict) and i.get("type") not in (None, "None")]))
_register("line.route_km", NUMBER, (POSITIONS, "lines[].stops[].stationGroup"),
          "Straight-line length of the line through its stops, in kilometres.",
          lambda r: (lambda legs: None if legs is None else sum(legs))(_route_legs_km(r)),
          derived=True, requires=(POSITIONS,), collected=False,
          caveat="Needs station positions, which the collector does not emit yet. Chain of straight legs, not track length.")
_register("line.stop_distances_km", LIST_NUMBER, (POSITIONS, "lines[].stops[].stationGroup"),
          "Straight-line distance of each leg between consecutive stops, in kilometres.",
          _route_legs_km, derived=True, requires=(POSITIONS,), collected=False,
          caveat="Needs station positions, which the collector does not emit yet.")
_register("line.role", STRING, ("(methodology roles)",), "Role this methodology assigned to the line, or `unclassified`.",
          lambda r: r.role or r.facts.line_roles.get(r.raw.get("id"), UNCLASSIFIED), derived=True)

# ---------------------------------------------------------------------------
# vehicle


def _vehicle_family(rec: Record) -> str | None:
    snap = rec.facts.snap
    models = rec.raw.get("models") or []
    if not models:
        return None
    model = snap.models.get(models[0]) or next((m for m in snap.catalog if m.get("id") == models[0]), None)
    return model_family((model or {}).get("res"))


_register("vehicle.id", NUMBER, ("vehicles[].id",), "Entity id of the vehicle.", lambda r: r.raw.get("id"))
_register("vehicle.name", STRING, ("vehicles[].name",), "Vehicle name.", lambda r: _present(r.raw.get("name")))
_register("vehicle.carrier", STRING, ("vehicles[].carrier",), "Transport mode of the vehicle.", lambda r: r.raw.get("carrier"))
_register("vehicle.maintenance_state", NUMBER, ("vehicles[].maintenanceState",),
          "Maintenance condition, 0 to 1 (1 = excellent).", lambda r: r.raw.get("maintenanceState"))
_register("vehicle.model_family", STRING, ("vehicles[].models", "models[].res"),
          "Vehicle family from the model resource path. Observed in a real snapshot: `bus`, `truck`, `plane`, `helicopter`, `ship`.",
          _vehicle_family, derived=True)
_register("vehicle.age_years", NUMBER, ("vehicles[].purchaseTime", "meta.yearDuration"), "Vehicle age in game years.",
          lambda r: r.facts.snap.age_years(r.raw.get("purchaseTime")),
          caveat="Divided by meta.yearDuration, which may differ from the calendar year.")
_register("vehicle.profit_year", NUMBER, ("vehicles[].profitYear",), "Rolling game-year profit of the vehicle.",
          lambda r: r.raw.get("profitYear"), caveat="Rolling game year, not calendar income.")
_register("vehicle.state", STRING, ("vehicles[].state",), "Vehicle state reported by the game.", lambda r: r.raw.get("state"))
_register("vehicle.days_in_depot", NUMBER, ("vehicles[].daysInDepot",), "Days the vehicle has been in a depot.",
          lambda r: r.raw.get("daysInDepot"))
_register("vehicle.value", NUMBER, ("vehicles[].value",), "Recorded resale value.", lambda r: r.raw.get("value"))
_register("vehicle.line_id", NUMBER, ("vehicles[].line",), "Id of the line the vehicle is assigned to.",
          lambda r: r.raw.get("line") or None)
_register("vehicle.role", STRING, ("(methodology roles)",), "Role this methodology assigned to the vehicle.",
          lambda r: r.role or UNCLASSIFIED, derived=True)

# ---------------------------------------------------------------------------
# stop (a line's stop; used by aggregate rules)

_register("stop.station", NUMBER, ("lines[].stops[].stationGroup",), "Station group id of the stop.",
          lambda r: r.raw.get("stationGroup"), label_kind="station")
_register("stop.station_name", STRING, ("stations[].name",), "Station group name.",
          lambda r: _present((r.facts.stop_station(r.raw) or {}).get("name") or r.raw.get("name")))
_register("stop.terminal", NUMBER, ("lines[].stops[].terminal",), "Terminal (platform or gate) the stop uses.",
          lambda r: r.raw.get("terminal"),
          caveat="Only the terminals used by the player's lines are known; the station's total terminals are not collected.")
_register("stop.town", NUMBER, ("lines[].stops[].stationGroup", "stations[].townName"),
          "Town of the stop's station group.", lambda r: _town_key(r.facts.stop_station(r.raw)), derived=True,
          label_kind="town", caveat="Missing when the station group is absent from stations[].")
_register("stop.line_id", NUMBER, ("lines[].id",), "Id of the line the stop belongs to.",
          lambda r: None if r.line is None else r.line.get("id"))

# ---------------------------------------------------------------------------
# industry


def _industry_ratio(rec: Record, flows: str, num: str, den: str) -> float | None:
    items = [f for f in rec.raw.get(flows) or [] if isinstance(f, dict)]
    if not items or any(f.get(num) is None or f.get(den) is None for f in items):
        return None
    return _ratio(sum(f[num] for f in items), sum(f[den] for f in items))


_register("industry.id", NUMBER, ("industries[].id",), "Entity id of the industry.", lambda r: r.raw.get("id"))
_register("industry.name", STRING, ("industries[].name",), "Industry name.", lambda r: _present(r.raw.get("name")))
_register("industry.type", STRING, ("industries[].type",),
          "Industry resource path, for example `::/industries/oil_refinery/oil_refinery.con`.",
          lambda r: r.raw.get("type"))
_register("industry.level", NUMBER, ("industries[].level",), "Current production level.", lambda r: r.raw.get("level"))
_register("industry.production_rating", NUMBER, ("industries[].productionRating",), "Production rating reported by the game.",
          lambda r: r.raw.get("productionRating"))
_register("industry.shipped_ratio", NUMBER, ("industries[].outputs[].producedYear", "industries[].outputs[].shippedYear"),
          "Shipped over produced, summed over all outputs, per rolling game year.",
          lambda r: _industry_ratio(r, "outputs", "shippedYear", "producedYear"), derived=True,
          caveat="Missing when the industry produces nothing. Rolling game year.")
_register("industry.input_delivery_ratio", NUMBER,
          ("industries[].inputs[].deliveredYear", "industries[].inputs[].maxConsumptionYear"),
          "Delivered over maximum consumption, summed over all inputs, per rolling game year.",
          lambda r: _industry_ratio(r, "inputs", "deliveredYear", "maxConsumptionYear"), derived=True,
          caveat="Missing for industries without inputs. Rolling game year.")
_register("industry.closing", BOOL, ("industries[].closureTimeStamp", "problems.closingIndustries"),
          "Whether the industry is scheduled to close.",
          lambda r: analysis.industry_row(r.facts.snap, r.raw)["closing"])
_register("industry.role", STRING, ("(methodology roles)",), "Role this methodology assigned to the industry.",
          lambda r: r.role or UNCLASSIFIED, derived=True)

# ---------------------------------------------------------------------------
# stock

_register("stock.kind", STRING, ("stocks[].kind",), "Stock owner kind: station, industry or warehouse.",
          lambda r: r.raw.get("kind"))
_register("stock.owner_name", STRING, ("stocks[].ownerName",), "Name of the stock's owner.",
          lambda r: _present(r.raw.get("ownerName")))
_register("stock.count", NUMBER, ("stocks[].count",), "Units in the stock.", lambda r: r.raw.get("count"))
_register("stock.capacity", NUMBER, ("stocks[].capacity",), "Stock capacity in units.", lambda r: r.raw.get("capacity"))
_register("stock.fill_ratio", NUMBER, ("stocks[].count", "stocks[].capacity"), "Stock fill, count over capacity, 0 to 1.",
          lambda r: _ratio(r.raw.get("count"), r.raw.get("capacity")), derived=True,
          caveat="Instantaneous reading. Full destination stocks can prevent unloading.")
_register("stock.role", STRING, ("(methodology roles)",), "Role this methodology assigned to the stock.",
          lambda r: r.role or UNCLASSIFIED, derived=True)

# ---------------------------------------------------------------------------
# town


def _town_pairs(rec: Record) -> list[float] | None:
    key = rec.raw.get("id")
    centres = rec.facts.town_centres
    if key not in centres:
        return None
    here = centres[key]
    others: dict[Any, float] = {}
    for line in rec.facts.snap.lines:
        towns = list(dict.fromkeys(_town_key(rec.facts.stop_station(s)) for s in line.get("stops") or []))
        if key not in towns:
            continue
        for other in towns:
            if other is not None and other != key and other in centres:
                others[other] = math.hypot(here[0] - centres[other][0], here[1] - centres[other][1]) / 1000
    return [others[k] for k in sorted(others, key=lambda k: others[k])] or None


_register("town.id", NUMBER, ("towns[].id",), "Entity id of the town.", lambda r: r.raw.get("id"))
_register("town.name", STRING, ("towns[].name",), "Town name.", lambda r: _present(r.raw.get("name")))
_register("town.capacity_sum", NUMBER, ("towns[].capacities",),
          "Sum of residential, commercial and industrial capacities.",
          lambda r: sum(r.raw["capacities"]) if r.raw.get("capacities") else None, derived=True,
          caveat="A proxy for population [INFERENCE].")
_register("town.line_usage", NUMBER, ("towns[].lineUsage",), "Share of the town using the player's lines.",
          lambda r: r.raw.get("lineUsage"))
_register("town.pair_distance_km", LIST_NUMBER, (POSITIONS, "lines[].stops[].stationGroup"),
          "Straight-line distances from this town to the other towns its lines connect, in kilometres.",
          _town_pairs, derived=True, requires=(POSITIONS,), collected=False,
          caveat="Needs station positions, which the collector does not emit yet. Centre = mean of the town's stations.")
_register("town.role", STRING, ("(methodology roles)",), "Role this methodology assigned to the town.",
          lambda r: r.role or UNCLASSIFIED, derived=True)


# ---------------------------------------------------------------------------
# Inherited line fields and dynamic name captures

def _inherit(prefix: str, spec: FieldSpec) -> FieldSpec:
    base = spec.getter

    def getter(rec: Record, _base: Getter = base) -> Any:
        line = rec.line_record
        return None if line is None else _base(line)

    suffix = spec.name.split(".", 1)[1]
    return FieldSpec(f"{prefix}.line.{suffix}", prefix, spec.type, spec.sources, spec.caveat, spec.description,
                     getter, spec.derived, spec.requires, spec.collected, spec.label_kind)


for _entity in _INHERITING:
    for _spec in [s for s in _REGISTRY.values() if s.entity == "line"]:
        _inherited = _inherit(_entity, _spec)
        _REGISTRY[_inherited.name] = _inherited

_CAPTURE_RE = re.compile(r"^(line|vehicle\.line|stop\.line)\.name_capture\.([a-z][a-z0-9_]*)$")


def capture_name(name: str) -> tuple[str, str] | None:
    """(entity prefix, capture name) for `line.name_capture.<n>` style fields."""
    match = _CAPTURE_RE.match(name)
    return (match.group(1).split(".", 1)[0], match.group(2)) if match else None


def lookup(name: str) -> FieldSpec | None:
    spec = _REGISTRY.get(name)
    if spec is not None:
        return spec
    cap = _CAPTURE_RE.match(name)
    if cap is None:
        return None
    prefix, capture = cap.group(1), cap.group(2)

    def getter(rec: Record, _capture: str = capture) -> Any:
        line = rec.line_record
        found = None if line is None else line.facts.captures(line.raw)
        return None if found is None else found.get(_capture)

    return FieldSpec(name, prefix.split(".", 1)[0], STRING, ("lines[].name",), "Capture from the first matching name pattern.",
                     f"Name capture `{capture}` (missing when no name pattern matches).", getter, derived=True)


def all_fields() -> list[FieldSpec]:
    """Canonical registry entries (the inherited `<entity>.line.*` views are listed once, in the docs)."""
    return [s for s in _REGISTRY.values() if ".line." not in s.name]


def inherited_fields() -> list[FieldSpec]:
    return [s for s in _REGISTRY.values() if ".line." in s.name]


def known_entity(prefix: str) -> bool:
    return prefix in ENTITIES


def suggest(name: str) -> str | None:
    names = [n for n in _REGISTRY]
    close = difflib.get_close_matches(name, names, n=1, cutoff=0.7)
    return close[0] if close else None


# ---------------------------------------------------------------------------
# Snapshot data availability

def _walk(value: Any, parts: list[str]) -> tuple[bool, bool]:
    """(containers_seen, value_found) for a dotted/array path below `value`."""
    if not parts:
        found = value is not None and value != [] and value != {}
        return True, found
    head, rest = parts[0], parts[1:]
    is_array = head.endswith("[]")
    key = head[:-2] if is_array else head
    child = value.get(key) if isinstance(value, dict) else None
    if child is None:
        return isinstance(value, dict), False
    if is_array:
        items = list(child.values()) if isinstance(child, dict) else child
        if not isinstance(items, list) or not items:
            return False, False
        seen = False
        for item in items:
            s, f = _walk(item, rest)
            seen = seen or s
            if f:
                return True, True
        return seen, False
    return _walk(child, rest)


def probe_path(snap: Snapshot, path: str) -> bool | None:
    """True when the snapshot carries a value at `path`; False when entities exist but none has it;
    None when there is nothing to inspect (no entities of that kind)."""
    if path.startswith("("):
        return True
    seen, found = _walk(snap.raw, path.split("."))
    if found:
        return True
    return False if seen else None
