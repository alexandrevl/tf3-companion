## Why

Early player sessions identified valuable problems manually: trucks configured for the wrong cargo, full industry output stocks, capital tied up in idle ships and incomplete lines. Those sessions also established that instantaneous load is not average utilization. The delivered findings cover verified stock and line evidence; cargo mismatch and calibrated suitability require additional verified collector fields and units.

## What Changes

- **Cargo config mismatch** finding: a vehicle's configured cargo (`loadConfig`) that no stop of its line can load or unload.
- **Full stocks** findings: industry output stocks ≥90%, full warehouses, full station stocks.
- **Load trend**: line occupancy aggregated over the last N snapshots (mean, last, slope) with findings for persistently high/low load. When enough history exists, trend findings replace the instant-load findings (**behaviour change** to the findings introduced by `rebrand-tf3-companion`; see design).
- **Fleet fit**: per line, compare the fitted model with this year's catalog (capacity × speed ÷ running cost); flag vehicles near end of life and models out of production.
- **Idle capital**: vehicles in depots with no line, grouped by depot, with tied-up value.
- **Empty/orphan lines**: lines with no vehicles, no stops, or both.
- **Line scope economics**: profit per vehicle by line-length band (local/regional/intercity) computed from stop positions, independent of any line-naming mod.
- **Decision follow-up**: compare metrics of entities linked to a journaled decision before/after, once enough game time has passed for the rolling 12-month profit window to reflect the change.
- **Investigation**: determine and document what `transportedYear` really measures; no analysis uses it until documented.
- Every analysis yields findings with a stable `code` and numeric `evidence`, and is exposed through the `Companion` service plus MCP tools and `tf3c` commands where an on-demand view is useful (`findings` gains a `code` filter).
- **New mod data** (needs in-game validation): station-group positions and the industries/towns each station group serves. Required by cargo mismatch and line scope economics only. Snapshot `schemaVersion` bumps to 3 (additive fields). All other analyses use data already in snapshots.
- Store: per-line load history columns and a "done" game time on decisions (additive migration).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `company-analysis`: ADDED requirements for each analysis above (findings, evidence, trend, fleet fit, scope economics, data-availability behaviour).
- `decision-journal`: ADDED requirements for follow-up with before/after metrics and maturity states.

(The mod-side additions are an implementation prerequisite documented in design/tasks; the baseline `snapshot-bridge` and `agent-interface`/`companion-cli` specs are not changed in requirements here — new tools/commands are covered by the `company-analysis` and `decision-journal` requirements that expose them.)

## Impact

- Code: `analysis.py` (new finding builders, trend/fit/scope views), `store.py` (migration, history queries), `service.py` (`Companion` methods), `mcp_server.py` (tools `line_load_trend`, `fleet_fit`, `scope_economics`, `decision_followup`; `code` filter on `findings`), `cli.py`, `export.py` (findings sheet gains `code`).
- Mod: `content/tf3_companion/*.lua` station collector (positions, served industries/towns); schema doc in `knowledge/snapshot_schema.md`; knowledge `mechanics` gains `transportedYear` semantics.
- Tests: unit tests per analysis on synthetic snapshots; in-game validation of the new station fields and of `lifespan` units.
- Depends on changes 1–2 (English strings, finding `code`s, per-save store, schema v2). Feeds `basic-reports` (lines, fleet, cargo and decision follow-up reports reuse these views).
