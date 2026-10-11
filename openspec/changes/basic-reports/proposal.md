# Proposal

## Why

The first sessions showed that conversation plus tables and charts beats a spreadsheet: players want to *read* how their company is doing, and agents need a ready-made, evidence-backed summary instead of stitching 20 tool calls together. Today the only output is an XLSX export that is opened with macOS Numbers (`open -a Numbers`), which is unusable on Windows and hard to share. The monthly snapshots already hold a full history, but nothing turns it into a per-year story ("how did 1984 go?"). With `analysis-insights` landed (load trend, fleet fit, idle capital), the inputs for good reports exist.

## What Changes

- New **reports** feature with six kinds: `company`, `lines`, `fleet`, `cargo`, `decisions` (follow-up) and `annual` (one report per game year).
- **Markdown is the primary format**: tables plus Mermaid charts that render in chat clients and on GitHub. Every chart is accompanied by a table with the same numbers, so nothing is lost where Mermaid does not render.
- **Self-contained HTML variant** (`--html`): one offline file with inline CSS and inline SVG charts, no CDN, no scripts, no network.
- **Annual report**: start/end balance and loan, total line profit, best/worst lines, lines and vehicles added/removed, modal mix change, decisions taken that year and their outcomes, notable findings; compares with the previous year when data exists. Behaviour is defined for incomplete years and missing history (explicit completeness label, never invented numbers).
- Reports are written under `<data>/saves/<saveId>/reports/` and use full entity names (line names, vehicle names, "depot in <town>").
- CLI: `tf3c report <kind> [--year Y] [--html] [--open] [--save <id>]`; `--open` uses the OS default app (Windows/macOS/Linux).
- MCP: new tool `report(kind, year?)` returning Markdown.
- XLSX stays as the raw-data export (`tf3c export`, `export_spreadsheet`), but the macOS-only `open -a Numbers` coupling is removed: opening uses the OS default application on Windows and macOS. Opening is requested with `--open`/`open` and never happens implicitly.
- `export_spreadsheet`'s `open_in_numbers` parameter (default true) is replaced by an `open` parameter defaulting to false. **BREAKING** for any agent that passed `open_in_numbers`; the MCP tool schema changes (pre-release product, no shim).

Out of scope: PDF output, e-mail/sharing, scheduled/automatic report generation, reports for several saves in one document, new analyses (those belong to `analysis-insights`), editing the game, any network access, interactive HTML (no JavaScript).

## Capabilities

### New Capabilities
- `reports`: report kinds, their content, the annual-report rules (completeness, comparison, history gaps), output formats (Markdown, offline HTML, XLSX raw export), file locations and naming.

### Modified Capabilities
- `companion-cli`: ADDED requirements for `tf3c report` and for cross-platform `--open` (applies also to `tf3c export`).
- `agent-interface`: ADDED requirements for the `report` MCP tool and the changed `export_spreadsheet` opening parameter.

## Impact

- Code (post-rebrand names): new `src/tf3companion/reports/` package (document model, one builder per kind, Markdown and HTML renderers); `service.py` gains `report(...)`; `cli.py` gains `report`; `mcp_server.py` gains `report` and the `export_spreadsheet` change; `export.py` loses nothing but is no longer tied to Numbers; a small cross-platform `open_file` helper in `paths.py`/service.
- Store: read-only access to monthly snapshots and decisions; one new query for "snapshots of game year Y". No schema change.
- Depends on: `cross-platform-and-saves` (per-save `reports/` dir, `--save`), `analysis-insights` (load trend, fleet fit, idle capital, finding codes).
- Dependencies: none new (HTML is generated from strings with escaping; `openpyxl` already present).
- Docs: `docs/reports.md` gets drafted here with sample output; the full docs set is `release-readiness`.
- Verification: pytest on the fixture store; the player eyeballs a real report in a chat client, a browser and Excel/Numbers.
