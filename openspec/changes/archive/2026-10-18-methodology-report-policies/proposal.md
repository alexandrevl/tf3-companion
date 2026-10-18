# Proposal

## Why

The selected methodology currently reaches only duplicated maturity and full-stock thresholds in three report builders; other reports silently create default `Thresholds` or embed judgment constants. A player's verdicts and suggested priorities can therefore disagree with the methodology recorded in their header. Make those report decisions explicit, reproducible player policy without allowing policy to weaken evidence safeguards.

## What Changes

- Add optional `report_policies` to methodology schema 1: a finite registry of numeric criteria for industries, lines-history, bottlenecks and expansion, with documented units, ranges and cross-field constraints. Existing files and default report decisions remain unchanged.
- Resolve one immutable report analysis context containing engine thresholds and effective report policies, then pass it through all affected builders/helpers, including vehicle-roi fit checks and expansion/bottlenecks. Eliminate hidden default threshold construction along these paths.
- Expose effective values, default-versus-file origins and registry revision in report documents, `methodology show`, analysis JSON and manifests. Preserve identity/hash and standard data caveats.
- Keep sample sufficiency minima, bounded history access, schema validation, missing-data behavior, game mechanics and presentation caps engine-owned; disallow attempts to configure them.
- Preserve existing report algorithms, greedy ranking, deterministic tie-breaking and default recommendations. Test actual verdict/ranking changes, not only configuration parsing.

## Capabilities

### New Capabilities

- `report-policies`: closed report judgment registry, resolution, guarded consumption and effective-policy disclosure.

### Modified Capabilities

- `analysis-methodology`: report selection/provenance includes effective report policy and engine thresholds; the three-layer separation explicitly permits report verdict/ranking differences over identical measured facts.

## Impact

Affected implementation: `methodology/schema-1.json`, validator/loader/model/resolution/lens/summary/provenance, report dispatch and builders for industries, lines-history, bottlenecks, expansion and vehicle-roi, service/CLI/MCP outputs sharing those paths. Extend existing methodology/report tests and `docs/methodologies.md`; revise the report-local constants section rather than adding a second authoring convention. No database or snapshot migration.

Dependencies: the archived `analysis-methodologies` implementation is the baseline. Reuse the document model, safe renderers and report orchestration already supplied by `basic-reports`; do not redo its remaining annual-report/opening tasks. `analysis-insights` owns station positions/links and their in-game validation. Its absent geometry remains unavailable; these policy changes need no new collector and cannot make distance ladders evaluable. No dependency on save isolation from `cross-platform-and-saves`; comparison is supported in the current implicit single-save store. Coordinate report signatures with any concurrently applied game-year methodology change without importing its time-calibration scope.

`validated-methodology-activation` owns the shared strict validation/debug gate and preservation of previous selection/results on failure. This change registers all report-policy constraints with that gate; invalid policy never activates or falls back silently. Missing report evidence remains a valid-methodology insufficient-data case.

Out of scope: arbitrary expressions/Python, new report kinds, presentation/table/chart knobs, custom score formulas, user lowering of minimum samples, reinterpretation of units or rolling accounting, additional station collection, calibrated game-year changes, localization, plugins, network access, persistent verdicts, game actions, save management or a new comparison subcommand. CLI smoke uses existing explicit methodology selection on the same stored evidence.
