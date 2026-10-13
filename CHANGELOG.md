# Changelog

## Unreleased

### Added

- English public roadmap and nine OpenSpec change plans, including data-integrity and service-boundary hardening and agent-assisted installation.
- MIT license and author credit for Alexandre Lima.
- Dated player notes outside the repository, accessible through the CLI and MCP.
- Stable finding codes and actionable rejection of newer snapshot schemas.
- Portable Steam discovery, read-only `doctor` diagnostics and bundled mod installation/removal.
- Six Markdown/offline HTML reports, including annual coverage and decision follow-up.
- Six MCP review prompts, packaged analyst instructions and knowledge/notes/latest-report resources.
- Agent-assisted installation: a README bootstrap request, a canonical Windows/macOS setup guide with stage-by-stage evidence and recovery, and the offline `setup-check` MCP prompt and `tf3c://setup` resource, available without the game, snapshots or companion storage.
- Verified import receipts, safe pruning, strict Lua/snapshot validation and identified-lineage conflict protection.
- Three-platform CI configuration, contribution guide, privacy/troubleshooting documentation and issue templates.
- Lua polling lifecycle regression coverage through Lupa.

### Changed

- Product and package renamed to TF3 Companion (`tf3companion`); CLI renamed to `tf3c`.
- Bridge renamed to `tf3_companion_bridge`, with English metadata and `[tf3c]` logging.
- English code, documentation, MCP descriptions, reports and packaged knowledge.
- Data stored in the platform user-data directory, with `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` overrides.
- Bridge source uses the observed `towns_industries` output sink only.
- Spreadsheet opening uses the operating system's default application.

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
