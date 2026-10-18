# Changelog

## Unreleased

### Added

- Engine and runtime knowledge: new packaged topics `engine` (clock and threads, entities and id reuse, Lua runtime, commands, construction and terrain behaviour, files, logs and crash artifacts, ownership and determinism, known unknowns) and `api_catalog` (calls, components, game-script state and events), plus an evidence legend (`MPF:<file>`, `[ADOPTED: observed|code|assumed|claim]`) that separates facts imported on the author's word from facts this project verified; sections `mechanics` M13 to M16, `snapshot_schema` identity and timing caveats and a collector-gap table, and file-location and crash guidance in `docs/troubleshooting.md`. The imported research is paraphrased from MPFever (https://github.com/dkdknight/MPFever, MIT licence, studied at commit `ae5fc96`). The mod and collector are unchanged.
- Metro-and-circuit brand identity: dark/light colour tokens, route-and-chip SVG marks, a vector MCP transit-map cover, a brand guide and prompts for text-free illustration.
- Bundled bridge revision 3 includes the metro-and-circuit listing cover; revision-2 installations need `tf3c mod install` to receive it.
- English public roadmap and nine OpenSpec change plans, including data-integrity and service-boundary hardening and agent-assisted installation.
- Contributor conventions in `AGENTS.md` (also loaded as `CLAUDE.md`): English-only rule covering file names, gitignored paths and commit messages, product boundary, verification and OpenSpec planning; `CONTRIBUTING.md` principle 4 mirrors the rule.
- MIT license and author credit for Alexandre Lima.
- Dated player notes outside the repository, accessible through the CLI and MCP.
- Stable finding codes and actionable rejection of newer snapshot schemas.
- Portable Steam discovery, read-only `doctor` diagnostics and bundled mod installation/removal.
- Six Markdown/offline HTML reports, including annual coverage and decision follow-up.
- Seven additional Markdown/offline HTML templates: company history, vehicle profitability and replacement candidates, line history, industry evolution, town comparisons, expansion opportunities and persistent bottlenecks.
- Six MCP review prompts, packaged analyst instructions and knowledge/notes/latest-report resources.
- Agent-assisted installation: a README bootstrap request, a canonical Windows/macOS setup guide with stage-by-stage evidence and recovery, and the offline `setup-check` MCP prompt and `tf3c://setup` resource, available without the game, snapshots or companion storage.
- Verified import receipts, safe pruning, strict Lua/snapshot validation and identified-lineage conflict protection.
- Three-platform CI configuration, contribution guide, privacy/troubleshooting documentation and issue templates.
- Lua polling lifecycle regression coverage through Lupa.
- Mod listing: player-facing mod description with the unofficial disclaimer, image slots under `assets/`, `scripts/make_assets.py` and `scripts/check_listing.py`, and `docs/publishing-mod.md` with the Mod Hub flow, shot list and pre-upload checklist.
- Analysis methodologies: one declarative, shareable JSON file (schema `tf3c-methodology/1`) with roles, tolerances, rules, aggregates, recommendations, a distance-band ladder, threshold and finding overrides and report selection, validated on load with a strict structure and bounded regular expressions. A missing value is never zero: rules over fields the save lacks are skipped, unknown fields are unsupported, and per-entity gaps are counted as not evaluable. See `docs/methodologies.md`.
- Methodology library and commands: packaged `default` (reproduces the engine's findings exactly) and the author's rules as an English example, a user `methodologies/` folder, `tf3c methodology list|show|validate|import|export|use|unuse|fields`, per-save binding with request override, `tf3c analyse`, the `--methodology` option on `findings` and `report`, and the `methodology` verdicts report kind.
- MCP: `list_methodologies`, `methodology_detail`, `analyse`, a `methodology` argument on `findings` and `report` (library ids only, never paths), the `apply-methodology` prompt, the `methodology-fields` knowledge topic and analyst-brief rules that treat methodology text as untrusted.
- Mandatory methodology activation validation across import, selection and runtime, including effective overrides; structured multi-error diagnostics, read-only CLI/MCP draft validation and preservation of prior configuration/results on rejection. Validation certifies compatibility, not strategic quality or prompt-injection safety.
- Library-root methodology user defaults (`set-default`/`clear-default`) beneath explicit requests and save overrides; deliberate MCP setters, lazy selection, inspection without game/database setup and explicit selection provenance.
- `tf3c evaluate` and MCP `evaluate`: the complete version-1 analytical result (snapshot/save, methodology and time provenance, effective criteria, roles, every rule outcome, findings, recommendations, coverage) over stored evidence only, through `Companion.open_stored`: no Steam discovery, ingestion or creation of any file, a SQLite read-only connection that never migrates, and one consistent read view per operation. `analyse`, `findings` and `report` keep their checked ingestion and public shapes; `analyse` now builds its summary from the same evaluation, and a dual-format report composes its document once.
- Finite `report_policies` registry for industries, line trajectories, bottlenecks and expansion, with shared engine thresholds in fleet fit, effective values/origins and immutable evidence safeguards.
- Analysis views: `tf3c evaluate --view NAME` (repeatable) and MCP `evaluate(views=[...])` add structured, report-independent analyses of stored history (`bottlenecks`, `expansion`, `lines-history`, `history`, `industries`, `vehicle-roi`, `towns`) under `analysisViews`, with coverage, sample counts, bounds and engine-owned criteria. Nothing is computed unless requested; unknown names fail before any read. The seven specialized reports and the company, lines, fleet, cargo, annual and decisions reports now present these typed results (`facts.py` for the base reports) instead of calculating their own. Historical queries are bounded at the selected endpoint in SQL and stream compact rows in batches of 256. See `docs/reports.md`.
- Installed-distribution acceptance (`tests/test_installed_analysis.py`): a wheel built into temporary storage and installed offline into a clean environment runs the installed service, `tf3c evaluate`, the MCP `evaluate` tool, all seven analysis views, report composition/publication and `tf3c analyse` outside the checkout over synthetic evidence and name-free methodologies. It fails naming its offline prerequisite instead of using a package index.
- Ordered `TODO.md` project board and a contributor delivery lifecycle: one active workstream/integration owner per worktree, explicit blocked gates, evidence-backed Done cards and authorized coherent commits before starting unrelated work.

### Changed

- Product and package renamed to TF3 Companion (`tf3companion`); CLI renamed to `tf3c`.
- Bridge renamed to `tf3_companion_bridge`, with English metadata and `[tf3c]` logging.
- English code, documentation, MCP descriptions, reports and packaged knowledge.
- Data stored in the platform user-data directory, with `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` overrides.
- Bridge source uses the observed `towns_industries` output sink only.
- Spreadsheet opening uses the operating system's default application.
- **BREAKING (pre-release):** a report is now written into a lens folder, `<data>/reports/<game-date>__<methodology-id>@<version>/<kind>.md`, instead of `<data>/reports/<kind>.md`; `reports/latest.md` stays a copy of the last generated single report. Earlier flat report files are left in place and are no longer written; no compatibility shim exists.
- `findings` items gain `methodology`, `methodology_hash` and `source` (`engine` or `methodology`); `report` headers name the methodology, its content hash, effective parameters and the skipped, unsupported and not-evaluable counts.
- **BREAKING (pre-release):** age and elapsed duration use `game-calendar-v1`: in-game Gregorian days normalized by 365.25, exact anchors or bounded interpolation, no nominal-tick fallback or extrapolation. Unsupported purchases return unknown; line age remains an oldest-current-vehicle proxy. Outputs expose conversion and isolation provenance. Raw snapshots, decisions and user methodology files are not migrated; old reports without provenance retain an unknown time basis.
- **BREAKING (pre-release):** unsupported methodology fields/capabilities can be inspected as drafts but cannot be imported, selected or applied as a partial policy. Selection origins and listing fields now distinguish save overrides, user defaults and packaged defaults without legacy aliases.
- **BREAKING (pre-release):** the author-local analysis generator is removed: `data/analise/{gerar,common,raio_x,evolucao,cidades,cadeias,frota}.py` and their caches. Nothing replaces it (no wrapper or private generator); use `tf3c evaluate`, `tf3c analyse` and `tf3c report`. Snapshots, databases, preferences, notes, methodologies and previously generated reports are untouched, and `data/analysis-rules.md` keeps its history with updated source-of-truth pointers.
- The `analysis-methodology` specification no longer requires parity with the author's scripts: it requires generic declarative policies and optional self-contained examples. The packaged `local-feeder-intercity-trunk` example is retained as it is; its watch from 3.0 / problem from 3.5 aircraft-per-terminal screening is policy screening, not congestion, and differs deliberately from the old watch-only prototype (`docs/methodologies.md`). Its boundary fixtures now live in `tests/test_example_methodology.py`.

### Fixed

- Invalid refresh timeouts no longer publish requests; concurrent refresh writers cannot replace one another's requests.
- Log bounds reject zero instead of returning the entire file.
- Current-state queries disclose failed imports rather than silently using older data.
- Bridge revision 2 acknowledges requests only after successful writes and throttles failed attempts.
- Catalog retirement boundaries and current reports exclude retained future samples after a rewind.
- History report: net position (balance minus loan) is blank when the loan is unknown instead of treating it as zero, and failing-collector families with equal sample counts are listed in a stable order.
- Rankings do not repeat lines when fewer than thirty exist; decision references survive renaming through baseline identity.
- Reports escape untrusted Markdown/HTML; XLSX names cannot become formulas.
- Default-application failures preserve exported files and report their paths.
- Managed-folder symlink protection no longer rejects macOS system aliases above the configured userdata root.
- Expansion no longer reports an industry whose recorded input usage is unknown as a starved consumer, and no longer lists a cargo as unmet town demand when the town's recorded supply is unknown.
- Towns report no longer lists a town with unknown line usage as having zero usage or as "served but below cap", and no longer counts unreported industry output flows as zero produced or unshipped cargo (or as proof that no industry produces a demanded cargo).
- Bottlenecks report at an earlier selected endpoint no longer reads samples after it, and equally ranked rising stocks, depots and collector-error families are ordered by name rather than input order.
- Industries report no longer charts an unknown service ratio (no production in a sample or type) as 0%, and equally ranked events, movers, outliers, chains, links and review candidates are ordered by industry id rather than input order.
- Base reports: company net position, annual closing line profit, idle-depot capital and annual modal profit changes no longer treat unknown values as zero (known subtotals state how many members were unknown); balance/loan charts and methodology-report charts leave out unknown values instead of plotting zero; equally ranked lines, fleet losses and added/removed entities are ordered by id; decision follow-up ignores decisions recorded after the selected endpoint and never reads a baseline past it; the cargo report applies the effective full-stock threshold to both the screen and its label.

### Validation status

- Local source tests, isolated CLI/MCP round trips, package builds, installed-wheel checks and browser report inspection are recorded in `docs/review-notes.md`.
- Real Windows/game activation, persistent save lineage, thumbnail presentation and third-party GUI-client rehearsals remain release gates.
- Consolidation review: 943 Python tests pass locally. Open known issues include the older MCP tools' shared SQLite thread affinity, per-view hydration coverage leaking across combined requests and line-detail capacity decoding/filtering; these are prioritized in `TODO.md`, not claimed fixed by the architecture changes.
- No live mod installation, player-data migration, GitHub remote, package publication or mod upload is performed during this review.
