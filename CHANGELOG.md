# Changelog

## Unreleased

### Added

- English public roadmap and nine OpenSpec change plans, including data-integrity and service-boundary hardening and agent-assisted installation.
- Contributor conventions in `AGENTS.md` (also loaded as `CLAUDE.md`): English-only rule covering file names, gitignored paths and commit messages, product boundary, verification and OpenSpec planning, plus a Portuguese-detection check command; `CONTRIBUTING.md` principle 4 mirrors the rule.
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
- Analysis methodologies: one declarative, shareable JSON file (schema `tf3c-methodology/1`) with roles, tolerances, rules, aggregates, recommendations, a distance-band ladder, threshold and finding overrides and report selection, validated on load with a strict structure and bounded regular expressions. A missing value is never zero: rules over fields the save lacks are skipped, unknown fields are unsupported, and per-entity gaps are counted as not evaluable. See `docs/methodologies.md`.
- Methodology library and commands: packaged `default` (reproduces the engine's findings exactly) and the author's rules as an English example, a user `methodologies/` folder, `tf3c methodology list|show|validate|import|export|use|unuse|fields`, per-save binding with request override, `tf3c analyse`, the `--methodology` option on `findings` and `report`, and the `methodology` verdicts report kind.
- MCP: `list_methodologies`, `methodology_detail`, `analyse`, a `methodology` argument on `findings` and `report` (library ids only, never paths), the `apply-methodology` prompt, the `methodology-fields` knowledge topic and analyst-brief rules that treat methodology text as untrusted.

### Changed

- Product and package renamed to TF3 Companion (`tf3companion`); CLI renamed to `tf3c`.
- Bridge renamed to `tf3_companion_bridge`, with English metadata and `[tf3c]` logging.
- English code, documentation, MCP descriptions, reports and packaged knowledge.
- Data stored in the platform user-data directory, with `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` overrides.
- Bridge source uses the observed `towns_industries` output sink only.
- Spreadsheet opening uses the operating system's default application.
- **BREAKING (pre-release):** a report is now written into a lens folder, `<data>/reports/<game-date>__<methodology-id>@<version>/<kind>.md`, instead of `<data>/reports/<kind>.md`; `reports/latest.md` stays a copy of the last generated single report. Earlier flat report files are left in place and are no longer written; no compatibility shim exists.
- `findings` items gain `methodology`, `methodology_hash` and `source` (`engine` or `methodology`); `report` headers name the methodology, its content hash, effective parameters and the skipped, unsupported and not-evaluable counts.

### Fixed

- Invalid refresh timeouts no longer publish requests; concurrent refresh writers cannot replace one another's requests.
- Log bounds reject zero instead of returning the entire file.
- Current-state queries disclose failed imports rather than silently using older data.
- Bridge revision 2 acknowledges requests only after successful writes and throttles failed attempts.
- Catalog retirement boundaries and current reports exclude retained future samples after a rewind.
- Rankings do not repeat lines when fewer than thirty exist; decision references survive renaming through baseline identity.
- Reports escape untrusted Markdown/HTML; XLSX names cannot become formulas.
- Default-application failures preserve exported files and report their paths.
- Managed-folder symlink protection no longer rejects macOS system aliases above the configured userdata root.

### Validation status

- Local source tests, isolated CLI/MCP round trips, package builds, installed-wheel checks and browser report inspection are recorded in `docs/review-notes.md`.
- Real Windows/game activation, persistent save lineage, thumbnail presentation and third-party GUI-client rehearsals remain release gates.
- No live mod installation, player-data migration, GitHub remote, package publication or mod upload is performed during this review.
