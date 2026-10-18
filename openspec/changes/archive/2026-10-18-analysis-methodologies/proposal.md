# Proposal

## Why

How a company should be judged depends on how the player plays. The author's own rules (local passenger lines feed the town bus station and may lose money within a tolerance; towns are joined by intercity buses; freight may lose money while it matures) live in `data/analysis-rules.md` and are hard-coded in `data/analise/common.py`: a Portuguese, name-based classifier, role tolerances, markers and a fixed report set. Another player may join towns by train up to some distance, climb a bus -> train -> plane ladder by distance band, or struggle with an oil/chemicals chain and want rules tuned for that. The product is going to be distributed, so these policies must become data that players can write, share and apply, instead of code that only the author can change. Today the engine in `src/tf3companion/analysis.py` has exactly one implicit policy (the `Thresholds` dataclass plus fixed finding builders and severities), and the `report_*.py` modules carry further implicit knobs (persistence streaks, maturity years, trend windows).

## What Changes

- **Methodology** concept, kept separate from game mechanics (`knowledge/`, shared facts) and from evidence (per-save snapshots). The engine computes facts; a methodology assigns roles, markers/severities, tolerances, threshold overrides and recommendations, and says which reports and charts form its standard set.
- **Methodology file**: one self-contained, declarative JSON file validated against a packaged JSON Schema (`tf3c-methodology/1`). No executable code, no includes, no network. It contains roles (selectors over name patterns, transport mode, cargo, town count, stop geometry, industry type), tolerance parameters, rules (conditions over engine metrics with graded outcomes and templated messages), aggregate rules (per town, per station group), recommendations triggered by rule hits (including a distance-band mode ladder), engine threshold overrides, and a report/chart selection. Free-text `description` and `rationale` fields are part of the format.
- **Validation on load**: schema version, unknown structural keys, bad parameters and bad regexes are errors. Rules that reference a field the collector does not produce are listed as unsupported and skipped; a missing value is never evaluated as zero.
- **Library**: a packaged neutral `default` methodology (reproduces today's findings exactly) plus a user folder `<data>/methodologies/`. Import/export is plain file copy through `tf3c methodology import|export`. No marketplace, no download.
- **Applying**: per-save default binding, an explicit per-request override (`--methodology` on the CLI, `methodology` parameter on MCP tools), and a new one-shot `tf3c analyse` / MCP `analyse` that produces the methodology's standard report set. The analyst brief gains list/apply instructions.
- **Security**: methodology text is untrusted data. Its prose never instructs tool use, file operations or disclosure, never overrides data caveats, and is rendered as escaped plain text. MCP tools accept methodology ids only, never file paths.
- **Reproducibility**: every report, finding and verdict records `id@version` and a content hash. Changing the methodology never rewrites stored history because no verdicts are stored.
- **Output layout**: `<data>/saves/<saveId>/reports/<game-date>__<methodology-id>@<version>/`, one folder per game date and lens; the same inputs overwrite idempotently and different lenses coexist. **BREAKING** (pre-release): single-report output moves from `<data>/reports/<kind>.md` into the lens folder; `reports/latest.md` stays as a copy of the last generated report.
- **Author's methodology ported to English** as a packaged example, proving the schema expresses the current hard-coded rules without loss, including the town feeder balance and aircraft-per-terminal screening.

### Dependencies and overlap

- `cross-platform-and-saves` (D4/D5): save identity and `<data>/saves/<id>/` are not yet implemented or verified in game. This change resolves the report root and the binding location through one indirection (`save_root`); until save layout lands it falls back to `<data>` itself, with no claim of isolation. No part of this change blocks on the in-game identity probe.
- `basic-reports` already specifies `<data>/saves/<saveId>/reports/`; this change refines the sub-folder naming and adds the `methodology` provenance block. `analysis-insights` provides `Thresholds` growth, finding codes and load-trend/scope-economics facts that methodology rules can reference; its station-group positions are not in snapshots today, so distance rules stay unsupported until they exist. `agent-experience` owns the analyst brief that this change extends. Reconcile at archive time; none of those changes is edited here.

## Capabilities

### New Capabilities

- `analysis-methodology`: the methodology file format, field/operator vocabulary, roles, rules, aggregates, recommendations, ladders, thresholds overrides, report selection, load-time validation, evaluation semantics for missing data, security and provenance.
- `methodology-library`: packaged default and user folder, import/export, per-save binding and request override, `analyse` entry points on CLI and MCP, analyst-brief behaviour, report output layout by save, game date and methodology.

### Modified Capabilities

None. The only main spec in `openspec/specs/` is `installation-onboarding`, which this change does not alter. Requirements that touch capabilities still living in unarchived changes (`reports`, `companion-cli`, `agent-interface`, `save-management`) are stated inside the two new capabilities and should be folded into those capabilities when this change is archived after them.

## Impact

- Code (new): `src/tf3companion/methodology/` (loader, schema validation without new heavy dependencies, field registry, evaluator, templates, library, `default.json`, `schema-1.json`, `examples/`).
- Code (touched): `analysis.py` (apply threshold overrides and finding overrides, accept a resolved methodology), `reports.py` / `report_*.py` (take the methodology's tolerances where they currently use module constants, new `methodology` verdicts report kind), `service.py` (`Companion.analyse`, resolution, output layout), `cli.py` (`methodology` and `analyse` commands, `--methodology` flag), `mcp_server.py` (`list_methodologies`, `methodology_detail`, `analyse`, `methodology` parameter), `agent_instructions.md`, `knowledge/` (field catalog topic), `docs/` and `CHANGELOG.md`.
- Dependencies: none new. Validation is a small in-repo validator against the packaged schema; `jsonschema` is not added to runtime dependencies (see design D2).
- Data: no snapshot, store or collector change. `save.json` gains an optional `methodology` binding when the save layout exists.
- Tests: pytest on synthetic snapshots (default equivalence, author port, hypothetical oil/chemicals fixture, unsupported-field and security cases).

## Out of scope

- Any network sharing: registry, marketplace, download-by-URL, signing or update checks.
- Executable plugins or scripting inside methodology files (no expressions beyond the closed vocabulary).
- Collector/mod changes. Fields that would make methodologies stronger (station-group positions and served industries/towns, total terminals per station, "waiting to land" state, line creation date) are listed in the design as future work; rules needing them are reported unsupported until the collector provides them.
- Localization of methodology text or engine messages.
- Retiring or modifying `data/analise/` and `data/analysis-rules.md` (author-local, Portuguese, gitignored); the English port is created fresh and the old scripts are only read for parity checks.
- Per-entity manual overrides ("treat this line as local") and methodology inheritance/merging.
- Writing verdict history to the database.
