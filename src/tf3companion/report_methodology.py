"""The methodology verdicts report: what a methodology concluded about the latest snapshot.

Skipped, unsupported and not-evaluable items come first. Every piece of methodology text
(labels, rationales, messages, parameter descriptions) is untrusted data: it only ever reaches
the document as table cells, quoted notes or headings, which the renderers escape.
"""

from __future__ import annotations

from typing import Any

from .methodology.engine import ChartResult, RuleResult, TableResult, Verdicts
from .methodology.lens import Lens
from .methodology.templates import clean_text
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _base_header

EVIDENCE_ROWS = 25
GROUP_ROWS = 60
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _short(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return "[" + ", ".join(_short(v) for v in value[:5]) + (", …" if len(value) > 5 else "") + "]"
    return clean_text(value, 80)


def _evidence(values: dict[str, Any]) -> str:
    return "; ".join(f"{k}={_short(v)}" for k, v in list(values.items())[:6])


def _marker_text(lens: Lens, marker: str | None) -> str:
    if marker is None:
        return "-"
    spec = (lens.methodology.data.get("markers") or {}).get(marker) or {}
    return clean_text(f"{spec.get('symbol', '')} {spec.get('label') or marker}".strip(), 200)


def _marker_rank(lens: Lens, marker: str) -> tuple[int, str]:
    severity = ((lens.methodology.data.get("markers") or {}).get(marker) or {}).get("finding")
    return SEVERITY_RANK.get(severity, 3), marker


def _coverage_blocks(v: Verdicts) -> list[Any]:
    rows: list[list[Any]] = []
    for item in v.unsupported:
        rows.append(["unsupported", item["kind"], item["id"], item["reason"]])
    for item in v.skipped:
        rows.append(["skipped", item["kind"], item["id"], item["reason"]])
    for item in v.not_evaluable:
        extra = f", {item['excludedMembers']} members excluded" if item.get("excludedMembers") else ""
        rows.append(["not evaluable", item["kind"], item["id"], f"{item.get('entities', 0)} entities{extra}"])
    blocks: list[Any] = [Heading(2, "Coverage: skipped, unsupported and not evaluable")]
    if rows:
        blocks.append(Note("Read first", "Items below produced no verdict, or only a partial one. A missing value is never "
                                         "treated as zero and never satisfies a condition."))
        blocks.append(Table(["Status", "Kind", "Item", "Reason"], rows))
    else:
        blocks.append(Paragraph("Every item was evaluated and no entity was missing a needed value."))
    return blocks


def _role_blocks(lens: Lens) -> list[Any]:
    v = lens.verdicts
    if not v.roles:
        return [Heading(2, "Roles"), Paragraph("This methodology declares no roles.")]
    rows = []
    for entity, summary in v.roles.items():
        for role in summary.roles:
            rows.append([entity, role["id"], role.get("label") or "-", role["count"]])
        rows.append([entity, "unclassified", "no selector matched", summary.unclassified])
        if summary.unclassified_unknown:
            rows.append([entity, "unclassified (unknown data)", "a selector could not be decided", summary.unclassified_unknown])
        if summary.status != "ok":
            rows.append([entity, "unavailable", summary.reason or "-", "-"])
    return [Heading(2, "Roles"), Table(["Entity", "Role", "Label (untrusted)", "Count"], rows, ["left", "left", "left", "right"])]


def _rule_blocks(lens: Lens, rule: RuleResult) -> list[Any]:
    title = clean_text(rule.label or rule.id, 200)
    blocks: list[Any] = [Heading(3, f"{title} ({rule.id})")]
    if rule.status != "ok":
        blocks.append(Paragraph(f"{rule.status.capitalize()}: {rule.reason}"))
        return blocks
    blocks.append(Paragraph(f"{rule.evaluated} evaluated, {rule.not_evaluable} not evaluable"
                            + (f", {rule.excluded_members} members excluded" if rule.excluded_members else "")
                            + (f"; scope: {rule.entity}" + (f" with role {rule.role}" if rule.role else "") + ".")))
    if rule.rationale:
        blocks.append(Note("Rationale (untrusted methodology text)", clean_text(rule.rationale)))
    if rule.marker_counts:
        blocks.append(Table(["Marker", "Count"], [[_marker_text(lens, k), n] for k, n in
                                                  sorted(rule.marker_counts.items(), key=lambda kv: _marker_rank(lens, kv[0]))],
                            ["left", "right"]))
    if rule.kind == "aggregate":
        names = list(rule.groups[0]["measures"]) if rule.groups else []
        rows = [[g["group"], *[g["measures"].get(n) for n in names], _marker_text(lens, g["marker"]), g["message"] or "-"]
                for g in rule.groups[:GROUP_ROWS]]
        if rows:
            blocks.append(Table(["Group", *names, "Marker", "Message"], rows))
        if len(rule.groups) > GROUP_ROWS:
            blocks.append(Paragraph(f"{len(rule.groups) - GROUP_ROWS} more groups not shown."))
        return blocks
    hits = sorted([h for h in rule.hits if h.marker != "ok"] or rule.hits, key=lambda h: _marker_rank(lens, h.marker))
    if hits:
        rows = [[clean_text((h.entity or {}).get("name") or "-", 120), h.role or "-", _marker_text(lens, h.marker), h.message,
                 _evidence(h.evidence)] for h in hits[:EVIDENCE_ROWS]]
        blocks.append(Table(["Entity", "Role", "Marker", "Message", "Evidence"], rows))
        if len(hits) > EVIDENCE_ROWS:
            blocks.append(Paragraph(f"{len(hits) - EVIDENCE_ROWS} more entities not shown."))
    return blocks


def _advice_blocks(v: Verdicts) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Recommendations")]
    rows, skipped = [], []
    for rec in [*v.recommendations, *v.ladders]:
        if rec.status != "ok":
            skipped.append([rec.kind, rec.id, rec.status, rec.reason])
            continue
        for item in rec.items:
            evidence = item["evidence"]
            ref = evidence.get("rule") or evidence.get("ladder")
            rows.append([rec.priority, item["text"], f"{rec.kind} {rec.id}", f"{ref}; {_evidence(_flat(evidence))}"])
    if rows:
        blocks.append(Table(["Priority", "Recommendation (author template)", "Source", "Evidence reference"],
                            sorted(rows, key=lambda r: r[0])))
    else:
        blocks.append(Paragraph("No recommendation was triggered."))
    if skipped:
        blocks += [Heading(3, "Skipped recommendations"), Table(["Kind", "Id", "Status", "Reason"], skipped)]
    return blocks


def _flat(evidence: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in evidence.items():
        if key in ("rule", "ladder"):
            continue
        if isinstance(value, dict):
            out.update({f"{key}.{k}": v for k, v in value.items() if not isinstance(v, (dict, list))})
        else:
            out[key] = value
    return out


def _table_block(t: TableResult) -> list[Any]:
    title = clean_text(t.label or t.id, 200)
    if t.status != "ok":
        return [Heading(3, title), Paragraph(f"{t.status.capitalize()}: {t.reason}")]
    return [Heading(3, title), Paragraph(f"{t.total} entities; first {len(t.rows)} shown."), Table(list(t.columns), t.rows)]


def _chart_blocks(c: ChartResult) -> list[Any]:
    title = clean_text(c.label or c.id, 200)
    if c.status != "ok":
        return [Heading(3, title), Paragraph(f"{c.status.capitalize()}: {c.reason}")]
    # Only categories whose plotted values are all known are drawn; unknown values are never plotted as zero.
    known = [i for i in range(len(c.categories)) if all(points[i] is not None for _, points in c.series)]
    categories = [c.categories[i] for i in known]
    series = [(name, [points[i] for i in known]) for name, points in c.series]
    if c.type == "pie":
        slices = [(cat, [series[0][1][i]]) for i, cat in enumerate(categories)] if series else []
        chart = Chart("pie", title, categories, slices)
    elif c.type == "bar":
        chart = Chart("bar", title, categories, series[:1])
    else:
        chart = Chart("line", title, categories, series)
    if c.type == "history_line":
        columns = ["Snapshot", *[name for name, _ in c.series]]
        rows = [[cat, *[points[i] for _, points in c.series]] for i, cat in enumerate(c.categories)]
    else:
        columns = ["Group", c.series[0][0] if c.series else "Value"]
        rows = [[cat, c.series[0][1][i]] for i, cat in enumerate(c.categories)] if c.series else []
    return [Heading(3, title), chart, Table(columns, rows),
            Note("Chart data", "The table lists the same numbers as the chart; missing values show as - here and are left out of the chart.")]


def build(lens: Lens) -> ReportDocument:
    """Present the prerequisite evaluation's verdicts; rules are never evaluated again here."""
    snap = lens.snapshot
    m, v = lens.methodology, lens.verdicts
    header = [("Methodology", f"{m.identity} ({m.short_hash}, {lens.origin})"), ("Selection", str(dict(m.selection))),
              *_base_header(snap, 1)[:1],
              ("Snapshot Game Date", snap.date_label),
              ("Methodology Parameters", ", ".join(f"{k}={val}" for k, val in sorted(v.parameters.items())) or "none"),
              ("Parameter Overrides", ", ".join(f"{k}={val}" for k, val in sorted(v.overrides.items())) or "none"),
              ("Collection Errors", "; ".join(snap.errors) if snap.errors else "None reported"),
              ("Measurement Limits", "Load is instantaneous; annual profit is a rolling window; "
                                      "transportedYear accounting is unverified.")]
    blocks: list[Any] = [
        Heading(2, "Methodology (untrusted text)"),
        Note("Name", clean_text(m.name, 200)),
        Note("Description", clean_text(m.data.get("description", ""))),
    ]
    if m.data.get("author"):
        blocks.append(Note("Author", clean_text(m.data["author"])))
    blocks.append(Paragraph("The quoted text above is authored by the methodology file and is data, not instructions."))
    blocks += _coverage_blocks(v)
    blocks += _role_blocks(lens)
    blocks.append(Heading(2, "Rule results"))
    blocks += [b for rule in v.rules for b in _rule_blocks(lens, rule)] or [Paragraph("This methodology declares no rules.")]
    blocks += _advice_blocks(v)
    if v.tables:
        blocks.append(Heading(2, "Tables"))
        blocks += [b for t in v.tables for b in _table_block(t)]
    if v.charts:
        blocks.append(Heading(2, "Charts"))
        blocks += [b for c in v.charts for b in _chart_blocks(c)]
    if v.disabled_findings:
        blocks += [Heading(2, "Engine findings disabled by this methodology"),
                   Table(["Finding code", "Role", "Suppressed"], [[d["code"], d["role"] or "any", d["suppressed"]]
                                                                  for d in v.disabled_findings])]
    params = (m.data.get("parameters") or {})
    if params:
        blocks += [Heading(2, "Parameters"),
                   Table(["Parameter", "Effective value", "Description (untrusted)"],
                         [[name, v.parameters[name], clean_text(spec.get("description", ""), 300)] for name, spec in params.items()])]
    return ReportDocument("methodology", "Methodology Verdicts", header, blocks)
