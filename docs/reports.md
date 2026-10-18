# Reports

TF3 Companion generates local reports in Markdown and self-contained offline HTML. Reports explain what was observed and what remains unknown. They do not simulate the game or alter company finances.

## Commands

```sh
uv run tf3c report company
uv run tf3c report lines
uv run tf3c report fleet
uv run tf3c report cargo
uv run tf3c report decisions
uv run tf3c report annual --year 1983
uv run tf3c report annual --year 1983 --html
uv run tf3c report annual --year 1983 --open
uv run tf3c report methodology
uv run tf3c report lines --methodology default
uv run tf3c analyse
uv run tf3c evaluate --json
```

Reports are written under `<data>/reports/<game-date>__<methodology-id>@<version>/`, where `<data>` is the selected companion/save data root, the date is the snapshot's `YYYY-MM-DD` (or `t<gameTime>`) and selection is explicit request > save override > user default > packaged default. Each lens folder holds `<kind>.md`, `annual-<year>.md`, optional `.html` and a `manifest.json` recording identity/hash, selection, effective parameters/engine thresholds/report policies, calendar time basis, snapshot tick, files and coverage gaps. `reports/latest.md` copies the most recent single report. Different methodology identities or dates coexist; rerunning replaces the corresponding output without retaining every execution. Failed validation leaves previous output intact. Earlier flat `reports/<kind>.md` files are no longer written. Inspect generated files:

A report is composed once into an in-memory document, then rendered (Markdown and, with `--html`, HTML from the same composition) and published atomically; the analytical result behind it comes from `tf3c evaluate`, which needs no report folder. Evaluation keeps working when the report destination is unwritable, and a failed publication leaves the previous bundle in place.

- macOS: `ls -la "$HOME/Library/Application Support/tf3-companion/reports"`
- Windows PowerShell: `Get-ChildItem "$env:LOCALAPPDATA\tf3-companion\reports"`
- Linux: `ls -la "$HOME/.local/share/tf3-companion/reports"`

`--html` generates a matching `.html` file alongside the Markdown report. `--open` opens the report using your system's default application (your browser for HTML, or your default editor/viewer for Markdown). The MCP `report` tool accepts `kind`, optional `year` and optional `methodology` (a library id, never a path), returning the Markdown text directly. Every report header names the methodology, its version, content hash and effective parameters, and how many items were skipped, unsupported or not evaluable.

`--year` applies only to annual reports. An invalid kind, missing year data or failed import does not create report output. `--html --open` selects the browser; `--open` alone selects the Markdown handler. Opening failures are reported without discarding the generated file.

## Kinds

| Kind | Contents | Limitations to remember |
| --- | --- | --- |
| `company` | Finances, network/fleet counts, previous-sample and year-ago comparisons, modal results and balance/loan history. | Current-timeline observations only; rolling annual profit is not calendar income. |
| `lines` | Non-overlapping financial rankings, stop/vehicle counts, loss findings, incomplete lines and monthly occupancy samples. | Sample mean and sample-index slope are not time-weighted utilization. Route-scope economics await verified station links. |
| `fleet` | Vehicle age, raw model lifespan, loss-makers, idle depot capital, stored model availability and guarded model comparisons. | Lifespan units are unverified; fitness scoring is withheld without explicitly verified speed/cost units. |
| `cargo` | Unshipped production, nearest consumer industries, near-capacity stocks and industry closures. | Distances are straight-line industry-to-industry estimates, not actual route lengths. Full stocks alone do not establish profitability. |
| `decisions` | Status, rationale, outcome and referenced line/vehicle profit comparisons; line vehicle counts and instant load before/after. | Removed/ambiguous entities and incomplete profit windows are disclosed. Vehicle occupancy is not inferred from uncollected fields. |
| `annual` | Review of a specific calendar year's observations, monthly coverage checks, and closing line performance. | **Annual income cannot be summed from rolling numbers.** See the annual coverage rules below. |
| `history` | Company trajectory, period comparisons, fleet/network turnover, milestones and sampling coverage. | History starts at the first collected snapshot; counter semantics and unsampled transactions remain unknown. |
| `vehicle-roi` | Profitability by model/carrier/cargo/age, same-line comparisons and guarded replacement candidates. | A profitability comparison, not verified investment ROI or a promised payback; model suitability needs route evidence. |
| `lines-history` | Line trajectories, explicit trend classification, fleet changes and manual investigation priorities. | Short-term sampled rolling windows cannot establish causality; inferred age is not a line creation date. |
| `industries` | Industry evolution, production/shipping comparisons, upgrades, closures and service gaps. | Stock/catchment links and delivered counters may be incomplete. |
| `towns` | Town capacity growth, passenger coverage, cargo supply and pollution/noise comparisons. | Capacity is a population proxy; station assignment does not prove catchment coverage. |
| `expansion` | Transparent heuristic ranking of potential cargo routes, downstream demand and compatible catalog models. | Scores are not profit forecasts; existing-route exclusions cannot guarantee catchment-based or renamed connections are absent. |
| `bottlenecks` | Persistent stock saturation, line issues, occupancy and terminal/depot congestion proxies. | Sample persistence is not time-weighted duration; terminal presence alone does not prove congestion. |
| `methodology` | The verdicts of a methodology: coverage (skipped, unsupported, not evaluable) first, roles with counts, rule results with evidence, aggregate tables, recommendations, declared tables and charts. | Everything a methodology says is a policy applied to the same facts; its text is untrusted data. Verdicts are computed on demand and never stored. |

Generate the additional templates with the same format options:

```sh
uv run tf3c report history --html
uv run tf3c report vehicle-roi --html
uv run tf3c report lines-history --html
uv run tf3c report industries --html
uv run tf3c report towns --html
uv run tf3c report expansion --html
uv run tf3c report bottlenecks --html
```

These templates use collected observations, not a reconstructed save history. They become richer as snapshots accumulate. Where calendar dates disagree with `meta.yearDuration`, age estimates use calendar-based calibration and disclose the fallback or uncertainty. Cargo indices in line capacity data can differ from vehicle/catalog indices; comparisons must respect each source's indexing convention.

The MCP server must be restarted after upgrading to expose the additional `report` kinds to a connected client.

## Annual coverage and financial interpretation

Transport Fever 3's in-game `profitYear` is a **rolling game-year window**, not a discrete monthly or quarterly ledger. Adding rolling numbers across snapshots creates duplicate counting and false totals. TF3 Companion adheres to strict accounting boundaries:

- **No summing rolling profit:** Rolling annual profit is evaluated at closing observation points or compared over intervals, never accumulated snapshot-by-snapshot.
- **Explicit baseline and end dates:** Every annual report states the exact opening baseline date, the closing date, and every observation date included in the review.
- **Coverage disclosure:** Monthly coverage is complete only with samples in all twelve months, a preceding December baseline, and no detected retained-future timeline. In-progress years, missing months and exact observation dates are disclosed; completeness does not mean exact calendar-year accounting.
- **`transportedYear` remains unverified:** Transported volume numbers are marked provisional until game accounting definitions are confirmed.

Always review report numbers alongside the observation dates and collection warnings printed in the header.

## Analysis views: the numbers behind a report

Every analytic number, ranking and diagnostic of a report is computed before the document is laid out. Seven specialized
families are public **analysis views**, requested by name and returned under `analysisViews` by `tf3c evaluate --view NAME`
(repeatable) and MCP `evaluate(views=[...])`:

| View | Typed result | What it holds |
|---|---|---|
| `bottlenecks` | `BottlenecksView` | observations with eligible-sample denominators, streaks, persistent/intermittent/new/resolved status, severity, stock rises (slope in units per sample, extrapolation conditional), sampled occupancy, station and depot groups, health trend, collector coverage |
| `expansion` | `ExpansionView` | greedy ranked candidates with raw flows, distance method, allocated volume, score parts and penalties, alternatives, exclusions and dead ends, proven cargo economics, estimated town anchors, starved consumers, vehicle-fit evidence |
| `lines-history` | `LinesHistoryView` | line series, early/recent medians, MAD, every threshold term, maturity, class and reason, sampled occupancy, vehicle-change events, created/removed lines, manual follow-ups |
| `history` | `HistoryView` | company periods, growth and year-over-year, year-ends, turnover, milestones and extremes, earnings-offset segments, purchase cohorts |
| `industries` | `IndustriesView` | complete/unknown flows, cohort aggregates, lifecycle events, service outliers, chains, stock progression, closure exposure, name-inferred links, manual review |
| `vehicle-roi` | `VehicleRoiView` | vehicle observations, carrier/model/cargo/age groups and ranks, same-line comparisons, trends, mismatch and size-fit screens, weak groups and swap hypotheses |
| `towns` | `TownsView` | capacity/usage/demand rows and ranks, growth and stall screens, coverage, headroom, hotspots, passenger pairs, key observations |

The base reports (company, lines, fleet, cargo, annual, decisions) use internal typed projections of the same kind
(`facts.py`); they are not extra public view names. Report builders only choose sections, wording, formatting, escaping,
chart styling and display caps (with accurate omitted counts); they never decide whether a diagnostic is true or a candidate
eligible, so Markdown, HTML and the structured result agree on every number, rank and event date.

`evaluate` (stored evidence, no documents), `analyse` (ingest, evaluate, compose, publish) and `report` (compose and publish
one kind) differ only in what they acquire and write. `evaluate --view` never ingests, refreshes, renders or writes, and
without `--view` no extended history is read.

All of this runs from an installed package. Evaluation and report composition read the configured companion store, the packaged
methodologies and your imported methodology files; nothing reads a source checkout's `data/` folder, and no personal save path,
line-name convention or town code is required (a methodology can classify by factual fields alone). Reports generated earlier
by retired author-local scripts stay where they are as historical files; they are not regenerated or relabelled.

**Criteria.** Methodology-owned judgments (`report_policies` and shared engine thresholds) are applied under the evaluation's
effective values and origins; changing a methodology changes classes, ranks and scores, never measured values such as medians,
MAD, distances or counters. Statistical minima (for example five line-history points, three vehicles or samples for ROI
groups, three samples for persistence) and algorithm limits (expansion `TOP_N=10`, town `PAIR_POOL=10`) stay engine-owned. Heuristics
that are not part of the registry (town quantile and headroom screens, history gap and earnings-offset heuristics, ROI
weak-group loss share and capacity-per-cost ordering) are disclosed under each view's `criteria` as fixed engine screens, not
configurable policy and not physical facts.

**Bounded reads.** Every query is bounded in SQL at or before the selected endpoint; stored rows after it (a retained rewound
branch) never reach a result, and a historical closing endpoint has its own bounded evaluation. Compact histories stream in
batches of 256 rows over the whole eligible prefix; full snapshots are hydrated only under each view's sampling bound
(`coverage.hydrationLimit`: bottlenecks 240, expansion 21, lines-history 12 plus the endpoint, vehicle-roi 33, history, industries
and towns only the endpoint). `coverage` also lists the eligible, read and used sample counts, the sampled references and the
collector-error families. Missing values are `null` with a reason, never zero; known subtotals state how many members were unknown.

## Calendar time, ages and policy disclosure

All age and elapsed-duration consumers share `game-calendar-v1`. One `GAME-YEAR` is 365.25 elapsed in-game Gregorian days,
including real leap dates; it is not the collector's nominal `meta.yearDuration` query window or wall-clock time.
Exact dated anchors are used directly. An interior timestamp can be interpolated only within an enclosing observed span
of at least seven calendar days; interpolation is labelled an estimate. No nominal fallback or extrapolation is used.

Examples:
- Two anchors exactly 366 calendar days apart give `366 / 365.25` GAME-YEAR, not exactly one.
- A purchase older than the first observed calendar anchor has unknown age, not age zero.
- A single dated observation can establish zero age for a purchase at exactly that observation tick, but cannot date older purchases.
- Missing/ambiguous intervals cannot be annualized; known zero intervals are distinct and also cannot be divisors.

Line age is the oldest currently assigned vehicle's age, not line creation time. First-observed service history is labelled
separately. The company comparison selects an observed baseline at/before the calendar target 365.25 days earlier and discloses
the actual date/span. Decision follow-up distinguishes `elapsedGameYears` from a nominal collector-query-window diagnostic;
neither establishes completed calendar accounting, profit-window completeness or causal impact.
Model lifespan and raw `daysInDepot`/`daysAtTerminal` retain their independent unverified unit caveats.

JSON rows expose `ageYears`, `ageTime` and `timeBasis`; summaries/manifests and XLSX disclose the same clock version, normalization,
anchor hash and isolation warnings. Markdown and HTML use the same document model. Observable rewinds or contradictory dates
refuse cross-snapshot conversion; monotone legacy stores are still `legacy-unverified`, not proven isolated saves.
Existing evidence and user methodology files are never migrated, and old report files are not regenerated automatically.
Historical files without time provenance have an unknown time basis.

Finite methodology `report_policies` can alter verdict/ranking criteria in industries, line-history, bottlenecks and expansion.
Shared stock/load/maturity/fleet thresholds also reach the corresponding report helpers, including vehicle-ROI fit.
Reports disclose applicable effective values, units and default-versus-methodology origins; manifests carry the full registry.
Sample sufficiency minima, missing-value handling, bounded history and game mechanics remain engine-owned.
Finding-code overrides apply to matching findings, not every report screening row. See [methodologies](methodologies.md).


## Formats and offline privacy

Markdown reports use plain text tables and diagrams where helpful. HTML reports are **completely offline and self-contained**:

- Embedded CSS and vector styling only;
- No remote web fonts, CDN scripts, trackers or external stylesheets;
- Designed for local browser review without an internet connection.

Exported spreadsheets (`uv run tf3c export`) remain available for raw tabular analysis in Excel, LibreOffice or Google Sheets.
