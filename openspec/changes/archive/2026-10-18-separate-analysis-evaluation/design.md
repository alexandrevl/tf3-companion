# Design

## Context

See proposal.md for motivation. `service.Companion.analyse()` currently obtains `_with_prev()`, builds a `Lens`, computes findings, calls `reports.render_report()` per kind, writes a bundle and calls `methodology.summary.summarise()`. That summary requires a folder and caps findings/recommendations at 10/15. `Lens` already supplies prepared policy, verdicts, a calendar clock and resolved report criteria; reuse it rather than building another evaluator. `reports.py` already has an in-memory `ReportDocument` and safe Markdown/HTML renderers, but builders still query `Store` and perform analyses; `extract-report-analyses` owns that latter extraction.

`Companion()` currently calls `load_paths()` (Steam discovery and directory creation) and `Store()` runs schema DDL. Merely skipping `_checked_ingest()` is therefore insufficient for a genuinely stored-only interface. MCP also caches a writable Companion across calls; the new read-only route must not inherit its thread-bound connection.

## Goals / Non-Goals

**Goals:** A useful complete machine evaluation independent of output folders; one validated policy/evidence context per operation; offline noncreating reads; preserve existing acquisition and publication conveniences; make boundaries enforceable through consumer behavior.

**Non-Goals:** A generic dependency-injection framework, new plugin system, persistent evaluation handles, global caching, mathematical rewrites, or a simultaneous extraction of every report algorithm. Existing report documents remain legitimate presentation models, not the new analysis API.

## Decisions

### D1. Four responsibilities, with the application owning composition

Evidence owns acquisition/persistence, identity resolution, units, clocks and measured facts. Analysis owns reusable domain algorithms and interpretation under prepared methodology. Presentation owns report selection, composition, formatting and escaping. Application operations orchestrate them; CLI/MCP adapt those operations and serialize results. Neither adapter independently reads game exports, classifies entities or builds reports.

Keep the current service as the application entry point rather than creating four deployable services. Modules need one-way responsibility boundaries, not a prescribed directory tree or a second implementation beside `analysis.py`.

### D2. A detached analytical result and an operation-local context

Add `evaluation.py` with an `Evaluation` result, a single `evaluate_selected(...)` application helper and a serializer. Reuse `Lens`, `Verdicts`, `Finding` and their numerical/evidence semantics. Keep validated methodology, selected snapshot and prepared calculation context as internal references; no live `Store`, SQLite connection, `ReportDocument`, HTML or output path belongs in the serialized result.

The machine envelope is versioned with `version: 1` and has these stable keys:

| Key | Contract |
|---|---|
| `snapshot` | Existing selected `{date, gameTime}` identity |
| `save` | Existing scope description, including honest isolation warning |
| `methodology` | Identity, content hash, selection origin, effective parameters/overrides and untrusted-content labeling |
| `timeBasis` | Existing shared calendar provenance and unknown reasons |
| `reportPolicy`, `engineThresholds`, `engineThresholdOrigins` | Existing effective criterion provenance; no second criteria registry |
| `roles` | Role counts plus entity assignments, unclassified and unknown classifications |
| `ruleResults` | Complete ordered rule/aggregate outcomes, hit evidence and aggregate measures, statuses and exclusions |
| `findings` | Complete finding objects using existing code/source/severity/entity/evidence semantics |
| `recommendations` | Complete ordered recommendations/ladders with priority, trigger evidence and untrusted text labeling |
| `disabledFindings` | Existing suppression decisions/counts |
| `coverage` | `skipped`, `unsupported`, `notEvaluable` with reasons and counts |

Measured evidence is carried in rule/finding records with the existing field caveats; this is not an unbounded copy of every raw snapshot. Unsupported structural/release capabilities fail through the shared gate, whereas ordinary missing live evidence stays in coverage. Preserve first-true/Kleene behavior and explicit methodology missing-value branches; do not introduce automatic success/maturity fallbacks.

Summary counts are derived from this result. Move folder/file fields and display caps into the bundle summary adapter in `methodology/summary.py`. Analytical findings, rule outcomes and recommendations are never capped by those summary limits. Methodology-requested table/chart projections retain their existing documented selection caps as presentation projections, not limits on rule evaluation. Their numeric series can be reused during composition; no figure rendering occurs in evaluation.

`extract-report-analyses` later adds `analysisViews` and an explicit finite `views` selector to this envelope, empty by default. This first change does not implement placeholder views, an empty extension registry, or new report calculations.

### D3. Stored-only construction and lifecycle

Add `Companion.open_stored(data: Path | None = None, save: str | None = None)` as an explicit read-only construction path. Resolve `data_directory()` and existing save scope/preferences without `load_paths()`, Steam discovery or mkdir. Factor common construction locally rather than retaining a second service implementation. Existing writable construction and acquisition APIs keep their behavior.

Add `Store(..., read_only=True)` using a SQLite read-only URI and no schema DDL or migration. Reuse read queries; validate the schema is readable and fail with actionable compatibility guidance otherwise. A missing root/database fails without creation; an existing supported empty store raises the existing no-snapshot error. Do not silently migrate, backfill or repair. Read-only mode is enforced by SQLite, not a convention to avoid calling writes. Writable methods used on this route must fail before filesystem side effects.

`Companion.evaluate(methodology=None, allow_path=False, param_overrides=None)` selects stored evidence only, whether invoked on an ordinary or read-only Companion. It never calls `current()`, `_with_prev()` or ingestion. CLI/MCP use `open_stored`, so startup also satisfies the no-write contract. Each MCP evaluation opens/closes its own read connection within the executing call; it never borrows the cached writable `_companion`. This fixes only the lifecycle needed for the new endpoint, not every existing MCP tool.

### D4. Capture selection once; preserve each history algorithm's bounds

Use a SQLite read transaction around selection and all evidence reads for an operation. Capture the same stored selector used by `Store.latest()` (not a new MAX(game_time) interpretation), the previous snapshot, prepared methodology bytes and parameters, and `Store.time_context(selected)`. Resolve preference precedence via the existing resolver, not in the adapters.

An operation-local evidence reader wraps the transaction and selected endpoint for consumers. Historical queries cannot cross that endpoint; different analysis families retain their own windows and statistical minima. In particular, `PROBE_SNAPSHOTS` is a rule support probe, not a replacement cap for every history report or clock anchor set. A reader can cache repeated bounded requests during one operation; there is no cross-call cache or persistent verdict history. Reuse selected snapshot objects rather than loading the same raw observation per report.

For standalone evaluation, close the read transaction after constructing the detached result. For the composite report workflow, keep the captured reader available while existing builders compose documents. Write output files only after evidence reads/document generation complete. A writer committing newer evidence concurrently does not change the operation's selected state. Existing legacy-unverified and rewind/identity limitations remain visible.

### D5. Separate evaluate, compose, render and publish without changing conveniences

Expose internal stages through the application boundary:

1. `evaluate_selected` produces the reusable result from selected evidence and prepared policy.
2. Document composition consumes that result and captured evidence reader; first-change adapters allow existing builders their current bounded factual queries.
3. Pure renderers turn a composed `ReportDocument` into Markdown or HTML. One single-report call with both formats composes once and renders twice.
4. Existing `methodology/output.py` stages and publishes files/manifests atomically.

Migrate `analyse`, `findings` and single-report generation to the shared evaluation helper while preserving their existing checked ingestion, response shapes, stable finding codes, standard report set, report-folder layout and latest-pointer semantics. `analyse` remains a convenience, not a compatibility shim for removed evaluation code. For multi-report bundles, policy preparation and base engine/methodology evaluation occur once for the selected endpoint. Annual/historical endpoints require their own bounded endpoint evaluation; never attach latest-snapshot verdict facts to historical data. `extract-report-analyses` removes remaining report-local diagnostic computations after this boundary is established.

A publication failure must not destroy previous output, and must not make standalone evaluation depend on a writable report directory. Validation happens before publication, using the existing shared preparation gate. An initial evaluation can succeed even if later document composition cannot; the composite call must report its own failure, not claim reports were produced.

### D6. Small additive adapter contract

Add `tf3c evaluate [--methodology ID|FILE] [--save ID] [--param NAME=VALUE ...] [--json]`. Without `--json`, print an evaluation summary with no output-folder claim; with it, emit the complete version-1 envelope. Reuse existing parameter parsing. Do not add a stored/fresh toggle: this command is always stored-only. Acquisition remains `ingest`/`refresh`; `analyse` retains its current acquisition stage.

Add MCP `evaluate(methodology=None, save=None, parameters=None)` with the same policy-override validation and reference restrictions. `parameters` maps to the service's `param_overrides`; MCP never accepts a methodology path. JSON results must be semantically identical to the CLI for identical explicit inputs. No adapter adds business rules or parses a report to answer a query.

Update analyst guidance and `docs/methodologies.md` to distinguish evaluate/analyse/report, stale stored evidence, untrusted text and baseline criteria. Do not rewrite unrelated tool freshness contracts or claim all existing query endpoints are now nonmutating.

## Risks / Trade-offs

- Read-only legacy schema incompatibility -> explicit error requiring the existing supported write/upgrade workflow; never migrate under an evaluation label.
- Longer read transaction while old builders compose -> bound history reads, reuse loaded observations, close before file publication; report extraction later removes composition-time database access.
- Complete analytical lists are larger than summaries -> preserve semantics first, serialize only result/evidence records and retain existing file/rule limits; do not hide truncation behind presentation caps.
- Concurrent implementation of clock/activation/default/report-policy changes -> depend on their actual shared APIs and provenance; do not copy historical formulas or freeze intermediate bugs as intended behavior.
- Result objects containing mutable internal mappings -> keep them operation-owned, never cache globally or mutate between consumers; public serialization must not leak private runtime records.

## Migration Plan

Implement read-only construction and result serialization, then expose stored evaluation, then cut over composite consumers and adapters. Update affected tests/callers without deprecated forwarding aliases. Keep existing bundle outputs and stored evidence untouched; this change has no database migration or report regeneration on startup. Reverting code must not require restoring player evidence or preferences. Integrate after the four prerequisite methodology/time changes; continue with `extract-report-analyses`, then `retire-local-analysis-generator`.
