"""Report document model and pure renderers (Markdown and self-contained HTML).

Deterministic output, safe escaping across Markdown/HTML, and honest accounting:
- Rolling annual profits are never summed across snapshots or labeled calendar income.
- Every chart has an adjacent table containing the same numbers.
- Self-contained offline HTML: no <script>, no external href/src/url() dependencies.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from . import analysis, facts
from .snapshot import Snapshot
from .store import Store

VALID_KINDS = (
    "company", "lines", "fleet", "cargo", "decisions", "annual",
    "history", "vehicle-roi", "lines-history", "industries", "towns",
    "expansion", "bottlenecks", "methodology",
)


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------

@dataclass
class Heading:
    level: int
    text: str


@dataclass
class Paragraph:
    text: str


@dataclass
class Note:
    label: str
    text: str


@dataclass
class Table:
    columns: list[str]
    rows: list[list[Any]]
    align: list[str] = field(default_factory=list)


@dataclass
class Chart:
    kind: str  # "line", "bar", "pie"
    title: str
    categories: list[str]
    series: list[tuple[str, list[float]]]  # (label, points)


@dataclass
class ReportDocument:
    kind: str
    title: str
    header: list[tuple[str, str]]
    blocks: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Formatting & Escaping Helpers
# ---------------------------------------------------------------------------

def _escape_md(text: Any) -> str:
    s = str(text if text is not None else "-")
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    s = html.escape(s, quote=False)
    return re.sub(r"([\\`*_\[\]()!|])", r"\\\1", s)


def _escape_block(text: Any) -> str:
    """Escape text that starts a Markdown paragraph: also neutralise headings, quotes, lists, rules and fences."""
    s = _escape_md(text)
    s = re.sub(r"^(\s*)([#>+\-~=])", r"\1\\\2", s)
    return re.sub(r"^(\s*\d+)([.)])", r"\1\\\2", s)


def _clean_mermaid(text: Any, limit: int = 40) -> str:
    s = str(text if text is not None else "-").strip()
    s = re.sub(r'["`\[\](){}:;\n\r]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return (s[:limit - 1] + "…") if len(s) > limit else (s or "-")


def _fmt(val: Any) -> str:
    if val is None:
        return "-"
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, int):
        return f"{val:,}"
    if isinstance(val, float):
        return f"{val:,.2f}"
    return str(val)


def _fmt_pct(val: float | None) -> str:
    return "-" if val is None else f"{val * 100:.1f}%"


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_markdown(doc: ReportDocument) -> str:
    out: list[str] = [f"# {_escape_md(doc.title)}", ""]
    for k, v in doc.header:
        out.append(f"- **{_escape_md(k)}:** {_escape_md(v)}")
    out.append("")

    for b in doc.blocks:
        if isinstance(b, Heading):
            out.append(f"{'#' * b.level} {_escape_md(b.text)}\n")
        elif isinstance(b, Paragraph):
            out.append(f"{_escape_block(b.text)}\n")
        elif isinstance(b, Note):
            out.append(f"> **{_escape_md(b.label)}:** {_escape_md(b.text)}\n")
        elif isinstance(b, Table):
            cols = b.columns
            out.append("| " + " | ".join(_escape_md(c) for c in cols) + " |")
            align_row = []
            for i in range(len(cols)):
                a = b.align[i] if i < len(b.align) else "left"
                align_row.append(":---:" if a == "center" else ("---:" if a == "right" else ":---"))
            out.append("| " + " | ".join(align_row) + " |")
            for r in b.rows:
                out.append("| " + " | ".join(_escape_md(_fmt(v)) for v in r) + " |")
            out.append("")
        elif isinstance(b, Chart):
            out.append("```mermaid")
            if b.kind == "pie":
                out.append(f'pie title "{_clean_mermaid(b.title)}"')
                for cat, (_, pts) in zip(b.categories, b.series):
                    val = max(0, pts[0]) if pts else 0
                    if val > 0:
                        out.append(f'    "{_clean_mermaid(cat)}" : {val:.2f}')
            elif b.kind in ("line", "bar"):
                out.append("xychart-beta")
                out.append(f'    title "{_clean_mermaid(b.title)}"')
                cats = [_clean_mermaid(c, 20) for c in b.categories[:60]]
                out.append('    x-axis [' + ", ".join(f'"{c}"' for c in cats) + ']')
                for s_name, pts in b.series:
                    decimated = pts[:len(cats)]
                    out.append(f'    {b.kind} [' + ", ".join(f"{p:.2f}" for p in decimated) + ']')
            out.append("```\n")
    return "\n".join(out).strip() + "\n"


def render_html(doc: ReportDocument) -> str:
    body: list[str] = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        '<meta charset="utf-8">',
        f'<title>{html.escape(doc.title)}</title>',
        "<style>",
        ":root { --c1: #2563eb; --c2: #f59e0b; --c3: #10b981; --c4: #a855f7; --c5: #ef4444; --c6: #06b6d4; }",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; "
        "margin: 2rem auto; max-width: 1040px; line-height: 1.5; color: #1e293b; background: #ffffff; padding: 0 1rem; }",
        "h1, h2, h3 { color: #0f172a; margin-top: 1.8rem; margin-bottom: 0.6rem; }",
        "h1 { border-bottom: 2px solid #e2e8f0; padding-bottom: 0.4rem; }",
        "ul.header { list-style: none; padding: 0; margin-bottom: 2rem; background: #f8fafc; border: 1px solid #e2e8f0; "
        "border-radius: 6px; padding: 1rem; }",
        "ul.header li { margin: 0.3rem 0; }",
        "table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; font-size: 0.95rem; }",
        "th, td { border: 1px solid #cbd5e1; padding: 0.5rem 0.75rem; text-align: left; }",
        "th { background: #f1f5f9; font-weight: 600; }",
        ".right { text-align: right; }",
        ".center { text-align: center; }",
        ".note { border-left: 4px solid #3b82f6; background: #eff6ff; padding: 0.75rem 1rem; margin: 1rem 0; "
        "border-radius: 0 4px 4px 0; }",
        ".svg-chart { margin: 1.5rem 0; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem; background: #fafafa; }",
        "@media (prefers-color-scheme: dark) {",
        "  :root { --c1: #60a5fa; --c2: #fbbf24; --c3: #34d399; --c4: #c084fc; --c5: #f87171; --c6: #22d3ee; }",
        "  body { background: #0f172a; color: #cbd5e1; }",
        "  h1, h2, h3 { color: #f8fafc; }",
        "  h1 { border-bottom-color: #334155; }",
        "  ul.header { background: #1e293b; border-color: #334155; }",
        "  th { background: #1e293b; }",
        "  th, td { border-color: #334155; }",
        "  .note { background: #1e293b; border-left-color: #60a5fa; color: #e2e8f0; }",
        "  .svg-chart { background: #1e293b; border-color: #334155; }",
        "}",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(doc.title)}</h1>",
        '<ul class="header">',
    ]
    for k, v in doc.header:
        body.append(f"  <li><strong>{html.escape(k)}:</strong> {html.escape(str(v))}</li>")
    body.append("</ul>")

    for b in doc.blocks:
        if isinstance(b, Heading):
            lvl = min(max(b.level, 1), 6)
            body.append(f"<h{lvl}>{html.escape(b.text)}</h{lvl}>")
        elif isinstance(b, Paragraph):
            body.append(f"<p>{html.escape(b.text)}</p>")
        elif isinstance(b, Note):
            body.append(f'<div class="note"><strong>{html.escape(b.label)}:</strong> {html.escape(b.text)}</div>')
        elif isinstance(b, Table):
            body.append("<table>")
            body.append("  <thead><tr>")
            for i, col in enumerate(b.columns):
                cls = f' class="{b.align[i]}"' if i < len(b.align) and b.align[i] != "left" else ""
                body.append(f"    <th{cls}>{html.escape(col)}</th>")
            body.append("  </tr></thead>")
            body.append("  <tbody>")
            for r in b.rows:
                body.append("  <tr>")
                for i, v in enumerate(r):
                    cls = f' class="{b.align[i]}"' if i < len(b.align) and b.align[i] != "left" else ""
                    body.append(f"    <td{cls}>{html.escape(_fmt(v))}</td>")
                body.append("  </tr>")
            body.append("  </tbody></table>")
        elif isinstance(b, Chart):
            body.append(f'<div class="svg-chart">{_render_svg(b)}</div>')

    body.extend(["</body>", "</html>"])
    return "\n".join(body) + "\n"


def _render_svg(chart: Chart) -> str:
    title_esc = html.escape(chart.title)
    if chart.kind == "bar":
        cats = chart.categories[:20]
        points = chart.series[0][1][:len(cats)] if chart.series else []
        max_val = max([abs(p) for p in points] + [1.0])
        h = max(160, len(cats) * 26 + 60)
        svg = [f'<svg viewBox="0 0 600 {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg">',
               f'<title>{title_esc}</title>',
               f'<text x="20" y="24" font-weight="bold" font-size="14" fill="currentColor">{title_esc}</text>']
        for i, (cat, val) in enumerate(zip(cats, points)):
            y = 45 + i * 24
            bar_w = int((abs(val) / max_val) * 260)
            fill = "#3b82f6" if val >= 0 else "#ef4444"
            cat_esc = html.escape(cat)
            svg.append(f'<text x="20" y="{y + 13}" font-size="11" fill="currentColor">{cat_esc}</text>')
            svg.append(f'<rect x="220" y="{y}" width="{bar_w}" height="16" fill="{fill}" rx="2"/>')
            svg.append(f'<text x="{225 + bar_w}" y="{y + 12}" font-size="10" fill="currentColor">{_fmt(val)}</text>')
        svg.append('</svg>')
        return "\n".join(svg)

    if chart.kind == "line":
        cats = chart.categories[:60]
        series = [(label, values[:len(cats)]) for label, values in chart.series]
        values = [value for _, points in series for value in points]
        if not values or len(cats) < 2:
            return f'<svg viewBox="0 0 600 100" xmlns="http://www.w3.org/2000/svg"><title>{title_esc}</title><text x="20" y="40" fill="currentColor">{title_esc} (insufficient points)</text></svg>'
        min_v, max_v = min(values), max(values)
        span = (max_v - min_v) or 1.0
        svg = ['<svg viewBox="0 0 600 230" width="100%" height="230" xmlns="http://www.w3.org/2000/svg">',
               f'<title>{title_esc}</title>',
               f'<text x="20" y="20" font-weight="bold" font-size="14" fill="currentColor">{title_esc}</text>',
               f'<text x="10" y="45" font-size="10" fill="currentColor">{_fmt(max_v)}</text>',
               f'<text x="10" y="165" font-size="10" fill="currentColor">{_fmt(min_v)}</text>']
        for index, (label, points) in enumerate(series):
            coords = [f"{65 + i * (495 / (len(cats) - 1)):.1f},{160 - ((value - min_v) / span) * 120:.1f}"
                      for i, value in enumerate(points)]
            color = f"var(--c{index % 6 + 1})"
            svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{" ".join(coords)}"/>')
            svg.append(f'<text x="{65 + index * 160}" y="215" font-size="12" fill="{color}">{html.escape(label)}</text>')
        svg.extend([
            f'<text x="65" y="185" font-size="10" fill="currentColor">{html.escape(cats[0])}</text>',
            f'<text x="560" y="185" text-anchor="end" font-size="10" fill="currentColor">{html.escape(cats[-1])}</text>',
            '</svg>'
        ])
        return "\n".join(svg)

    if chart.kind == "pie":
        slices = [(category, max(0, points[0])) for category, (_, points) in zip(chart.categories, chart.series) if points]
        total = sum(value for _, value in slices)
        svg = ['<svg viewBox="0 0 600 240" width="100%" height="240" xmlns="http://www.w3.org/2000/svg">',
               f'<title>{title_esc}</title>',
               f'<text x="20" y="20" font-size="14" fill="currentColor">{title_esc}</text>']
        angle = -math.pi / 2
        for index, (label, value) in enumerate(slices):
            if value == 0:
                continue
            end = angle + 2 * math.pi * value / total
            color = f"var(--c{index % 6 + 1})"
            if value == total:
                svg.append(f'<circle cx="120" cy="130" r="80" fill="{color}"/>')
            else:
                x1, y1 = 120 + 80 * math.cos(angle), 130 + 80 * math.sin(angle)
                x2, y2 = 120 + 80 * math.cos(end), 130 + 80 * math.sin(end)
                svg.append(f'<path d="M120,130 L{x1:.2f},{y1:.2f} A80,80 0 {int(value / total > .5)},1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>')
            svg.append(f'<text x="230" y="{55 + index * 24}" font-size="12" fill="{color}">{html.escape(label)}: {_fmt(value)} ({value / total:.1%})</text>')
            angle = end
        if total == 0:
            svg.append('<text x="20" y="60" fill="currentColor">No positive values to plot.</text>')
        svg.append('</svg>')
        return "\n".join(svg)

    raise ValueError(f"Unknown chart kind: {chart.kind}")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _base_header(snap: Snapshot, count: int) -> list[tuple[str, str]]:
    return [
        ("Company / Save", snap.company.get("name") or "Primary Company"),
        ("Latest Sample Date", snap.date_label),
        ("Snapshots Used", str(count)),
        ("Collection Errors", "; ".join(snap.errors) if snap.errors else "None reported"),
        ("Measurement Limits", "Load is instantaneous; annual profit is a rolling window; transportedYear accounting is unverified."),
    ]


def _header(h: facts.Header) -> list[tuple[str, str]]:
    return [
        ("Company / Save", h.company),
        ("Latest Sample Date", h.date_label),
        ("Snapshots Used", str(h.samples_used)),
        ("Collection Errors", "; ".join(h.errors) if h.errors else "None reported"),
        ("Measurement Limits", "Load is instantaneous; annual profit is a rolling window; transportedYear accounting is unverified."),
    ]


def _fmt_delta(change: int | float | None) -> str:
    """Display form of a delta the analysis layer already computed."""
    if change is None:
        return "-"
    return f"{'+' if change > 0 else ''}{_fmt(change)}"


def _line_label(row: dict[str, Any]) -> str:
    return row.get("name") or f"Line #{row['id']}"


def _finance_chart(title: str, points: Sequence[facts.FinancePoint]) -> Chart | None:
    """Balance/loan chart over the samples where both are known; the table keeps every sample."""
    known = [p for p in points if p.balance is not None and p.loan is not None]
    if len(known) < 2:
        return None
    return Chart("line", title, [p.date_label for p in known],
                 [("Balance", [float(p.balance) for p in known]), ("Loan", [float(p.loan) for p in known])])


def _build_company_report(data: facts.CompanyFacts) -> ReportDocument:
    ind = {i.key: i for i in data.indicators}

    def row(label: str, key: str, previous: bool = True) -> list[Any]:
        i = ind[key]
        if key in ("balance", "loan"):
            return [label, i.current, _fmt_delta(i.since_previous), _fmt_delta(i.since_year_ago)]
        if key in ("lines", "vehicles"):
            return [label, i.current, i.since_previous, i.since_year_ago]
        return [label, i.current, None, None]

    blocks: list[Any] = [
        Heading(2, "Company Status"),
        Paragraph("Operational standing and rolling annual totals at the latest snapshot sample."),
        Table(["Indicator", "Value", "Previous Sample Change", "Year-Ago Change"],
              [row("Cash Balance", "balance"), row("Outstanding Loan", "loan"),
               row("Net Position (Balance - Loan)", "net_position"), row("Company Value", "company_value"),
               row("Lines", "lines"), row("Vehicles", "vehicles"),
               row("Total Rolling Annual Line Profit", "lines_profit_year")],
              ["left", "right", "right", "right"]),
        Note("Semantics Notice", "Annual line profit is a rolling 12-month figure at this sample date, not a calendar sum."),
    ]
    modal = data.modal
    if modal:
        blocks.extend([
            Heading(2, "Results by Transport Mode"),
            Table(["Mode", "Lines", "Vehicles", "Rolling Annual Profit", "Profit / Vehicle", "Losing Lines"],
                  [[m["carrier"], m["lines"], m["vehicles"], m["profitYear"], m["profitPerVehicle"], m["losingLines"]] for m in modal],
                  ["left", "right", "right", "right", "right", "right"]),
            Chart("bar", "Annual Profit by Mode", [m["carrier"] for m in modal],
                  [("Profit", [float(m["profitYear"]) for m in modal])]),
            Chart("pie", "Vehicle Mix by Mode", [m["carrier"] for m in modal],
                  [(m["carrier"], [float(m["vehicles"])]) for m in modal]),
        ])
    if len(data.history) > 1:
        blocks.extend([Heading(2, "Financial Sample History"),
                       Table(["Date", "Balance", "Loan"], [[p.date_label, p.balance, p.loan] for p in data.history],
                             ["left", "right", "right"])])
        chart = _finance_chart("Balance and Loan History", data.history)
        if chart:
            blocks.append(chart)
    else:
        blocks.append(Note("History Notice", "Only a single snapshot sample exists; historical trend charts are omitted."))
    blocks.append(Note("Calendar baseline", f"At/before 365.25 calendar days ago: {data.year_ago_date or 'unavailable'}; "
                       f"actual elapsed GAME-YEAR: {data.elapsed_game_years}. Rolling finance values are unchanged; "
                       "this calendar comparison does not prove a complete profitYear query window."))
    return ReportDocument("company", "Company Performance Report", _header(data.header), blocks)


def _line_table(rows: Sequence[dict[str, Any]]) -> Table:
    return Table(["Line", "Carrier", "Vehicles", "Rolling Annual Profit", "Load (Instant)"],
                 [[_line_label(r), r["carrier"], r["vehicles"], r["profitYear"], _fmt_pct(r["load"])] for r in rows],
                 ["left", "left", "right", "right", "right"])


def _build_lines_report(data: facts.LinesFacts) -> ReportDocument:
    n = len(data.ranked)
    top_n = min(15, n)
    top_rows = data.ranked[:top_n]
    bottom_n = min(15, n - top_n)
    bottom_rows = data.ranked[-bottom_n:] if bottom_n else []
    blocks: list[Any] = [Heading(2, f"Most Profitable Lines ({len(top_rows)})"), _line_table(top_rows)]
    if bottom_rows:
        blocks.extend([Heading(2, f"Least Profitable Lines ({len(bottom_rows)})"), _line_table(bottom_rows)])
    if data.losing:
        blocks.extend([Heading(2, "Loss-Making Lines and Identified Findings"),
                       Table(["Line", "Rolling Annual Loss", "Finding Codes"],
                             [[_line_label(r), r["profitYear"], ", ".join(codes) or "unspecified"] for r, codes in data.losing],
                             ["left", "right", "left"])])
    if data.empty:
        blocks.extend([Heading(2, "Lines Without Vehicles"),
                       Table(["Line", "Stops", "Rate"], [[_line_label(r), r["stops"], r["rate"]] for r in data.empty],
                             ["left", "right", "right"])])
    if data.no_stop_pair:
        blocks.extend([Heading(2, "Lines Without a Usable Stop Pair"),
                       Table(["Line", "Stops", "Vehicles"], [[_line_label(r), r["stops"], r["vehicles"]] for r in data.no_stop_pair])])
    if data.trends:
        blocks.extend([
            Heading(2, "Occupancy Sample Trends"),
            Paragraph(f"Derived from {data.samples} recent snapshot sample points (sample index slope, not time averages)."),
            Table(["Line", "Mean Sampled Occupancy", "Latest Occupancy", "Samples", "Occupancy Slope / Sample", "Status"],
                  [[t["name"], _fmt_pct(t["meanLoad"]), _fmt_pct(t["latestLoad"]), t["samples"], t["slope"], t["status"]]
                   for t in data.trends],
                  ["left", "right", "right", "right", "right", "left"]),
        ])
    return ReportDocument("lines", "Lines Performance Report", _header(data.header), blocks)


def _build_fleet_report(data: facts.FleetFacts) -> ReportDocument:
    blocks: list[Any] = [
        Heading(2, "Loss-Making Vehicles"),
        Table(["Vehicle", "Line", "Carrier", "Age (GAME-YEAR)", "Rolling Annual Profit", "Value"],
              [[r["name"] or f"Vehicle #{r['id']}", r["lineName"] or "Unassigned", r["carrier"], r["ageYears"], r["profitYear"], r["value"]]
               for r in data.losing[:20]],
              ["left", "left", "left", "right", "right", "right"]),
        Heading(2, "Fleet Age and Model Lifespan"),
        Table(["Vehicle", "Age (GAME-YEAR)", "Models", "Model Lifespan (Raw Units)"],
              [[r["name"] or f"Vehicle #{r['id']}", r["ageYears"], ", ".join(r["models"]) or "Unknown",
                ", ".join(_fmt(span) for span in spans) or "Unknown"] for r, spans in data.aging]),
        Note("Unit Limit", "Model lifespan units are unverified; no age/lifespan ratio or expiry claim is inferred."),
    ]
    if data.catalog_date:
        blocks.extend([
            Heading(2, "Stored Catalog Models No Longer in Production"),
            Table(["Model", "Carrier", "Retirement Year"],
                  [[m.get("name") or m.get("res") or f"Model #{m.get('id')}", m.get("carrier"), m["yearTo"]]
                   for m in data.retired_models]),
            Note("Catalog Coverage", f"Catalog sampled on {data.catalog_date}; models absent from that sample cannot be classified."),
        ])
    if data.idle_in_depot:
        blocks.extend([
            Heading(2, "Idle Capital in Depots"),
            Table(["Vehicle", "Depot", "Days In Depot", "Recorded Asset Value"],
                  [[r["name"] or f"Vehicle #{r['id']}", r["depotName"], r["daysInDepot"], r["value"]] for r in data.idle_in_depot],
                  ["left", "left", "right", "right"]),
            Paragraph(f"Known tied-up capital in depots: {_fmt(data.idle_value_known)} recorded currency units"
                      + (f"; {data.idle_value_unknown} vehicle(s) have no recorded value, so this is a known subtotal."
                         if data.idle_value_unknown else ".")),
        ])
    fit = data.fit
    blocks.append(Heading(2, "Fleet Fit Analysis"))
    if fit["status"] == "unavailable":
        blocks.append(Note("Analysis Pending", f"{fit['reason']} Catalog fitness requires verified units."))
    else:
        blocks.append(Table(
            ["Vehicle", "Current Model", "Main Cargo", "Score", "Best Replacement", "Potential Improvement", "Better Available"],
            [[r["vehicle"], r["model"], r["cargo"], r["score"], r["alternative"], _fmt_pct(r["improvement"]), r["better"]]
             for r in fit.get("rows", [])[:25]],
            ["left", "left", "left", "right", "left", "right", "center"]))
    return ReportDocument("fleet", "Fleet Composition and Capital Report", _header(data.header), blocks)


def _build_cargo_report(data: facts.CargoFacts) -> ReportDocument:
    blocks: list[Any] = []
    percent = f"{data.full_stock_ratio * 100:g}%"
    if data.full_stocks:
        blocks.extend([
            Heading(2, f"Stocks Near Capacity (≥{percent} Full)"),
            Table(["Facility", "Kind", "Cargos", "Count", "Capacity", "Fill Ratio", "Actively Served"],
                  [[r["name"], r["kind"], ", ".join(r["cargoNames"]), r["count"], r["capacity"], _fmt_pct(r["fill"]),
                    "Yes" if r["served"] else ("No" if r["served"] is False else "-")] for r in data.full_stocks],
                  ["left", "left", "left", "right", "right", "right", "center"]),
        ])
    else:
        blocks.append(Paragraph(f"No stocks currently exceed the {percent} fullness threshold."))
    if data.unshipped:
        blocks.extend([
            Heading(2, "Unshipped Production Opportunities"),
            Table(["Producer", "Cargo", "Produced / Year", "Shipped / Year", "Unshipped / Year", "Nearest Consumer", "Distance (km)"],
                  [[o["producer"]["name"] or f"Industry #{o['producer']['id']}", o["cargo"], o["producedYear"], o["shippedYear"],
                    o["unshippedYear"], o["nearestConsumers"][0]["name"] if o["nearestConsumers"] else "None",
                    o["nearestConsumers"][0]["distanceKm"] if o["nearestConsumers"] else None] for o in data.unshipped[:15]],
                  ["left", "left", "right", "right", "right", "left", "right"]),
            Note("Feasibility Boundary", "Straight-line distance does not promise transport feasibility or rail route availability."),
        ])
    if data.closing:
        blocks.extend([
            Heading(2, "Scheduled Industry Closures"),
            Table(["Industry", "Type", "Closing Timestamp"],
                  [[ind.get("name") or f"Industry #{ind['id']}", ind.get("type", "-"), ind.get("closureTimeStamp", "Flagged")]
                   for ind in data.closing],
                  ["left", "left", "left"]),
        ])
    return ReportDocument("cargo", "Cargo Production and Flow Report", _header(data.header), blocks)


def _decision_details(item: facts.DecisionComparison) -> list[Any]:
    decision = item.decision
    blocks: list[Any] = [
        Heading(3, f"Decision #{decision['id']}: {decision['title']}"),
        Paragraph(f"Rationale: {decision['rationale']}"),
        Note("Calendar elapsed", f"elapsedGameYears={item.elapsed_game_years}; {item.elapsed_reason}; GAME-YEAR"),
        Note("Nominal query-window diagnostic", f"elapsedNominalWindows={item.elapsed_nominal_windows}; "
                                                "not proof of a complete profitYear window or causality."),
    ]
    rows = []
    for entity in item.entities:
        if not entity.resolved:
            rows.append([entity.reference, "Unresolved or no longer tracked", None, None, None])
            continue
        if entity.removed:
            blocks.append(Note("Entity Removed", f"{entity.name}: entity no longer exists in the comparison snapshot."))
        for m in entity.metrics:
            rows.append([entity.name, m.metric, m.before, m.after, _fmt_delta(m.change)])
    if rows:
        blocks.append(Table(["Entity", "Metric", f"Decision Sample ({item.baseline_date or 'unavailable'})",
                             f"Comparison Sample ({item.comparison_date})", "Difference"], rows))
    return blocks


def _decision_table(decisions: Sequence[dict[str, Any]], align: list[str] | None = None) -> Table:
    return Table(["ID", "Game Date", "Title", "Status", "Outcome"],
                 [[d["id"], d.get("game_date") or "-", d["title"], d["status"], d.get("outcome") or "-"] for d in decisions],
                 align or [])


def _build_decisions_report(data: facts.DecisionsFacts) -> ReportDocument:
    blocks: list[Any] = []
    if not data.decisions:
        blocks.append(Paragraph("No player decisions have been recorded in the journal."))
    else:
        blocks.append(Heading(2, "Recorded Decisions Journal"))
        blocks.append(_decision_table(data.decisions))
        for item in data.comparisons:
            blocks.extend(_decision_details(item))
    return ReportDocument("decisions", "Decisions Follow-Up Report", _header(data.header), blocks)


def _compared_row(c: facts.Compared, count: bool = False) -> list[Any]:
    return [c.label, c.baseline, c.closing, c.change if count else _fmt_delta(c.change)]


def _names(items: Sequence[dict[str, Any]], kind: str) -> str:
    return ", ".join(i.get("name") or f"{kind} #{i['id']}" for i in items) or "None"


def _build_annual_report(data: facts.AnnualFacts) -> ReportDocument:
    year = data.year
    status = "monthly coverage complete" if data.complete_monthly else "partial-year coverage"
    if data.in_progress:
        status += f"; in progress through {data.closing_date}; figures to date"
    if data.future_history:
        status += "; retained future history indicates a timeline rewind"
    header = [
        ("Company / Save", data.header.company),
        ("Reporting Game Year", str(year)),
        ("Coverage Assessment", status),
        ("Baseline Sample", data.baseline_date or "None (history starts mid-year)"),
        ("Closing Sample", data.closing_date),
        ("Observed Sample Dates", ", ".join(data.observed_dates)),
        ("Missing Calendar Months", ", ".join(str(m) for m in data.missing_months) if data.missing_months else "None"),
        ("Snapshots Used", str(data.samples_used)),
        ("Collection Errors", "; ".join(data.header.errors) if data.header.errors else "None reported"),
    ]
    cash, loan, lines, vehicles = data.financial
    profit_note = (f" ({data.closing_profit_unknown_lines} line(s) without a recorded profit are excluded)"
                   if data.closing_profit_unknown_lines else "")
    blocks: list[Any] = [
        Heading(2, f"Financial Summary ({status})"),
        Paragraph("Closing numbers reflect single snapshot samples. Total line profit is the sum of rolling 12-month line profits "
                  "at closing sample, not a calendar-year income sum." + (f" Known subtotal only{profit_note}." if profit_note else "")),
        Table(["Metric", f"Baseline ({data.baseline_label})", f"Closing ({data.closing_date})", "Net Change"],
              [_compared_row(cash), _compared_row(loan), _compared_row(lines, True), _compared_row(vehicles, True),
               ["Closing Rolling Annual Line Profit", None, data.closing_profit_known, None]],
              ["left", "right", "right", "right"]),
    ]
    ranked = data.ranked_lines
    best_5 = ranked[:5]
    worst_5 = ranked[-5:] if len(ranked) > 5 else []
    blocks.extend([
        Heading(2, "Top 5 Lines by Closing Annual Profit"),
        Table(["Line", "Rolling Annual Profit"], [[_line_label(l), l.get("profitYear")] for l in best_5], ["left", "right"]),
        Heading(2, "Bottom 5 Lines by Closing Annual Profit"),
        Table(["Line", "Rolling Annual Profit"], [[_line_label(l), l.get("profitYear")] for l in worst_5], ["left", "right"]),
        Heading(2, "Fleet and Network Adjustments"),
        Table(["Category", "Entities Added", "Entities Removed"],
              [["Lines", _names(data.lines_added, "Line"), _names(data.lines_removed, "Line")],
               ["Vehicles", _names(data.vehicles_added, "Vehicle"), _names(data.vehicles_removed, "Vehicle")]],
              ["left", "left", "left"]),
        Heading(2, "Modal Mix Adjustments"),
        Table(["Mode", "Baseline Lines", "Closing Lines", "Baseline Vehicles", "Closing Vehicles",
               "Baseline Annual Profit", "Closing Annual Profit", "Profit Change"],
              [[m.carrier, m.baseline_lines, m.closing_lines, m.baseline_vehicles, m.closing_vehicles,
                m.baseline_profit, m.closing_profit, _fmt_delta(m.profit_change)] for m in data.modal],
              ["left", "right", "right", "right", "right", "right", "right", "right"]),
        Heading(2, f"Year-over-Year Comparison with {data.previous_year}"),
    ])
    if data.yoy is None:
        blocks.append(Paragraph("no previous-year data"))
    else:
        rows = [_compared_row(c, c.label in ("Lines", "Vehicles")) for c in data.yoy]
        rows.append(["Best Line", data.yoy_best_line[0], data.yoy_best_line[1], None])
        blocks.append(Table(["Metric", f"{data.previous_year} Closing", f"{year} Closing", "Difference"], rows,
                            ["left", "right", "right", "right"]))
    blocks.append(Heading(2, f"Decisions Recorded in {year}"))
    if data.decisions:
        blocks.append(_decision_table([c.decision for c in data.decisions], ["right", "left", "left", "left", "left"]))
        for item in data.decisions:
            blocks.extend(_decision_details(item))
    else:
        blocks.append(Paragraph(f"no decisions were recorded in {year}"))
    blocks.append(Heading(2, "High-Severity Closing Findings"))
    if data.high_findings:
        blocks.append(Table(["Code", "Category", "Title", "Detail"],
                            [[f["code"], f["category"], f["title"], f["detail"]] for f in data.high_findings],
                            ["left", "left", "left", "left"]))
    else:
        blocks.append(Paragraph("No high-severity findings recorded at closing sample."))
    blocks.extend([Heading(2, "Sampled Financial Timeline"),
                   Table(["Date", "Balance", "Loan"], [[p.date_label, p.balance, p.loan] for p in data.timeline],
                         ["left", "right", "right"])])
    chart = _finance_chart(f"{year} Balance and Loan History", data.timeline)
    if chart:
        blocks.append(chart)
    return ReportDocument("annual", f"Annual Company Report ({year})", header, blocks)


# ---------------------------------------------------------------------------
# Public Report Generation Entry Point
# ---------------------------------------------------------------------------

def render_report(store: Store, kind: str, year: int | None = None, html: bool = False,
                  thresholds: analysis.Thresholds | None = None, lens: Any = None, context=None) -> str:
    """Pure in-memory report generation without disk writing or service dependency."""
    doc = compose_report(store, kind, year, thresholds=thresholds, lens=lens, context=context)
    return render_html(doc) if html else render_markdown(doc)


def compose_report(store: Store, kind: str, year: int | None = None,
                   thresholds: analysis.Thresholds | None = None, lens: Any = None, context=None) -> ReportDocument:
    """Compose a report document once; Markdown and HTML are separate pure renderings of it."""
    from .report_policy import resolve_context, REGISTRY
    if lens is not None and (thresholds is not None or context is not None):
        raise ValueError("lens and explicit thresholds/context are mutually exclusive")
    if context is not None and thresholds is not None:
        raise ValueError("context and explicit thresholds are mutually exclusive")
    context = lens.report_context if lens else context or resolve_context(thresholds=thresholds)
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 0 <= year <= 2**63 - 1):
        raise ValueError("year must be a nonnegative 64-bit integer.")
    if year is not None and kind != "annual":
        raise ValueError("year applies only to annual reports.")
    if kind not in VALID_KINDS:
        raise ValueError(f"Unknown report kind '{kind}'. Valid kinds: {', '.join(VALID_KINDS)}")

    endpoint = store.latest()
    if endpoint is None and kind != "methodology":
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    if endpoint is not None:
        from .analysis_views import EvaluationContext, EvidenceReader
        operation = (EvaluationContext.from_lens(lens, None, store.previous_of(endpoint)) if lens is not None else
                     EvaluationContext(endpoint, context, store.time_context(endpoint), None, store.previous_of(endpoint)))
        reader = EvidenceReader(store, operation)
    methodology = lens.methodology if lens else None
    if kind == "company":
        doc = _build_company_report(facts.company_facts(reader, operation))
    elif kind == "lines":
        doc = _build_lines_report(facts.lines_facts(reader, operation, methodology))
    elif kind == "fleet":
        doc = _build_fleet_report(facts.fleet_facts(reader, operation))
    elif kind == "cargo":
        doc = _build_cargo_report(facts.cargo_facts(reader, operation))
    elif kind == "decisions":
        doc = _build_decisions_report(facts.decisions_facts(reader, operation))
    elif kind == "annual":
        doc = _build_annual_report(facts.annual_facts(reader, operation, year, methodology))
    elif kind == "methodology":
        from . import report_methodology

        if lens is None:
            raise ValueError("The methodology report presents an evaluated methodology: pass the prepared lens.")
        doc = report_methodology.build(lens)
    else:
        # Local imports keep presentation builders free to reuse the document model. Each builder
        # renders the typed view that its family evaluated at the latest stored endpoint.
        from importlib import import_module
        from .analysis_views import evaluate_views

        views = evaluate_views(store, operation, (kind,))
        module = import_module(f"{__package__}.report_{kind.replace('-', '_')}")
        doc = module.build(getattr(views, kind.replace("-", "_")), context=operation)

    if endpoint is not None:
        basis = operation.clock.time_basis
        doc.header.extend([("Time Basis", f"{basis['version']}; 365.25 calendar days / GAME-YEAR"),
                           ("Calendar Anchor Hash", basis["anchorHash"])])
        doc.blocks.append(Note("Calendar evidence", " ".join(basis["warnings"]) or "Bounded calendar evidence; interpolation is an estimate."))
    doc.header.append(("Report Policy Registry", "1"))
    doc.blocks.append(Heading(2, "Report policy"))
    families = list(REGISTRY) if kind == "methodology" else [kind] if kind in REGISTRY else []
    rows = [[family + "." + key, getattr(context.policies[family], key), spec.unit,
             context.origins[family][key], spec.comparison]
            for family in families for key, spec in REGISTRY[family].items()]
    rows += [["engine." + key, value, "engine criterion", context.threshold_origins[key], "effective shared threshold"]
             for key, value in context.provenance()["engineThresholds"].items()]
    doc.blocks.append(Table(["Criterion", "Value", "Unit", "Origin", "Comparison"], rows))
    if lens is not None and kind != "methodology":
        doc.header.extend(lens.header())
    return doc
