"""Typed factual projections behind the base reports (company, lines, fleet, cargo, annual, decisions).

Every number, membership, ordering and diagnostic of those reports is computed here from evidence read
at the operation's endpoint through an `EvidenceReader`; the report builders only lay the results out.
They are internal projections, not public analysis views. Existing `analysis` helpers do the factual
work; nothing here evaluates a rule. Unknown values stay `None` (never zero) and subtotals state how
many members were unknown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from . import analysis
from .analysis_views.models import EvaluationContext
from .analysis_views.reader import EvidenceReader
from .snapshot import Snapshot

LINES_WINDOW = 12
COMPANY_WINDOW = 36
CLOSING_FINDINGS_HISTORY = 24
DECISION_LIMIT = 10_000


def _change(current: Any, baseline: Any) -> float | int | None:
    return None if current is None or baseline is None else current - baseline


def _known_sum(values: list[Any]) -> tuple[float | int | None, int]:
    known = [v for v in values if v is not None]
    return (sum(known) if known else None), len(values) - len(known)


@dataclass(frozen=True)
class Header:
    """The report identity fields of the endpoint sample."""

    company: str
    date_label: str
    errors: tuple[str, ...]
    samples_used: int

    @classmethod
    def of(cls, snapshot: Snapshot, samples_used: int) -> "Header":
        return cls(snapshot.company.get("name") or "Primary Company", snapshot.date_label,
                   tuple(snapshot.errors), samples_used)


@dataclass(frozen=True)
class Indicator:
    """One current value with its change since the previous sample and the calendar year-ago sample."""

    key: str
    current: Any
    since_previous: Any = None
    since_year_ago: Any = None


@dataclass(frozen=True)
class FinancePoint:
    date_label: str
    balance: Any
    loan: Any


@dataclass(frozen=True)
class CompanyFacts:
    header: Header
    indicators: tuple[Indicator, ...]
    modal: tuple[dict[str, Any], ...]
    history: tuple[FinancePoint, ...]
    year_ago_date: str | None
    elapsed_game_years: float | None
    elapsed_reason: str | None


def _balance_net(company: dict[str, Any]) -> Any:
    balance, loan = company.get("balance"), company.get("loan")
    return None if balance is None or loan is None else balance - loan


def company_facts(reader: EvidenceReader, context: EvaluationContext) -> CompanyFacts:
    snaps = reader.recent(COMPANY_WINDOW)
    latest = snaps[-1]
    prev = snaps[-2] if len(snaps) > 1 else None
    y_ago = reader.store.calendar_baseline(latest)
    ov = analysis.company_overview(latest, prev)
    c = latest.company

    def trio(key: str, current: Any, getter) -> Indicator:
        return Indicator(key, current,
                         _change(current, getter(prev)) if prev else None,
                         _change(current, getter(y_ago)) if y_ago else None)

    indicators = (
        trio("balance", c.get("balance"), lambda s: s.company.get("balance")),
        trio("loan", c.get("loan"), lambda s: s.company.get("loan")),
        Indicator("net_position", _balance_net(c)),
        Indicator("company_value", c.get("value")),
        trio("lines", len(latest.lines), lambda s: len(s.lines)),
        trio("vehicles", len(latest.vehicles), lambda s: len(s.vehicles)),
        Indicator("lines_profit_year", ov.get("linesProfitYear")),
    )
    elapsed = context.clock.elapsed_between_ticks(y_ago.game_time, latest.game_time) if y_ago else None
    history = tuple(FinancePoint(s.date_label, s.company.get("balance"), s.company.get("loan")) for s in snaps)
    return CompanyFacts(Header.of(latest, len(snaps)), indicators, tuple(analysis.modal_summary(latest)), history,
                        y_ago.date_label if y_ago else None, elapsed.value if elapsed else None,
                        (elapsed.reason or elapsed.method) if elapsed else None)


@dataclass(frozen=True)
class LinesFacts:
    header: Header
    ranked: tuple[dict[str, Any], ...]        # every line, most profitable first; unknown profit last, id tie-break
    losing: tuple[tuple[dict[str, Any], tuple[str, ...]], ...]   # (line row, finding codes)
    empty: tuple[dict[str, Any], ...]
    no_stop_pair: tuple[dict[str, Any], ...]
    trends: tuple[dict[str, Any], ...]
    samples: int


def lines_facts(reader: EvidenceReader, context: EvaluationContext, methodology: Any = None) -> LinesFacts:
    snaps = reader.recent(LINES_WINDOW)
    latest = snaps[-1]
    rows = [analysis.line_row(latest, line, clock=context.clock) for line in latest.lines]
    ranked = sorted(rows, key=lambda r: (-(r["profitYear"] if r["profitYear"] is not None else -10**15), r["id"]))
    losing_rows = [r for r in rows if r["profitYear"] is not None and r["profitYear"] < 0]
    losing: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    if losing_rows:
        found = analysis.findings(latest, reader.store.previous_of(latest), t=context.thresholds,
                                  methodology=methodology, history=reader.recent(CLOSING_FINDINGS_HISTORY),
                                  clock=context.clock)
        line_findings = [f for f in found if f.category == "lines"]
        for r in losing_rows:
            losing.append((r, tuple(f.code for f in line_findings if f.entity and f.entity.get("id") == r["id"])))
    return LinesFacts(Header.of(latest, len(snaps)), tuple(ranked), tuple(losing),
                      tuple(r for r in rows if r["vehicles"] == 0), tuple(r for r in rows if r["stops"] < 2),
                      tuple(analysis.load_trend(snaps)), len(snaps))


@dataclass(frozen=True)
class FleetFacts:
    header: Header
    losing: tuple[dict[str, Any], ...]               # most negative first
    aging: tuple[tuple[dict[str, Any], tuple[Any, ...]], ...]   # (vehicle row, raw model lifespans)
    catalog_date: str | None
    retired_models: tuple[dict[str, Any], ...]
    idle_in_depot: tuple[dict[str, Any], ...]         # vehicle rows plus resolved `depotName`
    idle_value_known: float | int | None
    idle_value_unknown: int
    fit: dict[str, Any]


def fleet_facts(reader: EvidenceReader, context: EvaluationContext) -> FleetFacts:
    latest = reader.recent(1)[-1]
    catalog_snap = reader.catalog()
    rows = [analysis.vehicle_row(latest, v, clock=context.clock) for v in latest.vehicles]
    losing = sorted((r for r in rows if r["profitYear"] is not None and r["profitYear"] < 0),
                    key=lambda r: (r["profitYear"], r["id"]))
    aging = tuple((r, tuple(latest.models.get(m, {}).get("lifespan") for m in vehicle.get("models") or []))
                  for vehicle, r in zip(latest.vehicles, rows))
    retired: list[dict[str, Any]] = []
    if catalog_snap:
        year = (latest.date or {}).get("year", latest.meta.get("year"))
        retired = [model for model in catalog_snap.catalog
                   if year is not None and model.get("yearTo") is not None and 0 < model["yearTo"] <= year]
    depots = {d["id"]: d.get("name") or f"Depot #{d['id']}" for d in latest.depots}
    idle = tuple({**r, "depotName": depots.get(r["depot"], "Unknown Depot")}
                 for r in rows if r["state"] == "IN_DEPOT" and not r["line"])
    known, unknown = _known_sum([r["value"] for r in idle])
    return FleetFacts(Header.of(latest, 1), tuple(losing), aging, catalog_snap.date_label if catalog_snap else None,
                      tuple(retired), idle, known, unknown, analysis.fleet_fit(latest, catalog_snap, context.thresholds))


@dataclass(frozen=True)
class CargoFacts:
    header: Header
    full_stock_ratio: float
    full_stocks: tuple[dict[str, Any], ...]
    unshipped: tuple[dict[str, Any], ...]
    closing: tuple[dict[str, Any], ...]


def cargo_facts(reader: EvidenceReader, context: EvaluationContext) -> CargoFacts:
    latest = reader.recent(1)[-1]
    t = context.thresholds
    ops = analysis.opportunities(latest, t)
    flagged = set(latest.problems.get("closingIndustries") or [])
    closing = tuple(ind for ind in latest.industries if ind.get("closureTimeStamp") or ind.get("id") in flagged)
    return CargoFacts(Header.of(latest, 1), t.full_stock_ratio, tuple(analysis.full_stocks(latest, t)),
                      tuple(o for o in ops if o.get("kind") == "unshipped"), closing)


# ---- decisions -------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricChange:
    metric: str
    before: Any
    after: Any
    change: Any


@dataclass(frozen=True)
class EntityComparison:
    reference: str
    resolved: bool
    name: str | None = None
    kind: str | None = None
    removed: bool = False
    metrics: tuple[MetricChange, ...] = ()


@dataclass(frozen=True)
class DecisionComparison:
    decision: dict[str, Any]
    baseline_date: str | None
    comparison_date: str
    elapsed_game_years: float | None
    elapsed_reason: str | None
    elapsed_nominal_windows: float | None
    entities: tuple[EntityComparison, ...]


def _resolve_entity(snap: Snapshot | None, reference: Any) -> tuple[str, dict[str, Any]] | None:
    if snap is None:
        return None
    kind = None
    if isinstance(reference, dict):
        kind = reference.get("type") or reference.get("kind")
        reference = reference.get("id", reference.get("name"))
    elif isinstance(reference, str) and reference.partition(":")[0] in ("line", "vehicle"):
        kind, _, reference = reference.partition(":")
    if kind is not None and kind not in ("line", "vehicle"):
        return None
    collections = {"line": snap.lines, "vehicle": snap.vehicles}
    candidates = [(entity_kind, entity) for entity_kind, entries in collections.items()
                  if kind is None or entity_kind == kind for entity in entries]
    text = str(reference).casefold()
    if type(reference) is int or (isinstance(reference, str) and reference.isdigit()):
        matches = [(k, e) for k, e in candidates if e["id"] == int(reference)]
    else:
        matches = [(k, e) for k, e in candidates if (e.get("name") or "").casefold() == text]
        if not matches and text and reference is not None:
            matches = [(k, e) for k, e in candidates if text in (e.get("name") or "").casefold()]
    return matches[0] if len(matches) == 1 else None


def decision_comparison(reader: EvidenceReader, decision: dict[str, Any], comparison: Snapshot) -> DecisionComparison:
    """Before/after facts of one recorded decision; baseline and comparison never lie past the endpoint."""
    recorded = decision.get("game_time")
    baseline = reader.at_or_before(min(recorded, comparison.game_time)) if recorded is not None else None
    clock = reader.clock_at(comparison)
    elapsed = clock.elapsed_between_ticks(recorded, comparison.game_time)
    nominal = ((comparison.game_time - recorded) / comparison.year_duration
               if recorded is not None and comparison.year_duration else None)
    out: list[EntityComparison] = []
    for reference in decision.get("entities") or []:
        resolved = _resolve_entity(baseline, reference) or _resolve_entity(comparison, reference)
        if resolved is None:
            out.append(EntityComparison(str(reference), False))
            continue
        kind, entity = resolved
        before = _resolve_entity(baseline, {"type": kind, "id": entity["id"]})
        after = _resolve_entity(comparison, {"type": kind, "id": entity["id"]})
        old, new = before[1] if before else None, after[1] if after else None
        name = (new or old).get("name") or f"{kind.title()} #{entity['id']}"
        metrics = [("Rolling Annual Profit", old.get("profitYear") if old else None, new.get("profitYear") if new else None)]
        if kind == "line":
            metrics.extend([
                ("Vehicles", len(old.get("vehicles") or []) if old else None, len(new.get("vehicles") or []) if new else None),
                ("Instant Load Ratio", analysis.line_load(old) if old else None, analysis.line_load(new) if new else None),
            ])
        out.append(EntityComparison(str(reference), True, name, kind, new is None,
                                    tuple(MetricChange(m, a, b, _change(b, a)) for m, a, b in metrics)))
    return DecisionComparison(decision, baseline.date_label if baseline else None, comparison.date_label,
                              elapsed.value, elapsed.reason or elapsed.method, nominal, tuple(out))


def recorded_decisions(reader: EvidenceReader, until_tick: int) -> list[dict[str, Any]]:
    """Journal entries recorded at or before `until_tick`, newest first; undated ones stay (no baseline)."""
    return [d for d in reader.store.list_decisions(limit=DECISION_LIMIT)
            if d.get("game_time") is None or d["game_time"] <= until_tick]


@dataclass(frozen=True)
class DecisionsFacts:
    header: Header
    decisions: tuple[dict[str, Any], ...]
    comparisons: tuple[DecisionComparison, ...]


def decisions_facts(reader: EvidenceReader, context: EvaluationContext) -> DecisionsFacts:
    latest = context.snapshot
    decisions = recorded_decisions(reader, latest.game_time)
    return DecisionsFacts(Header.of(latest, reader.count_samples()), tuple(decisions),
                          tuple(decision_comparison(reader, d, latest) for d in decisions))


# ---- annual ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Compared:
    label: str
    baseline: Any
    closing: Any
    change: Any


@dataclass(frozen=True)
class ModalChange:
    carrier: str
    baseline_lines: int
    closing_lines: int
    baseline_vehicles: int
    closing_vehicles: int
    baseline_profit: Any
    closing_profit: Any
    profit_change: Any


@dataclass(frozen=True)
class AnnualFacts:
    year: int
    header: Header                       # of the closing sample
    complete_monthly: bool
    in_progress: bool
    future_history: bool
    missing_months: tuple[int, ...]
    observed_dates: tuple[str, ...]
    baseline_date: str | None
    closing_date: str
    samples_used: int
    financial: tuple[Compared, ...]
    baseline_label: str                  # date label of the baseline (or first in-year sample)
    closing_profit_known: Any
    closing_profit_unknown_lines: int
    ranked_lines: tuple[dict[str, Any], ...]     # closing lines, most profitable first
    lines_added: tuple[dict[str, Any], ...]
    lines_removed: tuple[dict[str, Any], ...]
    vehicles_added: tuple[dict[str, Any], ...]
    vehicles_removed: tuple[dict[str, Any], ...]
    modal: tuple[ModalChange, ...]
    previous_year: int
    yoy: tuple[Compared, ...] | None
    yoy_best_line: tuple[str, str] | None
    decisions: tuple[DecisionComparison, ...]
    high_findings: tuple[dict[str, Any], ...]
    timeline: tuple[FinancePoint, ...]


def _year_of(meta: dict[str, Any]) -> int | None:
    year = (meta.get("date") or {}).get("year", meta.get("year"))
    return year if type(year) is int else None


def annual_years(reader: EvidenceReader) -> list[tuple[int, int, int | None]]:
    """(tick, year, month) of every eligible sample whose year is known, oldest first."""
    out = []
    for tick, _label, parts in reader.projection(("meta",)):
        meta = parts.get("meta") or {}
        year = _year_of(meta)
        if year is not None:
            out.append((tick, year, (meta.get("date") or {}).get("month")))
    return out


def _name(entity: dict[str, Any] | None, kind: str) -> str:
    if not entity:
        return f"{kind} #unknown"
    return entity.get("name") or f"{kind.title()} #{entity.get('id', 'unknown')}"


def _best(lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(lines, key=lambda l: l.get("profitYear") if l.get("profitYear") is not None else -math.inf, default=None)


def _compared(label: str, baseline: Any, closing: Any) -> Compared:
    return Compared(label, baseline, closing, _change(closing, baseline))


def annual_facts(reader: EvidenceReader, context: EvaluationContext, year: int | None, methodology: Any = None) -> AnnualFacts:
    index = annual_years(reader)
    available = sorted({y for _, y, _ in index})
    if not available:
        raise ValueError("no snapshot found")
    current = context.snapshot
    if year is None:
        year = (current.date or {}).get("year") if current.date else available[-1]
        year = year if year is not None else available[-1]
    if year not in available:
        raise ValueError(f"No snapshots found for year {year}. Available years: {', '.join(str(y) for y in available)}")

    ticks = [t for t, y, _ in index if y == year]
    year_ticks = set(ticks)
    start_snap = reader.hydrate(ticks[0])
    end_snap = reader.hydrate(ticks[-1])
    baseline_snap = reader.store.latest_before(start_snap.game_time)
    months = sorted({m for t, y, m in index if y == year and m})
    missing = tuple(sorted(set(range(1, 13)) - set(months)))
    has_baseline = (baseline_snap is not None and baseline_snap.date is not None
                    and baseline_snap.date["year"] == year - 1 and baseline_snap.date["month"] == 12)
    future = reader.store.snapshot_count() > reader.count_samples()
    complete = not missing and has_baseline and not future
    in_progress = (current.date or {}).get("year") == year and (end_snap.date or {}).get("month", 0) < 12

    base = baseline_snap or start_snap
    profits = [l.get("profitYear") for l in end_snap.lines]
    known_profit, unknown_lines = _known_sum(profits)
    ranked = sorted(end_snap.lines, key=lambda l: (-(l["profitYear"] if l.get("profitYear") is not None else -10**15),
                                                   l["id"]))

    def keyed(items: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
        return {i["id"]: i for i in items}

    base_lines, end_lines = keyed(base.lines), keyed(end_snap.lines)
    base_v, end_v = keyed(base.vehicles), keyed(end_snap.vehicles)
    m_start = {m["carrier"]: m for m in analysis.modal_summary(base)}
    m_end = {m["carrier"]: m for m in analysis.modal_summary(end_snap)}
    modal = []
    for carrier in sorted(set(m_start) | set(m_end)):
        s, e = m_start.get(carrier), m_end.get(carrier)
        modal.append(ModalChange(carrier, s["lines"] if s else 0, e["lines"] if e else 0,
                                 s["vehicles"] if s else 0, e["vehicles"] if e else 0,
                                 s["profitYear"] if s else None, e["profitYear"] if e else None,
                                 _change(e["profitYear"] if e else None, s["profitYear"] if s else None)))

    financial = (
        _compared("Cash Balance", base.company.get("balance"), end_snap.company.get("balance")),
        _compared("Outstanding Loan", base.company.get("loan"), end_snap.company.get("loan")),
        _compared("Lines Count", len(base.lines), len(end_snap.lines)),
        _compared("Vehicles Count", len(base.vehicles), len(end_snap.vehicles)),
    )

    prev_year = year - 1
    yoy = best = None
    prev_ticks = [t for t, y, _ in index if y == prev_year]
    if prev_ticks:
        p_end = reader.hydrate(prev_ticks[-1])
        p_profit, _ = _known_sum([l.get("profitYear") for l in p_end.lines])
        yoy = (
            _compared("Cash Balance", p_end.company.get("balance"), end_snap.company.get("balance")),
            _compared("Outstanding Loan", p_end.company.get("loan"), end_snap.company.get("loan")),
            _compared("Lines", len(p_end.lines), len(end_snap.lines)),
            _compared("Vehicles", len(p_end.vehicles), len(end_snap.vehicles)),
            _compared("Closing Rolling Line Profit", p_profit, known_profit),
        )
        best = (_name(_best(p_end.lines), "Line"), _name(_best(end_snap.lines), "Line"))

    in_year = [d for d in recorded_decisions(reader, end_snap.game_time)
               if (d.get("game_date") or "").startswith(f"{year:04d}-")]
    decisions = tuple(decision_comparison(reader, d, end_snap) for d in in_year)

    found = analysis.findings(end_snap, reader.store.previous_of(end_snap), t=context.thresholds, methodology=methodology,
                              history=reader.store.recent_snapshots(CLOSING_FINDINGS_HISTORY, end_snap.game_time),
                              clock=reader.clock_at(end_snap))
    high = tuple({"code": f.code, "category": f.category, "title": f.title, "detail": f.detail}
                 for f in found if f.severity == "high")
    timeline = tuple(FinancePoint(p["date_label"], p["balance"], p["loan"])
                     for p in reader.company_points() if p["game_time"] in year_ticks)

    return AnnualFacts(
        year, Header.of(end_snap, len(ticks) + int(baseline_snap is not None)), complete, in_progress, future,
        missing, tuple(label for t, label, _ in reader.sample_index() if t in year_ticks),
        baseline_snap.date_label if baseline_snap else None, end_snap.date_label, len(ticks) + int(baseline_snap is not None),
        financial, base.date_label, known_profit, unknown_lines, tuple(ranked),
        tuple(end_lines[i] for i in sorted(set(end_lines) - set(base_lines))),
        tuple(base_lines[i] for i in sorted(set(base_lines) - set(end_lines))),
        tuple(end_v[i] for i in sorted(set(end_v) - set(base_v))),
        tuple(base_v[i] for i in sorted(set(base_v) - set(end_v))),
        tuple(modal), prev_year, yoy, best, decisions, high, timeline)
