# Design

## Context

See `proposal.md` for motivation. `data/analise/gerar.py` loads every stored snapshot, classifies it in `common.py`, dynamically imports five renderers and writes dated Markdown pages. `common.py` prepends checkout `src/` to `sys.path`, defaults to a personal macOS save directory and writes beneath checkout `data/exports/analise`. These are observed legacy details, not supported product interfaces.

The package already has methodology roles/rules/aggregates, factual rows, findings and fourteen report kinds. Current source and docs already use the shared calendar clock; playtest P-020's old file/line references are historical observations, not current bugs. `pyproject.toml` packages `src/tf3companion` and the bridge. `tests/test_methodology_packaging.py` currently loads resources in the checkout and inspects wheel ZIP members; that does not prove installed runtime independence.

The main methodology spec still requires the author's source port and a 3.5-aircraft problem marker. Local rules/common are watch-only; `docs/methodologies.md` both describes the packaged problem marker and instructs its deletion. Retirement removes the source-parity obligation and documents this as a historical prototype difference. It preserves the packaged example unchanged rather than migrating a local policy into the engine or treating the discrepancy as a blocker.

## Goals / Non-Goals

**Goals:** one installed analysis implementation, explicit capability disposition and safe retirement; independent synthetic behavioral acceptance; self-contained optional example policy.

**Non-Goals:** reproducing the author's five pages, introducing another generator, inventing evidence or diagnoses absent from current product contracts, or making collector work a deletion prerequisite. No user-store or historical-report migration.

## Decisions

### D1 — Implement only after the shared analysis cutover

Sequence: `separate-analysis-evaluation` -> `extract-report-analyses` -> this change. The first owns operation-scoped bounded evidence, selected validated policy/clock, structured evaluation and pure stored-evidence service/CLI/MCP entrypoints. The second moves the seven finite operational views' actual diagnostic, ranking and trend calculations out of presentation. CLI/MCP are peer adapters over application orchestration, not homes for replacement logic. Existing `analyse` keeps its ingestion/evaluate/compose/publish convenience and bundle return contract; retirement does not make it pure by accident.

Use existing `methodology-report-policies`, calendar, activation and default-selection contracts unchanged. No second policy registry. A protected player store, imported methodology or package resource is valid runtime input; the prohibited dependency is on assets under the development checkout's `data/`, not arbitrary paths named `data`.

### D2 — Capability disposition is the acceptance inventory

Each row is a deliberate preservation or discard decision; report kind names describe product equivalents, not required page mappings.

| Legacy source and capability | Disposition | Product equivalent / boundary |
| --- | --- | --- |
| `common`: cargo indexing and positive capacity, town-from-stop attribution, actual passenger capacity, model/carrier facts | Already covered; preserve factual behavior | `analysis` rows, snapshot relations and methodology field catalog. Arbitrary names work; missing data stays unknown. |
| `common`, `raio_x`, `cidades`: personal name captures, local/intercity/freight roles, graded loss/maturity, town feeder ratio | Already covered as optional policy | Declarative methodology selectors, rules, aggregates and `methodology` report; no personal codes or tolerances in engine defaults. |
| `common`, all pages: local time calibration and age | Preserve intent, discard algorithm | Current shared calendar clock and bounded evaluation; no 16,000-tick fallback, extrapolated ages or zero-age substitution. |
| `raio_x`: company finances, line/role totals, loss priorities and instant load | Already covered | Company/line facts, built-in findings, methodology aggregation, company/lines/methodology reports. Rolling numbers are not calendar income. |
| `raio_x`, `cadeias`: full stocks split by observed shipping/service, production gaps and nearest consumer opportunities | Preserve generic evidence through existing package and extraction | Cargo/industries/bottlenecks/expansion analyses: observed output/shipping and stocks with caveats. No name-derived ownership of stocks or routes. |
| `evolucao`: company/network turnover, first observations, line results and sampled occupancy persistence | Already covered; preserve extracted computations | History/lines-history/bottlenecks views and analysis load trends. Existing sample sufficiency and default algorithms win over local eight-snapshot/majority heuristic. |
| `evolucao`: year-boundary reset test and personal new-line contribution narrative | Discard as compatibility requirement | Keep documented rolling-window accounting and factual point comparisons; no heuristic establishes undocumented counter semantics. |
| `evolucao`, `frota`: maintenance values and physical-vehicle history safety | Preserve values and identity safety; no new delta diagnostic required | Vehicle factual rows and methodology maintenance markers; existing history comparisons must not conflate reused id with different purchase ticks. Local bespoke maintenance delta ranking is not required parity. |
| `cidades`: town capacity proxy, usage, demand, pollution, station/town assignment | Already covered | Town factual rows, towns report and methodology stop aggregates. Capacity is not population; station assignment is not catchment. |
| `cidades`: personal passenger graph, shortest hops and feeder-only/gap page arrangement | Discard as product requirement | Existing supported coverage/rankings remain; no graph/dashboard or personal role topology is needed for retirement. |
| `common`, `frota`: aircraft fleet per used terminal and maintenance screening | Already covered factual/policy capability; preserve optional example | Methodology stop aggregates, vehicle rows and bottleneck proxies. Ratio is not total capacity, arrival rate or observed queue; retain packaged 3.0 watch / 3.5 problem policy as screening only, not prototype parity. Missing terminals stay unavailable. |
| `frota`: fleet/model/carrier/cargo grouping, age, profit, maintenance, no-path/stopped/depot facts | Already covered | Fleet/vehicle-roi analyses, rows and methodology markers; model-family facts do not depend on localized mode labels. |
| `frota`: lifespan divided by 365.25 and hard-coded 80% alert, terminal-day thresholds | Discard speculative conversions and personal alerts | Preserve raw lifespan/depot/terminal facts and unverified-unit caveats; no unverified lifespan conversion is imported. |
| `frota`: catalog availability/retirement, suitable alternatives and raw comparisons | Already covered | Stored catalog and fleet/vehicle-roi/expansion guarded comparisons; disclose catalog observation and unknown units, use only evidence bounded to selected snapshot. Local two-year retirement horizon is not parity. |
| `frota`: throughput-per-cost replacement score, resale savings and payback | Explicitly discard | Do not port `(price - mean resale) / estimated saving`, capacity-linear cost scaling or implied investment return. Existing guarded product comparisons are retained, not weakened. |
| `cadeias`: name normalization, town-based source/sink cross products, hub inference, chain graph and chain profit aggregation | Explicitly discard | No verified station-industry links; product opportunities are candidates, not established ownership/flow. New geometry collection is not a prerequisite. |
| `cadeias`: starvation/chain-edge verdicts based on those inferred links | Discard unsafe linkage; preserve observed input/output facts | Existing industries/bottleneck evidence only; do not claim verified downstream causation. |
| `gerar`, formatting helpers: five page names, Portuguese literals, Mermaid flow layout, local navigation, output path | Discard presentation/source parity | Package report composition/rendering and explicit publication; current report kinds, safe escaping and offline resources remain. |

No newly added diagnostic is necessary for retirement: useful generic capabilities are covered by the product or the two prerequisites. Discarded features are not hidden future blockers.

### D3 — Replace source parity without changing packaged policy

Rename `Author's methodology expressible without loss` to `Generic declarative policies and optional examples` with a full replacement delta. Preserve generic expressive features and fixture boundaries, not literal source execution or all personal policies. Keep the packaged `local-feeder-intercity-trunk` file bytes, identity, version, parameters and outcomes unchanged, including 3.0 watch and 3.5 problem aircraft screening. Document these as policy markers, never measured congestion or justification for construction/fleet changes. Retain `air_per_terminal_problem`; do not migrate the prototype's watch-only policy into the engine. The historical difference is explicitly accepted and does not block retirement. Do not rewrite user copies, bindings, preferences or historical output. Activation/default-resolution failures retain their existing repair behavior, never trigger automatic migration or fallback.

### D4 — Exact deletion and reference migration

Delete only `data/analise/gerar.py`, `common.py`, `raio_x.py`, `evolucao.py`, `cidades.py`, `cadeias.py`, `frota.py` and their generated bytecode/cache artifacts. Do not recursively delete `data/`, export directories or unknown files. Do not move the scripts into `scripts/`, tests or a package-private compatibility layer.

Update current `docs/methodologies.md` port section to describe the self-contained optional example, unchanged packaged aircraft-screening thresholds and historical watch-only prototype difference, plus clock/missing-evidence distinctions without instructions to consult deleted code or change packaged policy. Update `docs/reports.md`, README and CONTRIBUTING's current command/architecture/testing guidance to the evaluation-versus-analysis boundary and installed smoke as appropriate; retain installation and read-only/local-first constraints and the changelog-equivalent roadmap record. Inspect active unarchived acceptance text for any dependency on running the generator and migrate operational requirements to independent fixtures; do not rewrite archived OpenSpec or fabricate historical verification. The main source-parity spec changes via the delta, not by altering archived artifacts.

Keep `data/analysis-rules.md` and `data/playtest-issues.md` as records. Only replace current generator invocation/source-of-truth instructions with supported package guidance and distinguish historical references; preserve issue ids/evidence/status without silently marking old issues fixed. No mass language rewrite of player records, source-name renaming inside evidence, or historical output regeneration. Never delete snapshots, databases, config, preferences, decisions, notes or user methodology files.

### D5 — Real installed-wheel behavioral smoke

Add `tests/test_installed_analysis.py` as a normal behavioral integration test, reusing existing synthetic fixture conventions rather than checking source strings. Build into a temporary wheelhouse; create a temporary virtual environment; install the wheel and its dependencies offline using an already provisioned dependency wheelhouse/environment. If dependencies are unavailable, fail with the exact offline prerequisite rather than accessing a package index. Clear `PYTHONPATH`, disable Python user-site imports, remove checkout entries from child environment and run the child from a temporary directory outside the repository. Assert the imported package resolves inside the temporary environment, not checkout `src/`. Read-only fixture construction runs in the parent; the installed child receives only serialized synthetic evidence and validated methodology JSON, never imports test modules or generator code.

Seed a temporary runtime store using synthetic dated snapshots spanning the clock's minimum bracket and sufficient points for operational views: arbitrary line/town names, known profit/load/maintenance facts, used terminals, missing geometry and unverified catalog units, plus two factual-field methodologies whose tolerances differ. All runtime data/userdata/HOME-equivalent overrides target temporary roots. Exercise installed `Companion.evaluate`, CLI `tf3c evaluate --json --methodology REF` and the registered MCP evaluation adapter against the same store; use explicit offline methodology import beforehand if needed. Assert factual values and provenance agree; changed policy changes a verdict but not measured facts; geometry-dependent coverage is unavailable; no report/preference or evidence writes occur during evaluation. Exercise extracted views and report composition against that evaluation, then explicitly publish a report and inspect valid Markdown/offline HTML plus manifest provenance in the temporary output root. Check the existing `analyse` convenience bundle through a synthetic acquisition folder only; no refresh or mod actions. Snapshot/database/preferences/historical-output sentinels remain unchanged except explicitly requested synthetic ingest/output writes. No network calls, live game or real player directories.

Use subprocess-visible outputs and independent numeric assertions. A text search for `data/analise` or a wheel member assertion alone is not acceptance. The ordinary packaging-resource test remains useful but insufficient.

## Risks / Trade-offs

- Removing five familiar pages changes a personal workflow: publish the explicit inventory and supported commands, not a shadow generator or false parity claim.
- The packaged example and historical prototype differ in screening policy: document the existing 3.0 watch / 3.5 problem markers as policy, preserve example bytes and reject congestion claims. Do not use retirement to change thresholds or version.
- A subprocess may accidentally resolve editable checkout imports: require an outside-checkout cwd, sanitized environment and installed-module-origin assertion.
- Offline install can fail on an unprovisioned machine: provision dependency wheels separately before running the smoke; test execution itself must not fetch them.
- Historical records contain stale bug reports and source paths: preserve them as history, while making current operational instructions unambiguous. No status-only archival cleanup claims.
