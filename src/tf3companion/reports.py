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

from . import analysis
from .snapshot import Snapshot
from .store import Store

VALID_KINDS = ("company", "lines", "fleet", "cargo", "decisions", "annual")


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
    s = html.escape(s.replace("\n", " ").replace("\r", " "), quote=False)
    return re.sub(r"([\\`*_\[\]()!|])", r"\\\1", s)


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


def _fmt_change(curr: int | float | None, prev: int | float | None) -> str:
    if curr is None or prev is None:
        return "-"
    diff = curr - prev
    return f"{'+' if diff > 0 else ''}{_fmt(diff)}"


def _entity_name(entity: dict[str, Any] | None, kind: str = "Entity") -> str:
    if not entity:
        return f"{kind} #unknown"
    return entity.get("name") or f"{kind.title()} #{entity.get('id', 'unknown')}"


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
            out.append(f"{_escape_md(b.text)}\n")
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


def _recent_current(store: Store, limit: int) -> list[Snapshot]:
    latest = store.latest()
    if latest is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    return store.recent_snapshots(limit=limit, game_time=latest.game_time)


def _build_company_report(store: Store) -> ReportDocument:
    snaps = _recent_current(store, 36)
    if not snaps:
        raise ValueError("no snapshot found")
    latest = snaps[-1]
    prev = snaps[-2] if len(snaps) > 1 else None
    y_ago = None
    if latest.date:
        for s in reversed(snaps):
            if s.date and s.date.get("year") == latest.date["year"] - 1 and s.date.get("month") == latest.date["month"]:
                y_ago = s
                break

    ov = analysis.company_overview(latest, prev)
    c = latest.company
    blocks: list[Any] = [
        Heading(2, "Company Status"),
        Paragraph("Operational standing and rolling annual totals at the latest snapshot sample."),
        Table(
            ["Indicator", "Value", "Previous Sample Change", "Year-Ago Change"],
            [
                ["Cash Balance", c.get("balance"), _fmt_change(c.get("balance"), prev.company.get("balance") if prev else None),
                 _fmt_change(c.get("balance"), y_ago.company.get("balance") if y_ago else None)],
                ["Outstanding Loan", c.get("loan"), _fmt_change(c.get("loan"), prev.company.get("loan") if prev else None),
                 _fmt_change(c.get("loan"), y_ago.company.get("loan") if y_ago else None)],
                ["Net Position (Balance - Loan)", (c.get("balance") or 0) - (c.get("loan") or 0), None, None],
                ["Company Value", c.get("value"), None, None],
                ["Lines", len(latest.lines), len(latest.lines) - len(prev.lines) if prev else None,
                 len(latest.lines) - len(y_ago.lines) if y_ago else None],
                ["Vehicles", len(latest.vehicles), len(latest.vehicles) - len(prev.vehicles) if prev else None,
                 len(latest.vehicles) - len(y_ago.vehicles) if y_ago else None],
                ["Total Rolling Annual Line Profit", ov.get("linesProfitYear"), None, None],
            ],
            ["left", "right", "right", "right"]
        ),
        Note("Semantics Notice", "Annual line profit is a rolling 12-month figure at this sample date, not a calendar sum.")
    ]

    modal = analysis.modal_summary(latest)
    if modal:
        blocks.extend([
            Heading(2, "Results by Transport Mode"),
            Table(
                ["Mode", "Lines", "Vehicles", "Rolling Annual Profit", "Profit / Vehicle", "Losing Lines"],
                [[m["carrier"], m["lines"], m["vehicles"], m["profitYear"], m["profitPerVehicle"], m["losingLines"]] for m in modal],
                ["left", "right", "right", "right", "right", "right"]
            ),
            Chart("bar", "Annual Profit by Mode", [m["carrier"] for m in modal],
                  [("Profit", [float(m["profitYear"] or 0) for m in modal])])
        ])
        blocks.append(Chart("pie", "Vehicle Mix by Mode", [m["carrier"] for m in modal],
                            [(m["carrier"], [float(m["vehicles"])]) for m in modal]))

    if len(snaps) > 1:
        hist_rows = [[s.date_label, s.company.get("balance"), s.company.get("loan")] for s in snaps]
        blocks.extend([
            Heading(2, "Financial Sample History"),
            Table(["Date", "Balance", "Loan"], hist_rows, ["left", "right", "right"]),
            Chart("line", "Balance and Loan History", [s.date_label for s in snaps],
                  [("Balance", [float(s.company.get("balance") or 0) for s in snaps]),
                   ("Loan", [float(s.company.get("loan") or 0) for s in snaps])])
        ])
    else:
        blocks.append(Note("History Notice", "Only a single snapshot sample exists; historical trend charts are omitted."))

    return ReportDocument("company", "Company Performance Report", _base_header(latest, len(snaps)), blocks)


def _build_lines_report(store: Store) -> ReportDocument:
    snaps = _recent_current(store, 12)
    if not snaps:
        raise ValueError("no snapshot found")
    latest = snaps[-1]
    prev = snaps[-2] if len(snaps) > 1 else None
    rows = [analysis.line_row(latest, line) for line in latest.lines]
    by_profit = sorted(rows, key=lambda r: (r["profitYear"] if r["profitYear"] is not None else -10**15), reverse=True)

    n = len(by_profit)
    top_n = min(15, n)
    top_rows = by_profit[:top_n]
    bottom_n = min(15, n - top_n)
    bottom_rows = by_profit[-bottom_n:] if bottom_n else []

    blocks: list[Any] = [
        Heading(2, f"Most Profitable Lines ({len(top_rows)})"),
        Table(
            ["Line", "Carrier", "Vehicles", "Rolling Annual Profit", "Load (Instant)"],
            [[r["name"] or f"Line #{r['id']}", r["carrier"], r["vehicles"], r["profitYear"], _fmt_pct(r["load"])] for r in top_rows],
            ["left", "left", "right", "right", "right"]
        )
    ]
    if bottom_rows:
        blocks.extend([
            Heading(2, f"Least Profitable Lines ({len(bottom_rows)})"),
            Table(
                ["Line", "Carrier", "Vehicles", "Rolling Annual Profit", "Load (Instant)"],
                [[r["name"] or f"Line #{r['id']}", r["carrier"], r["vehicles"], r["profitYear"], _fmt_pct(r["load"])] for r in bottom_rows],
                ["left", "left", "right", "right", "right"]
            )
        ])

    losing = [r for r in rows if r["profitYear"] is not None and r["profitYear"] < 0]
    if losing:
        line_findings = [f for f in analysis.findings(latest, prev) if f.category == "lines"]
        table_rows = []
        for r in losing:
            causes = [f.code for f in line_findings if f.entity and f.entity.get("id") == r["id"]]
            table_rows.append([r["name"] or f"Line #{r['id']}", r["profitYear"], ", ".join(causes) or "unspecified"])
        blocks.extend([
            Heading(2, "Loss-Making Lines and Identified Findings"),
            Table(["Line", "Rolling Annual Loss", "Finding Codes"], table_rows, ["left", "right", "left"])
        ])

    empty = [r for r in rows if r["vehicles"] == 0]
    if empty:
        blocks.extend([
            Heading(2, "Lines Without Vehicles"),
            Table(["Line", "Stops", "Rate"], [[r["name"] or f"Line #{r['id']}", r["stops"], r["rate"]] for r in empty], ["left", "right", "right"])
        ])
    no_stops = [r for r in rows if r["stops"] < 2]
    if no_stops:
        blocks.extend([
            Heading(2, "Lines Without a Usable Stop Pair"),
            Table(["Line", "Stops", "Vehicles"],
                  [[r["name"] or f"Line #{r['id']}", r["stops"], r["vehicles"]] for r in no_stops])
        ])

    trends = analysis.load_trend(snaps)
    if trends:
        blocks.extend([
            Heading(2, "Occupancy Sample Trends"),
            Paragraph(f"Derived from {len(snaps)} recent snapshot sample points (sample index slope, not time averages)."),
            Table(
                ["Line", "Mean Sampled Occupancy", "Latest Occupancy", "Samples", "Occupancy Slope / Sample", "Status"],
                [[t["name"], _fmt_pct(t["meanLoad"]), _fmt_pct(t["latestLoad"]), t["samples"], t["slope"], t["status"]] for t in trends],
                ["left", "right", "right", "right", "right", "left"]
            )
        ])

    return ReportDocument("lines", "Lines Performance Report", _base_header(latest, len(snaps)), blocks)


def _build_fleet_report(store: Store) -> ReportDocument:
    snaps = _recent_current(store, 1)
    if not snaps:
        raise ValueError("no snapshot found")
    latest = snaps[-1]
    catalog_snap = store.latest_with_catalog(game_time=latest.game_time)
    rows = [analysis.vehicle_row(latest, v) for v in latest.vehicles]

    losing = [r for r in rows if r["profitYear"] is not None and r["profitYear"] < 0]
    blocks: list[Any] = [
        Heading(2, "Loss-Making Vehicles"),
        Table(
            ["Vehicle", "Line", "Carrier", "Age (Years)", "Rolling Annual Profit", "Value"],
            [[r["name"] or f"Vehicle #{r['id']}", r["lineName"] or "Unassigned", r["carrier"], r["ageYears"], r["profitYear"], r["value"]]
             for r in sorted(losing, key=lambda x: x["profitYear"] or 0)[:20]],
            ["left", "left", "left", "right", "right", "right"]
        )
    ]
    blocks.extend([
        Heading(2, "Fleet Age and Model Lifespan"),
        Table(["Vehicle", "Age (Years)", "Models", "Model Lifespan (Raw Units)"],
              [[r["name"] or f"Vehicle #{r['id']}", r["ageYears"], ", ".join(r["models"]) or "Unknown",
                ", ".join(_fmt(latest.models.get(m, {}).get("lifespan"))
                          for m in vehicle.get("models") or []) or "Unknown"]
               for vehicle, r in zip(latest.vehicles, rows)]),
        Note("Unit Limit", "Model lifespan units are unverified; no age/lifespan ratio or expiry claim is inferred.")
    ])
    if catalog_snap:
        year = (latest.date or {}).get("year", latest.meta.get("year"))
        expired = [model for model in catalog_snap.catalog
                   if year is not None and model.get("yearTo") is not None
                   and 0 < model["yearTo"] <= year]
        blocks.extend([
            Heading(2, "Stored Catalog Models No Longer in Production"),
            Table(["Model", "Carrier", "Retirement Year"],
                  [[model.get("name") or model.get("res") or f"Model #{model.get('id')}",
                    model.get("carrier"), model["yearTo"]] for model in expired]),
            Note("Catalog Coverage", f"Catalog sampled on {catalog_snap.date_label}; models absent from that sample cannot be classified.")
        ])

    idle_depot = [r for r in rows if r["state"] == "IN_DEPOT" and not r["line"]]
    if idle_depot:
        depot_map = {d["id"]: d.get("name") or f"Depot #{d['id']}" for d in latest.depots}
        blocks.extend([
            Heading(2, "Idle Capital in Depots"),
            Table(
                ["Vehicle", "Depot", "Days In Depot", "Recorded Asset Value"],
                [[r["name"] or f"Vehicle #{r['id']}", depot_map.get(r["depot"], "Unknown Depot"), r["daysInDepot"], r["value"]]
                 for r in idle_depot],
                ["left", "left", "right", "right"]
            ),
            Paragraph(f"Total tied-up capital in depots: {_fmt(sum(r['value'] or 0 for r in idle_depot))} recorded currency units.")
        ])

    fit = analysis.fleet_fit(latest, catalog_snap)
    blocks.append(Heading(2, "Fleet Fit Analysis"))
    if fit["status"] == "unavailable":
        blocks.append(Note("Analysis Pending", f"{fit['reason']} Catalog fitness requires verified units."))
    else:
        fit_rows = fit.get("rows", [])
        blocks.append(Table(
            ["Vehicle", "Current Model", "Main Cargo", "Score", "Best Replacement", "Potential Improvement", "Better Available"],
            [[r["vehicle"], r["model"], r["cargo"], r["score"], r["alternative"], _fmt_pct(r["improvement"]), r["better"]]
             for r in fit_rows[:25]],
            ["left", "left", "left", "right", "left", "right", "center"]
        ))

    return ReportDocument("fleet", "Fleet Composition and Capital Report", _base_header(latest, len(snaps)), blocks)


def _build_cargo_report(store: Store) -> ReportDocument:
    snaps = _recent_current(store, 1)
    if not snaps:
        raise ValueError("no snapshot found")
    latest = snaps[-1]

    blocks: list[Any] = []
    full = analysis.full_stocks(latest)
    if full:
        blocks.extend([
            Heading(2, "Stocks Near Capacity (≥90% Full)"),
            Table(
                ["Facility", "Kind", "Cargos", "Count", "Capacity", "Fill Ratio", "Actively Served"],
                [[r["name"], r["kind"], ", ".join(r["cargoNames"]), r["count"], r["capacity"], _fmt_pct(r["fill"]),
                  "Yes" if r["served"] else ("No" if r["served"] is False else "-")] for r in full],
                ["left", "left", "left", "right", "right", "right", "center"]
            )
        ])
    else:
        blocks.append(Paragraph("No stocks currently exceed the 90% fullness threshold."))

    ops = analysis.opportunities(latest)
    unshipped = [o for o in ops if o.get("kind") == "unshipped"]
    if unshipped:
        blocks.extend([
            Heading(2, "Unshipped Production Opportunities"),
            Table(
                ["Producer", "Cargo", "Produced / Year", "Shipped / Year", "Unshipped / Year", "Nearest Consumer", "Distance (km)"],
                [[o["producer"]["name"] or f"Industry #{o['producer']['id']}", o["cargo"], o["producedYear"], o["shippedYear"],
                  o["unshippedYear"], o["nearestConsumers"][0]["name"] if o["nearestConsumers"] else "None",
                  o["nearestConsumers"][0]["distanceKm"] if o["nearestConsumers"] else None] for o in unshipped[:15]],
                ["left", "left", "right", "right", "right", "left", "right"]
            ),
            Note("Feasibility Boundary", "Straight-line distance does not promise transport feasibility or rail route availability.")
        ])

    closing = [ind for ind in latest.industries if ind.get("closureTimeStamp") or ind.get("id") in set(latest.problems.get("closingIndustries") or [])]
    if closing:
        blocks.extend([
            Heading(2, "Scheduled Industry Closures"),
            Table(
                ["Industry", "Type", "Closing Timestamp"],
                [[ind.get("name") or f"Industry #{ind['id']}", ind.get("type", "-"), ind.get("closureTimeStamp", "Flagged")] for ind in closing],
                ["left", "left", "left"]
            )
        ])

    return ReportDocument("cargo", "Cargo Production and Flow Report", _base_header(latest, len(snaps)), blocks)


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


def _decision_details(store: Store, decision: dict[str, Any], comparison: Snapshot) -> list[Any]:
    recorded_time = decision.get("game_time")
    baseline = store.snapshot_at_or_before(recorded_time) if recorded_time is not None else None
    age = (comparison.game_time - recorded_time) / comparison.year_duration if recorded_time is not None and comparison.year_duration else None
    window = ("window unknown" if age is None else "comparison precedes decision" if age < 0 else
              "profit window not yet complete" if age < 1 else "window complete")
    blocks: list[Any] = [Heading(3, f"Decision #{decision['id']}: {decision['title']}"),
                         Paragraph(f"Rationale: {decision['rationale']}"),
                         Note("Profit Window", window)]
    rows = []
    for reference in decision.get("entities") or []:
        resolved = _resolve_entity(baseline, reference) or _resolve_entity(comparison, reference)
        if resolved is None:
            rows.append([str(reference), "Unresolved or no longer tracked", None, None, None])
            continue
        kind, entity = resolved
        before = _resolve_entity(baseline, {"type": kind, "id": entity["id"]})
        after = _resolve_entity(comparison, {"type": kind, "id": entity["id"]})
        old, new = before[1] if before else None, after[1] if after else None
        name = (new or old).get("name") or f"{kind.title()} #{entity['id']}"
        if new is None:
            blocks.append(Note("Entity Removed", f"{name}: entity no longer exists in the comparison snapshot."))
        metrics = [("Rolling Annual Profit", old.get("profitYear") if old else None, new.get("profitYear") if new else None)]
        if kind == "line":
            metrics.extend([
                ("Vehicles", len(old.get("vehicles") or []) if old else None, len(new.get("vehicles") or []) if new else None),
                ("Instant Load Ratio", analysis.line_load(old) if old else None, analysis.line_load(new) if new else None)
            ])
        for metric, old_value, new_value in metrics:
            rows.append([name, metric, old_value, new_value, _fmt_change(new_value, old_value)])
    if rows:
        blocks.append(Table(["Entity", "Metric", f"Decision Sample ({baseline.date_label if baseline else 'unavailable'})",
                             f"Comparison Sample ({comparison.date_label})", "Difference"], rows))
    return blocks


def _build_decisions_report(store: Store) -> ReportDocument:
    latest = store.latest()
    if not latest:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    decisions = store.list_decisions(limit=10000)
    blocks: list[Any] = []
    if not decisions:
        blocks.append(Paragraph("No player decisions have been recorded in the journal."))
    else:
        blocks.append(Heading(2, "Recorded Decisions Journal"))
        blocks.append(Table(["ID", "Game Date", "Title", "Status", "Outcome"],
                            [[d["id"], d.get("game_date") or "-", d["title"], d["status"], d.get("outcome") or "-"]
                             for d in decisions]))
        for decision in decisions:
            blocks.extend(_decision_details(store, decision, latest))
    return ReportDocument("decisions", "Decisions Follow-Up Report", _base_header(latest, store.snapshot_count()), blocks)


def _build_annual_report(store: Store, year: int | None = None) -> ReportDocument:
    available = store.available_years()
    if not available:
        raise ValueError("no snapshot found")
    if year is None:
        latest = store.latest()
        year = latest.date["year"] if latest and latest.date else available[-1]
    if year not in available:
        raise ValueError(f"No snapshots found for year {year}. Available years: {', '.join(str(y) for y in available)}")

    year_snaps = store.snapshots_for_year(year)
    current = store.latest()
    if current and year == (current.date or {}).get("year", current.meta.get("year")):
        year_snaps = [sample for sample in year_snaps if sample.game_time <= current.game_time]
    start_snap = year_snaps[0]
    end_snap = year_snaps[-1]
    baseline_snap = store.latest_before(start_snap.game_time)

    observed_months = sorted({s.date["month"] for s in year_snaps if s.date})
    all_months = set(range(1, 13))
    missing_months = sorted(all_months - set(observed_months))
    has_baseline = baseline_snap is not None and baseline_snap.date is not None and baseline_snap.date["year"] == year - 1 and baseline_snap.date["month"] == 12
    future_history = current is not None and store.snapshot_at_or_before(2**63 - 1).game_time > current.game_time
    complete_monthly = len(missing_months) == 0 and has_baseline and not future_history

    status_label = "monthly coverage complete" if complete_monthly else "partial-year coverage"
    in_progress = current is not None and (current.date or {}).get("year") == year and (end_snap.date or {}).get("month", 0) < 12
    if in_progress:
        status_label += f"; in progress through {end_snap.date_label}; figures to date"
    if future_history:
        status_label += "; retained future history indicates a timeline rewind"
    all_dates = [s.date_label for s in year_snaps]

    header = [
        ("Company / Save", end_snap.company.get("name") or "Primary Company"),
        ("Reporting Game Year", str(year)),
        ("Coverage Assessment", status_label),
        ("Baseline Sample", baseline_snap.date_label if baseline_snap else "None (history starts mid-year)"),
        ("Closing Sample", end_snap.date_label),
        ("Observed Sample Dates", ", ".join(all_dates)),
        ("Missing Calendar Months", ", ".join(str(m) for m in missing_months) if missing_months else "None"),
        ("Snapshots Used", str(len(year_snaps) + int(baseline_snap is not None))),
        ("Collection Errors", "; ".join(end_snap.errors) if end_snap.errors else "None reported"),
    ]

    base = baseline_snap or start_snap
    blocks: list[Any] = [
        Heading(2, f"Financial Summary ({status_label})"),
        Paragraph("Closing numbers reflect single snapshot samples. Total line profit is the sum of rolling 12-month line profits at closing sample, not a calendar-year income sum."),
        Table(
            ["Metric", f"Baseline ({base.date_label})", f"Closing ({end_snap.date_label})", "Net Change"],
            [
                ["Cash Balance", base.company.get("balance"), end_snap.company.get("balance"),
                 _fmt_change(end_snap.company.get("balance"), base.company.get("balance"))],
                ["Outstanding Loan", base.company.get("loan"), end_snap.company.get("loan"),
                 _fmt_change(end_snap.company.get("loan"), base.company.get("loan"))],
                ["Lines Count", len(base.lines), len(end_snap.lines), len(end_snap.lines) - len(base.lines)],
                ["Vehicles Count", len(base.vehicles), len(end_snap.vehicles), len(end_snap.vehicles) - len(base.vehicles)],
                ["Closing Rolling Annual Line Profit", None, sum(l.get("profitYear") or 0 for l in end_snap.lines), None]
            ],
            ["left", "right", "right", "right"]
        )
    ]

    lines_by_profit = sorted(end_snap.lines, key=lambda l: (l.get("profitYear") if l.get("profitYear") is not None else -10**15), reverse=True)
    best_5 = lines_by_profit[:5]
    worst_5 = lines_by_profit[-5:] if len(lines_by_profit) > 5 else []
    blocks.extend([
        Heading(2, "Top 5 Lines by Closing Annual Profit"),
        Table(["Line", "Rolling Annual Profit"],
              [[l.get("name") or f"Line #{l['id']}", l.get("profitYear")] for l in best_5], ["left", "right"]),
        Heading(2, "Bottom 5 Lines by Closing Annual Profit"),
        Table(["Line", "Rolling Annual Profit"],
              [[l.get("name") or f"Line #{l['id']}", l.get("profitYear")] for l in worst_5], ["left", "right"]),
    ])

    base_lines = {l["id"]: l for l in base.lines}
    end_lines = {l["id"]: l for l in end_snap.lines}
    added_lines = [end_lines[i] for i in (set(end_lines) - set(base_lines))]
    removed_lines = [base_lines[i] for i in (set(base_lines) - set(end_lines))]

    base_v = {v["id"]: v for v in base.vehicles}
    end_v = {v["id"]: v for v in end_snap.vehicles}
    added_v = [end_v[i] for i in (set(end_v) - set(base_v))]
    removed_v = [base_v[i] for i in (set(base_v) - set(end_v))]

    blocks.extend([
        Heading(2, "Fleet and Network Adjustments"),
        Table(
            ["Category", "Entities Added", "Entities Removed"],
            [
                ["Lines", ", ".join(l.get("name") or f"Line #{l['id']}" for l in added_lines) or "None",
                 ", ".join(l.get("name") or f"Line #{l['id']}" for l in removed_lines) or "None"],
                ["Vehicles", ", ".join(v.get("name") or f"Vehicle #{v['id']}" for v in added_v) or "None",
                 ", ".join(v.get("name") or f"Vehicle #{v['id']}" for v in removed_v) or "None"]
            ],
            ["left", "left", "left"]
        )
    ])

    m_start = {m["carrier"]: m for m in analysis.modal_summary(base)}
    m_end = {m["carrier"]: m for m in analysis.modal_summary(end_snap)}
    all_carriers = sorted(set(m_start) | set(m_end))
    modal_rows = []
    for c in all_carriers:
        s_row = m_start.get(c, {"lines": 0, "vehicles": 0, "profitYear": 0})
        e_row = m_end.get(c, {"lines": 0, "vehicles": 0, "profitYear": 0})
        modal_rows.append([
            c, s_row["lines"], e_row["lines"], s_row["vehicles"], e_row["vehicles"],
            s_row["profitYear"], e_row["profitYear"], _fmt_change(e_row["profitYear"], s_row["profitYear"])
        ])
    blocks.extend([
        Heading(2, "Modal Mix Adjustments"),
        Table(
            ["Mode", "Baseline Lines", "Closing Lines", "Baseline Vehicles", "Closing Vehicles",
             "Baseline Annual Profit", "Closing Annual Profit", "Profit Change"],
            modal_rows, ["left", "right", "right", "right", "right", "right", "right", "right"]
        )
    ])

    prev_year = year - 1
    if prev_year in available:
        prev_snaps = store.snapshots_for_year(prev_year)
        p_end = prev_snaps[-1]
        blocks.extend([
            Heading(2, f"Year-over-Year Comparison with {prev_year}"),
            Table(
                ["Metric", f"{prev_year} Closing", f"{year} Closing", "Difference"],
                [
                    ["Cash Balance", p_end.company.get("balance"), end_snap.company.get("balance"),
                     _fmt_change(end_snap.company.get("balance"), p_end.company.get("balance"))],
                    ["Outstanding Loan", p_end.company.get("loan"), end_snap.company.get("loan"),
                     _fmt_change(end_snap.company.get("loan"), p_end.company.get("loan"))],
                    ["Lines", len(p_end.lines), len(end_snap.lines), len(end_snap.lines) - len(p_end.lines)],
                    ["Vehicles", len(p_end.vehicles), len(end_snap.vehicles), len(end_snap.vehicles) - len(p_end.vehicles)],
                    ["Closing Rolling Line Profit", sum(l.get("profitYear") or 0 for l in p_end.lines),
                     sum(l.get("profitYear") or 0 for l in end_snap.lines),
                     _fmt_change(sum(l.get("profitYear") or 0 for l in end_snap.lines),
                                 sum(l.get("profitYear") or 0 for l in p_end.lines))],
                    ["Best Line",
                     _entity_name(max(p_end.lines, key=lambda line: line.get("profitYear") if line.get("profitYear") is not None else -math.inf, default=None), "Line"),
                     _entity_name(max(end_snap.lines, key=lambda line: line.get("profitYear") if line.get("profitYear") is not None else -math.inf, default=None), "Line"), None]
                ],
                ["left", "right", "right", "right"]
            )
        ])
    else:
        blocks.extend([
            Heading(2, f"Year-over-Year Comparison with {prev_year}"),
            Paragraph("no previous-year data")
        ])

    year_decisions = [d for d in store.list_decisions(limit=10000) if (d.get("game_date") or "").startswith(f"{year:04d}-")]
    blocks.append(Heading(2, f"Decisions Recorded in {year}"))
    if year_decisions:
        blocks.append(Table(
            ["ID", "Game Date", "Title", "Status", "Outcome"],
            [[d["id"], d["game_date"], d["title"], d["status"], d.get("outcome") or "-"] for d in year_decisions],
            ["right", "left", "left", "left", "left"]
        ))
        for decision in year_decisions:
            blocks.extend(_decision_details(store, decision, end_snap))
    else:
        blocks.append(Paragraph(f"no decisions were recorded in {year}"))

    high_findings = [f for f in analysis.findings(end_snap) if f.severity == "high"]
    blocks.append(Heading(2, "High-Severity Closing Findings"))
    if high_findings:
        blocks.append(Table(
            ["Code", "Category", "Title", "Detail"],
            [[f.code, f.category, f.title, f.detail] for f in high_findings],
            ["left", "left", "left", "left"]
        ))
    else:
        blocks.append(Paragraph("No high-severity findings recorded at closing sample."))

    hist_rows = [[s.date_label, s.company.get("balance"), s.company.get("loan")] for s in year_snaps]
    blocks.extend([
        Heading(2, "Sampled Financial Timeline"),
        Table(["Date", "Balance", "Loan"], hist_rows, ["left", "right", "right"]),
        Chart("line", f"{year} Balance and Loan History", [s.date_label for s in year_snaps],
              [("Balance", [float(s.company.get("balance") or 0) for s in year_snaps]),
               ("Loan", [float(s.company.get("loan") or 0) for s in year_snaps])])
    ])

    return ReportDocument("annual", f"Annual Company Report ({year})", header, blocks)


# ---------------------------------------------------------------------------
# Public Report Generation Entry Point
# ---------------------------------------------------------------------------

def render_report(store: Store, kind: str, year: int | None = None, html: bool = False) -> str:
    """Pure in-memory report generation without disk writing or service dependency."""
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 0 <= year <= 2**63 - 1):
        raise ValueError("year must be a nonnegative 64-bit integer.")
    if year is not None and kind != "annual":
        raise ValueError("year applies only to annual reports.")
    if kind not in VALID_KINDS:
        raise ValueError(f"Unknown report kind '{kind}'. Valid kinds: {', '.join(VALID_KINDS)}")

    if kind == "company":
        doc = _build_company_report(store)
    elif kind == "lines":
        doc = _build_lines_report(store)
    elif kind == "fleet":
        doc = _build_fleet_report(store)
    elif kind == "cargo":
        doc = _build_cargo_report(store)
    elif kind == "decisions":
        doc = _build_decisions_report(store)
    elif kind == "annual":
        doc = _build_annual_report(store, year)
    else:
        raise ValueError(f"Unknown report kind '{kind}'")

    return render_html(doc) if html else render_markdown(doc)
