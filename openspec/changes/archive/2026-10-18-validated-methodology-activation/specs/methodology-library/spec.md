# Spec Delta

## MODIFIED Requirements

### Requirement: Import, export and validation commands
The CLI SHALL provide `tf3c methodology list`, `show <id>`, `validate <file>`, `import <file>`, `export <id>` and `use`/`unuse`. Validation SHALL be read-only and report structural validity, activation compatibility and required data. Import SHALL require strict activation validation before copying under the id/version name. Existing different-content overwrite protection SHALL remain; force SHALL NOT bypass validation. Export SHALL preserve stored bytes.

#### Scenario: Import a shared file
- **WHEN** the player imports a structurally valid, release-compatible shared file
- **THEN** it is copied into the user folder and `list` shows it without changing the current binding

#### Scenario: Import refuses an invalid file
- **WHEN** import is run on a file with an unknown structural key or damaged JSON
- **THEN** nothing is copied or replaced and structured diagnostics identify the error

#### Scenario: Import refuses incompatible policy even when forced
- **WHEN** a file refers to an unknown field or an unsupported collector capability and import is requested with force
- **THEN** import fails before changing any existing library file, binding, configuration or report

#### Scenario: Import would overwrite
- **WHEN** a different compatible file with the same `id@version` is already in the folder
- **THEN** import fails unless forced, and says both content hashes
- **AND** a packaged identity with different bytes cannot be overwritten even with force

#### Scenario: Export round trip
- **WHEN** a methodology is exported and imported on another compatible installation
- **THEN** the content hash on both machines is identical

## ADDED Requirements

### Requirement: One activation gate across all entry points
Strict activation validation SHALL guard managed import, save bindings, user-default setters and every runtime application from library ids, drop-ins, request overrides, defaults and CLI file paths. MCP SHALL retain its no-arbitrary-path boundary. Failed validation SHALL NOT silently fall back, apply a supported subset, alter persistent selections or replace results.

#### Scenario: Damaged drop-in is isolated
- **WHEN** a damaged file is copied into the library beside valid files
- **THEN** listing exposes its invalid status and diagnostics while valid entries remain usable
- **AND** copying alone changes no selection or report, and attempting to apply the damaged entry fails

#### Scenario: Invalid one-off CLI file
- **WHEN** `analyse`, `findings` or `report` is requested with an invalid or incompatible CLI file path
- **THEN** the request fails through the same validation contract as library selection without changing the library or reports

#### Scenario: Failed selection preserves the old binding
- **WHEN** a save binding or user-wide default is replaced with an invalid, incompatible or conflicting methodology
- **THEN** the setter fails and previous configuration and binding bytes remain unchanged

#### Scenario: Runtime rechecks a changed default
- **WHEN** a previously selected save or user-default methodology becomes invalid or incompatible on disk
- **THEN** runtime fails with diagnostics instead of applying it or falling back to another methodology
- **AND** existing selection metadata and previous report results remain available unchanged

### Requirement: Validation is bound to content rather than file trust
Every activation SHALL validate the actual bytes and effective overrides used by that operation. A prior successful check or unchanged filename/id/version SHALL NOT authorize edited content. Identity/hash conflicts SHALL remain blocking, and validation SHALL NOT rewrite files or stamp trust on mutable content.

#### Scenario: Stale validation after editing
- **WHEN** a file passes validation and is then edited without a version bump into an invalid or incompatible file
- **THEN** import, binding and runtime use reject the changed bytes even if a prior successful result exists
- **AND** the diagnostic hash identifies the current bytes when readable

#### Scenario: Valid compatible path
- **WHEN** a compatible file is validated, imported, selected and applied without intervening edits
- **THEN** it succeeds and outputs record the exact validated hash and effective parameters
- **AND** stored evidence and the game simulation remain unchanged

### Requirement: Read-only methodology debugging surfaces
The CLI validation command SHALL support local files and effective parameter checks without activation. MCP SHALL expose `validate_methodology` for library references including invalid candidates and directly supplied draft JSON text, never arbitrary paths. Both SHALL return the same structured diagnostics without creating library/configuration/database/report files, ingesting snapshots or requesting game/network/plugin actions.

#### Scenario: Debug without importing
- **WHEN** an author validates a broken local file on the CLI or draft JSON text through MCP with no snapshot present
- **THEN** the response reports structural validity, activation eligibility and diagnostics without activation or persistent writes

#### Scenario: Debug an invalid library entry through MCP
- **WHEN** MCP validation targets an invalid candidate by library reference
- **THEN** it returns candidate diagnostics without requiring successful activation resolution
- **AND** ambiguity or conflicting candidates are reported with their source files and hashes

#### Scenario: MCP rejects file-path validation
- **WHEN** a file path is supplied as the MCP methodology reference
- **THEN** the request fails with guidance to use a library reference or explicit draft text instead

### Requirement: Transactional preservation of selections and outputs
Validation and effective-policy preparation SHALL finish before replacing selection metadata or publishing outputs. A failed validation SHALL leave existing library targets, bindings, defaults, report files, manifests and latest-report pointers unchanged. Successful replacement SHALL publish complete staged content rather than delete the previous valid state first.

#### Scenario: Failed report regeneration preserves results
- **WHEN** a same-date methodology report bundle exists and regeneration fails validation after a file edit or invalid override
- **THEN** the prior bundle, manifest and latest-report pointer remain byte-for-byte unchanged
- **AND** no new partial report folder is published

#### Scenario: Successful replacement preserves output contract
- **WHEN** a compatible methodology produces a complete replacement bundle
- **THEN** the complete new bundle is published under the existing output-layout contract with matching provenance
- **AND** unrelated methodology/date report folders remain unchanged
