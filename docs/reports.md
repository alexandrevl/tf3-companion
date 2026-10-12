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
```

Reports are written under `<data>/reports/`, where `<data>` is the platform companion data directory (or `TF3C_DATA_DIR`). Inspect the directory to list generated files:

- macOS: `ls -la "$HOME/Library/Application Support/tf3-companion/reports"`
- Windows PowerShell: `Get-ChildItem "$env:LOCALAPPDATA\tf3-companion\reports"`
- Linux: `ls -la "$HOME/.local/share/tf3-companion/reports"`

`--html` generates a matching `.html` file alongside the Markdown report. `--open` opens the report using your system's default application (your browser for HTML, or your default editor/viewer for Markdown). The MCP `report` tool accepts `kind` and optional `year`, returning the Markdown text directly.

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
