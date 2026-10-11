# Design

## Context

See proposal.md for motivation. Current state (pre-rebrand code, names translated per the shared contract):

- `store.py` keeps every ingested snapshot as JSON in `snapshots` (`game_time`, `date_label`, `balance`, `loan`, `lines`, `vehicles`, full `data`) plus `line_history` (per line: profit, transported, rate, vehicles). `company_history` / `line_history` queries exist; there is no "snapshots of game year Y" query. The decision journal (`decisions`) stores `game_time`, `game_date`, `status`, `outcome`, `entities` (JSON list).
- `analysis.py` has `company_overview`, `line_row`, `vehicle_row`, `modal_summary`, `findings`, `opportunities`; `analysis-insights` adds load trend, fleet fit, idle capital.
- `export.py` writes the XLSX; `service.export_spreadsheet` shells out to `open -a Numbers`.
- Snapshot facts that shape reports: `meta.date{year,month,day}` gives the game calendar; `meta.yearDuration` converts game time to years; `line.profitYear` is a **rolling 12-month** figure, not a calendar-year total; the vehicle catalog is only present in `start`/`request` snapshots, so fleet sections must look back to the newest snapshot that has one. `analysis-insights` bumps the snapshot schema to 3 (station positions/links); reports must tolerate older stored snapshots without those fields.
- Reports live in `<data>/saves/<saveId>/reports/` (change 2). Findings have `code`, `severity`, `category`, `entity`, `evidence`.

## Goals / Non-Goals

**Goals:**
- One data-gathering path per report, rendered to Markdown and HTML from the same document model so the two cannot diverge.
- Deterministic output: same store → same bytes (except the generation line), so reports are testable with golden files.
- Honest handling of incomplete years and missing history.

**Non-Goals:**
- New analyses (consume `analysis-insights`, do not recompute), interactive charts, JavaScript, PDF, templates configurable by the user, a Markdown parser dependency.

## Decisions

### D1. Document model with two renderers
Builders return a small in-memory document: ordered blocks `Heading`, `Paragraph`, `Table(columns, rows, align)`, `Chart(kind: line|bar|pie, title, series, categories)`, `Note(label, text)`. `render_markdown(doc)` and `render_html(doc)` consume it. A chart is always emitted together with its table (the builder adds the table; the renderers never hide it).
*Alternatives:* generate Markdown then convert to HTML with a library (new dependency, Mermaid blocks would need special casing, escaping hard to guarantee); Jinja templates (dependency, logic in templates, two templates per report to keep in sync). The model costs ~300 lines and makes parity testable (every `Table` appears in both outputs).

### D2. Charts
- Markdown: fenced `mermaid` blocks — `xychart-beta` for balance/loan and profit rankings, `pie` for modal mix. Labels are sanitised (strip quotes, brackets, backticks, newlines; truncate to 40 chars in the chart only — the table keeps the full name). Large series are decimated to at most 60 points for charts (tables keep all rows, limited to a sane cap such as 36 months).
- HTML: the same `Chart` becomes inline `<svg>` (polyline for lines, rects for bars, arc paths for pie) with `<title>` text, axis labels and a fixed palette; `viewBox`-scaled so it fits any width. Colours and fonts come from an inline `<style>` using system font stacks; `prefers-color-scheme` handled in CSS only.
*Alternative rejected:* embedding the Mermaid JS from a CDN or inlined (hundreds of KB, needs JS, violates offline/no-script).

### D3. HTML safety and self-containment
All text goes through one escape function; no raw HTML ever passes through the model. The document has no `<script>`, no external `href`/`src`/`url()`, no web fonts. Tests grep the output for those patterns and for an injected `<script>` in a line name.

### D4. Data sources per section

| Report / section | Source |
|---|---|
| Header (label, date, snapshot count) | save label from `saves.py`; latest snapshot `meta.date`; store snapshot count |
| Company: balance, loan, value, lines, vehicles, total line profit, deltas | `analysis.company_overview(latest, previous)`; year-ago delta from the snapshot nearest `gameTime − yearDuration` |
| Company: profit by mode, profit per vehicle | `analysis.modal_summary(latest)` |
| Company: balance/loan chart | `store.company_history` (monthly rows) |
| Lines: top/bottom 15, loss-makers, empty lines | `analysis.line_row` over latest snapshot; loss-making causes from findings of category `lines` (by `code`, `entity`) |
| Lines: load trend | `analysis-insights` load-trend result over the last N snapshots (N from that capability) |
| Fleet: age vs lifespan, losing vehicles | `analysis.vehicle_row`, catalog `lifespan` from `latest_with_catalog` |
| Fleet: idle capital, fleet fit, models out of production | `analysis-insights` idle-capital and fleet-fit results; catalog from `latest_with_catalog` (section omitted with a note if none) |
| Cargo: full stocks, unshipped production, closing | `analysis.industry_row`, stocks and findings of category `industries`, from the newest snapshot that contains industries |
| Cargo: nearest consumers | `analysis.opportunities` |
| Decisions | `store.list_decisions`; metrics from `line_history` (profit, vehicles) and snapshot JSON (load via `analysis.line_load`) at the decision's `game_time` snapshot and the latest one |
| Annual | see D5 |
| Notable findings | `analysis.findings` run on the end snapshot (with the snapshot before it) filtered to `severity == high` |

If an `analysis-insights` result cannot be computed for a snapshot (e.g. a schema 2 snapshot without station positions), the section prints a one-line note instead of failing.

### D5. Annual report algorithm
1. `years = {meta.date.year}` over stored snapshots (new store query: snapshots for a year ordered by `game_time`, plus `years()`); fall back to `meta.year` when `date` is absent.
2. `year` defaults to the latest year; unknown year → error with the available years.
3. `end` = last snapshot of Y. `start` = last snapshot of Y-1; if none, first snapshot of Y and flag `history starts mid-year`.
4. Coverage: always display the actual baseline/end dates, observed months and sampling gaps. A year is historical if later-year snapshots exist, not automatically complete. Mark partial coverage when the baseline is absent, sampling has gaps, or December is unobserved. Use "monthly coverage complete", not exact calendar-year accounting, only with all twelve months and a preceding-year baseline.
5. Closing figures use `end`: balance, loan and sum of line `profitYear` values at that single snapshot. Never sum rolling annual figures across snapshots or label them calendar-year income.
6. Best/worst 5: `line_row` on `end`.
7. Added/removed: set difference of line ids and vehicle ids between `start` and `end` snapshots. Entities created and destroyed between the two snapshots are invisible; lines additionally use the union of `line_history` ids inside Y to report "added and removed within the year" when present. Names come from the snapshot where the entity exists (removed ones from `start`).
8. Modal mix: `modal_summary(start)` vs `modal_summary(end)`, with deltas; pie for `end`.
9. Decisions: journal rows whose `game_date` year is Y (rows without `game_date` are matched by `game_time`); metrics as in the decisions report.
10. Previous year: the same extraction on Y-1 (end snapshot of Y-1 only; no recursion) to fill the comparison table; absent → "no previous-year data".

### D6. Decision follow-up metrics
Entities in a decision are stored as free JSON (names/ids). Resolution tries id, then exact name, then unique partial name against the decision-time snapshot (`snapshots.game_time == decision.game_time`) and the latest. Unresolvable entities are listed as such, never guessed. Window flag: `latest.game_time − decision.game_time < yearDuration` → "profit window not yet complete".

### D7. Orchestration and files
`Companion.report(kind, year=None, html=False)` ingests, builds the document, writes `<kind>.md` (`annual-<year>.md`) and optionally `.html` to `reports/` via write-temp-then-`os.replace`, and returns `{markdown, paths}`. CLI prints paths; MCP returns the Markdown plus the path line. File names are fixed so repeated runs overwrite; no history of reports is kept (the store is the history).

### D8. Opening files
A single `open_file(path)` helper: `os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux; failures return a warning string instead of raising. `export_spreadsheet(open=False)` and `report --open` use it; `_numbers_app` and `open -a Numbers` are deleted. Exports move to `<data>/saves/<saveId>/exports/` (already the layout from change 2).

### D9. Language and formatting
All labels English; numbers with thousands separators and no currency symbol assumption beyond "$" used by the game; dates `YYYY-MM-DD` from game calendar. Agents translate when presenting.

## Risks / Trade-offs

- [Mermaid `xychart-beta` support varies between renderers] → every chart has an equivalent table; pie and xychart syntax kept minimal; HTML does not depend on Mermaid.
- [Rolling 12-month profit misread as calendar profit] → explicit label in the annual report, documented in `docs/reports.md`.
- [Catalog only in start/request snapshots] → fleet sections use the newest snapshot that has a catalog and print its date; if none, a note.
- [Large saves (~100 lines, ~350 vehicles) produce long tables] → top/bottom N caps, vehicle tables limited to the 20 worst/oldest, full data stays in XLSX.
- [Entity references in old decisions are unstructured] → conservative resolution, "unresolved" rows.
- [Years extracted from `meta.date` only exist from the schema that includes it] → fallback to `meta.year`, else the snapshot is ignored for annual grouping with a warning.
- [Golden-file tests brittle] → renderers are deterministic; timestamps live in a single "generated" line excluded from comparisons.

## Migration Plan

No data migration. `export_spreadsheet` parameter changes from `open_in_numbers` to `open` (default false); the agent-facing schema updates automatically on the next MCP start. Roll back by reverting the change; stored reports are regenerable from the store.

## Open Questions

- Exact balance of the modal chart when a mode has zero lines at the start (shown as 0 in the table; pie omits zero slices) — cosmetic, decidable during implementation.
