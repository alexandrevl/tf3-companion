# Tasks

## 1. Report document model and renderers

- [ ] 1.1 Create `src/tf3companion/reports/` with the document model (heading, paragraph, note, table, chart) and verify with a unit test that a sample document builds
- [ ] 1.2 Implement the Markdown renderer (pipe tables, fenced `mermaid` for line/bar/pie, escaping of `|`, quotes, newlines, label truncation in charts, series decimation) and verify with golden-file tests including the hostile name `A | B "quoted" <b>`
- [ ] 1.3 Implement the HTML renderer (inline CSS, inline SVG line/bar/pie with `<title>`, full escaping, no scripts, no external references) and verify with tests: no `<script>`, no `http`/`//`/`url(` references, `<script>alert(1)</script>` name rendered inert, every Markdown table has an HTML counterpart with equal cell values
- [ ] 1.4 Add atomic file writing to the save's `reports/` dir (temp file + replace, create dir) and verify with tests for naming (`<kind>.md`, `annual-<year>.md`, `.html`) and overwrite

## 2. Store queries and shared helpers

- [ ] 2.1 Add store queries for the years present, the snapshots of a game year (ordered), the snapshot nearest a given game time, and a snapshot at an exact `game_time`; verify with `tests/test_store.py` cases (including snapshots without `meta.date`)
- [ ] 2.2 Add the cross-platform `open_file` helper (Windows `os.startfile`, macOS `open`, Linux `xdg-open`, failure → warning) and delete `_numbers_app` / `open -a Numbers`; verify with tests that patch the platform and assert the chosen opener, and that failure does not raise
- [ ] 2.3 Add the entity-name helper (full name or "<Kind> #<id>") and the decision-entity resolver (id → exact name → unique partial name); verify with unit tests incl. unresolved and removed entities

## 3. Company, lines, fleet and cargo reports

- [ ] 3.1 Implement the company report builder (D4 sources, previous-month and year-ago deltas, single-snapshot case) and verify with fixture-store tests for 1 snapshot and ≥13 monthly snapshots
- [ ] 3.2 Implement the lines report builder (top/bottom 15 without duplicates, loss-makers with finding causes, empty lines, load trend from `analysis-insights`, short-history note) and verify with tests for 99-line, 10-line and empty-line fixtures
- [ ] 3.3 Implement the fleet report builder (age vs lifespan, loss-making vehicles, idle capital with depot names, out-of-production models, fleet fit; no-catalog note) and verify with fixture tests for catalog present/absent
- [ ] 3.4 Implement the cargo report builder (full stocks ≥90%, unshipped production, nearest consumers in km, closing industries) and verify with fixture tests, including a store whose snapshots are schema 2 (no station positions)

## 4. Decisions follow-up and annual report

- [ ] 4.1 Implement the decisions report builder (before/after metrics at decision time vs latest, young-decision flag, entity gone, empty journal) and verify with tests for each scenario in `specs/reports`
- [ ] 4.2 Implement the annual report builder following D5 (baseline, completeness, gaps, totals with rolling-profit label, best/worst 5, added/removed, modal mix change, decisions of the year, high-severity findings, previous-year comparison) and verify with tests: complete year, in-progress year, mid-year history start, gap inside the year, first year of history, year without data, default year
- [ ] 4.3 Add a fixture store builder in `tests/` that synthesises 2 game years of monthly snapshots with known lines, vehicles, balances and decisions, and use it for golden Markdown and HTML outputs of every kind; verify with `pytest tests/test_reports*.py`

## 5. Service, CLI and MCP integration

- [ ] 5.1 Add `Companion.report(kind, year, html)` (ingest, build, write, return Markdown and paths) with validation of kind/year and the "no snapshot" error; verify with service tests that no file is written on any error
- [ ] 5.2 Add `tf3c report <kind> [--year] [--html] [--open] [--save]` and `--open` for `tf3c export`; verify with CLI tests for paths printed, exit codes, the year-on-wrong-kind and no-year-data errors, and `--open` calling the helper only when given
- [ ] 5.3 Add the MCP tool `report(kind, year?)` with the per-kind description and replace `export_spreadsheet`'s `open_in_numbers` with `open=false`; verify with MCP tool tests (Markdown returned, file written, invalid args error, old parameter rejected)
- [ ] 5.4 Update `export.py` strings/sheets only as needed to drop Numbers references and write to the save's `exports/`; verify the workbook still has the nine sheets in a test

## 6. Documentation and real-save check

- [ ] 6.1 Write `docs/reports.md` (kinds, annual report semantics incl. rolling profit and incomplete years, HTML offline guarantee, file locations, sample output) and verify every command in it runs as written against the fixture store
- [ ] 6.2 Final integration check: run `pytest` and, with the real save, `tf3c report annual --html --open` and `tf3c report company`; confirm the Markdown renders Mermaid in a chat client/GitHub preview, the HTML opens offline (network disabled) with charts visible, and `tf3c export --open` opens in the default spreadsheet app
