"""Vehicle ROI report: which vehicle types make (or lose) money, and what to test instead.

Presentation over `analysis_views.vehicle_roi.VehicleRoiView`: headings, prose, formatting, display
caps and charts only. Every statistic, rank, order, screen and swap hypothesis comes from the view.

Honesty rules shown here:
- ``profitYear`` is a rolling game-year figure. Per-vehicle values are only ever summed *within one
  snapshot* (distinct vehicles at one instant), never across snapshots; trends compare point samples.
- Vehicles younger than one game year have a partial window; group statistics are ranked on mature
  vehicles and young vehicles are reported separately as a lower bound.
- Catalog speed / running-cost / price units are unverified unless the catalog snapshot carries
  ``meta.verifiedUnits``. The swap section therefore only shows raw values and unit-free ratios.
"""

from __future__ import annotations

from typing import Any

from .analysis_views import EvaluationContext
from .analysis_views.vehicle_roi import (
    LOAD_HISTORY,
    MIN_LOAD_SAMPLES,
    MIN_SAMPLE,
    GroupStats,
    VehicleRoiView,
)
from .reports import (
    Chart,
    Heading,
    Note,
    Paragraph,
    ReportDocument,
    Table,
    _base_header,
    _fmt_pct,
)

MODEL_ROWS = 30
CARGO_ROWS = 25

AGE_LABELS = {0.0: "<1y (partial window)", 1.0: "1-3y", 3.0: "3-6y", 6.0: "6-10y", 10.0: "10-20y", 20.0: "20y+"}

_GROUP_COLUMNS = ["Vehicles", "Mature (>=1y)", "Young (<1y)", "Mean profit/vehicle", "Median", "Total (mature)",
                  "Loss-making (mature)", "Profit / value", "Young mean (partial)", "Sample"]
_GROUP_ALIGN = ["right"] * 9 + ["left"]


def _money(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def _flag(stats: GroupStats) -> str:
    if stats.sample == "no-mature":
        return "No mature vehicles"
    if stats.sample == "small-sample":
        return f"Small sample (n={stats.mature})"
    return "OK"


def _group_cells(stats: GroupStats) -> list[Any]:
    return [stats.n, stats.mature, stats.young, _money(stats.mean), _money(stats.median), _money(stats.total),
            _fmt_pct(stats.loss_share), _fmt_pct(stats.return_on_value), _money(stats.young_mean), _flag(stats)]


def _ratio_cell(ratio: float | None) -> str | None:
    return None if ratio is None else f"x{ratio:.2f}"


def _plain_number(value: float | None) -> Any:
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _insufficient(title: str, why: str) -> list[Any]:
    return [Heading(2, title), Note("Insufficient Data", why)]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _summary(view: VehicleRoiView, context: EvaluationContext) -> list[Any]:
    overall = view.overall
    blocks: list[Any] = [Heading(2, "Summary (Observations)")]
    if not view.observations:
        return blocks + [Note("Insufficient Data", "The latest snapshot has no vehicles.")]
    lines = [
        f"{overall.n} vehicles in the latest snapshot ({context.snapshot.date_label}): {overall.mature} meet calendar maturity policy "
        f"and {overall.young} are young; calendar age does not prove a complete rolling-profit window.",
    ]
    if overall.mature:
        lines.append(
            f"Mature vehicles: mean {_money(overall.mean):,} and median {_money(overall.median):,} rolling annual profit per "
            f"vehicle; {_fmt_pct(overall.loss_share)} are loss-making. Sum of those distinct vehicles' rolling profits at this one "
            f"snapshot: {_money(overall.total):,} (not calendar income)."
        )
    ranked = sorted((m for m in view.models if m.rank is not None), key=lambda m: m.rank)
    if ranked:
        best, worst = ranked[0], ranked[-1]
        lines.append(f"Best model group with n>={MIN_SAMPLE} mature vehicles: {best.key} - mean {_money(best.stats.mean):,} "
                     f"(n={best.stats.mature}).")
        if worst.key != best.key:
            lines.append(f"Worst: {worst.key} - mean {_money(worst.stats.mean):,}, {_fmt_pct(worst.stats.loss_share)} loss-making "
                         f"(n={worst.stats.mature}).")
    if view.model_groups_below_minimum:
        lines.append(f"{view.model_groups_below_minimum} of {len(view.models)} model groups have fewer than {MIN_SAMPLE} mature "
                     "vehicles and are flagged, not ranked.")
    blocks.extend(Paragraph(t) for t in lines)
    return blocks


def _carrier_section(view: VehicleRoiView) -> list[Any]:
    if not view.observations:
        return _insufficient("By Carrier", "No vehicles.")
    blocks: list[Any] = [
        Heading(2, "By Carrier"),
        Table(["Carrier"] + _GROUP_COLUMNS, [[g.key] + _group_cells(g.stats) for g in view.carriers], ["left"] + _GROUP_ALIGN),
    ]
    charted = [g for g in view.carriers if g.stats.mature > 0]
    if len(charted) >= 2:
        blocks.append(Chart("bar", "Mean rolling profit per mature vehicle, by carrier",
                            [g.key for g in charted], [("Mean profit", [float(_money(g.stats.mean)) for g in charted])]))
    blocks.append(Note("Reading This", "Carriers differ in cargo, distance and vehicle price, so this compares business lines, "
                                       "not how good a vehicle is. 'Profit / value' is aggregate rolling profit over aggregate "
                                       "recorded vehicle value (value depreciates, so old vehicles look better on this ratio)."))
    return blocks


def _model_section(view: VehicleRoiView) -> list[Any]:
    if not view.observations:
        return _insufficient("By Model", "No vehicles.")
    shown = view.models[:MODEL_ROWS]
    blocks: list[Any] = [
        Heading(2, "By Model"),
        Table(["Model [Carrier]"] + _GROUP_COLUMNS, [[m.key] + _group_cells(m.stats) for m in shown], ["left"] + _GROUP_ALIGN),
    ]
    if len(view.models) > len(shown):
        blocks.append(Paragraph(f"{len(view.models) - len(shown)} further model groups omitted (lowest ranked / youngest)."))
    blocks.append(Paragraph("Multi-part vehicles (trains) are grouped by their full consist: locomotive and wagon models with part "
                            "counts, so differently sized consists are separate groups."))

    reliable = sorted((m for m in view.models if m.rank is not None), key=lambda m: m.rank)
    blocks.append(Heading(3, f"Ranking (groups with at least {MIN_SAMPLE} mature vehicles)"))
    if not reliable:
        blocks.append(Note("Insufficient Data", f"No model group has {MIN_SAMPLE} or more mature vehicles yet."))
    else:
        top = reliable[:6]
        bottom = reliable[6:][-6:]
        picks = top + bottom
        blocks.append(Table(["Rank", "Model [Carrier]", "Mature n", "Mean profit/vehicle", "Median", "Loss-making"],
                            [[m.rank, m.key, m.stats.mature, _money(m.stats.mean), _money(m.stats.median),
                              _fmt_pct(m.stats.loss_share)] for m in picks],
                            ["right", "left", "right", "right", "right", "right"]))
        blocks.append(Chart("bar", "Mean rolling profit per mature vehicle (best and worst groups)",
                            [m.key for m in picks], [("Mean profit", [float(_money(m.stats.mean)) for m in picks])]))
        blocks.append(Paragraph(f"Ranked {len(reliable)} groups; top {len(top)} and bottom {len(bottom)} shown."))

    blocks.append(Heading(3, "Cost Basis (Raw Catalog-Style Values)"))
    rows = [[m.key, m.stats.mature, _money(m.median_list_price), _money(m.median_running_cost),
             _fmt_pct(m.stats.return_on_price),
             None if m.stats.return_on_running_cost is None else f"{m.stats.return_on_running_cost:.2f}"] for m in shown]
    blocks.append(Table(["Model [Carrier]", "Mature n", "List price (raw, median)", "Running cost (raw, median)",
                         "Profit / list price", "Profit / running cost (raw ratio)"], rows,
                        ["left", "right", "right", "right", "right", "right"]))
    blocks.append(Note("Unit Limit", "List price and running cost are the stored model values (running cost also appears per "
                                     "vehicle) in unverified units; no per-year or currency conversion is applied. 'Profit / list "
                                     "price' ignores the per-vehicle price factor and any resale; whether rolling profit already "
                                     "nets out running costs is unverified, so 'profit / running cost' is a raw ratio for "
                                     "ordering only."))
    return blocks


def _cargo_section(view: VehicleRoiView) -> list[Any]:
    if not view.observations:
        return _insufficient("By Cargo", "No vehicles.")
    blocks: list[Any] = [
        Heading(2, "By Cargo"),
        Table(["Cargo (vehicle's configured load)"] + _GROUP_COLUMNS,
              [[g.key] + _group_cells(g.stats) for g in view.cargos[:CARGO_ROWS]], ["left"] + _GROUP_ALIGN),
    ]
    if len(view.cargos) > CARGO_ROWS:
        blocks.append(Paragraph(f"{len(view.cargos) - CARGO_ROWS} further cargo groups omitted."))
    blocks.append(Note("Reading This", "Cargo is taken from each vehicle's current load configuration. In this game every freight "
                                       "cargo pays the same per item and distance (see knowledge: cargo_economy), so cargo rows "
                                       "mostly reflect route length, vehicle capacity and return loads, not goods type."))
    return blocks


def _age_section(view: VehicleRoiView) -> list[Any]:
    if not view.ages:
        return _insufficient("By Age", "No vehicle has a usable purchase time.")
    rows = [[a.carrier, AGE_LABELS[a.lower_years], a.stats.n, _money(a.reported_mean), _money(a.stats.median),
             _fmt_pct(a.stats.loss_share),
             None if a.stats.mean_condition is None else round(a.stats.mean_condition, 2),
             "Partial window (lower bound)" if a.partial_window else _flag(a.stats)] for a in view.ages]
    return [
        Heading(2, "By Age (Within Carrier)"),
        Table(["Carrier", "Age", "Vehicles", "Mean profit/vehicle", "Median", "Loss-making", "Mean condition (0-1)", "Sample"],
              rows, ["left", "left", "right", "right", "right", "right", "right", "left"]),
        Note("Reading This", "Age is elapsed GAME-YEAR on the shared game-calendar-v1 clock (365.25 calendar days): exact snapshot-date anchors or bounded interpolation between observed dates. "
                             "Purchases outside observed history have unknown age and are excluded here; no nominal tick duration is used as a fallback (see header for the time basis). Condition is maintenanceState (1 = excellent). "
                             "The <1y bucket shows the partial-window mean, which understates a full year. Older vehicles may "
                             "also sit on different lines, so age and profit are associated here, not shown to be causal."),
    ]


def _head_to_head(view: VehicleRoiView) -> list[Any]:
    if not view.same_line:
        return _insufficient("Same-Line Head-to-Head", "No line currently runs two or more model groups with a mature vehicle each.")
    rows = [[c.line, c.better, f"n={c.better_n}, mean {_money(c.better_mean):,}, avg age {c.better_avg_age:.1f}y",
             c.weaker, f"n={c.weaker_n}, mean {_money(c.weaker_mean):,}, avg age {c.weaker_avg_age:.1f}y", _money(c.gap),
             f"Small sample (smaller side n={min(c.better_n, c.weaker_n)})" if c.small_sample else "OK"]
            for c in view.same_line]
    total = len(rows)
    return [
        Heading(2, "Same-Line Head-to-Head"),
        Paragraph("Models operating on the same line share the route, so this removes route effects. Best vs worst mean per-vehicle "
                  "rolling profit among mature vehicles; lines with more than two model groups show only the extremes."),
        Table(["Line", "Better model", "Better: sample", "Weaker model", "Weaker: sample", "Mean gap", "Evidence"],
              rows[:15], ["left", "left", "left", "left", "left", "right", "left"]),
        Paragraph(f"{total} lines compared; top {min(15, total)} by gap shown." if total > 15 else f"{total} lines compared."),
        Note("Caution", "Vehicles on one line may differ in age, purchase date, depot or timetable position; this is an observation "
                        "of association only, mostly with n<3 per side."),
    ]


def _trend_section(view: VehicleRoiView) -> list[Any]:
    samples = view.trend_samples
    if len(samples) < 2:
        return _insufficient("Group Profit At Sampled Dates", "Fewer than two sampled snapshots; no point-in-time comparison possible.")
    per_sample = [{g.key: g.stats for g in s.groups} for s in samples]
    cats = [s.sample.date for s in samples]

    def cell(st: GroupStats | None) -> str:
        if not st or st.mature == 0:
            return "-"
        return f"{_money(st.mean):,} (n={st.mature}){'*' if st.mature < MIN_SAMPLE else ''}"

    rows = [["All vehicles"] + [cell(s.overall) for s in samples]]
    rows += [[k] + [cell(p.get(k)) for p in per_sample] for k in view.trend_groups]
    blocks: list[Any] = [
        Heading(2, "Group Profit At Sampled Dates"),
        Paragraph(f"Mean rolling profit per mature vehicle at {len(samples)} sampled snapshot dates ({cats[0]} to {cats[-1]}); each "
                  "column is an independent point-in-time reading of a rolling window and the vehicle set changes between dates "
                  "(purchases, sales). Values are never summed or averaged across dates."),
        Table(["Model [Carrier]"] + cats, rows, ["left"] + ["right"] * len(cats)),
        Paragraph("* n<3 mature vehicles at that date. '-' = no mature vehicle of that group at that date (unknown, not zero)."),
    ]
    complete = [(k, [p[k].mean for p in per_sample]) for k in view.trend_groups
                if all(k in p and p[k].mature > 0 for p in per_sample)]
    if complete:
        blocks.append(Chart("line", "Mean rolling profit per mature vehicle at sampled dates (groups present at every date)",
                            cats, [(k, [float(_money(v)) for v in vals]) for k, vals in complete]))
    movers = view.trend_movers
    picks = [m for m in movers if m.change < 0][:4] + [m for m in reversed(movers) if m.change > 0][:4]
    if picks:
        blocks.append(Heading(3, f"Largest Changes Between {cats[0]} and {cats[-1]} (groups with n>={MIN_SAMPLE} at both dates)"))
        blocks.append(Table(["Model [Carrier]", f"Mean at {cats[0]}", "n", f"Mean at {cats[-1]}", "n ", "Change"],
                            [[m.key, _money(m.first_mean), m.first_n, _money(m.last_mean), m.last_n, _money(m.change)]
                             for m in picks],
                            ["left", "right", "right", "right", "right", "right"]))
        blocks.append(Paragraph("Two point readings of a rolling one-year window: a drop can mean fewer or weaker recent months replacing "
                                "strong old ones, a changed route, or a different vehicle mix; it is not a measured per-period income."))
    return blocks


def _reason_text(reason) -> str:
    if reason.code == "cargo-not-in-can-carry":
        return "configured cargo not in the vehicle's own canCarry list"
    return f"catalog lists no capacity for {reason.cargo} on {reason.model}"


def _fit_section(view: VehicleRoiView, context: EvaluationContext) -> list[Any]:
    thresholds = context.thresholds
    blocks: list[Any] = [Heading(2, "Fit Checks: Cargo Match and Size vs Line Load")]
    blocks.append(Heading(3, "Cargo / Model Mismatch"))
    if view.mismatches:
        flagged = [[m.vehicle, m.line or "Unassigned", m.model, m.cargo, "; ".join(sorted({_reason_text(r) for r in m.reasons}))]
                   for m in view.mismatches]
        blocks.append(Table(["Vehicle", "Line", "Model", "Configured Cargo", "Evidence"], flagged[:25]))
        if len(flagged) > 25:
            blocks.append(Paragraph(f"{len(flagged) - 25} further flagged vehicles omitted."))
    else:
        blocks.append(Paragraph(f"No mismatch found among {view.mismatch_checked} vehicles with a stored load configuration (checked against each "
                                "vehicle's canCarry list and, where the model matches the stored catalog, the catalog capacity entries)."))
    if view.game_issues:
        blocks.append(Table(["Line", "Game-reported issue", "Stop index", "Cargo index (base unverified)"],
                            [[i.line, i.type, i.stop_index, i.cargo_index] for i in view.game_issues[:25]]))
    else:
        blocks.append(Paragraph("No game-reported VehicleUseless / NoVehicleToLoadCargo / LineCargoConfig issues in the latest snapshot."))

    cols = ["Line", "Vehicles", "Models", "Per-vehicle capacity (median)", "Load across samples: median (range)", "Line rolling profit"]
    align = ["left", "right", "left", "right", "right", "right"]

    def row(f) -> list[Any]:
        return [f.line, f.vehicles, "; ".join(f.models),
                None if f.capacity_median is None else round(f.capacity_median),
                f"{f.load_median * 100:.0f}% ({f.load_min * 100:.0f}-{f.load_max * 100:.0f}%, n={f.load_samples})",
                _money(f.line_profit)]

    blocks.append(Heading(3, "Sustained High Load (Possible Undersizing)"))
    if view.high_load:
        blocks.append(Table(cols, [row(f) for f in view.high_load[:12]], align))
        blocks.append(Paragraph(f"{len(view.high_load)} lines ({thresholds.underused_min_vehicles}+ vehicles) at or above {thresholds.overloaded_load:.0%} median sampled load; top {min(12, len(view.high_load))} shown."))
    else:
        blocks.append(Paragraph(f"No multi-vehicle line has median sampled load >= {thresholds.overloaded_load:.0%} across at least {MIN_LOAD_SAMPLES} samples."))
    blocks.append(Heading(3, "Sustained Low Load (Possible Oversizing)"))
    if view.low_load:
        blocks.append(Table(cols, [row(f) for f in view.low_load[:12]], align))
        blocks.append(Paragraph(f"{len(view.low_load)} lines ({thresholds.underused_min_vehicles}+ vehicles) at or below {thresholds.underused_load:.0%} median sampled load; top {min(12, len(view.low_load))} shown."))
    else:
        blocks.append(Paragraph(f"No multi-vehicle line has median sampled load <= {thresholds.underused_load:.0%} across at least {MIN_LOAD_SAMPLES} samples."))
    first, last = (view.load_samples[0].date, view.load_samples[-1].date) if view.load_samples else ("-", "-")
    blocks.append(Note("Evidence Limit", f"Load is instantaneous occupancy over a line's full capacity; here the median of up to "
                                         f"{LOAD_HISTORY} snapshots ({first} to {last}) is used, and those snapshots cluster in time. "
                                         "One-way freight lines carry cargo in only one direction, so low load can be structural "
                                         "[INFERENCE]; a high load does not by itself prove demand exceeds capacity. Hypotheses to "
                                         "test, not conclusions: add vehicles or test a larger model on high-load lines; test fewer "
                                         "vehicles or a smaller model on low-load lines."))
    return blocks


_UNASSESSED = {
    "multi-part-consist": "multi-part consist - locomotive/wagon replacement depends on the whole consist and is not assessed.",
    "no-load-configuration": "no stored load configuration, so the cargo to match is unknown.",
    "multiple-cargos": "vehicles are configured for several cargos at once; single-cargo candidates are not proposed.",
}


def _swap_section(view: VehicleRoiView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Suggested Swaps (Hypotheses to Test)")]
    if view.swap_status == "no-weak-groups":
        return blocks + [Paragraph(f"No model group with at least {MIN_SAMPLE} mature vehicles is loss-making (median < 0) or has a "
                                   "loss share of 40% or more, so no swap hypothesis is generated.")]
    catalog = view.catalog
    if view.swap_status == "no-catalog" or catalog is None:
        return blocks + [Note("Insufficient Data", "No stored catalog snapshot: replacement candidates cannot be listed. The catalog is "
                                                    "collected only in start/request snapshots.")]
    blocks.append(Paragraph(
        f"Weak groups: at least {MIN_SAMPLE} mature vehicles and either median profit below 0 or a loss share of 40% or more. "
        f"Catalog sampled {catalog.sample.date} (production status judged against game year "
        f"{view.game_year if view.game_year is not None else 'unknown'}). "
        "Candidates are catalog models of the same carrier, in production, that list capacity for the vehicle's configured cargo, "
        "ordered by capacity per raw running cost. Ratios compare each candidate with the current model in the same raw units; no "
        "unit conversion, payback or profit forecast is made."
    ))
    evidence_rows: list[list[Any]] = []
    rows: list[list[Any]] = []
    notes: list[str] = []
    for g in view.weak_groups:
        if g.status in _UNASSESSED:
            notes.append(f"{g.key}: {_UNASSESSED[g.status]}")
            continue
        s = g.stats
        evidence_rows.append([g.key, g.cargo, s.mature, _money(s.mean), _money(s.median), _fmt_pct(s.loss_share),
                              None if g.lines_median_load is None else f"{g.lines_median_load * 100:.0f}%",
                              _plain_number(g.current_capacity), g.current_lifespan,
                              "In stored catalog" if g.in_stored_catalog else "Not in stored catalog (retired or absent)"])
        if not g.candidates:
            rows.append([g.key, "No in-production catalog model lists capacity for this cargo", None, None, None, None, None, None, None])
            continue
        for c in g.candidates:
            if not c.in_fleet:
                own_cell = "Not in fleet"
            elif c.own_mature:
                own_cell = f"n={c.own_mature}, mean {_money(c.own_mean):,}" + (" (small sample)" if c.own_mature < MIN_SAMPLE else "")
            else:
                own_cell = f"{c.own_young} young only"
            rows.append([g.key, c.name, f"{c.capacity:g}", _ratio_cell(c.capacity_ratio), _ratio_cell(c.top_speed_ratio),
                         _ratio_cell(c.price_ratio), _ratio_cell(c.running_cost_ratio), c.lifespan, own_cell])
    if evidence_rows:
        blocks.append(Heading(3, "Evidence: Weak Groups (Observations)"))
        blocks.append(Table(["Weak group", "Configured cargo", "Mature n", "Mean profit/vehicle", "Median", "Loss-making",
                             "Median load of its lines (sampled)", "Current capacity (median)", "Current lifespan (raw)", "Catalog match"],
                            evidence_rows, ["left", "left", "right", "right", "right", "right", "right", "right", "right", "left"]))
    if rows:
        blocks.append(Heading(3, "Candidates (Hypotheses)"))
        blocks.append(Table(["Weak group", "Candidate model", "Candidate capacity", "Capacity ratio", "Top speed ratio", "Price ratio",
                             "Running cost ratio", "Candidate lifespan (raw)", "Candidate in own fleet (mature, observed)"],
                            rows, ["left", "left", "right", "right", "right", "right", "right", "right", "left"]))
        blocks.append(Paragraph("Ratios are candidate / current (x1.00 = equal). Compare 'Candidate lifespan (raw)' with 'Current lifespan "
                                "(raw)' in the evidence table; lifespan units are unverified, so no age/expiry claim is made."))
    for n in notes:
        blocks.append(Paragraph(n))
    unit_note = ("Top speed is labelled m/s by verifiedUnits." if catalog.top_speed_verified else "Top speed unit unverified.") + " " + (
        "Running costs are labelled currency/year by verifiedUnits." if catalog.running_cost_verified else "Running-cost unit unverified.")
    blocks.append(Note("What Is Missing", "These are hypotheses, not recommendations. Not known from the data: route length and terrain "
                                          "per line, whether a candidate suits the road/track/airport/dock in use, loading time, "
                                          "the candidate's real earnings, the vehicle price factor, resale value, and whether rolling "
                                          "profit already nets out running costs. Ratios of 'x1.00' mean equal raw values; '-' means "
                                          "a value (current model not in the stored catalog, or field absent) is unknown. " + unit_note +
                                          " Manual test in game: trial one candidate on one weak line and compare after the rolling "
                                          "window has advanced."))
    return blocks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(view: VehicleRoiView, *, context: EvaluationContext) -> ReportDocument:
    mature = view.mature_years
    header = _base_header(context.snapshot, view.coverage.eligible)
    header.insert(3, ("Sample Coverage", f"{view.first_sample.date} to {view.last_sample.date}; point-in-time snapshots, not continuous telemetry"))
    header.insert(4, ("Catalog Sample", view.catalog.sample.date if view.catalog else "None stored"))
    header.append(("Age Scale", f"GAME-YEAR; game-calendar-v1; anchor hash {view.time_basis_anchor_hash}; bracketed estimates only"))
    header.append(("Vehicle Scope", f"{len(view.observations)} vehicles analysed from the latest snapshot; mature = age >= {mature:g} game year"))

    blocks: list[Any] = []
    blocks += _summary(view, context)
    blocks += _carrier_section(view)
    blocks += _model_section(view)
    blocks += _cargo_section(view)
    blocks += _age_section(view)
    blocks += _head_to_head(view)
    blocks += _trend_section(view)
    blocks += _fit_section(view, context)
    blocks += _swap_section(view)
    blocks.append(Note("Method And Limits",
                       "profitYear is a rolling game-year figure per vehicle; per-vehicle values are only combined across distinct "
                       f"vehicles within one snapshot. Vehicles younger than {mature:g} game year have partial windows and are kept out of "
                       "rankings. Vehicle profit mixes the vehicle's quality with the route it runs; use the same-line comparison "
                       "to separate them. transportedYear is not used (accounting unverified). Names come from the game and are "
                       "shown as stored."))
    return ReportDocument("vehicle-roi", "Vehicle ROI Report", header, blocks)
