# Spec Delta

## Purpose

Defines the reports the companion generates from a save's snapshot history: their kinds, content, behaviour with incomplete or missing history, output formats and where they are stored. Reports turn raw snapshots into readable, evidence-backed summaries for players and agents.

## ADDED Requirements

### Requirement: Report kinds
The system SHALL provide the report kinds `company`, `lines`, `fleet`, `cargo`, `decisions` and `annual`. Requesting any other kind MUST fail with an error listing the valid kinds and MUST NOT write a file.

#### Scenario: Valid kinds
- **WHEN** a report is requested for each of `company`, `lines`, `fleet`, `cargo`, `decisions` and `annual` on a save with data
- **THEN** each request produces a non-empty Markdown report

#### Scenario: Unknown kind
- **WHEN** a report of kind `weekly` is requested
- **THEN** the request fails, the error lists the six valid kinds, and no file is written

### Requirement: Report header and provenance
Every report SHALL start with a title, the company or save label, the game date of the snapshot it is based on, the number of snapshots it used and the generation notes (completeness, missing data). Money SHALL be shown with thousands separators and values SHALL come only from stored snapshots and decisions.

#### Scenario: Header content
- **WHEN** a company report is generated from a snapshot dated 1984-03-01
- **THEN** the header shows the save label, the date 1984-03-01 and the count of snapshots used

### Requirement: Full entity names
Reports SHALL identify lines, vehicles, industries, stations, towns and depots by their full names, never only by numeric id. When an entity has no name, the report SHALL use the kind plus id (for example "Line #123").

#### Scenario: Named entities
- **WHEN** the lines report lists a line named "Utrecht - Amersfoort Freight"
- **THEN** that full name appears in the table and the numeric id does not replace it

#### Scenario: Unnamed entity
- **WHEN** a vehicle has no name in the snapshot
- **THEN** the report shows it as "Vehicle #<id>"

### Requirement: Company report
The company report SHALL show balance, loan, net position, company value, number of lines and vehicles, total annual line profit, the change against the previous snapshot and (when a snapshot about one game year earlier exists) against the previous year, annual profit and vehicle count by transport mode, profit per vehicle by transport mode, and a balance/loan history chart over the stored snapshots.

#### Scenario: Previous month and year available
- **WHEN** the store holds monthly snapshots covering at least 13 months and the company report is generated
- **THEN** it shows deltas against the previous month and against the same month one year earlier

#### Scenario: Only one snapshot
- **WHEN** the store holds a single snapshot
- **THEN** the report shows current figures, states that no comparison is available and omits the history chart rather than drawing a single point

### Requirement: Lines report
The lines report SHALL list the 15 most and 15 least profitable lines by annual profit, the loss-making lines with likely causes drawn from existing findings, lines without vehicles or stops, and the load trend over the last stored snapshots (the `analysis-insights` trend, not the instantaneous load).

#### Scenario: Top and bottom
- **WHEN** a save has 99 lines and the report is generated
- **THEN** it contains a top-15 and a bottom-15 table ordered by annual profit

#### Scenario: Few lines
- **WHEN** a save has 10 lines
- **THEN** each line appears at most once across the top and bottom tables

#### Scenario: Load trend with short history
- **WHEN** fewer snapshots exist than the load-trend window
- **THEN** the report uses the available snapshots and states how many were used

#### Scenario: Empty lines
- **WHEN** a line has no vehicles
- **THEN** it appears in the "lines without vehicles" section with its full name

### Requirement: Fleet report
The fleet report SHALL show vehicle age against model lifespan, loss-making vehicles, vehicles idle in depots with the capital tied up in them, models no longer in production and, when a vehicle catalog is stored, better models available in the game year (fleet fit).

#### Scenario: Idle capital
- **WHEN** 10 vehicles sit in depots without a line
- **THEN** the report lists them with their depot name and shows the summed value

#### Scenario: No catalog stored
- **WHEN** no stored snapshot carries a vehicle catalog
- **THEN** the report omits the model-availability section and says the catalog is missing

### Requirement: Cargo report
The cargo report SHALL show industries with full output stocks, unshipped production, the nearest consumers of that cargo with distance in km, and industries that are closing or about to close.

#### Scenario: Full output stock
- **WHEN** an industry's output stock is at least 90% full
- **THEN** it appears in the full-stocks table with the stock, capacity and cargo

#### Scenario: No industry data
- **WHEN** the snapshot has no industries
- **THEN** the cargo report states that no industry data is available and is still produced

### Requirement: Decisions follow-up report
The decisions report SHALL list each journaled decision with its status, game date, rationale and outcome, and for every decision that references measurable entities (lines, vehicles) SHALL show those entities' key metrics (annual profit, vehicles, load) at the decision's snapshot and in the latest snapshot. A decision younger than one game year SHALL be flagged as "profit window not yet complete" because annual profit is a rolling 12-month figure.

#### Scenario: Before and after
- **WHEN** a decision recorded in 1983-03 refers to a line and the latest snapshot is 1984-06
- **THEN** the report shows that line's profit, vehicles and load at 1983-03 and at 1984-06 with their differences

#### Scenario: Young decision
- **WHEN** a decision is 4 game months old
- **THEN** its comparison is shown but flagged as "profit window not yet complete"

#### Scenario: Entity gone or unresolved
- **WHEN** a decision references an entity absent from the latest snapshot
- **THEN** the row states "entity no longer exists" and the report is still produced

#### Scenario: No decisions
- **WHEN** the journal is empty
- **THEN** the report states that no decisions are recorded

### Requirement: Annual report content
The annual report for a game year Y SHALL contain: balance and loan at the start and end of Y; total annual line profit at the end of Y; the best 5 and worst 5 lines by annual profit at the end of Y; lines and vehicles added and removed during Y; the modal mix (lines, vehicles, annual profit by transport mode) at the start and end of Y with its change; decisions recorded during Y with their status and outcome; notable findings (high-severity findings at the end of Y); and a balance/loan chart over Y's snapshots.

#### Scenario: Full monthly coverage
- **WHEN** there is a preceding-year baseline and at least one observation in every month of Y without a timeline rewind
- **THEN** the report labels its monthly coverage complete, prints exact observation dates and does not claim exact calendar-year accounting

#### Scenario: Added and removed entities
- **WHEN** a line exists at the end of Y but not at the start
- **THEN** it is listed under lines added with its full name, and a line present only at the start is listed under lines removed

#### Scenario: Default year
- **WHEN** `annual` is requested without a year
- **THEN** the report is generated for the game year of the most recent stored snapshot

#### Scenario: Year with no snapshots
- **WHEN** `annual --year 1950` is requested and no snapshot belongs to 1950
- **THEN** the request fails with an error naming the years that do have data and no file is written

### Requirement: Annual report year comparison
When snapshots exist for year Y-1, the annual report SHALL add a comparison against Y-1 (end balance, end loan, total line profit, number of lines and vehicles, best line). When they do not, the comparison section SHALL say "no previous-year data" and SHALL NOT show zeros or blanks as if they were values.

#### Scenario: Previous year present
- **WHEN** the store has snapshots in both 1983 and 1984 and the 1984 annual report is generated
- **THEN** it contains a comparison table with 1983 and 1984 columns and their differences

#### Scenario: First year of history
- **WHEN** the store starts in 1984 and the 1984 report is generated
- **THEN** the comparison section states no previous-year data exists

### Requirement: Incomplete years and baselines
The annual report SHALL show actual baseline/end dates, observed months and sampling gaps. A later-year snapshot MUST NOT establish completeness of Y. Coverage is partial without a preceding-year baseline, any month or an uninterrupted timeline. With all twelve months and a preceding-year baseline it SHALL say "monthly coverage complete", not exact calendar-year accounting.

#### Scenario: Year in progress
- **WHEN** the latest snapshot is 1984-06-01 and `annual --year 1984` is generated
- **THEN** the report is labelled "in progress through 1984-06-01" and all figures are "to date"

#### Scenario: Missing previous-year-end snapshot
- **WHEN** no snapshot exists in Y-1 and the first snapshot of Y is 1984-03-01
- **THEN** the start balance and loan come from 1984-03-01, the report says "history starts mid-year" and the lines and vehicles added/removed refer to that interval

#### Scenario: Gap in the middle of the year
- **WHEN** snapshots for Y are missing for three consecutive months
- **THEN** the report lists the gap and its charts show only the points that exist, without interpolation

#### Scenario: Annual profit semantics
- **WHEN** the annual report states total line profit
- **THEN** it identifies the figure as the sum of the game's rolling 12-month line profit at the end snapshot, not a calendar sum of the monthly values

#### Scenario: Later year with missing coverage
- **WHEN** only March of Y and January of Y+1 were collected
- **THEN** Y is historical but has partial coverage; its March figures are not described as year-end figures

### Requirement: Annual report and decisions
The annual report SHALL list decisions whose game date falls in Y. For each it SHALL show status and recorded outcome, and the before/after metrics of referenced entities as in the decisions report, flagging windows that are not yet complete.

#### Scenario: Decision outcomes in the year
- **WHEN** one decision was recorded in Y with status `done` and an outcome
- **THEN** the annual report lists its title, status, outcome and the metrics of its entities

#### Scenario: No decisions in the year
- **WHEN** no decision has a game date in Y
- **THEN** the section says no decisions were recorded that year

### Requirement: Markdown with Mermaid charts
Reports SHALL be written as Markdown using pipe tables and fenced `mermaid` blocks for charts (line/bar charts for history and rankings, pie for modal mix). Every chart SHALL be followed by or accompanied by a table containing the same values. User-provided names MUST be escaped so they cannot break tables or Mermaid syntax.

#### Scenario: Chart plus table
- **WHEN** a report contains a balance history chart
- **THEN** the Markdown has a fenced `mermaid` block and a table with the same data points

#### Scenario: Hostile name
- **WHEN** a line is named `A | B "quoted" <b>`
- **THEN** the pipe table keeps its column count and the Mermaid block remains syntactically valid

### Requirement: Offline HTML variant
When HTML is requested the system SHALL write a single self-contained `.html` file with the same content as the Markdown, with inline CSS and charts drawn as inline SVG. The file MUST NOT reference external resources (stylesheets, fonts, scripts, images, CDNs), MUST NOT contain JavaScript and MUST render without network access. All text from the save MUST be HTML-escaped.

#### Scenario: Self-contained
- **WHEN** an HTML annual report is generated
- **THEN** the file contains no `<script>` element and no `src=`/`href=`/`url(` pointing to `http`, `https`, `//` or a relative file

#### Scenario: Same content
- **WHEN** the Markdown and HTML versions of a report are generated from the same data
- **THEN** every table in the Markdown has an equivalent table in the HTML with the same values

#### Scenario: Escaped names
- **WHEN** a line is named `<script>alert(1)</script>`
- **THEN** the HTML shows the text literally and contains no executable element

### Requirement: Report storage
Reports SHALL be written under the active save's `reports/` directory (`<data>/saves/<saveId>/reports/`), creating it if missing. File names SHALL be `<kind>.md`, or `annual-<year>.md` for annual reports, with `.html` for the HTML variant. Generating the same report again SHALL overwrite the previous file. Writing SHALL be atomic enough that an interrupted run never leaves a truncated report under the final name.

#### Scenario: Location and names
- **WHEN** the fleet report and the 1984 annual report are generated for save `a1b2c3`
- **THEN** `…/saves/a1b2c3/reports/fleet.md` and `…/saves/a1b2c3/reports/annual-1984.md` exist

#### Scenario: Overwrite
- **WHEN** the company report is generated twice
- **THEN** one `company.md` exists and it reflects the second run

#### Scenario: Reports never mix saves
- **WHEN** reports are generated for two saves
- **THEN** each save's `reports/` directory contains only its own reports

### Requirement: No data, no report
When the active save has no stored snapshot, report generation SHALL fail with an error that says no snapshot was found and how to obtain one, and SHALL NOT write a file.

#### Scenario: Empty store
- **WHEN** any report kind is requested on an empty store
- **THEN** the request fails with a "no snapshot" error and no report file exists

### Requirement: Spreadsheet remains a raw-data export
The XLSX export SHALL remain a raw-data export of the current snapshot and its history, independent of the reports, written under the save's `exports/` directory. Opening the file SHALL be done only on request and with the operating system's default application.

#### Scenario: Export unchanged
- **WHEN** the export is generated
- **THEN** an `.xlsx` file with the Summary, Lines, Vehicles, Industries, Towns, Opportunities, Findings, History and Decisions sheets is written under `exports/`

#### Scenario: No implicit open
- **WHEN** the export is generated without the open option
- **THEN** no application is launched

#### Scenario: Open on request on each OS
- **WHEN** the export is generated with the open option
- **THEN** the file is opened via the default handler (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux) and a failure to open produces a warning while the file path is still reported
