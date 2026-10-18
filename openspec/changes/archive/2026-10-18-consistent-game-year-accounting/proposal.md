# Proposal

## Why

The same vehicle and three-year maturity policy currently produce different ages in core analysis and historical reports: core analysis divides by `meta.yearDuration`, while reports calibrate against the game's calendar with incompatible constants and fallbacks. Playtest P-020 records 5,856,303 observed ticks per calendar year versus a nominal 1,461,000, changing the observed mature losing freight-line count from 10 to 2; that observation is evidence for one save, not a universal conversion constant.

## What Changes

- Define `GAME-YEAR` as 365.25 elapsed days of the in-game calendar (not wall time, the nominal default-year duration or a rolling financial accounting period), with one shared conversion and explicit precision/provenance.
- Introduce a pure, evidence-bound calendar clock built from the selected history, with direct dated spans and bracketed tick-to-calendar estimates. Missing dates, insufficient calibration, out-of-range purchases and ambiguous timelines remain unknown; never use a hard-coded 4x correction, local-script fallback or nominal-duration fallback.
- **BREAKING**: keep public age field names but change their numeric basis consistently across CLI, MCP, XLSX, findings, methodology facts and all reports. Unsupported historical ages become null rather than nominal-year estimates. Add machine-readable `timeBasis` provenance and a conversion version to generated outputs.
- Preserve the oldest currently assigned vehicle as the line-age proxy; label first-observed spans separately. Keep policy thresholds numeric and unchanged, document their GAME-YEAR unit and never let a methodology select a different physical clock.
- Preserve stored raw snapshots, decisions and rolling financial facts. Recompute on demand, retain old generated files as historical artifacts, and describe the behavior of legacy single-save stores without claiming isolation.
- Separate decision elapsed GAME-YEAR coverage from the collector's nominal financial query window; do not call a calendar-year comparison a proven completed `profitYear` window.

## Capabilities

### New Capabilities

- `game-calendar-time`: a shared, evidence-bound GAME-YEAR conversion, consumer consistency, unknown-state behavior and migration/provenance contract.

### Modified Capabilities

None. The new capability supplies the numeric-fact contract underneath `analysis-methodology`'s existing three-layer separation, field catalog, maturity override and missing-value requirements, without changing their scenarios or methodology structure.

## Impact

Targets `snapshot.py`, `store.py` history selection, `analysis.py`, `service.py`, export/MCP surfaces, `methodology/fields.py` and its generated field catalog, methodology engine/summary/report metadata, `reports.py`, `report_history.py`, `report_lines_history.py`, `report_vehicle_roi.py`, `report_towns.py`, `report_industries.py`, the remaining report consumers of year duration, tests and English knowledge/docs/changelog. No evidence database rewrite or collector schema bump is needed.

### Dependencies and ordering

Implement the clock and evidence selection before consumer migration, then methodology provenance/documentation and isolated real-data verification. `cross-platform-and-saves` owns verified lineage, storage routing and rewind detection; consume its verified context when available, do not implement those features here. Ambiguous legacy histories must fail closed for cross-snapshot conversion meanwhile. `analysis-insights` owns fleet fit, scope economics, decision follow-up and geometry collection; its future age/follow-up calculations must consume this clock rather than its planned `yearDuration` arithmetic. `basic-reports` owns annual reporting, coverage and output orchestration; preserve those features and replace only their time-basis assumptions. These proposals do not need to finish before the pure clock or conservative single-store migration, but verified cross-save/branch analysis remains gated on `cross-platform-and-saves`.

### Non-goals

No implementation during this proposal; no save identity invention, lineage repair, snapshot routing or collector changes; no recalculation of `profitYear`, finance ledger, calendar-year profit reconstruction or `transportedYear` interpretation; no inferred line creation date; no model-lifespan/depot-day unit conversion without independently verified units; no speed-control collection, universal ticks/year calibration, rewriting local `data/analise` scripts or player data, localization, plugins or network behavior.
