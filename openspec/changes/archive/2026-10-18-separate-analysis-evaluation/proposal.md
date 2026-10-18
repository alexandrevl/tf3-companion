# Proposal

## Why

`Companion.analyse()` currently evaluates a methodology, renders documents and publishes a bundle as one implementation path, while the machine summary is coupled to output folders and presentation caps. Agents and future presentation surfaces need the complete analytical result without creating reports or importing fresh game exports implicitly.

## What Changes

- Add a stored-evidence-only evaluation operation, exposed as `Companion.evaluate`, `tf3c evaluate` and MCP `evaluate`, returning structured findings, roles, rule outcomes, aggregate measures, recommendations, evidence references and coverage with methodology/time/policy provenance.
- Separate four responsibilities: evidence acquisition and factual measurement; analysis under declarative policy; document composition/rendering; CLI/MCP adapters and application orchestration. MCP and CLI remain peer interfaces to the same application operations.
- Capture one operation-scoped evidence selection and validated effective methodology. Evaluation neither ingests nor refreshes, renders documents, writes outputs/preferences nor persists verdicts. Existing stored data can be evaluated without Steam discovery or an installed game.
- Preserve `analyse` as the convenient checked-ingestion -> evaluation -> report composition -> atomic publication workflow, including its existing report layout and summary. Preserve single-report publication and latest-report behavior.
- Move machine result construction out of folder-dependent summary code; reuse the same evaluation in findings, report composition and bundle orchestration rather than recalculating it per consumer. Keep existing public acquisition behavior of those convenience calls unless explicitly stated here.
- Document that a packaged default is an explicit baseline policy, not the absence of judgment. General analysis must not require the author's naming convention or a particular playstyle.

## Capabilities

### New Capabilities

- `analysis-evaluation`: stored-only analytical evaluation, structured result/provenance contract, operation-scoped evidence and adapter equivalence without presentation or publication side effects.

### Modified Capabilities

- `methodology-library`: retain one-step analysis as composition over the evaluation operation, explicitly distinguish stored evaluation from fresh-evidence acquisition and report publication.

## Impact

Affected code: `service.py`, `analysis.py`, `methodology/{lens,summary,engine}.py`, `store.py`, `paths.py`, `reports.py`, report publication call sites, CLI/MCP registration and analyst guidance. Add a small `evaluation.py` boundary rather than a plugin framework or a second analysis engine. Extend existing methodology/service/report tests and add focused evaluation behavior coverage; update existing documentation and release notes during implementation.

Prerequisites: consume the effective-policy preparation supplied by `validated-methodology-activation`, precedence/provenance from `user-methodology-default`, resolved criteria from `methodology-report-policies`, and the calendar evidence API from `consistent-game-year-accounting`. Do not recreate their validators, clocks or configuration layers. These changes are actively being implemented; their actual APIs must be integrated rather than inferred from unchecked task counts.

Follow-on changes: `extract-report-analyses` consumes this boundary to move report-local diagnostics into reusable analytical views. `retire-local-analysis-generator` closes the local experiment after the selected general capabilities have official owners. Neither follow-on is required to expose the initial evaluation of existing engine/methodology results.

Out of scope: implementing new report-local analytical views, changing existing mathematical algorithms or policy defaults, adding collector fields, fixing all existing MCP lifecycle/concurrency issues, dashboards, network access, plugins, a persistent evaluation cache, arbitrary historical CLI selectors, save isolation, removal of local scripts, and deleting or migrating player evidence or historical reports. No mod or simulation change is needed.
