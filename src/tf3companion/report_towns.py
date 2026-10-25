"""Towns report: evolution, ranking, coverage by our lines, unmet cargo demand, hot spots.

Everything is derived from stored snapshots. Town "size" is the sum of the three building
capacities (residential + commercial + industrial). That is a capacity proxy, not a head count.
"""
from __future__ import annotations

from typing import Any

from .analysis_views.models import EvaluationContext
from .analysis_views.towns import (
    HEADROOM_MARGIN,
    LARGE_QUANTILE,
    MIN_WINDOW_SAMPLES,
    MIN_WINDOW_YEARS,
    USAGE_CAP,
    TownRow,
    TownsView,
)
from .game_time import DAYS_PER_YEAR
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _base_header, _fmt_pct

MAX_TABLE_ROWS = 15

_STALL_READINGS = {
    "no-station": "No station of ours; growth comes only from transport [documented]",
    "freight-only": "Freight stations only",
    "usage-at-cap": "Usage at passenger cap; other XP sources or ratings limit it [INFERENCE]",
    "usage-unknown": "Served; line usage unknown",
    "below-cap": "Served but usage below cap",
}
_PAIR_STATUS = {
    "indirect-shared-network": "Indirect (shared passenger network)",
    "no-passenger-link": "No passenger link",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _signed(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    if round(value, digits) == 0:
        return "0"
    return f"{value:+.{digits}f}"


def _signed_pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:+.1f}%"


def _pct(value: float | None) -> str:
    return _fmt_pct(value) if value is not None else "-"


def _num_str(value: float | None, digits: int = 0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _rank_label(row: TownRow) -> str:
    return f"#{row.rank}" if row.rank else "-"


def _line_names(row: TownRow, limit: int = 4) -> str:
    shown = [f"{line.name} [{'P' if line.passenger else 'F'}]" for line in row.lines[:limit]]
    extra = f" +{len(row.lines) - limit} more" if len(row.lines) > limit else ""
    return "; ".join(shown) + extra if shown else "none"


def _demands_met(row: TownRow) -> str:
    return f"{row.demands_met}/{row.demands_total}" if row.demands_total else "-"


def _unreported(known: float, unknown: int) -> str:
    return _num_str(known) + (f" (+{unknown} unreported)" if unknown else "")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _proxy_section() -> list[Any]:
    return [
        Heading(2, "What the town numbers mean"),
        Note("Capacity proxy",
             "'Size' here is capacity = residential + commercial + industrial building capacity from "
             "townBuildingSystem. It is a capacity proxy, not a head count: population is only approximated "
             "by it [INFERENCE]. Town growth in this game comes only from transport XP (mechanics M2), and new "
             "capacity arrives in small steps, so short windows show few or no changes."),
        Note("Line usage", "lineUsage is the game's town line usage. The passenger rating is double the usage "
             f"clamped to 0-1 (mechanics M2), so usage above {USAGE_CAP:.0%} adds nothing to that rating. "
             "Headroom below means the gap to that cap."),
        Note("Cargo supply / limit", "cargoSupply gives, per cargo the town demands, a supply and a limit in game "
             "units that are not verified (per-year meaning unconfirmed); the 'extra' field is not interpreted. "
             "Supply as a percentage of limit is used as a relative fulfilment measure only."),
        Note("Pollution / noise", "Units and scale are unverified. Values are compared between towns and over "
             "time only; whether a town is actually penalised (authority rating) cannot be told from these numbers."),
    ]


def _overview(view: TownsView) -> list[Any]:
    s = view.summary
    if not s.sized:
        return [Heading(2, "Overview"), Paragraph("Insufficient data: no town reports building capacities.")]
    rows_out = [
        ["Towns tracked", s.towns],
        ["Total capacity (latest)", _num_str(s.total_capacity)],
        ["Total capacity change over window", _signed(s.capacity_change)],
        ["Towns with growth observed in window", "-" if s.growing is None else f"{s.growing} of {s.sized}"],
        ["Towns with a station of ours", f"{s.served} of {s.sized} ({_pct(s.served_share)} of capacity)"],
        ["Towns with a passenger line of ours", f"{s.passenger_served} of {s.sized} ({_pct(s.passenger_share)} of capacity)"],
        ["Capacity-weighted line usage", _pct(s.weighted_usage)],
        ["Towns with development active", f"{s.development_active} of {s.sized}"],
    ]
    return [Heading(2, "Overview"), Table(["Measure", "Value"], rows_out, ["left", "right"])]


def _evolution(view: TownsView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Evolution")]
    if not view.evolution:
        return blocks + [Paragraph("Insufficient data: only one snapshot, no evolution to show yet.")]
    picked = view.evolution
    blocks.append(Paragraph(
        f"{len(picked)} sample points from {view.summary.window_samples} snapshots ({picked[0].label} to "
        f"{picked[-1].label}); one point per month, quarter or year depending on the span, always including "
        "the first and latest."))
    blocks.append(Chart("line", "Total town capacity (all towns)", [p.label for p in picked],
                        [("Total capacity", [p.total_capacity for p in picked])]))
    blocks.append(Table(
        ["Sample", "Total capacity", "Change vs first", "Residential", "Commercial", "Industrial",
         "Weighted line usage", "Dev. active"],
        [[p.label, _num_str(p.total_capacity), _signed(p.change_vs_first), _num_str(p.residential),
          _num_str(p.commercial), _num_str(p.industrial), _pct(p.weighted_usage), p.development_active]
         for p in picked],
        ["left", "right", "right", "right", "right", "right", "right", "right"]))
    return blocks


def _league(view: TownsView, sized: list[TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Town ranking")]
    if not sized:
        return blocks + [Paragraph("Insufficient data: no capacities available.")]
    top = sized[:MAX_TABLE_ROWS]
    blocks.append(Paragraph(
        f"Largest {len(top)} of {len(sized)} towns by capacity proxy. Change columns compare the first sample "
        f"({view.summary.window_first.date}) with the latest ({view.summary.window_last.date}); 'Growth/yr' is a linear "
        "extrapolation per calendar year and only shown when the window is long enough."))
    blocks.append(Chart("bar", "Town capacity (largest towns)", [r.name for r in top[:20]],
                        [("Capacity", [r.capacity for r in top[:20]])]))
    blocks.append(Table(
        ["#", "Town", "Capacity", "Share", "Res / Com / Ind", "Change", "Growth", "Growth/yr", "Line usage",
         "Usage change", "Stations", "Lines (pax/all)"],
        [[r.rank, r.name, _num_str(r.capacity), _pct(r.share),
          " / ".join(_num_str(c) for c in r.capacities) if len(r.capacities) >= 3 else "-", _signed(r.delta),
          _signed_pct(r.growth), _signed_pct(r.annual_growth), _pct(r.usage), _signed_pct(r.usage_change),
          r.stations, f"{r.lines_passenger}/{r.lines_all}"] for r in top],
        ["right", "left", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"]))
    return blocks


def _growth(view: TownsView, by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Growth and stalls")]
    g, s = view.growth, view.summary
    if not g.window_sufficient:
        span_text = "unknown" if s.span_years is None else f"{s.span_years:.2f}"
        return blocks + [Paragraph(
            f"Insufficient data: growth needs at least {MIN_WINDOW_SAMPLES} snapshots spanning "
            f"{MIN_WINDOW_YEARS} GAME-YEAR (have {s.window_samples} spanning {span_text}).")]
    risers = [by_id[i] for i in g.risers]
    if risers:
        shown = risers[:10]
        blocks.append(Heading(3, "Fastest-growing towns"))
        blocks.append(Table(
            ["Town", "Capacity", "Change", "Growth", "Growth/yr", "Last change seen", "Line usage", "Stations"],
            [[r.name, _num_str(r.capacity), _signed(r.delta), _signed_pct(r.growth), _signed_pct(r.annual_growth),
              r.last_change or "-", _pct(r.usage), r.stations] for r in shown],
            ["left", "right", "right", "right", "right", "left", "right", "right"]))
        if len(risers) > len(shown):
            blocks.append(Paragraph(f"{len(risers) - len(shown)} further growing towns omitted."))
        blocks.append(Note("Observation", f"{len(risers)} of {g.comparable} towns gained capacity in the window; "
                           f"median growth is {_signed_pct(g.median_growth)}."))
    else:
        blocks.append(Paragraph("No town gained capacity in the window."))
    stalled = [by_id[i] for i in g.stalled]
    blocks.append(Heading(3, "Stalled towns (no net capacity gain in the window)"))
    if not stalled:
        blocks.append(Paragraph("No stalled towns in the window."))
        return blocks
    shown = stalled[:MAX_TABLE_ROWS]
    blocks.append(Table(
        ["Town", "Capacity", "Rank", "Stations", "Pax lines", "Line usage", "Cargo demands met", "Noise", "Situation"],
        [[r.name, _num_str(r.capacity), _rank_label(r), r.stations, r.lines_passenger, _pct(r.usage),
          _demands_met(r), _num_str(r.noise), _STALL_READINGS[r.reading]] for r in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right", "left"]))
    if len(stalled) > len(shown):
        blocks.append(Paragraph(f"{len(stalled) - len(shown)} smaller stalled towns omitted."))
    blocks.append(Note(
        "Observation", f"{len(stalled)} towns did not grow ({g.stalled_unserved} have none of our stations, "
        f"{g.stalled_served} do). A window of {s.span_years:.2f} calendar years is short; capacity arrives in steps, "
        "so a stall here is not proof of a lasting problem."))
    if g.large_served_stalled:
        names = ", ".join(by_id[i].name for i in g.large_served_stalled[:5])
        blocks.append(Note(
            "Suggestion", f"Look first at large towns we already serve that did not grow ({names}): inspect their "
            "line usage, which cargo demands are unmet (see the cargo section) and the authority ratings shown in "
            "the town window in-game; the snapshot does not collect the six ratings directly."))
    return blocks


def _coverage(view: TownsView, sized: list[TownRow], by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Coverage by our lines")]
    c = view.coverage_screen
    if not c.stations_known:
        return blocks + [Paragraph("Insufficient data: the snapshot lists no stations with a town assignment, so "
                                   "coverage by our lines cannot be verified.")]
    gaps = [by_id[i] for i in c.passenger_gaps]
    blocks.append(Note(
        "Method", "A town counts as touched by a line when a stop's station group is assigned to that town in "
        "stations[].town (verifiable from the snapshot). stations[] only lists station groups our lines use. A "
        "station assigned to town A may physically cover part of town B, and catchment radius is not collected, so "
        "a town can be reached without being listed [unverifiable]. [P] = line has passenger capacity in its "
        "vehicles, [F] = freight only."))
    if not gaps:
        blocks.append(Paragraph("Every town has at least one passenger line touching it."))
    else:
        shown = gaps[:MAX_TABLE_ROWS]
        blocks.append(Heading(3, "Towns without a passenger line"))
        blocks.append(Table(
            ["Town", "Capacity", "Rank", "Status", "Stations", "Freight lines", "Line usage", "Dev. active"],
            [[r.name, _num_str(r.capacity), _rank_label(r), "No station of ours" if not r.served else "Freight lines only",
              r.stations, r.lines_all - r.lines_passenger, _pct(r.usage),
              "-" if r.development is None else ("yes" if r.development else "no")] for r in shown],
            ["left", "right", "right", "left", "right", "right", "right", "right"]))
        if len(gaps) > len(shown):
            blocks.append(Paragraph(f"{len(gaps) - len(shown)} smaller towns omitted."))
        blocks.append(Note(
            "Observation", f"{c.gaps_unserved} of {len(sized)} towns have no station of ours ({_pct(c.gaps_unserved_share)} of "
            f"capacity); {len(gaps) - c.gaps_unserved} more are touched only by freight lines."))
    if c.zero_usage:
        blocks.append(Note(
            "Observation", "Passenger lines touch these towns but line usage is 0: "
            + ", ".join(f"{by_id[i].name} ({_num_str(by_id[i].capacity)})" for i in c.zero_usage[:8])
            + ". Possible reasons: the line was just built, or the station is far from the town's houses "
            "[INFERENCE; catchment is not collected]."))
    top = [by_id[i] for i in c.served_ranked[:12]]
    if top:
        blocks.append(Heading(3, "Lines touching the largest served towns"))
        blocks.append(Table(
            ["Town", "Rank", "Stations", "Pax lines", "Freight lines", "Examples ([P] passenger, [F] freight)"],
            [[r.name, _rank_label(r), r.stations, r.lines_passenger, r.lines_all - r.lines_passenger,
              _line_names(r, 3)] for r in top],
            ["left", "right", "right", "right", "right", "left"]))
    return blocks


def _usage_gap(view: TownsView, by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Large towns with low line usage")]
    gap = view.usage_gap
    if gap.code:
        return blocks + [Paragraph("Insufficient data: too few towns with capacity and line usage.")]
    low = [by_id[i] for i in gap.towns]
    if not low:
        return blocks + [Paragraph(f"No large town (upper {100 - int(LARGE_QUANTILE * 100)}% by capacity) is more "
                                   f"than {HEADROOM_MARGIN * 100:g} points below the {USAGE_CAP:.0%} usage cap.")]
    shown = low[:MAX_TABLE_ROWS]
    blocks.append(Paragraph(
        f"Large = upper {100 - int(LARGE_QUANTILE * 100)}% of towns by capacity. Ranked by capacity x headroom "
        f"(gap to the {USAGE_CAP:.0%} usage cap)."))
    blocks.append(Table(
        ["Town", "Capacity", "Residential", "Line usage", "Headroom", "Usage change", "Stations", "Pax lines"],
        [[r.name, _num_str(r.capacity), _num_str(r.capacities[0]) if r.capacities else "-", _pct(r.usage),
          _pct(r.headroom), _signed_pct(r.usage_change), r.stations, r.lines_passenger] for r in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right"]))
    if len(low) > len(shown):
        blocks.append(Paragraph(f"{len(low) - len(shown)} further towns omitted."))
    top = low[0]
    blocks.append(Note("Observation", f"{top.name} has the largest gap: capacity {_num_str(top.capacity)}, usage "
                       f"{_pct(top.usage)} against the {USAGE_CAP:.0%} cap, {top.lines_passenger} passenger line(s)."))
    blocks.append(Note(
        "Suggestion", "For these towns consider (manually) more or better-placed passenger stops, higher "
        "frequency, or a connection to another sizeable town; passenger trips to farther towns earn more XP "
        "than same-town trips (5/10/20 XP tiers, mechanics M2). Check the town's existing stops first: this "
        "report cannot see station position relative to the houses."))
    return blocks


def _cargo_demand(view: TownsView, by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Cargo demand: supply vs limit")]
    demand = view.cargo_demand
    if not demand.towns_with_demand:
        return blocks + [Paragraph("Insufficient data: towns report no cargoSupply entries.")]
    ranked = demand.by_cargo
    shown = ranked[:MAX_TABLE_ROWS]
    blocks.append(Heading(3, "By cargo"))
    blocks.append(Table(
        ["Cargo", "Towns demanding", "Towns with zero supply", "Supply", "Limit", "Supply / limit",
         "Producers on map", "Produced / yr", "Unshipped / yr"],
        [[c.cargo_name, c.towns, c.zero_supply_towns, _num_str(c.supply), _num_str(c.limit), _pct(c.ratio),
          c.producers, _unreported(c.produced_year, c.produced_unknown),
          _unreported(c.unshipped_year, c.unshipped_unknown)] for c in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right", "right"]))
    if len(ranked) > len(shown):
        blocks.append(Paragraph(f"{len(ranked) - len(shown)} further cargos omitted."))
    blocks.append(Heading(3, "Unmet demand in towns where we already have a station"))
    if not demand.served_towns:
        blocks.append(Paragraph("No town with cargo demand has a station of ours."))
    else:
        shown_t = demand.served_towns[:MAX_TABLE_ROWS]
        blocks.append(Table(
            ["Town", "Rank", "Demands met", "Supply", "Limit", "Supply / limit", "Largest unmet (cargo, gap)"],
            [[by_id[t.town_id].name, _rank_label(by_id[t.town_id]), _demands_met(by_id[t.town_id]),
              _num_str(t.supply), _num_str(t.limit), _pct(t.ratio),
              f"{t.largest_cargo_name} ({_num_str(t.largest_gap)})"] for t in shown_t],
            ["left", "right", "right", "right", "right", "right", "left"]))
        if len(demand.served_towns) > len(shown_t):
            blocks.append(Paragraph(f"{len(demand.served_towns) - len(shown_t)} further served towns omitted."))
    top = ranked[0]
    blocks.append(Note(
        "Observation", f"{demand.towns_receiving_none} of {demand.towns_with_demand} towns receive none of the cargo they demand. "
        f"Largest overall gap: {top.cargo_name} (supply {_num_str(top.supply)} against limit "
        f"{_num_str(top.limit)}, {top.zero_supply_towns} of {top.towns} towns at zero)."))
    if demand.idle_names:
        blocks.append(Note(
            "Observation", f"No industry currently produces {', '.join(demand.idle_names[:6])}"
            f"{' and others' if len(demand.idle_names) > 6 else ''} (produced per year is 0 in every output), and towns get none "
            "of it: these demands cannot be met until an upstream industry chain is producing them."))
    blocks.append(Note(
        "Inference", "Towns only add cargo demands after receiving some cargo, and delivered cargo gives growth XP "
        "(mechanics M2); an unmet demand is therefore both a possible freight market and a growth lever. Whether "
        "'limit' is a hard cap or annual demand is unverified. Producers/unshipped figures come from industries, "
        "not from where the cargo could physically be routed; towns have no coordinates in snapshots, so "
        "distances cannot be checked."))
    return blocks


def _hotspots(view: TownsView, by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Pollution and noise hot spots")]
    h = view.hotspots
    if not h.pollution and not h.noise:
        return blocks + [Paragraph("Insufficient data: no pollution or noise values in the snapshots.")]
    blocks.append(Paragraph("Ranked by value; units and thresholds are unverified, so only relative comparison and "
                            "change over the window are shown. 'Per 100 capacity' controls for town size."))
    for title, items, digits in (("Pollution", h.pollution, 0), ("Noise", h.noise, 1)):
        if not items:
            continue
        blocks.append(Heading(3, f"Highest {title.lower()}"))
        blocks.append(Table(
            ["Town", title, "Change", "Per 100 capacity", "Capacity", "Line usage", "Stations"],
            [[by_id[i.town_id].name, _num_str(i.value, digits), _signed(i.change, digits), _num_str(i.per_100_capacity, 1),
              _num_str(by_id[i.town_id].capacity), _pct(by_id[i.town_id].usage), by_id[i.town_id].stations]
             for i in items[:8]],
            ["left", "right", "right", "right", "right", "right", "right"]))
    p = h.pollution_summary
    if p is not None:
        top = by_id[p.town_id]
        text = (f"{top.name} has the highest pollution ({_num_str(p.value)}), {p.ratio_to_next:.1f}x the next town and "
                f"{p.ratio_to_median:.0f}x the median town." if p.ratio_to_next is not None
                else f"{top.name} has the highest pollution ({_num_str(p.value)}).")
        if p.relative_worst_id is not None:
            worst = by_id[p.relative_worst_id]
            text += (f" Relative to size the worst is {worst.name} "
                     f"({_num_str(worst.pollution)} for capacity {_num_str(worst.capacity)}).")
        blocks.append(Note("Observation", text))
    blocks.append(Note(
        "Inference", "Noise and pollution are two of the six authority ratings whose minimum scales growth XP "
        "(mechanics M2). The report cannot tell whether a hot spot is actually the limiting rating; compare with "
        "the in-game town ratings before acting. Industry and road traffic near a town, rather than our lines, "
        "may be the source."))
    return blocks


def _pairs(view: TownsView, by_id: dict[int, TownRow]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Large towns without a direct passenger line between them")]
    p = view.pairs
    if len(p.pool) < 2:
        return blocks + [Paragraph("Insufficient data: fewer than two towns with capacities.")]
    blocks.append(Paragraph(
        f"Pairs among the {len(p.pool)} largest towns. {p.linked_pairs} of those pairs already share a passenger line "
        f"(any two towns on the same passenger line count as linked); {len(p.pairs)} do not, of which "
        f"{p.separate_networks} are in separate passenger networks (no transfer route at all) and "
        f"{p.transfer_pairs} could be reached with a transfer."))
    if not p.pairs:
        return blocks + [Paragraph("Every pair of large towns already shares a passenger line.")]
    shown = p.pairs[:MAX_TABLE_ROWS]
    blocks.append(Table(
        ["Town A", "Town B", "Capacity A", "Capacity B", "Status", "Straight-line distance (km, estimate)"],
        [[by_id[x.town_a].name, by_id[x.town_b].name, _num_str(x.capacity_a), _num_str(x.capacity_b),
          _PAIR_STATUS[x.status], _num_str(x.distance_km, 1) if x.distance_km is not None else "unknown"]
         for x in shown],
        ["left", "left", "right", "right", "left", "right"]))
    if len(p.pairs) > len(shown):
        blocks.append(Paragraph(f"{len(p.pairs) - len(shown)} further pairs omitted."))
    if p.any_distance:
        blocks.append(Note("Estimate", "Distances are straight-line from town positions (metres assumed, as for "
                           "industries); real road, rail or air routes will be longer and terrain may block them."))
    else:
        blocks.append(Note(
            "Unverifiable", "Snapshots contain no town coordinates, so distances between towns cannot be computed "
            "and candidate pairs are ranked by combined capacity only. Pair viability (and passenger XP tier, "
            "which depends on distance) must be judged in-game."))
    blocks.append(Note(
        "Suggestion", "Pairs in separate networks are the cleanest candidates for a new manually-built passenger "
        "connection; transfer-only pairs are second choice (a direct line would shorten the trip). Confirm "
        "distance and terrain in-game first."))
    return blocks


def _key_findings(view: TownsView, sized: list[TownRow], by_id: dict[int, TownRow]) -> list[Any]:
    if not sized:
        return []
    notes: list[Any] = []
    for o in view.key_observations:
        r = by_id[o.town_id]
        if o.code == "unserved-towns":
            notes.append(Note(
                "Observation", f"{o.count} of {o.total} towns have no station of ours; the largest is "
                f"{r.name} (capacity {_num_str(r.capacity)}, rank {_rank_label(r)})."))
        elif o.code == "usage-gap":
            notes.append(Note(
                "Observation", f"{r.name} is a large town (capacity {_num_str(r.capacity)}, rank {_rank_label(r)}) with line "
                f"usage {_pct(r.usage)} against the {USAGE_CAP:.0%} cap, {r.stations} station(s) of ours and "
                f"{r.lines_passenger} passenger line(s)."))
        elif o.code == "stalled-large-served":
            notes.append(Note(
                "Observation", f"{r.name} (rank {_rank_label(r)}, {r.stations} stations, usage {_pct(r.usage)}) gained "
                f"no capacity in {o.span_years:.2f} GAME-YEAR while {o.count} of {o.total} towns did."))
        elif o.code == "fastest-growth":
            notes.append(Note("Observation", f"Fastest relative growth: {r.name} {_signed_pct(o.growth)} "
                              f"({_signed(o.delta)} capacity), line usage {_pct(r.usage)}."))
        elif o.code == "starved-served":
            notes.append(Note(
                "Observation", f"{r.name} (rank {_rank_label(r)}) has our stations but receives none of its "
                f"{o.total} demanded cargos ({', '.join(o.cargo_names)}); "
                f"{o.count} served town(s) get no cargo at all."))
    if not notes:
        notes.append(Paragraph("No standout findings yet."))
    return [Heading(2, "Key findings")] + notes


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(view: TownsView, *, context: EvaluationContext) -> ReportDocument:
    s = view.summary
    sized = [r for r in view.rows if r.capacity is not None]
    by_id = {r.id: r for r in view.rows}
    header = _base_header(context.snapshot, s.window_samples)
    window = f"{s.window_first.date} to {s.window_last.date}" if s.window_samples > 1 else s.window_first.date
    detail = "unknown GAME-YEAR span" if s.span_years is None else f"{s.span_years:.2f} GAME-YEAR"
    if s.span_days is not None:
        detail += f", {s.span_days:g} days by calendar anchors"
    header.insert(2, ("Town Sample Window", f"{window} ({detail})" if s.window_samples > 1 else window))
    header.append(("Town Data Notes", "Capacity sum is a population proxy; stations[] covers only station groups our "
                   "lines use; towns carry no coordinates."))
    basis = context.clock.time_basis
    header.extend([
        ("Calendar Time Basis", f"{basis['version']}; {DAYS_PER_YEAR} days/GAME-YEAR; {basis['anchorHash']}"),
        ("Calendar Scope", basis["isolation"]),
    ])

    blocks: list[Any] = [Note("Calendar Warning", warning) for warning in basis["warnings"]]
    if not view.rows:
        blocks.append(Paragraph("Insufficient data: the latest snapshot lists no towns."))
    else:
        blocks += _key_findings(view, sized, by_id)
        blocks += _proxy_section()
        blocks += _overview(view)
        blocks += _evolution(view)
        blocks += _league(view, sized)
        blocks += _growth(view, by_id)
        blocks += _coverage(view, sized, by_id)
        blocks += _usage_gap(view, by_id)
        blocks += _cargo_demand(view, by_id)
        blocks += _hotspots(view, by_id)
        blocks += _pairs(view, by_id)
    return ReportDocument("towns", "Towns Report", header, blocks)
