# Changelog

## Unreleased

### Added

- Approved English roadmap and six OpenSpec change plans for portable setup, save isolation, analyses, annual/basic reports, MCP workflows and release preparation.
- MIT license and author credit for Alexandre Lima.
- Dated player notes outside the repository, accessible through the CLI and MCP.
- Stable finding codes and actionable rejection of newer snapshot schemas.

### Changed

- Product and package renamed to TF3 Companion (`tf3companion`); CLI renamed to `tf3c`.
- Bridge renamed to `tf3_companion_bridge`, with English metadata and `[tf3c]` logging.
- English code, documentation, MCP descriptions, reports and packaged knowledge.
- Data stored in the platform user-data directory, with `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` overrides.
- Bridge source uses the observed `towns_industries` output sink only.
- Spreadsheet opening uses the operating system's default application.

### Validation status

- The renamed bridge still requires a player-controlled reload and live refresh check.
- Windows automatic discovery, per-save isolation and annual reports are specified, not implemented in this cutover.
- No GitHub remote, package publication or mod upload is performed.
