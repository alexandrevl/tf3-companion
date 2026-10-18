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
```

Reports are written under `<data>/reports/<game-date>__<methodology-id>@<version>/`, where `<data>` is the platform companion data directory (or `TF3C_DATA_DIR`), the game date is the snapshot's `YYYY-MM-DD` (or `t<gameTime>` when it has no calendar date) and the methodology is the effective one (`--methodology`, else the save's binding, else `default`). Each folder holds the reports for that lens (`<kind>.md`, `annual-<year>.md`, optional `.html`) and a `manifest.json` with the methodology identity and hash, effective parameters, snapshot game time, files and the skipped, unsupported and not-evaluable lists. `reports/latest.md` is a copy of the most recently generated single report. Different methodologies or game dates make different sibling folders; rerunning on the same inputs overwrites one folder atomically. The earlier flat `reports/<kind>.md` files are no longer written. Inspect the directory to list generated files:

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

## Formats and offline privacy

Markdown reports use plain text tables and diagrams where helpful. HTML reports are **completely offline and self-contained**:

- Embedded CSS and vector styling only;
- No remote web fonts, CDN scripts, trackers or external stylesheets;
- Designed for local browser review without an internet connection.

Exported spreadsheets (`uv run tf3c export`) remain available for raw tabular analysis in Excel, LibreOffice or Google Sheets.
