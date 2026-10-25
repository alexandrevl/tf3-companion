"""Expansion opportunities report: ranked, evidence-backed candidates for new or extended routes.

Presentation over `ExpansionView`: every candidate, score part, exclusion, diagnostic and vehicle-fit
row is calculated in `analysis_views.expansion`; this module only chooses headings, prose, formatting
and display caps. Distances are straight-line estimates, rolling annual figures are never summed across
snapshots, and missing values are treated as unknown.
"""

from __future__ import annotations

from typing import Any

from .analysis_views.expansion import (
    PERSISTENCE_MIN_SAMPLES,
    PROVEN_MIN_VEHICLES,
    EntityRef,
    ExpansionCandidate,
    ExpansionView,
    Flag,
    Penalty,
    StarvedSupplier,
)
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

DISPLAY_ROWS = 10
PROVEN_DISPLAY_ROWS = 12


# ---------------------------------------------------------------------------
# small formatting helpers
# ---------------------------------------------------------------------------


def _label(ref: EntityRef, kind: str | None = None) -> str:
    return ref.name or f"{kind or ref.kind.capitalize()} #{ref.id if ref.id is not None else 'unknown'}"


def _f(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _short(text: str, limit: int = 34) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


_FLAG_TEXT = {
    "distance_unknown": "distance unknown",
    "town_distance_estimate": "town distance is a rough estimate",
    "water_producer": "water-based producer: ships/ports needed",
}

_PENALTY_TEXT = {
    "consumer_closing": "consumer industry is closing",
    "producer_closing": "producer industry is closing",
}

_WHY_TEXT = {
    "largest_capacity": "largest capacity",
    "lowest_running_cost_per_capacity": "lowest annual running cost per capacity",
}

_DEAD_END_TEXT = {
    "already_linked": "already linked by a line",
    "input_at_capacity": "consumer input already at recorded capacity",
    "booster_cargo_without_inputs": "booster cargo: primary industries use it but the snapshot lists no booster inputs",
    "no_consumer": "no consumer of this cargo in the snapshot",
}


def _flag(flag: Flag) -> str:
    if flag.code == "consumer_lacks_inputs":
        return f"consumer also lacks {flag.subject}"
    if flag.code == "producer_already_served":
        return f"producer already served by {_short(flag.subject or '', 40)} (check capacity first)"
    if flag.code == "output_stock_full":
        return f"output stock {_fmt_pct(flag.value)} full: destruction risk at capacity"
    if flag.code == "persistence_unavailable":
        return f"persistence n/a ({flag.samples} usable samples)"
    if flag.code == "persistence_underserved":
        return f"under-shipped in {flag.value * 100:.0f}% of {flag.samples} samples"
    return _FLAG_TEXT.get(flag.code, flag.code)


def _penalty(penalty: Penalty) -> str:
    if penalty.code == "consumer_input_stock_full":
        return f"consumer input stock {_fmt_pct(penalty.stock_ratio)} full"
    return _PENALTY_TEXT.get(penalty.code, penalty.code)


def _consumer_label(cand: ExpansionCandidate) -> str:
    return _label(cand.consumer, "Town" if cand.consumer_kind == "town" else "Industry")


def _candidate_label(cand: ExpansionCandidate) -> str:
    return f"{_label(cand.producer, 'Industry')} -> {_consumer_label(cand)}"


def _distance_note(cand: ExpansionCandidate) -> str:
    if cand.distance_method == "industry-positions":
        return "industry positions"
    if cand.distance_method == "town-anchor-estimate":
        n = cand.anchor_industries
        return (
            f"town estimated from {n} industr{'y' if n == 1 else 'ies'} "
            f"named after it (spread {cand.anchor_spread_km:.1f} km)"
        )
    return "town position not collected"


# ---------------------------------------------------------------------------
# report sections
# ---------------------------------------------------------------------------


def _formula_blocks(view: ExpansionView, ctx: EvaluationContext) -> list[Any]:
    policy = ctx.policies["expansion"]
    return [
        Heading(2, "Scoring Formula"),
        Paragraph(
            "Score = Volume + Distance + Urgency + Pull + Chain + Proven - Penalties, floored at 0. "
            "Maximum before penalties is 100. Every component is printed per candidate in the breakdown table."
        ),
        Table(
            ["Component", "Max", "Definition"],
            [
                [
                    "Volume",
                    policy.weight_volume,
                    f"{policy.weight_volume} x min(1, V / {policy.volume_reference}) where V = min(producer unshipped items per year, consumer unmet input or town unmet demand per year), "
                    "as recorded. Volume is deducted from a shared consumer as candidates are chosen, so two rows never claim the same capacity twice.",
                ],
                [
                    "Distance",
                    policy.weight_distance,
                    f"Straight-line km estimate. 0 below {policy.distance_short_km} km, linear ramp to full at {policy.distance_sweet_from_km} km, full to {policy.distance_sweet_to_km} km, "
                    f"then declines to {int(policy.distance_long_floor * 100)}% at {policy.distance_long_km:g} km and stays there. Heuristic: income grows with distance but trip time does too. Unknown distance scores 0.",
                ],
                [
                    "Urgency",
                    policy.weight_urgency,
                    f"{policy.weight_urgency} x (0.5 x (1 - shipped/produced) + 0.5 x output stock fill). Without a stock reading use 0.25 x (1 - shipped/produced) instead of the entire bracket. "
                    f"Scaled by 0.5 + 0.5 x persistence when at least {PERSISTENCE_MIN_SAMPLES} samples exist.",
                ],
                [
                    "Pull",
                    policy.weight_pull,
                    f"{policy.weight_pull} x unmet share of the consumer's recorded annual input capacity (industry) or of the town's recorded demand limit (town).",
                ],
                [
                    "Chain",
                    policy.weight_chain,
                    f"Industry consumers: {policy.weight_chain} if the consumer's outputs feed another industry, 60% of that if they only feed towns, halved while the consumer lacks another mandatory input. "
                    f"Town consumers: flat {policy.weight_chain // 2}.",
                ],
                [
                    "Proven",
                    policy.weight_proven,
                    f"{policy.weight_proven} x share of our vehicles hauling this cargo that currently show positive rolling annual profit (needs at least {PROVEN_MIN_VEHICLES} such vehicles, else 0). Water-based sources use WATER vehicles only.",
                ],
                [
                    "Penalties",
                    f"-{policy.full_input_penalty} / -{policy.closing_penalty}",
                    f"-{policy.full_input_penalty} consumer input stock at or above {int(view.full_stock_ratio * 100)}% full; "
                    f"-{policy.closing_penalty} each for a closing producer or consumer.",
                ],
            ],
            ["left", "right", "left"],
        ),
        Note(
            "Weights",
            "The weights and thresholds are this report's own heuristics, not game mechanics; treat the score as a ranking aid, never a profit forecast.",
        ),
    ]


def _steps(cand: ExpansionCandidate) -> str:
    producer, consumer = _label(cand.producer, "Industry"), _label(cand.consumer, "Industry")
    cargo = cand.cargo.name
    steps = [
        f"1. Check on the map that a road, rail or water connection between {producer} and {consumer} is physically possible."
    ]
    if cand.producer_lines:
        steps.append(
            f"2. {producer} already has a line carrying this cargo ({_short(cand.producer_lines[0], 50)}); "
            "first look at whether adding vehicles or fixing that line's destination removes the surplus."
        )
    else:
        steps.append(
            f"2. Build or reuse a loading station at {producer} and an unloading station at {consumer}, and create a line between them that carries {cargo}."
        )
    steps.append(
        "3. Compare the cargo-compatible models with purchase and upkeep figures in the game; the table is a shortlist, not a fleet-size prescription. Begin conservatively and inspect both stocks in later samples before adding vehicles."
    )
    if cand.missing_inputs:
        steps.append(
            f"4. {consumer} also needs {', '.join(cand.missing_inputs)}; delivering only {cargo} may not start its production. See the starved-consumer table for candidate suppliers."
        )
    if any(p.code == "consumer_input_stock_full" for p in cand.penalties):
        steps.append(
            "5. Its input stock is nearly full: deliveries could be refused or cargo destroyed until it consumes more."
        )
    return " ".join(steps)


def _observation(cand: ExpansionCandidate) -> str:
    cargo = cand.cargo.name
    bits = [
        f"{_label(cand.producer, 'Industry')} produced {cand.produced:,.0f} {cargo} per year and shipped {cand.shipped:,.0f} ({_fmt_pct(cand.ratio)})."
    ]
    if cand.out_fill is not None:
        bits.append(f"Its {cargo} output stock is {_fmt_pct(cand.out_fill)} full.")
    if cand.consumer_kind == "industry":
        bits.append(
            f"{_label(cand.consumer, 'Industry')} has {cand.unmet_recorded:,.0f} of {cand.consumer_capacity:,.0f} recorded annual {cargo} input capacity unused."
        )
    else:
        bits.append(
            f"{_label(cand.consumer, 'Town')} records demand limit {cand.consumer_capacity:,.1f} with {cand.town_supplied:,.1f} supplied (interpretation of 'limit' and 'supply' is unverified)."
        )
    proof = cand.proof
    if proof.share is not None:
        bits.append(
            f"Proven: {proof.profitable} of {proof.vehicles} of our {cargo} vehicles show positive rolling annual profit"
            + (f"; best carrier {proof.best_carrier}." if proof.best_carrier else ".")
        )
    else:
        bits.append(f"No proof: fewer than {PROVEN_MIN_VEHICLES} of our vehicles currently haul {cargo} on a line.")
    return " ".join(bits)


def _risks(cand: ExpansionCandidate) -> str:
    risks = [_penalty(p) for p in cand.penalties]
    if cand.input_stock_elevated:
        risks.append(f"consumer input stock already {_fmt_pct(cand.in_fill)} full")
    risks.append("a full destination stock can block unloading and destroy cargo")
    if cand.consumer_kind == "town":
        risks.append("town position is estimated, not measured")
    return "; ".join(risks)


def _alternative(view_alt) -> str:
    where = f"{_f(view_alt.distance_km)} km" if view_alt.distance_km is not None else "distance unknown"
    return f"{_label(view_alt.consumer)} (score {view_alt.score:.1f}, {where})"


def _ranking_blocks(view: ExpansionView) -> list[Any]:
    picked = view.candidates
    if not picked:
        return [
            Heading(2, "Top Expansion Candidates"),
            Note(
                "Insufficient Data",
                "No producer currently ships less than half of its output to an unserved consumer, "
                "or the stored snapshot lacks industry flow data.",
            ),
        ]
    blocks: list[Any] = [Heading(2, f"Top {len(picked)} Expansion Candidates")]
    blocks.append(
        Table(
            [
                "#",
                "Route (producer -> consumer)",
                "Cargo",
                "Volume / Yr",
                "Distance (km, straight line)",
                "Score",
                "Flags",
            ],
            [
                [
                    c.rank,
                    _candidate_label(c),
                    c.cargo.name,
                    round(c.volume),
                    _f(c.distance_km) if c.distance_km is not None else "unknown",
                    round(c.score, 1),
                    "; ".join(_flag(f) for f in c.flags) or "-",
                ]
                for c in picked
            ],
            ["right", "left", "left", "right", "right", "right", "left"],
        )
    )
    blocks.append(
        Chart(
            "bar",
            "Expansion score (higher is better)",
            [f"{c.rank}. {_short(_label(c.producer, 'Industry'), 14)}" for c in picked],
            [("Score", [round(c.score, 1) for c in picked])],
        )
    )
    blocks.append(Heading(3, "Score Breakdown"))
    blocks.append(
        Table(
            ["#", "Volume", "Distance", "Urgency", "Pull", "Chain", "Proven", "Penalties", "Total"],
            [
                [
                    c.rank,
                    round(c.parts.volume, 1),
                    round(c.parts.distance, 1),
                    round(c.parts.urgency, 1),
                    round(c.parts.pull, 1),
                    round(c.parts.chain, 1),
                    round(c.parts.proven, 1),
                    f"-{c.penalty_total:g}" if c.penalties else "0",
                    round(c.score, 1),
                ]
                for c in picked
            ],
            ["right"] * 9,
        )
    )
    blocks.append(
        Paragraph(
            "Volume is items per year as recorded by the bridge; distances use industry positions assumed to be metres; "
            "town distances use an anchor estimated from industries named after the town."
        )
    )

    blocks.append(Heading(3, "Candidate Detail"))
    for c in picked:
        alternatives = (
            "Alternative consumers for the same output: " + "; ".join(_alternative(a) for a in c.alternatives) + ". "
            if c.alternatives
            else ""
        )
        blocks.append(
            Note(
                f"#{c.rank} {_candidate_label(c)} ({c.cargo.name})",
                f"Observation: {_observation(c)} Distance basis: {_distance_note(c)}. "
                f"{alternatives}"
                f"Risks: {_risks(c)}. Manual steps: {_steps(c)}",
            )
        )

    catalog = view.catalog
    blocks.append(Heading(3, "Vehicle Fit"))
    if catalog.sample is None:
        blocks.append(Note("Analysis Pending", "No catalog snapshot is stored, so vehicle models cannot be suggested."))
    else:
        by_rank = {c.rank: c for c in picked}
        fit_rows = [
            [
                f.candidate_rank,
                f.cargo.name,
                f.carrier,
                f.model.name or f.model.res or f"Model #{f.model.id}",
                " and ".join(_WHY_TEXT.get(w, w) for w in f.why),
                f.capacity,
                _f(f.loads_per_year) if f.loads_per_year else "-",
                f.price,
                f.running_costs,
                f"{f.year_from or 'any'} to {f.year_to if f.year_to else 'open'}",
            ]
            for f in catalog.candidates
            if f.candidate_rank in by_rank
        ]
        blocks.append(
            Table(
                [
                    "#",
                    "Cargo",
                    "Carrier",
                    "Model",
                    "Why listed",
                    "Capacity / Unit",
                    "Loads / Yr To Move Volume",
                    "Price (verified currency)",
                    "Running Cost (verified currency/year)",
                    "Years",
                ],
                fit_rows,
                ["right", "left", "left", "left", "left", "right", "right", "right", "right", "left"],
            )
        )
        matched, compared = catalog.capacity_matched, catalog.capacity_compared
        check = (
            f"Capacity per unit matches the recorded capacity of {matched} of {compared} single-model fleet vehicles compared against this catalog."
            if compared
            else "Catalog capacity could not be cross-checked against any fleet vehicle."
        )
        blocks.append(
            Note(
                "Unit Limit",
                f"{check} Price and running costs are omitted when units are unverified; "
                "cost-based ranking and speed are omitted without verified units. Models are limited to those available in the game year; "
                "rail rows are wagons or units and a locomotive is also needed. Models listed fit the cargo, not necessarily the terrain.",
            )
        )
    return blocks


def _proven_blocks(view: ExpansionView) -> list[Any]:
    rows = [g for g in view.proven if g.qualifies]
    blocks: list[Any] = [Heading(2, "Extend the Proven: Cargo That Already Pays for Us")]
    if not rows:
        blocks.append(
            Note(
                "Insufficient Data",
                f"No freight cargo and carrier combination has at least {PROVEN_MIN_VEHICLES} line-assigned vehicles with a positive median rolling annual profit.",
            )
        )
        return blocks
    blocks.append(
        Table(
            [
                "Cargo",
                "Carrier",
                "Vehicles",
                "Profitable",
                "Median Rolling Annual Profit / Vehicle",
                "Candidates In Top List",
            ],
            [
                [g.cargo.name, g.carrier, g.vehicles, g.profitable, round(g.median_profit), g.candidates_in_ranking]
                for g in rows[:PROVEN_DISPLAY_ROWS]
            ],
            ["left", "left", "right", "right", "right", "right"],
        )
    )
    blocks.append(
        Note(
            "Reading This",
            "Figures are rolling annual profit of vehicles at the latest sample only (one snapshot, never summed across samples). "
            "A vehicle's main cargo is its largest configured load; a multi-cargo line's profit cannot be split by cargo. "
            "Profit is raw game currency units. Past profit on a cargo does not guarantee a new route's profit.",
        )
    )
    if len(rows) > PROVEN_DISPLAY_ROWS:
        blocks.append(Paragraph(f"{len(rows) - PROVEN_DISPLAY_ROWS} further cargo and carrier combinations omitted."))
    return blocks


def _supplier(s: StarvedSupplier) -> str:
    if s.producer is None:
        return f"{s.cargo.name}: no industry currently producing it"
    return f"{s.cargo.name}: {_label(s.producer, 'Industry')} {s.distance_km:.1f} km, {s.unshipped:,.0f} unshipped/yr"


def _starved_blocks(view: ExpansionView) -> list[Any]:
    rows = view.starved_consumers
    blocks: list[Any] = [Heading(2, "Starved Consumers: Chains That Cannot Start")]
    if not rows:
        blocks.append(
            Note("Insufficient Data", "No industry with recorded input capacity is currently below 10% input usage.")
        )
    else:
        blocks.append(
            Table(
                [
                    "Consumer",
                    "Annual Input Capacity (all inputs)",
                    "Outputs Waiting To Start",
                    "Nearest Producer Per Input",
                ],
                [
                    [
                        _label(r.consumer, "Industry"),
                        round(r.capacity),
                        ", ".join(o.name or "?" for o in r.outputs) or "-",
                        " | ".join(_supplier(s) for s in r.suppliers),
                    ]
                    for r in rows[:DISPLAY_ROWS]
                ],
                ["left", "right", "left", "left"],
            )
        )
        if len(rows) > DISPLAY_ROWS:
            blocks.append(
                Paragraph(
                    f"{len(rows) - DISPLAY_ROWS} further starved consumers omitted; shown by largest input capacity."
                )
            )
        blocks.append(
            Note(
                "Reading This",
                "Usage is the larger of delivered and consumed per year over the recorded capacity. "
                "Multi-input consumers need all mandatory inputs (a Food Factory takes Fish or Meat plus Sheet Metal), so supplying one input alone usually does nothing. "
                "Nearest producer ignores whether that producer's output is already shipped elsewhere.",
            )
        )
    if view.unassessed_consumers:
        blocks.append(
            Paragraph(
                f"{len(view.unassessed_consumers)} industries are not assessed because their recorded input usage is unknown."
            )
        )
    return blocks


def _town_blocks(view: ExpansionView) -> list[Any]:
    rows = view.towns
    blocks: list[Any] = [Heading(2, "Towns With No or Little Service")]
    if not rows:
        blocks.append(
            Note("Insufficient Data", "Every town has at least one of our stations and line usage of 20% or more.")
        )
        return blocks
    blocks.append(
        Table(
            ["Town", "Capacity Sum (population proxy)", "Line Usage", "Our Stations", "Cargo With Unmet Demand"],
            [
                [
                    _label(r.town, "Town"),
                    r.capacity_sum,
                    r.line_usage,
                    r.stations,
                    ", ".join(c.name or "?" for c in r.unmet_cargos) or "-",
                ]
                for r in rows[:DISPLAY_ROWS]
            ],
            ["left", "right", "right", "right", "left"],
        )
    )
    if len(rows) > DISPLAY_ROWS:
        blocks.append(Paragraph(f"{len(rows) - DISPLAY_ROWS} further towns omitted; shown by capacity sum."))
    blocks.append(
        Note(
            "Reading This",
            "Town positions are not collected, so no passenger route is scored or sized here. Capacity sum (residential + commercial + industrial) is an unverified population proxy; "
            "line usage is a recorded fraction whose exact meaning is unverified. These are leads to inspect, not recommendations.",
        )
    )
    return blocks


def _excluded_blocks(view: ExpansionView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Cross-Check: Routes That Already Exist (Never Recommended)")]
    rows = [
        [_label(e.producer, "Industry"), _label(e.consumer), e.cargo.name, _fmt_pct(e.ratio), "; ".join(e.lines[:2])]
        for e in view.excluded
    ]
    if rows:
        blocks.append(
            Table(
                ["Producer", "Consumer", "Cargo", "Shipped / Produced", "Existing Line(s)"],
                rows[:DISPLAY_ROWS],
                ["left", "left", "left", "right", "left"],
            )
        )
        if len(rows) > DISPLAY_ROWS:
            blocks.append(Paragraph(f"{len(rows) - DISPLAY_ROWS} further existing pairs omitted."))
        blocks.append(
            Note(
                "Meaning",
                "These producers still ship under half of their output although a cargo-compatible line or transfer path of ours connects both ends. "
                "Inspect its filters, capacity and scheduling before proposing a duplicate route; this is a possible connection, not proof of delivery.",
            )
        )
    else:
        blocks.append(Paragraph("No under-shipping producer is already linked to a consumer by one of our lines."))
    blocks.append(
        Note(
            "Matching Limit",
            "Industries match only station groups with exactly the industry's name. Cargo-compatible transfers at shared station groups are conservatively excluded; "
            "renamed stations, catchment overlap and unloading filters are not collected, so verify every candidate's existing network manually before construction.",
        )
    )
    blocks.append(Heading(3, "Unshipped Output With No Viable Target"))
    dead = view.dead_ends
    if dead:
        blocks.append(
            Table(
                ["Producer", "Cargo", "Unshipped / Yr", "Reason"],
                [
                    [
                        _label(d.producer, "Industry"),
                        d.cargo.name,
                        round(d.unshipped),
                        "; ".join(_DEAD_END_TEXT.get(r, r) for r in d.reasons),
                    ]
                    for d in dead[:DISPLAY_ROWS]
                ],
                ["left", "left", "right", "left"],
            )
        )
        if len(dead) > DISPLAY_ROWS:
            blocks.append(Paragraph(f"{len(dead) - DISPLAY_ROWS} further producers omitted."))
    else:
        blocks.append(Paragraph("Every under-shipping producer has at least one viable target."))
    return blocks


def build(view: ExpansionView, *, context: EvaluationContext) -> ReportDocument:
    latest = context.snapshot
    samples = view.coverage.sampled
    header = _base_header(latest, len(samples))
    header.insert(
        2,
        (
            "History Samples",
            f"{len(samples)} (monthly for the newest 12 game months, quarterly before): {samples[0].date} to {samples[-1].date}",
        ),
    )
    header.insert(3, ("Catalog Sample", view.catalog.sample.date if view.catalog.sample else "none stored"))
    header.append(
        (
            "Candidates Evaluated",
            f"{view.candidates_evaluated} producer-consumer pairs from {view.outputs_evaluated} under-shipping outputs",
        )
    )

    blocks: list[Any] = [
        Paragraph(
            "Ranked candidates for new or extended routes, built from producers that ship less than half of their output "
            "and consumers (industries or towns) that can use the cargo. Observations come straight from the latest sample; "
            "scores and fit lists are inference; manual steps are suggestions for you to carry out. Nothing here changes the game."
        ),
    ]
    blocks.extend(_formula_blocks(view, context))
    blocks.extend(_ranking_blocks(view))
    blocks.extend(_proven_blocks(view))
    blocks.extend(_starved_blocks(view))
    blocks.extend(_town_blocks(view))
    blocks.extend(_excluded_blocks(view))
    blocks.append(Heading(2, "Coverage and Limits"))
    blocks.append(
        Note(
            "Sampling",
            f"Output flows are rolling annual figures from the latest sample; persistence over earlier samples was usable for {view.persistence_usable} of {len(view.candidates)} listed candidates "
            f"(needs at least {PERSISTENCE_MIN_SAMPLES} samples). As snapshots accumulate over years, persistence and the history window fill in automatically.",
        )
    )
    blocks.append(
        Note(
            "Measurement Limits",
            "Distances are straight-line estimates between recorded positions and say nothing about terrain, rivers or route length. "
            "Production and demand figures are per-year values as recorded; the accounting of transportedYear is unverified. "
            "Town positions and station positions are not collected. Missing values are treated as unknown, not zero.",
        )
    )
    return ReportDocument("expansion", "Expansion Opportunities Report", header, blocks)
