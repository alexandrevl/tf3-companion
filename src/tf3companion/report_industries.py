"""Industries evolution report: how production, service, levels, closures and chains changed.

Presentation over `analysis_views.industries.IndustriesView`: headings, prose, number formatting,
display caps with omission notes and charts. Every number, class, rank and event comes from the view.

Complements the `cargo` report (unshipped production + nearest consumers) by focusing on
change over snapshots and comparison between industries, cargos and types.

Honesty rules applied here:
- producedYear/shippedYear/consumedYear are rolling annual figures per snapshot. They are
  compared snapshot to snapshot, never summed across snapshots.
- Service ratio = shipped / produced; ratios above 100% can reflect stock draw-down.
- Calendar time comes from meta.date, not from meta.yearDuration (which is not a calendar year).
- Station-to-industry links are inferred from an exact name match; the snapshot has no
  station position or catchment data.
"""

from __future__ import annotations

from typing import Any, Callable

from .analysis_views.industries import (
    STATUS_IDLE,
    STATUS_INPUT_LIMITED,
    STATUS_OUTPUT_FULL,
    STATUS_RUNNING,
    ClosureRemaining,
    IndustriesView,
    LifecycleEvent,
    Span,
)
from .analysis_views.models import EvaluationContext
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _fmt_pct

EVENT_CAP = 30

EVENT_LABELS = {
    "closure-at-first-sample": "Closure already scheduled at first sample",
    "new-industry": "New industry",
    "closure-scheduled": "Closure scheduled",
    "closure-cancelled": "Closure cancelled",
    "closed-as-scheduled": "Closed (as scheduled)",
    "closed-flagged": "Closed (flagged)",
    "disappeared": "Disappeared (never seen flagged)",
}
STATUS_LABELS = {
    STATUS_IDLE: "Idle (no input consumed)",
    STATUS_OUTPUT_FULL: "Output stock full, output below capacity",
    STATUS_INPUT_LIMITED: "Input-limited",
    STATUS_RUNNING: "Running",
}
STOCK_GROUP_LABELS = {
    "output-shipped": "Output stocks, cargo shipped",
    "output-not-shipped": "Output stocks, cargo not shipped",
    "input": "Input stocks (consumers)",
    "warehouse": "Warehouses",
}
TIER_LABELS = {
    "idle-every-sample": "Idle at every sample (capacity, zero output, never shipped)",
    "producing-never-shipped": "Producing but never shipped in any sample",
    "shipped-at-least-once": "Shipped in at least one sample",
}
ROLE_LABELS = {"producer": "producer", "consumer": "consumer", "producer-consumer": "producer + consumer"}
TITLE = "Industries Evolution and Comparison Report"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _int(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def _pp(a: float | None, b: float | None) -> str:
    """Percentage-point change b - a."""
    if a is None or b is None:
        return "-"
    diff = (b - a) * 100
    return f"{'+' if diff > 0 else ''}{diff:.1f} pp"


def _arrow(a: Any, b: Any, fmt: Callable[[Any], str] = lambda v: "-" if v is None else f"{v:,}") -> str:
    return f"{fmt(a)} → {fmt(b)}"


def _signed(v: float | int | None) -> str:
    if v is None:
        return "-"
    n = int(round(v))
    return f"{'+' if n > 0 else ''}{n:,}"


def _cap(rows: list[list[Any]], limit: int) -> tuple[list[list[Any]], int]:
    return rows[:limit], max(0, len(rows) - limit)


def _omitted(n: int, noun: str = "rows") -> list[Any]:
    return [Note("Omitted", f"{n} more {noun} not shown.")] if n > 0 else []


def _pct_text(ratio: float) -> str:
    return f"{ratio * 100:g}%"


def _fmt_amount(v: float) -> str:
    return f"{int(round(v)):,}"


def _span_text(span: Span) -> str:
    if span.game_years is None or span.calendar_days is None:
        return f"Calendar coverage unavailable ({span.reason})"
    return f"{span.calendar_days:g} calendar days ({span.game_years:.3f} GAME-YEAR)"


def _remaining_text(remaining: ClosureRemaining) -> str:
    if remaining.status == "none":
        return "-"
    if remaining.status == "due":
        return "due now / overdue"
    if remaining.status == "unavailable":
        return f"unavailable ({remaining.reason}; raw target tick {remaining.target_tick})"
    return f"~{remaining.game_days:.0f} GAME-DAY (estimate)"


def _closure_text(event: LifecycleEvent) -> str:
    if event.industry.closure_tick:
        return f"closes in {_remaining_text(event.remaining)}"
    return "flagged in problems.closingIndustries without a timestamp"


def _event_detail(e: LifecycleEvent) -> str:
    ind = e.industry
    if e.code in ("closure-at-first-sample", "closure-scheduled"):
        return _closure_text(e)
    if e.code == "new-industry":
        return f"{ind.label}; level {ind.level}/{ind.max_level}; produces {_fmt_amount(ind.produced)}/yr at first sight"
    if e.code == "closure-cancelled":
        return f"produced {_fmt_amount(ind.produced)}/yr, shipped {_fmt_amount(ind.shipped)}/yr now"
    if e.code == "disappeared" or e.code.startswith("closed"):
        return (
            f"flagged for closure; last seen {e.last_seen}" if e.code != "disappeared" else f"last seen {e.last_seen}"
        )
    return ""


def _failed(view: IndustriesView, name: str) -> bool:
    return any(u.code == "section-uninterpretable" and u.subject == name for u in view.coverage.unavailable)


def _unavailable(title: str) -> list[Any]:
    return [Heading(2, title), Paragraph("Section unavailable: snapshot data could not be interpreted.")]


def _flows_text(flows) -> str:
    return "; ".join(f"{f.cargo_name} {_int(f.value)}/{_int(f.capacity)}" for f in flows)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _section_summary(view: IndustriesView, full: float) -> list[Any]:
    c = view.comparison
    fa, la, fc, lc = c.all_first, c.all_last, c.common_first, c.common_last

    def row(metric: str, a: Any, b: Any, change: str | None = None) -> list[Any]:
        return [
            metric,
            "-" if a is None else a,
            "-" if b is None else b,
            change
            if change is not None
            else (_signed(b - a) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "-"),
        ]

    rows = [
        row("Industries in snapshot (all)", fa.n, la.n),
        row("Industries present at both ends (comparison set)", c.common_count, c.common_count, "0"),
        row("Industries producing (comparison set)", fc.producing, lc.producing),
        row("Idle industries: capacity but zero output (comparison set)", fc.idle, lc.idle),
        row("Production, items/yr (comparison set)", _int(fc.produced), _int(lc.produced)),
        row("Shipped, items/yr (comparison set)", _int(fc.shipped), _int(lc.shipped)),
        ["Service ratio (comparison set)", _fmt_pct(fc.ratio), _fmt_pct(lc.ratio), _pp(fc.ratio, lc.ratio)],
        row("Industries with any shipments (comparison set)", fc.served, lc.served),
        row("Primary-industry levels, sum of level (comparison set)", fc.level, lc.level),
        row("Closures flagged (all)", fa.flagged, la.flagged),
        row(f"Full output stocks ≥{_pct_text(full)} (all)", c.full_outputs_first, c.full_outputs_last),
    ]
    blocks: list[Any] = [
        Heading(2, "Change Since First Sample"),
        Paragraph(
            f"Comparing {c.first.date} with {c.last.date} ({_span_text(view.span)}). The comparison set contains the "
            f"{c.common_count} industries present at both ends so that new or closed industries do not distort the "
            "totals; they are listed separately below."
        ),
        Table(
            ["Metric", f"First ({c.first.date})", f"Latest ({c.last.date})", "Change"],
            rows,
            ["left", "right", "right", "right"],
        ),
    ]
    bullets: list[str] = []
    if fc.produced or lc.produced:
        bullets.append(
            f"Observation: production in the comparison set went {_fmt_amount(fc.produced)} → "
            f"{_fmt_amount(lc.produced)} items/yr and shipments {_fmt_amount(fc.shipped)} → "
            f"{_fmt_amount(lc.shipped)} items/yr (service ratio {_fmt_pct(fc.ratio)} → {_fmt_pct(lc.ratio)})."
        )
    if c.new_count or c.vanished_count:
        bullets.append(
            f"Observation: {c.new_count} new and {c.vanished_count} vanished industries between the two samples."
        )
    if c.level_ups or c.level_downs:
        bullets.append(f"Observation: {c.level_ups} industries gained a level and {c.level_downs} lost one.")
    if c.closures_scheduled or c.closures_cancelled:
        bullets.append(
            "Observation: closure schedule changes after the first sample: "
            f"{c.closures_scheduled} newly scheduled, {c.closures_cancelled} cancelled."
        )
    blocks.extend(Paragraph(b) for b in bullets)
    return blocks


def _section_evolution(view: IndustriesView) -> list[Any]:
    picks = view.evolution
    rows, produced, shipped, cats = [], [], [], []
    ratio_rows, ratio_cats, ratio_vals = [], [], []
    for p in picks:
        st = p.stats
        rows.append(
            [
                p.sample.date,
                st.n,
                st.producing,
                st.idle,
                _int(st.produced),
                _int(st.shipped),
                _fmt_pct(st.ratio),
                st.served,
                f"{st.level}/{st.max_level}",
                st.flagged,
                "-" if p.full_outputs is None else p.full_outputs,
            ]
        )
        cats.append(p.sample.date)
        produced.append(float(st.produced))
        shipped.append(float(st.shipped))
        ratio_rows.append([p.sample.date, "-" if st.ratio is None else round(st.ratio * 100, 1)])
        if st.ratio is not None:  # an unknown ratio is not charted as zero
            ratio_cats.append(p.sample.date)
            ratio_vals.append(round(st.ratio * 100, 1))
    blocks: list[Any] = [
        Heading(2, "Evolution Over Time"),
        Paragraph(
            f"Showing {len(picks)} of {view.sample_count} snapshots ({picks[0].sample.date} to {picks[-1].sample.date}). "
            "Every row is one snapshot's rolling annual figures; rows are not additive. Level is Σ level/Σ maxLevel over "
            "industries that have levels (primary industries)."
        ),
        Table(
            [
                "Sample",
                "Industries",
                "Producing",
                "Idle",
                "Produced/yr",
                "Shipped/yr",
                "Service ratio",
                "Industries shipping",
                "Level (Σ/Σ max)",
                "Closures flagged",
                "Full output stocks",
            ],
            rows,
            ["left"] + ["right"] * 10,
        ),
    ]
    if len(picks) >= 2:
        blocks.extend(
            [
                Chart(
                    "line",
                    "Produced vs shipped, items per year (all industries)",
                    cats,
                    [("Produced", produced), ("Shipped", shipped)],
                ),
                Table(["Sample", "Service ratio (%)"], ratio_rows, ["left", "right"]),
            ]
        )
        if ratio_cats:
            blocks.append(
                Chart("line", "Service ratio (%), shipped / produced", ratio_cats, [("Service ratio %", ratio_vals)])
            )
    else:
        blocks.append(Note("Insufficient data", "Only one snapshot is available; trend charts need at least two."))
    return blocks


def _section_events(view: IndustriesView) -> list[Any]:
    events = view.events
    blocks: list[Any] = [Heading(2, "Industry Lifecycle: New, Closed, Scheduled and Cancelled Closures")]
    if not events:
        return blocks + [
            Paragraph("No industry appeared, disappeared or changed closure status between the available snapshots.")
        ]
    shown = events[-EVENT_CAP:]
    rows = [[e.sample.date, EVENT_LABELS[e.code], e.industry.name, e.industry.label, _event_detail(e)] for e in shown]
    blocks.append(Table(["Sample", "Event", "Industry", "Type", "Detail"], rows, ["left"] * 5))
    if len(events) > len(shown):
        blocks.append(
            Note("Omitted", f"{len(events) - len(shown)} older events not shown (most recent {EVENT_CAP} displayed).")
        )
    return blocks


def _section_levels(view: IndustriesView) -> list[Any]:
    lv = view.levels
    blocks: list[Any] = [Heading(2, "Level Upgrades and Production Movers")]
    if lv.level_changes:
        rows = [
            [
                c.name,
                c.label,
                _arrow(c.level_first, c.level_last),
                _arrow(c.max_level_first, c.max_level_last),
                _arrow(_int(c.produced_first), _int(c.produced_last)),
                _arrow(_int(c.shipped_first), _int(c.shipped_last)),
                "Yes" if c.served_first else "No",
            ]
            for c in lv.level_changes
        ]
        shown, omitted = _cap(rows, 20)
        blocks.extend(
            [
                Paragraph(
                    f"{len(lv.level_changes)} industries changed level or maximum level between the first and latest sample."
                ),
                Table(
                    ["Industry", "Type", "Level", "Max level", "Produced/yr", "Shipped/yr", "Shipping at first sample"],
                    shown,
                    ["left", "left", "right", "right", "right", "right", "center"],
                ),
                *_omitted(omitted, "industries"),
            ]
        )
    else:
        blocks.append(Paragraph("No industry changed level or maximum level between the first and latest sample."))

    if lv.rating_changes:
        blocks.extend(
            [
                Heading(3, "Production-rating changes (absolute change ≥0.05)"),
                Paragraph(
                    "productionRating is the raw engine measure, not instantaneous vehicle load. "
                    "Changes do not establish a cause or guarantee an upgrade."
                ),
                Table(
                    ["Industry", "Type", "Rating first", "Rating latest", "Produced/yr"],
                    [
                        [
                            r.name,
                            r.label,
                            round(r.rating_first, 3),
                            round(r.rating_last, 3),
                            _arrow(_int(r.produced_first), _int(r.produced_last)),
                        ]
                        for r in lv.rating_changes[:12]
                    ],
                    ["left", "left", "right", "right", "right"],
                ),
                *_omitted(max(0, len(lv.rating_changes) - 12), "rating changes"),
            ]
        )

    if lv.upgrade_groups:
        labels = {
            "shipping-at-first": "Shipping at first sample",
            "not-shipping-at-first": "Not shipping at first sample",
        }
        blocks.extend(
            [
                Table(
                    ["Primary industries (with levels)", "Industries", "Gained a level", "Share"],
                    [
                        [
                            labels[g.code],
                            g.industries,
                            g.gained_level,
                            _fmt_pct(g.gained_level / g.industries) if g.industries else None,
                        ]
                        for g in lv.upgrade_groups
                    ],
                    ["left", "right", "right", "right"],
                ),
                Note(
                    "Reading",
                    "Observation only: the game's expansion check is documented to favour well-served industries "
                    "(see knowledge M3), but a few months of history and the small group sizes here cannot confirm a causal "
                    "effect. The table becomes more meaningful as snapshots span years.",
                ),
            ]
        )

    if lv.movers:

        def mover_row(m):
            hint = []
            if m.level_changed:
                hint.append(f"level {m.level_first}→{m.level_last}")
            if m.rating_changed:
                hint.append(f"rating {m.rating_first:.2f}→{m.rating_last:.2f}")
            return [
                m.name,
                m.cargo_name,
                _arrow(_int(m.produced_first), _int(m.produced_last)),
                _signed(m.delta),
                _arrow(_int(m.shipped_first), _int(m.shipped_last)),
                "; ".join(hint) or "-",
            ]

        ups = [m for m in lv.movers if m.direction == "up"][:8]
        downs = [m for m in lv.movers if m.direction == "down"][:8]
        rows = [["Up"] + mover_row(m) for m in ups] + [["Down"] + mover_row(m) for m in downs]
        blocks.extend(
            [
                Paragraph(
                    "Largest production changes per industry and cargo (threshold: at least 15 items/yr and 15% of the "
                    f"first value; {len(lv.movers)} outputs qualified, top 8 per direction shown)."
                ),
                Table(
                    ["Direction", "Industry", "Cargo", "Produced/yr", "Change", "Shipped/yr", "Level / rating change"],
                    rows,
                    ["left", "left", "left", "right", "right", "right", "left"],
                ),
            ]
        )
    else:
        blocks.append(Paragraph("No output changed enough to pass the movers threshold."))
    return blocks


def _section_service_by_cargo(view: IndustriesView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Service Ratio by Cargo (comparison set)")]
    rows = [
        [
            c.cargo_name,
            f"{c.served_last}/{c.producers_last}",
            _arrow(_int(c.produced_first), _int(c.produced_last)),
            _fmt_pct(c.ratio_first),
            _fmt_pct(c.ratio_last),
            _pp(c.ratio_first, c.ratio_last),
        ]
        for c in view.service_by_cargo
    ]
    if not rows:
        return blocks + [Paragraph("Insufficient data: no industry output was recorded in the comparison set.")]
    shown, omitted = _cap(rows, 20)
    blocks.extend(
        [
            Paragraph(
                "Per cargo: how much of what is produced is shipped, at the first and the latest sample. "
                "'Shipping/producing' counts industries with shipments against industries producing that cargo at the latest sample."
            ),
            Table(
                [
                    "Cargo",
                    "Shipping/producing (latest)",
                    "Produced/yr",
                    "Service ratio first",
                    "Service ratio latest",
                    "Change",
                ],
                shown,
                ["left", "right", "right", "right", "right", "right"],
            ),
            *_omitted(omitted, "cargos"),
        ]
    )
    return blocks


def _section_service_by_type(view: IndustriesView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Service by Industry Type and Outliers")]
    sv = view.service_by_type
    rows, chart_rows, no_output = [], [], []
    for t in sv.types:
        if t.no_output:
            no_output.append(f"{t.label} ({t.industries})")
            continue
        rows.append(
            [
                t.label,
                t.industries,
                f"{t.served_last}/{t.producing_last}",
                _arrow(_int(t.produced_first), _int(t.produced_last)),
                _fmt_pct(t.ratio_first),
                _fmt_pct(t.ratio_last),
                f"{t.mean_rating:.2f}" if t.mean_rating is not None else "-",
            ]
        )
        chart_rows.append((t.label, None if t.ratio_last is None else round(t.ratio_last * 100, 1)))
    blocks.extend(
        [
            Paragraph(
                "Types are the industry's building type. 'Shipping/producing' = industries with shipments over industries "
                "producing at the latest sample; the last column is the mean productionRating of producing industries."
            ),
            Table(
                [
                    "Type",
                    "Industries",
                    "Shipping/producing",
                    "Produced/yr",
                    "Service first",
                    "Service latest",
                    "Mean rating",
                ],
                rows,
                ["left", "right", "right", "right", "right", "right", "right"],
            ),
        ]
    )
    if no_output:
        blocks.append(
            Paragraph("Types with no production at either end (idle or input-starved): " + ", ".join(no_output) + ".")
        )
    if chart_rows:
        shown = chart_rows[:20]
        blocks.append(
            Table(["Type", "Service ratio (%)"], [[c, "-" if v is None else v] for c, v in shown], ["left", "right"])
        )
        known = [(c, v) for c, v in shown if v is not None]  # an unknown ratio is not charted as zero
        if known:
            blocks.append(
                Chart(
                    "bar",
                    "Service ratio by industry type, latest sample (%)",
                    [c for c, _ in known],
                    [("Service ratio %", [v for _, v in known])],
                )
            )
    if sv.outliers:
        shown, omitted = _cap(
            [
                [
                    o.name,
                    o.label,
                    _int(o.produced),
                    f"{o.peers_served}/{o.peers_producing}",
                    _fmt_pct(o.type_median_ratio),
                    "Yes" if o.served_first else "No",
                ]
                for o in sv.outliers
            ],
            12,
        )
        blocks.extend(
            [
                Heading(3, "Unserved while same-type peers are served"),
                Paragraph(
                    "Producing industries with zero shipments in a type where other industries do ship (≥3 producing in the type). "
                    "These are candidates worth comparing with their served peers (cargo and consumers: see the cargo report)."
                ),
                Table(
                    [
                        "Industry",
                        "Type",
                        "Produced/yr",
                        "Peers shipping",
                        "Type median service",
                        "Shipping at first sample",
                    ],
                    shown,
                    ["left", "left", "right", "right", "right", "center"],
                ),
                *_omitted(omitted, "industries"),
            ]
        )
    else:
        blocks.append(
            Paragraph(
                "No type has a mix of served and unserved producing industries (≥3 producing) at the latest sample."
            )
        )
    return blocks


def _section_chains(view: IndustriesView, full: float) -> list[Any]:
    ch = view.chains
    policy_ratio = next(c.value for c in view.criteria if c.name == "below_capacity_ratio")
    blocks: list[Any] = [Heading(2, "Consumer Chains: Inputs, Outputs and Throughput")]
    if not ch.consumers:
        return blocks + [Paragraph("No industry with inputs (consumer) is recorded at the latest sample.")]
    rows = [
        [
            b.cargo_name,
            f"{b.producing_producers}/{b.producers}",
            _int(b.produced),
            _int(b.shipped),
            f"{b.consuming_consumers}/{b.consumers}",
            _int(b.demand),
            _arrow(_int(b.consumed_first), _int(b.consumed_last)),
            _int(b.unused),
        ]
        for b in ch.balances
    ]
    shown, omitted = _cap(rows, 15)
    blocks.extend(
        [
            Heading(3, "Cargo balance: supply vs consumption capacity"),
            Paragraph(
                "Per input cargo at the latest sample: how much is produced and shipped against how much consumer industries "
                "could consume ('capacity' = maxConsumptionYear) and actually consume (consumedYear, first → latest). Ranked by "
                "unused consumption capacity. Consumption is measured by consumedYear; deliveredYear is not used because "
                "its meaning is unverified and it can be zero despite positive consumption."
            ),
            Table(
                [
                    "Cargo",
                    "Producing/producers",
                    "Produced/yr",
                    "Shipped/yr",
                    "Consuming/consumers",
                    "Consumption capacity/yr",
                    "Consumed/yr (first → latest)",
                    "Unused capacity/yr",
                ],
                shown,
                ["left", "right", "right", "right", "right", "right", "right", "right"],
            ),
            *_omitted(omitted, "cargos"),
        ]
    )
    summary = ", ".join(
        f"{STATUS_LABELS[k]}: {v}" for k, v in sorted(ch.status_counts, key=lambda kv: STATUS_LABELS[kv[0]])
    )
    status_rows = [
        [
            s.name,
            s.label,
            STATUS_LABELS[s.status],
            _flows_text(s.inputs),
            _flows_text(s.outputs),
            _arrow(_int(s.consumed_first), _int(s.consumed_last)),
            s.limiting_cargo_name if s.limiting_cargo is not None else "-",
            "Yes" if s.flagged else "No",
        ]
        for s in ch.consumer_statuses
        if s.status != STATUS_RUNNING
    ]
    blocks.append(Heading(3, "Consumer industries that are not running at capacity"))
    blocks.append(
        Paragraph(
            f"{ch.consumers} consumers at the latest sample ({summary}). Status is inferred from consumedYear "
            f"vs maxConsumptionYear and, where stock data exists, full output stocks while output is below {policy_ratio:.0%} of capacity; 'Input-limited' means at "
            "least one input is consumed below 50% of its capacity. Inputs/outputs read 'consumed/capacity' and "
            "'produced/capacity' items per year."
        )
    )
    if status_rows:
        shown, omitted = _cap(status_rows, 14)
        blocks.extend(
            [
                Table(
                    [
                        "Consumer",
                        "Type",
                        "Status",
                        "Inputs",
                        "Outputs",
                        "Consumed/yr (first → latest)",
                        "Weakest input",
                        "Closing",
                    ],
                    shown,
                    ["left", "left", "left", "left", "left", "right", "left", "center"],
                ),
                *_omitted(omitted, "consumers"),
                Note(
                    "Inference",
                    "An idle consumer is missing at least one required input; recipes need fixed ratios of all inputs "
                    "(knowledge M3). Which supplier to connect is a manual decision; the cargo report shows nearest producers/consumers.",
                ),
            ]
        )
    else:
        blocks.append(Paragraph("All consumers are running."))
    return blocks


def _section_stocks(view: IndustriesView, full: float) -> list[Any]:
    st = view.stocks
    blocks: list[Any] = [Heading(2, "Stock Fullness: Change in Time")]
    if st.samples_with_stocks == 0:
        return blocks + [Paragraph("Insufficient data: no snapshot contains stock data.")]
    if not st.latest_has_stocks:
        blocks.append(
            Note("Coverage", f"The latest snapshot has no stock data; using {st.last.date} as the latest stock sample.")
        )
    blocks.append(
        Paragraph(
            f"Stock data exists in {st.samples_with_stocks} of {view.sample_count} snapshots (first with stocks: {st.first.date}). Fill = count / capacity "
            "at that instant. Output stock is the stock of an output cargo; input stock is the buffer of an input cargo. Full output "
            "stocks cause production to be wasted (knowledge M3); the cargo report lists those currently at 90% or more."
        )
    )
    rows = [
        [
            STOCK_GROUP_LABELS[g.code],
            g.stocks_last,
            _fmt_pct(g.mean_fill_first),
            _fmt_pct(g.mean_fill_last),
            g.full_first,
            g.full_last,
        ]
        for g in st.groups
    ]
    blocks.append(
        Table(
            [
                "Stock group",
                "Stocks (latest)",
                f"Mean fill ({st.first.date})",
                f"Mean fill ({st.last.date})",
                f"≥{_pct_text(full)} first",
                f"≥{_pct_text(full)} latest",
            ],
            rows,
            ["left", "right", "right", "right", "right", "right"],
        )
    )
    if st.first.tick == st.last.tick:
        return blocks + [
            Note("Insufficient data", "Only one snapshot has stock data, so fill changes cannot be computed yet.")
        ]
    if st.movers:
        shown, omitted = _cap(
            [
                [
                    m.owner_name,
                    m.role,
                    ", ".join(m.cargos),
                    f"{_fmt_pct(m.fill_first)} → {_fmt_pct(m.fill_last)}",
                    _pp(m.fill_first, m.fill_last),
                ]
                for m in st.movers
            ],
            15,
        )
        blocks.extend(
            [
                Heading(3, "Largest changes in stock fill (≥20 percentage points)"),
                Table(
                    ["Industry", "Stock", "Cargo", "Fill (first → latest)", "Change"],
                    shown,
                    ["left", "left", "left", "right", "right"],
                ),
                *_omitted(omitted, "stocks"),
            ]
        )
    else:
        blocks.append(
            Paragraph(
                "No industry stock changed fill by 20 percentage points or more between the first and latest stock samples."
            )
        )
    return blocks


def _section_closures(view: IndustriesView) -> list[Any]:
    cl = view.closures
    blocks: list[Any] = [Heading(2, "Closures and Risk")]
    if cl.flagged_now:
        rows = []
        for r in cl.flagged_now:
            ind = r.industry
            cancel = []
            if "load-output" in r.cancel_ways:
                cancel.append("load its output")
            if "deliver-inputs" in r.cancel_ways:
                cancel.append("deliver inputs: " + ", ".join(r.input_cargo_names))
            link = "Yes (name match)" if r.station_link else ("No station found" if r.station_link is False else "-")
            rows.append(
                [
                    ind.name,
                    ind.label,
                    _remaining_text(r.remaining),
                    r.flagged_since.date if r.flagged_since else "-",
                    _int(ind.produced),
                    _int(ind.shipped),
                    _int(ind.consumed) if ind.inputs else None,
                    link,
                    "; ".join(cancel) or "-",
                ]
            )
        blocks.extend(
            [
                Heading(3, "Scheduled to close now"),
                Table(
                    [
                        "Industry",
                        "Type",
                        "Closes in",
                        "Flagged since",
                        "Produced/yr",
                        "Shipped/yr",
                        "Consumed/yr",
                        "Our station",
                        "Documented ways to cancel",
                    ],
                    rows,
                    ["left", "left", "left", "left", "right", "right", "right", "left", "left"],
                ),
                Note(
                    "Documented mechanic",
                    "A closure countdown is cancelled if production, consumption or loading resumes before it "
                    "ends (knowledge M4, from game code/wiki; not verified on this save). Whether to act is the player's call; "
                    "if one of our lines depends on its cargo, closure puts that supply or demand at risk.",
                ),
            ]
        )
    else:
        blocks.append(Paragraph("No industry is flagged for closure at the latest sample."))

    if cl.outcomes:
        rows = [
            [
                e.sample.date,
                EVENT_LABELS[e.code],
                e.industry.name,
                e.industry.label,
                _int(e.industry.produced),
                _int(e.industry.shipped),
            ]
            for e in cl.outcomes[-12:]
        ]
        blocks.extend(
            [
                Heading(3, "Closure outcomes observed"),
                Paragraph(
                    "Produced/shipped are the last values seen before the event row (for closed industries) or at the event (cancellations)."
                ),
                Table(
                    ["Sample", "Outcome", "Industry", "Type", "Produced/yr", "Shipped/yr"],
                    rows,
                    ["left", "left", "left", "left", "right", "right"],
                ),
            ]
        )

    blocks.extend(
        [
            Heading(3, "Closure-risk pool (not yet flagged)"),
            Paragraph(
                f"Covers {cl.samples} snapshots over {_span_text(cl.span)}. The documented draw is about "
                "1.1% per industry per year times the closing-frequency option, and only industries without recent use are "
                "eligible; the 'unused years' threshold (5 or 10) is unverified (knowledge M4). Our history cannot show how many "
                "years an industry has been unused, so the tiers below rank evidence, not probability."
            ),
            Table(
                ["Tier (among industries with outputs)", "Industries"],
                [[TIER_LABELS[t.code], t.industries] for t in cl.risk_tiers],
                ["left", "right"],
            ),
        ]
    )
    if cl.idle_pool:
        shown, omitted = _cap(
            [[i.name, i.label, _int(i.capacity), _flows_text(i.inputs) or "-"] for i in cl.idle_pool], 10
        )
        blocks.extend(
            [
                Table(
                    [
                        "Idle industry (largest demand first)",
                        "Type",
                        "Output capacity/yr",
                        "Inputs (consumed/capacity per yr)",
                    ],
                    shown,
                    ["left", "left", "right", "left"],
                ),
                *_omitted(omitted, "industries"),
            ]
        )
    return blocks


def _section_lines(view: IndustriesView) -> list[Any]:
    lk = view.links
    blocks: list[Any] = [Heading(2, "Which of Our Lines Serve Which Industry")]
    blocks.append(
        Note(
            "Evidence level",
            "The snapshot has no station position, catchment or stock-at-station data, so a station-industry link is NOT verified. "
            "Links below are inferred when a station group has exactly the same name as exactly one industry (stations built at an "
            "industry are named after it). The cargo check compares the cargos the line has vehicle capacity for with the industry's "
            "output (shipping) or input (delivering) cargos; capacity is read instantaneously and the cargo index is corrected from "
            "the bridge's 1-based numbering.",
        )
    )
    if not lk.links:
        return blocks + [
            Paragraph(
                "No station name matches an industry name, so no line can be linked to an industry at this sample."
            )
        ]
    rows = []
    for link in lk.links:
        ind = link.industry
        shown_lines = ", ".join(link.serving_lines[:2]) + (
            f" (+{len(link.serving_lines) - 2} more)" if len(link.serving_lines) > 2 else ""
        )
        if link.other_lines:
            shown_lines = (
                shown_lines + "; " if shown_lines else ""
            ) + f"{len(link.other_lines)} other line(s) stop there without its cargo"
        rows.append(
            [
                ind.name,
                ind.label,
                ROLE_LABELS[link.role],
                shown_lines,
                ", ".join(c.name for c in link.matched_cargos) or "none",
                "cargo matches" if link.cargo_matches else "no line carries its cargo",
                _arrow(_int(link.produced_first), _int(ind.produced)),
                _arrow(_int(link.shipped_first), _int(ind.shipped)),
                "Yes" if ind.flagged else "No",
            ]
        )
    shown, omitted = _cap(rows, 25)
    blocks.extend(
        [
            Paragraph(f"{len(lk.links)} industries have a name-matched station that is on at least one of our lines."),
            Table(
                [
                    "Industry",
                    "Type",
                    "Role",
                    "Lines at the station carrying its cargo (name match)",
                    "Cargo carried that matches",
                    "Verdict",
                    "Produced/yr (first → latest)",
                    "Shipped/yr (first → latest)",
                    "Closing",
                ],
                shown,
                ["left", "left", "left", "left", "left", "left", "right", "right", "center"],
            ),
            *_omitted(omitted, "industries"),
        ]
    )
    blocks.append(
        Table(
            ["Link coverage", "Industries"],
            [
                ["Industries with shipments at the latest sample", lk.shipping_industries],
                ["... of which with a name-matched station on our lines", lk.shipping_with_link],
                ["... of which link NOT verifiable (no station carries the industry's name)", lk.shipping_without_link],
                ["Name-matched industries whose station lines carry a matching cargo", lk.cargo_matched_industries],
            ],
            ["left", "right"],
        )
    )
    if lk.unlinked_shippers:
        names = ", ".join(i.name for i in lk.unlinked_shippers[:6])
        blocks.append(
            Paragraph(
                f"Observation: shipping industries without a verifiable station link include: {names}"
                f"{' …' if len(lk.unlinked_shippers) > 6 else ''}. The shipments exist (shippedYear > 0) but the snapshot does "
                "not say which of our stations or lines moves them (renamed stations, shared stations or distant "
                "stations cannot be matched)."
            )
        )
    return blocks


def _section_manual_review(view: IndustriesView, full: float) -> list[Any]:
    heading = Heading(2, "Suggested Manual Review Priorities")
    rows = []
    for r in view.manual_review:
        if r.code == "closure-flagged":
            rows.append(
                [
                    str(r.priority),
                    r.name,
                    f"Closure flagged; remaining {_remaining_text(r.remaining)}",
                    "Decide manually whether this industry is worth retaining. Inspect its input/output links in-game "
                    "before the countdown ends; otherwise allow closure and avoid depending on it.",
                ]
            )
        elif r.code == "production-decline":
            rows.append(
                [
                    str(r.priority),
                    r.name,
                    f"Produced/yr {_fmt_amount(r.produced_first)} → {_fmt_amount(r.produced_last)} ({_signed(-r.decline)})",
                    "Inspect its input buffer and the lines supplying it, then its downstream output buffers. "
                    "Determine whether supply fell or stock accumulated before changing vehicles.",
                ]
            )
        else:
            rows.append(
                [
                    str(r.priority),
                    r.name,
                    f"Some output ships, but another output cargo has zero shipments and a ≥{_pct_text(full)} full stock",
                    "Inspect the unshipped coproduct and its consumer chain. A line carrying one output does not "
                    "necessarily serve all of this industry's outputs. Compare against the cargo report.",
                ]
            )
    if rows:
        return [heading, Table(["Priority", "Industry", "Observation", "Suggestion (player action only)"], rows)]
    return [
        heading,
        Paragraph(
            "No closing industry, substantial production decline or full unshipped coproduct qualifies "
            "for these review priorities in the available samples."
        ),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build(view: IndustriesView, *, context: EvaluationContext) -> ReportDocument:
    full = context.thresholds.full_stock_ratio
    latest = context.snapshot
    header = [
        ("Company / Save", latest.company.get("name") or "Primary Company"),
        ("First Sample Date", view.first.date),
        ("Latest Sample Date", view.latest.date),
        ("Snapshots Used", str(view.sample_count)),
        ("Coverage", _span_text(view.span) if view.sample_count > 1 else "single snapshot (no change can be shown)"),
        (
            "Stock Coverage",
            (
                f"{view.stock_samples} of {view.sample_count} snapshots (from {view.first_stock_sample.date})"
                if view.first_stock_sample
                else "no stock data in any snapshot"
            ),
        ),
        ("Collection Errors", "; ".join(view.error_families) or "None reported"),
        (
            "Unknown Flows",
            f"{view.unknown_flow_count} latest industries excluded from flow totals "
            "(missing input/output fields or measurements)",
        ),
        (
            "Measurement Limits",
            "Production, shipments and consumption are rolling annual figures per snapshot (never summed "
            "across snapshots); service ratio is shipped / produced and can exceed 100% due to stock draw-down; "
            "incomplete input/output flows are omitted as unknown, never counted as zero; distances are not used; "
            "station-industry links are name-match inferences; calendar days come from meta.date.",
        ),
        (
            "Save Boundary",
            "One companion store; history is not guaranteed to belong to a single save. "
            "Comparisons assume these samples are from the same save.",
        ),
    ]
    if view.status == "no-industries":
        return ReportDocument(
            "industries",
            TITLE,
            header,
            [
                Heading(2, "Industries"),
                Paragraph("Insufficient data: the latest snapshot lists no industries."),
            ],
        )
    if view.status == "incomplete-flows":
        return ReportDocument(
            "industries",
            TITLE,
            header,
            [
                Heading(2, "Industries"),
                Paragraph(
                    "Insufficient data: no industry has complete input/output measurements; production, service and chain "
                    "comparisons are unknown, not zero."
                ),
            ],
        )

    def part(name: str, value: Any, title: str, make: Callable[[], list[Any]]) -> list[Any]:
        return _unavailable(title) if value is None and _failed(view, name) else ([] if value is None else make())

    blocks: list[Any] = []
    if view.comparison is None and not _failed(view, "summary"):
        blocks += [
            Heading(2, "Change Since First Sample"),
            Paragraph(
                "Insufficient data: at least two snapshots sharing industries are required to show change. "
                "The sections below describe the latest sample only where they can."
            ),
        ]
    else:
        blocks += part("summary", view.comparison, "Change Since First Sample", lambda: _section_summary(view, full))
    blocks += part("evolution", view.evolution, "Evolution Over Time", lambda: _section_evolution(view))
    if view.sample_count > 1:
        if _failed(view, "events"):
            blocks += _unavailable("Industry Lifecycle")
        else:
            blocks += _section_events(view)
    blocks += part("levels", view.levels, "Level Upgrades and Production Movers", lambda: _section_levels(view))
    blocks += part(
        "service-by-cargo", view.service_by_cargo, "Service Ratio by Cargo", lambda: _section_service_by_cargo(view)
    )
    blocks += part(
        "service-by-type", view.service_by_type, "Service by Industry Type", lambda: _section_service_by_type(view)
    )
    blocks += part("chains", view.chains, "Consumer Chains", lambda: _section_chains(view, full))
    blocks += part("stocks", view.stocks, "Stock Fullness", lambda: _section_stocks(view, full))
    blocks += part("closures", view.closures, "Closures and Risk", lambda: _section_closures(view))
    blocks += part("lines", view.links, "Lines and Industries", lambda: _section_lines(view))
    blocks += part(
        "manual-review",
        view.manual_review,
        "Suggested Manual Review Priorities",
        lambda: _section_manual_review(view, full),
    )
    return ReportDocument("industries", TITLE, header, blocks)
