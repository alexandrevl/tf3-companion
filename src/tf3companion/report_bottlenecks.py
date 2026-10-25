"""Network health / bottleneck report: presentation over the typed `BottlenecksView`.

The view owns observation, persistence, severity, stock rises, occupancy, grouping, health counts and
collector coverage; this module only chooses headings, wording, display caps (with omission text) and
number formatting. Entity names come from the game and are escaped by the renderers.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .analysis_views.bottlenecks import BottleneckItem, BottlenecksView
from .analysis_views.models import EvaluationContext
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

TABLE_CAP = 20
CODE_CAP = 8  # non-HIGH rows per finding family in a priority table, so one family cannot crowd out the rest

STATUS_ORDER = ("persistent", "intermittent", "new", "resolved")
STATUS_TITLES = {
    "persistent": "Persistent (present in the latest sample and in the last {streak}+ consecutive samples)",
    "intermittent": "Intermittent (present in the latest sample, but not for {streak}+ consecutive samples)",
    "new": "New or not yet classifiable (first seen recently, or too little history)",
    "resolved": "Seen earlier, not present in the latest sample",
}

AREA = {
    "vehicle_no_path": "Vehicles",
    "vehicle_user_stopped": "Vehicles",
    "vehicle_idle_depot": "Fleet / depots",
    "long_terminal_wait": "Vehicles",
    "line_config_issue": "Lines",
    "line_orphan": "Lines",
    "line_no_vehicles": "Lines",
    "line_no_stops": "Lines",
    "line_load_high": "Lines",
    "line_load_low": "Lines",
    "stock_output_full": "Stocks",
    "warehouse_full": "Stocks",
    "station_stock_full": "Stocks",
    "industry_closing": "Industries",
    "station_pileup": "Stations",
}

DATA_SOURCE_LABELS = {
    "lines_vehicles": "Lines and vehicles",
    "stocks": "Stocks (stations/industries/warehouses)",
    "depots": "Depots",
    "vehicle_depot_id": "Vehicle depot id",
}

AFFECTS_TEXT = {
    "depot": "depot names/positions (idle-capital attribution may show 'name not available'); depots that failed to read may be missing from depot listings; vehicle depot ids are unaffected",
    "stock": "stock fill and cargo-destruction findings",
    "line": "line occupancy, issues and profit",
    "vehicle": "vehicle state and no-path/idle findings",
    "industr": "industry flows and closing/served classification",
    "station": "station data",
    "town": "town data",
}


def _seen(it: BottleneckItem) -> str:
    return f"{it.observations} of {it.eligible}" + (f" (streak {it.streak})" if it.in_latest else "")


def _cargo_text(cargos: list[str]) -> str:
    if len(cargos) > 5:
        return f"{len(cargos)} cargo types (general-purpose stock)"
    return ", ".join(cargos) or "-"


def _money(v: Any) -> str:
    return "-" if v is None else f"{v:,}"


def _describe(it: BottleneckItem, policy) -> tuple[str, str, str]:
    """(evidence, what it may mean, what to check manually) for the latest flagged reading."""
    ev, c = it.evidence, it.code
    if c == "vehicle_no_path":
        return (
            f"Vehicle cannot find a path (line: {ev.get('line') or 'none'}, state {ev.get('state')}).",
            "Route is broken or the vehicle is stranded; it earns nothing and may block others.",
            "Open the vehicle's line and look for disconnected track/road, removed stops, one-way or signalling gaps.",
        )
    if c == "vehicle_user_stopped":
        return (
            f"Vehicle manually stopped (line: {ev.get('line') or 'none'}); recorded value {_money(ev.get('value'))}.",
            "Possibly deliberate; otherwise a forgotten stopped vehicle that still incurs costs.",
            "Confirm in the game whether the stop is intentional; restart or sell if not.",
        )
    if c == "vehicle_idle_depot":
        return (
            f"{ev['count']} vehicle(s) with no line inside this depot (longest {ev['days']} days; "
            f"{', '.join(ev['carriers']) or '-'}); recorded value {_money(ev['value'])}; e.g. {'; '.join(ev['examples'])}.",
            "Capital tied up (recent purchase awaiting assignment, or abandoned reserve vehicles).",
            "Assign them to a line or sell them if the reserve is not intended.",
        )
    if c == "long_terminal_wait":
        return (
            f"{ev['count']} of {ev['vehicles']} vehicles with daysAtTerminal >= {policy.long_wait_days} (max {ev['max']}).",
            "Queue or slow loading at a stop; may also be a normal full-load wait. Counter semantics are unverified.",
            "Inspect the line's stops: loading mode, waiting times, terminal count, whether cargo is available.",
        )
    if c == "line_config_issue":
        where = (
            f" at stop {ev.get('stopIndex')}" + (f" ({ev['stopName']})" if ev.get("stopName") else "")
            if isinstance(ev.get("stopIndex"), int) and ev.get("stopIndex", -1) >= 0
            else " (no specific stop)"
        )
        return (
            f"Game-reported issue {ev.get('type')}{where}, cargo {ev.get('cargo') or '-'}.",
            "The game says this line cannot load/unload or configure that cargo as set.",
            "Open the line, review stop cargo filters and compatible vehicles for that cargo.",
        )
    if c in ("line_orphan", "line_no_vehicles", "line_no_stops"):
        return (
            f"{ev.get('vehicles')} vehicles and {ev.get('stops')} stops.",
            "Incomplete or abandoned line.",
            "Complete it (vehicles and at least two stops) or remove it.",
        )
    if c == "line_load_high":
        return (
            f"Occupancy {_fmt_pct(ev['load'])} with {ev['vehicles']} vehicles.",
            "Vehicles often full at sampling time; may indicate unmet demand (not proven).",
            "Check station queues/waiting cargo before adding vehicles or capacity.",
        )
    if c == "line_load_low":
        return (
            f"Occupancy {_fmt_pct(ev['load'])} with {ev['vehicles']} vehicles; rolling profit {_money(ev.get('profitYear'))}.",
            "Often nearly empty at sampling time; possibly too many vehicles or weak demand.",
            "Check demand at the stops; consider fewer vehicles or merging lines.",
        )
    if c == "stock_output_full":
        ratio = (
            f"; shipped/produced {_money(ev['shipped'])}/{_money(ev['produced'])}"
            if ev.get("produced") is not None
            else ""
        )
        return (
            f"{ev['cargo']}: {ev['count']:,}/{ev['capacity']:,} ({_fmt_pct(ev['fill'])}){ratio}.",
            "Output stock near/full on an industry with recorded shipping: collection may be insufficient. At capacity, excess production is destroyed (documented mechanic); actual destruction is not measured.",
            "Inspect the serving line(s): vehicle count, capacity, frequency, loading time, queues at the pick-up stop.",
        )
    if c == "warehouse_full":
        cargos = _cargo_text(ev.get("cargos") or [])
        return (
            f"{ev['full']} of {ev['total']} stocks full ({cargos}).",
            "Full warehouse stocks may stop unloading deliveries [INFERENCE]; also tied-up cargo.",
            "Check which lines deliver to or collect from this warehouse and whether collection exists.",
        )
    if c == "station_stock_full":
        return (
            f"{ev['cargo']}: {ev['count']:,}/{ev['capacity']:,}.",
            "Station stock full.",
            "Check lines collecting that cargo at this station.",
        )
    if c == "industry_closing":
        return (
            "Marked for closure"
            + (
                "; your network ships from/delivers to it."
                if ev.get("served")
                else "; no recorded shipments or deliveries."
            ),
            "Dependent lines will lose their cargo source or sink.",
            "If lines depend on it, plan a replacement source or accept closure.",
        )
    if c == "station_pileup":
        return (
            f"{ev['waiting']} vehicles at the stop at once; {ev['lines']} line(s) call here ({'; '.join(ev['lineNames'])}).",
            "Possible congestion/queue at the station (vehicles at a terminal may also just be loading).",
            "Watch the station: add terminals/platforms or spread lines over alternative stops if a queue shows.",
        )
    return ("", "", "")


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def _priority_blocks(view: BottlenecksView, policy) -> list[Any]:
    s = view.summary
    blocks: list[Any] = [Heading(2, "Prioritized Findings")]
    blocks.append(
        Paragraph(
            f"Active now: {s.high} high, {s.medium} medium, {s.low} low severity "
            f"({s.persistent} persistent, {s.intermittent} intermittent, {s.new} new/unclassified). "
            f"{s.resolved} further finding(s) were seen earlier in the window but are absent from the latest sample."
        )
    )
    blocks.append(
        Note(
            "How to read persistence",
            f"'Seen N of M' counts samples in the persistence window in which the entity existed and the condition held "
            f"(M excludes samples where the entity or data source did not yet exist); streak is the number of consecutive "
            f"latest samples. Persistent needs a streak of {policy.persistence_streak}+. Samples are irregularly spaced points "
            f"in time, not continuous telemetry; use the listed calendar dates rather than treating sample counts as elapsed months. Severity is a heuristic ranking, not a measured loss: game-reported issues and no-path vehicles are HIGH; "
            f"a full output stock on a served industry is HIGH once persistent (full output stock destroys excess production, "
            f"per mechanics) and MEDIUM otherwise; occupancy extremes are MEDIUM only for crowded or loss-making lines.",
        )
    )
    for st in STATUS_ORDER:
        group = [i for i in view.items if i.status == st]
        title = STATUS_TITLES[st].format(streak=policy.persistence_streak)
        blocks.append(Heading(3, f"{title} - {len(group)} finding(s)"))
        if not group:
            blocks.append(Paragraph("None."))
            continue
        shown: list[BottleneckItem] = []
        omitted: Counter = Counter()
        taken: Counter = Counter()
        for it in group:
            if it.severity == "high" or taken[it.code] < CODE_CAP:
                taken[it.code] += 1
                shown.append(it)
            else:
                omitted[it.code] += 1
        rows = []
        for it in shown:
            evidence, meaning, check = _describe(it, policy)
            rows.append(
                [
                    it.severity.upper(),
                    AREA.get(it.code, it.code),
                    it.name,
                    evidence,
                    _seen(it),
                    f"{it.first_label}" if st != "resolved" else f"{it.first_label} - {it.last_label}",
                    meaning,
                    check,
                ]
            )
        cols = [
            "Severity",
            "Area",
            "Entity",
            "Evidence (latest flagged sample)",
            "Seen (N of M samples)",
            "First seen" if st != "resolved" else "Seen between",
            "What it may mean",
            "Check in game (manual)",
        ]
        blocks.append(Table(cols, rows))
        if omitted:
            blocks.append(
                Paragraph(
                    "Not shown (lower-ranked within their family; see the detail sections): "
                    + "; ".join(f"{n} x {AREA.get(c, c)} / {c}" for c, n in sorted(omitted.items()))
                    + "."
                )
            )
    return blocks


def _stock_blocks(view: BottlenecksView, policy, context: EvaluationContext) -> list[Any]:
    stocks = view.stocks
    blocks: list[Any] = [Heading(2, "Stocks: Cargo Destruction Risk")]
    if view.rising_interval_empty:
        blocks.append(Note("Effective criteria", "No not-yet-full interval under effective criteria."))
    if not stocks.latest_has_stocks:
        blocks.append(
            Note(
                "Insufficient data",
                "The latest sample has no stock data (mod/snapshot predates stock collection); "
                "no stock conclusion is possible.",
            )
        )
        return blocks
    blocks.append(
        Paragraph(
            f"Stock data exists in {stocks.samples_with_stocks} of {view.samples} samples (first: {stocks.first_with_stocks.date}). "
            "Earlier samples are unknown, not 'no problem'. Industry rows count only output stocks whose cargo matches a "
            "recorded industry output; 'served' means that output has annual shipments > 0."
        )
    )
    full_items = [i for i in view.items if i.code == "stock_output_full"]
    blocks.append(Heading(3, "Served industries with a full output stock"))
    if full_items:
        rows = []
        for it in full_items[:TABLE_CAP]:
            ev = it.evidence
            rows.append(
                [
                    it.name,
                    ev["cargo"],
                    f"{ev['count']:,}/{ev['capacity']:,}",
                    _seen(it),
                    it.first_label,
                    ev.get("produced"),
                    ev.get("shipped"),
                    _fmt_pct(ev.get("shippedRatio")),
                    it.status,
                ]
            )
        blocks.append(
            Table(
                [
                    "Industry",
                    "Cargo",
                    "Stock (latest flagged)",
                    "Full in N of M samples",
                    "First seen full",
                    "Produced (annual counter)",
                    "Shipped (annual counter)",
                    "Shipped/Produced",
                    "Status",
                ],
                rows,
                ["left", "left", "right", "left", "left", "right", "right", "right", "left"],
            )
        )
        if len(full_items) > TABLE_CAP:
            blocks.append(Paragraph(f"{len(full_items) - TABLE_CAP} more omitted."))
        blocks.append(
            Note(
                "Reading the counters",
                "Annual counters are rolling-year figures with unverified accounting; the ratio only indicates "
                "whether collection keeps up relative to production, it is not a destruction measurement.",
            )
        )
    else:
        blocks.append(
            Paragraph(
                "No served industry output stock is at or above "
                f"{context.thresholds.full_stock_ratio:.0%} in the window."
            )
        )

    wh = [i for i in view.items if i.code == "warehouse_full"]
    blocks.append(Heading(3, "Warehouses with full stocks"))
    if wh:
        blocks.append(
            Table(
                [
                    "Warehouse",
                    "Full stocks (latest flagged)",
                    "Cargos",
                    "Seen with a full stock (N of M)",
                    "First seen",
                    "Status",
                ],
                [
                    [
                        i.name,
                        f"{i.evidence['full']} of {i.evidence['total']}",
                        _cargo_text(i.evidence["cargos"]),
                        _seen(i),
                        i.first_label,
                        i.status,
                    ]
                    for i in wh[:TABLE_CAP]
                ],
            )
        )
    else:
        blocks.append(Paragraph("No warehouse stock at or above the full threshold."))

    blocks.append(Heading(3, "Rising stocks that are not yet full"))
    if view.stock_rises:
        rows = [
            [
                r.name,
                r.kind.title(),
                ", ".join(r.cargo_names),
                _fmt_pct(r.fill),
                r.count_start,
                r.count_latest,
                f"+{r.slope_per_sample:.1f}",
                round(r.samples_to_full, 1),
            ]
            for r in view.stock_rises[:TABLE_CAP]
        ]
        blocks.append(
            Table(
                [
                    "Stock owner",
                    "Kind",
                    "Cargo",
                    "Fill (latest)",
                    "Count (window start)",
                    "Count (latest)",
                    "Units per sample (linear)",
                    "Samples to full at this rate",
                ],
                rows,
                ["left", "left", "left", "right", "right", "right", "right", "right"],
            )
        )
        blocks.append(
            Note(
                "Inference",
                "Samples-to-full is a linear extrapolation over the last up to 6 samples; "
                "stocks do not necessarily rise linearly.",
            )
        )
    else:
        blocks.append(
            Paragraph(
                f"No stock at or above {policy.rising_stock_min_fill:.0%} and below the full threshold is rising by {policy.rising_stock_min_slope:.0%} of capacity per sample or more."
            )
        )

    blocks.append(Heading(3, "Near/full output stocks with zero recorded shipments"))
    blocks.append(
        Paragraph(
            f"{len(stocks.unserved)} industry output stock(s) are near/full with recorded annual shipments equal to zero in the latest sample. "
            "These are possible production opportunities, not proven network bottlenecks. A new or interrupted service may "
            "also have zero annual shipments; check connections before concluding they are unserved."
        )
    )
    return blocks


def _load_blocks(view: BottlenecksView, policy, context: EvaluationContext) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Line Occupancy Persistence")]
    if view.insufficient_history:
        blocks.append(
            Note(
                "Insufficient data",
                f"Persistence needs at least {policy.persistence_streak} samples; only {view.samples} available.",
            )
        )
        return blocks
    blocks.append(
        Paragraph(
            f"Lines whose instantaneous occupancy was >= {context.thresholds.overloaded_load:.0%} (or <= {context.thresholds.underused_load:.0%} with "
            f"{context.thresholds.underused_min_vehicles}+ vehicles) in at least {policy.persistence_streak} samples and {policy.noisy_min_share:.0%} of the "
            "samples where occupancy was measurable. Single readings that did not recur are deliberately not listed."
        )
    )
    cap = TABLE_CAP * 2
    rows = [
        [
            o.name,
            "Often full" if o.pattern == "high" else "Often nearly empty",
            f"{o.observations} of {o.eligible}",
            _fmt_pct(o.mean),
            _fmt_pct(o.minimum),
            _fmt_pct(o.maximum),
            _fmt_pct(o.latest),
            o.vehicles,
            o.profit_year,
            o.status,
        ]
        for o in view.occupancy[:cap]
    ]
    if rows:
        blocks.append(
            Table(
                [
                    "Line",
                    "Pattern",
                    "Flagged (N of M)",
                    "Sample mean",
                    "Min",
                    "Max",
                    "Latest",
                    "Vehicles",
                    "Rolling annual profit (latest)",
                    "Status",
                ],
                rows,
                ["left", "left", "left", "right", "right", "right", "right", "right", "right", "left"],
            )
        )
        blocks.append(
            Note(
                "Limits",
                "Sample mean is an unweighted average of instants, not a time average. High occupancy "
                "alone does not prove unmet demand; low occupancy alone does not prove no demand.",
            )
        )
        if len(view.occupancy) > cap:
            blocks.append(Paragraph(f"{len(view.occupancy) - cap} lower-ranked occupancy patterns omitted."))
    else:
        blocks.append(Paragraph("No line shows a recurring extreme occupancy in the window."))
    return blocks


def _station_depot_blocks(view: BottlenecksView, policy) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Station Pile-ups and Depots")]
    piles = view.station_groups
    if piles:
        blocks.append(
            Table(
                [
                    "Station",
                    "Recurring (N of M)",
                    "Vehicles waiting (latest flagged)",
                    "Lines calling",
                    "Example lines",
                    "Status",
                ],
                [
                    [g.name, f"{g.observations} of {g.eligible}", g.waiting, g.lines, "; ".join(g.line_names), g.status]
                    for g in piles[:TABLE_CAP]
                ],
            )
        )
        blocks.append(
            Note(
                "Limits",
                f"{policy.pileup_min}+ vehicles AT_TERMINAL at one stop in the same sample. The mod records no "
                "waiting-cargo or passenger counts per station, so starved or overcrowded stations cannot be "
                "measured directly; this is only a vehicle-side proxy.",
            )
        )
    else:
        blocks.append(
            Paragraph(f"No station had {policy.pileup_min}+ vehicles waiting simultaneously in a recurring way.")
        )
    blocks.append(Heading(3, "Vehicles inside depots (latest sample)"))
    if view.depot_groups:
        rows = [
            [g.name or f"Depot #{g.depot} (name not available)", g.vehicles, g.without_line, g.value_without_line]
            for g in view.depot_groups
        ]
        blocks.append(
            Table(
                ["Depot", "Vehicles inside", "Of which without a line", "Recorded value of those"],
                rows,
                ["left", "right", "right", "right"],
            )
        )
    else:
        blocks.append(Paragraph("No vehicle was inside a depot in the latest sample."))
    return blocks


def _trend_blocks(view: BottlenecksView, policy, context: EvaluationContext) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Network Health Over Time")]
    if len(view.health) < 2:
        blocks.append(Note("Insufficient data", "At least two samples are needed for a trend."))
        return blocks
    if view.bucketed:
        blocks.append(
            Note(
                "Sampling",
                "History is long; the last sample of each game quarter is shown (most recent "
                f"{len(view.health)} quarters).",
            )
        )
    groups = [
        (
            "Hard problems per sample",
            [
                ("Vehicles without path", "no_path"),
                ("Vehicles stopped by player", "user_stopped"),
                ("Lines with issues or incomplete", "line_issues"),
                ("Vehicles idle in depots", "idle_depot"),
            ],
            False,
        ),
        (
            "Instant pressure readings",
            [
                (f"Lines at {context.thresholds.overloaded_load:.0%}+ occupancy", "load_high"),
                (f"Lines at {context.thresholds.underused_load:.0%} or less occupancy", "load_low"),
                (f"Stops with {policy.pileup_min}+ vehicles waiting", "pileup"),
                ("Lines with long terminal waits", "long_wait"),
            ],
            False,
        ),
        (
            "Full stocks per sample",
            [("Served industry outputs full", "stock_output_full"), ("Warehouses with a full stock", "warehouse_full")],
            True,
        ),
    ]
    for title, series_def, needs_stocks in groups:
        pts = [p for p in view.health if p.stocks_known] if needs_stocks else list(view.health)
        if len(pts) < 2:
            if needs_stocks:
                blocks.append(Paragraph("Stock trend unavailable: fewer than two samples contain stock data."))
            continue
        series = [(label, [p.counts[key] for p in pts]) for label, key in series_def]
        series = [(label, vals) for label, vals in series if any(vals)]
        if not series:
            blocks.append(Paragraph(f"{title}: all counts are zero across {len(pts)} samples."))
            continue
        blocks.append(Heading(3, title))
        cat = [p.date_label for p in pts]
        blocks.append(Chart("line", title, cat, [(label, [float(v) for v in vals]) for label, vals in series]))
        blocks.append(
            Table(
                ["Sample date"] + [label for label, _ in series],
                [[cat[i]] + [vals[i] for _, vals in series] for i in range(len(pts))],
                ["left"] + ["right"] * len(series),
            )
        )
    return blocks


def _data_blocks(view: BottlenecksView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Data Coverage and Collection Errors")]
    blocks.append(
        Table(
            ["Data source", "Samples with data", "First sample with data"],
            [
                [DATA_SOURCE_LABELS[c.source], f"{c.samples} of {c.of}", c.first.date if c.first else "never"]
                for c in view.data_sources
            ],
        )
    )
    if view.error_families:
        rows = [
            [
                e.family,
                e.message,
                f"{e.samples} of {e.of}",
                e.latest_occurrences,
                AFFECTS_TEXT.get(e.affects, "unknown"),
            ]
            for e in view.error_families
        ]
        blocks.append(
            Table(
                ["Collector", "Message", "Samples with error", "Occurrences in latest sample", "Conclusions affected"],
                rows,
            )
        )
        blocks.append(
            Note(
                "Effect on this report",
                "Collector errors mean the affected entities are absent or partial in the data; their "
                "absence from a finding list is not evidence that they are healthy.",
            )
        )
    else:
        blocks.append(Paragraph("No collection errors reported in any sample of the window."))
    if view.terminal_resets:
        blocks.append(
            Note(
                "daysAtTerminal discontinuity",
                "Vehicles with daysAtTerminal >= 5 jump between zero and many across consecutive samples ("
                + "; ".join(f"{r.from_sample.date} to {r.to_sample.date}" for r in view.terminal_resets[:3])
                + "). The counter's semantics are unverified and may reset "
                "(for example on save reload), so long-wait findings that 'resolve' at such a boundary may be artifacts rather than real fixes.",
            )
        )
    return blocks


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def build(view: BottlenecksView, *, context: EvaluationContext) -> ReportDocument:
    policy = context.policies["bottlenecks"]
    cur = context.snapshot
    header = _base_header(cur, view.samples)
    header[1] = ("Latest Sample Date", cur.date_label)
    header[3] = (
        "Collection Errors",
        f"{view.latest_errors} in the latest sample (details under Data Coverage)"
        if view.latest_errors
        else "None reported",
    )
    header.insert(
        2,
        (
            "Persistence Window",
            f"{view.window_start.date} to {view.window_end.date} ({view.samples} samples after merging "
            f"near-simultaneous ones; {view.merged_available} available, up to {view.coverage.limits['persistenceWindow']} used)",
        ),
    )
    header.insert(
        3,
        (
            "Thresholds",
            f"stock full >= {context.thresholds.full_stock_ratio:.0%}; persistent = streak {policy.persistence_streak}+; "
            f"pile-up {policy.pileup_min}+ vehicles; long wait daysAtTerminal >= {policy.long_wait_days} (unverified unit); "
            f"occupancy >= {context.thresholds.overloaded_load:.0%} / <= {context.thresholds.underused_load:.0%}",
        ),
    )
    header.append(
        (
            "History Read Limit",
            f"Up to {view.coverage.limits['readLimit']} stored snapshots at or before the latest timeline point; "
            "older history beyond that is not evaluated.",
        )
    )

    blocks: list[Any] = []
    if view.insufficient_history:
        blocks.append(
            Note(
                "Limited history",
                f"Only {view.samples} sample(s) available: persistence cannot be judged, "
                "so findings are listed as new/unclassified and recurring-reading checks are suppressed.",
            )
        )
    blocks += _priority_blocks(view, policy)
    blocks += _stock_blocks(view, policy, context)
    blocks += _load_blocks(view, policy, context)
    blocks += _station_depot_blocks(view, policy)
    blocks += _trend_blocks(view, policy, context)
    blocks += _data_blocks(view)
    blocks.append(
        Note(
            "What this report cannot show",
            "Per-station waiting cargo/passengers, actual destroyed-item counts and vehicle queue order are not collected. "
            "Findings are observations at sampled instants plus inferences; every in-game change is yours to make and "
            "the 'check in game' column describes what to inspect, not a prescribed fix.",
        )
    )
    return ReportDocument("bottlenecks", "Network Health and Bottleneck Report", header, blocks)
