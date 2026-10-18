# Proposal

## Why

Several existing report builders own persistence diagnostics, expansion ranking and historical classifications, so those results cannot be reused without building presentation objects. After `separate-analysis-evaluation` establishes a stored-evidence evaluation boundary, the existing analytical work must move behind that boundary rather than leave a second report-owned engine.

## What Changes

- Extract the finite existing bottleneck, expansion, line-history, company-history, industry, vehicle-return and town analyses into typed reusable domain views, with evidence, reasons, deterministic order and coverage.
- Extend the prerequisite evaluation operation with an explicit closed selection of seven views; CLI and MCP remain peer adapters. Omitted views perform no extended analysis.
- Migrate every report builder's business calculations, including base company/lines/fleet/cargo/annual/decision comparisons, to the same analysis layer; preserve report kinds, algorithms and neutral-default outputs except documented evidence-safety corrections.
- Keep document layout, prose, escaping, chart styling and display caps in presentation; classification, candidate exclusion, score breakdowns and follow-up selection belong to analysis.
- Reuse validated methodology preparation, effective report policies, selection provenance and the shared calendar clock. Add no methodology criteria registry, preference file or derived-result database.
- Replace effectively unlimited/post-filtered history lookups with endpoint-bounded compact projections and fixed bounded full-snapshot hydration; disclose all sampling and coverage limits.

## Capabilities

### New Capabilities

- `operational-analysis-views`: Finite structured diagnostic, ranking and historical views reusable independently of reports, using the operation's selected evidence and policy.

### Modified Capabilities

None. This capability consumes the evaluation contract introduced by `separate-analysis-evaluation`; it does not redefine methodology syntax or selection.

## Impact

Implementation affects `reports.py`, the seven specialized report builders, analysis/domain types, store projections, `Companion.evaluate`, CLI/MCP evaluate adapters, report/evaluation tests, `docs/reports.md`, `docs/methodologies.md`, agent interface documentation and `CHANGELOG.md`. Existing direct builder consumers must migrate together rather than keep a legacy analytical path. Report Markdown/HTML and `analyse` bundle/publication contracts remain intact.

Dependencies: implement after `separate-analysis-evaluation`; consume `validated-methodology-activation`, `methodology-report-policies`, `consistent-game-year-accounting` and `user-methodology-default` without duplicating their responsibilities. `retire-local-analysis-generator` follows this extraction and separately decides which local-script behaviors to preserve. Existing `basic-reports` and `analysis-insights` plans overlap report/diagnostic territory and must consume these views for affected existing computations, not introduce competing implementations.

Out of scope: implementing these proposals now; local-generator deletion; historical report/evidence/preference/database modification; personal player defaults; mod or simulation changes; new geometry collection; dashboards; plugins; network access; speculative financial forecasts; guaranteed save/branch isolation; arbitrary user-defined analyses or history-query knobs. Configurable runtime player stores and explicitly imported methodology files remain supported; no checkout `data/` dependency is introduced.
