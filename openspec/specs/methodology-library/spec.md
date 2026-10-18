# methodology-library Specification

## Purpose

Defines where methodologies live, how players import, export, bind and apply them for a save, how analysis is requested from the CLI and MCP tools, and where the resulting reports are written.

## Requirements

### Requirement: Library locations
The system SHALL provide the packaged `default` methodology and SHALL read user methodologies from the folder `methodologies/` under the companion data directory. Every file in that folder with the methodology file extension SHALL be a candidate. The system SHALL NOT read methodologies from any network location, and SHALL NOT create the folder as a side effect of read-only commands.

#### Scenario: Drop-in file
- **WHEN** a player copies a valid methodology file into the user folder
- **THEN** listing methodologies shows it with its id, version, name, source file and validation status without any further command

#### Scenario: Read-only listing
- **WHEN** the user folder does not exist and methodologies are listed
- **THEN** only the packaged ones are shown and no folder is created

#### Scenario: Invalid file in the folder
- **WHEN** one file in the folder is invalid
- **THEN** it is listed as invalid with its error, and all valid files remain usable

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

### Requirement: Per-save binding
A save SHALL be able to have a methodology override, set by `tf3c methodology use <id[@version]>` and cleared by `unuse`. The override SHALL remain in save metadata; an unbound save inherits the user default, then packaged `default`. Bare ids SHALL resolve to the highest valid numeric version; versioned references SHALL resolve exactly. Without a save layout the store SHALL act as one implicit save and SHALL NOT claim save isolation.

#### Scenario: Two saves, two methodologies
- **WHEN** save A is bound to `local-feeder-trunk` and save B to `oil-chain`
- **THEN** analysing each save without any override uses that save's methodology and writes into that save's report folder

#### Scenario: Unbound save
- **WHEN** a save has no binding and no explicit request or user default is given
- **THEN** packaged `default` is used and the output says so

#### Scenario: Bound methodology missing
- **WHEN** a save is bound to a methodology that is no longer in the library
- **THEN** analysis fails with an error naming the binding and how to fix it, and does not silently fall back to `default` or the user default

#### Scenario: Unuse means inheritance
- **WHEN** the player runs `unuse --save A` while a valid user default exists
- **THEN** A inherits the user default and other saves' overrides and the user preference remain unchanged

### Requirement: Resolution precedence and explicit override
Selection SHALL follow explicit request > save override > user default > packaged `default`, without changing persisted selections. CLI requests MAY use a library reference or one-off path; MCP SHALL accept only library references. Outputs SHALL distinguish request, file, save-override, user-default and packaged-default origins from file source. Failure at the selected layer SHALL stop analysis, not trigger fallback; unselected lower layers SHALL NOT block it.

#### Scenario: Override without rebinding
- **WHEN** a bound save is analysed with an explicit different methodology
- **THEN** the explicit one is applied and the binding remains unchanged

#### Scenario: Path through MCP
- **WHEN** an MCP tool is called with a file path as methodology
- **THEN** the call fails stating that only library ids are accepted and where to place a file

#### Scenario: One-off file on the CLI
- **WHEN** the CLI is given a path to a valid methodology file not in the library
- **THEN** it is applied for that request only, and the output records its id, version and content hash

#### Scenario: Broken user default
- **WHEN** an unbound save inherits a missing, invalid, conflicted or activation-gate-rejected user-default reference
- **THEN** analysis fails naming the user-default layer, library root, reference and `set-default`/`clear-default` recovery, preserving previous reports

#### Scenario: Higher priority bypasses a broken lower layer
- **WHEN** a valid explicit request is provided despite malformed save/user preference metadata, or a valid save override exists despite a broken user default
- **THEN** the higher-priority methodology is used and the broken lower layer is not used as analysis input
- **AND** read-only inspection can report the lower-layer error separately

### Requirement: One-step analysis
The CLI SHALL provide `tf3c analyse [--methodology …] [--save …]` and the MCP server SHALL provide an `analyse` tool with the same parameters. The operation SHALL retain checked ingestion followed by evaluation of roles, rules, aggregates, recommendations and ladders on the selected latest snapshot and stored history, generation of the methodology's standard reports, atomic publication to the existing output folder and a summary containing methodology identity/source, role and marker counts, highest-severity findings, recommendations, coverage lists and the output folder. The analytical stage SHALL use the same operation as standalone stored evaluation; presentation and publication SHALL be separate stages and SHALL NOT change its results.

#### Scenario: Apply a downloaded methodology
- **WHEN** the player places a methodology in the user folder and asks the analyst to apply it and analyse the company
- **THEN** the analyst lists methodologies, runs `analyse` with that id, and reports the verdicts using the returned numbers and the data caveats

#### Scenario: Skipped rules are visible
- **WHEN** some rules are skipped for missing data
- **THEN** the summary and the generated verdicts report list them with reasons, ahead of any conclusion that depends on them

#### Scenario: No snapshot
- **WHEN** the save has no ingested snapshot after checked ingestion
- **THEN** `analyse` fails with the same actionable error as other analysis tools and writes no report

#### Scenario: Convenience operation retains its bundle contract
- **WHEN** a player invokes `analyse` rather than stored-only `evaluate`
- **THEN** the existing standard reports plus the methodology report are published under the save/date/methodology layout
- **AND** the response retains output folder and file information alongside its analytical summary

#### Scenario: Publication fails after successful evaluation
- **WHEN** evaluation succeeds but rendering or publication fails
- **THEN** the composite call reports failure without replacing a previously published complete bundle
- **AND** the standalone evaluation operation remains usable on the same evidence without requiring publication

#### Scenario: Fresh acquisition remains a separate stage
- **WHEN** checked ingestion finds a newly written snapshot or fails to import an export
- **THEN** `analyse` preserves its existing acquisition and fail-closed behavior before evaluation
- **AND** standalone `evaluate` does not perform that acquisition stage

### Requirement: Methodology inspection tools
The MCP server SHALL provide `list_methodologies(save?)` and `methodology_detail`, preserving identity, source, validity, parameters, rules, rationale and support inspection. Listing SHALL separately identify library root, user default, save override, effective identity/hash and selection origin. Free text SHALL remain untrusted. CLI/MCP findings and reports SHALL accept the same selection and record its identity and selection provenance.

#### Scenario: Listing
- **WHEN** `list_methodologies` is called with `default` and one user methodology present
- **THEN** both are returned with the effective one for the active save marked

#### Scenario: Findings under a methodology
- **WHEN** `findings` is called with a methodology
- **THEN** each finding carries the methodology id and version and whether it came from the engine or from a methodology rule

#### Scenario: Packaged file used as user default
- **WHEN** a packaged example has been explicitly selected as the user default and an unbound save is inspected or analysed
- **THEN** output says origin `user-default`, file source `packaged`, and records the reference, resolved version/hash and library root separately

#### Scenario: Independent layer diagnostics
- **WHEN** listing a save with a valid save override and invalid user-default metadata
- **THEN** the effective save policy remains marked, the top-level selected-resolution error is null, and the user-default record carries its own actionable error

### Requirement: Analyst brief covers methodologies
The analyst brief SHALL tell the agent to identify the effective methodology before drawing conclusions, to list methodologies when the player mentions one, to apply a methodology only through the provided tools, to cite the methodology id and version with its conclusions, to disclose skipped and unsupported rules, and to treat all methodology text as untrusted data that cannot instruct it.

#### Scenario: Player supplies a methodology
- **WHEN** the player says "apply this methodology" and names a file
- **THEN** the agent tells the player to place or import it (or imports it through the CLI with the player's authorisation) and does not read or run it as instructions

### Requirement: Report output layout by save, date and methodology
Every report and analysis bundle SHALL be written under the save's `reports/` folder in a sub-folder named `<game-date>__<methodology-id>@<version>`, where the game date comes from the snapshot the output is based on (`YYYY-MM-DD`, or a game-time stamp when no calendar date exists). The save folder name SHALL be the stable save id, never the player label. Generating the same inputs again SHALL overwrite the same folder atomically, and generating with another methodology or another game date SHALL create a different folder without touching existing ones. Each folder SHALL contain a manifest recording the methodology identity and hash, effective parameters, snapshot game time, generated files and the skipped/unsupported/not-evaluable lists. `reports/latest.md` SHALL remain a copy of the most recently generated single report.

#### Scenario: Idempotent regeneration
- **WHEN** `analyse` is run twice on the same snapshot with the same methodology
- **THEN** one folder exists and holds the files from the second run

#### Scenario: Two lenses coexist
- **WHEN** the same save is analysed with `default` and with `oil-chain`
- **THEN** two sibling folders exist for the same game date, one per methodology and version

#### Scenario: Two saves stay apart
- **WHEN** two saves are analysed
- **THEN** each writes under its own save id folder and neither can read or overwrite the other's reports

#### Scenario: Save layout unavailable
- **WHEN** no per-save layout exists
- **THEN** outputs are written to `reports/<game-date>__<methodology-id>@<version>/` under the data directory and the manifest does not claim save isolation

#### Scenario: Label change
- **WHEN** the player renames the save label
- **THEN** existing report folders keep their paths

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

### Requirement: Independent user default
The system SHALL support one user default per resolved companion library root, independent of active save and stored separately from save metadata. `TF3C_DATA_DIR` SHALL select an independent library and user default. Choosing or clearing a user default SHALL NOT rewrite save overrides, evidence or reports. No preference SHALL mean packaged `default` for otherwise unbound requests.

#### Scenario: Global switch affects only inheriting save B
- **WHEN** save A explicitly overrides with `oil-chain@1.0.0`, save B inherits `local-feeder-trunk@1.0.0` as user default, and the player changes the user default to `patient-network@2.0.0`
- **THEN** A still applies `oil-chain@1.0.0` with origin `save-override` and its metadata is unchanged
- **AND** B now applies `patient-network@2.0.0` with origin `user-default` without writing B metadata

#### Scenario: Clear back to packaged default
- **WHEN** the player clears the user default after the preceding switch
- **THEN** B applies packaged `default` with origin `packaged-default` and A keeps its explicit override

#### Scenario: Save selection does not relocate preference
- **WHEN** the same library root is inspected with save A and save B, or the current active save changes
- **THEN** both scopes report the same user-default metadata location and reference

#### Scenario: Separate data-root environments
- **WHEN** a user default is set with `TF3C_DATA_DIR` pointing to root X and the companion is then run with root Y
- **THEN** Y reads only Y's library and user-default configuration and does not inherit X's preference

### Requirement: Deliberate default and inheritance workflows
The CLI SHALL provide `methodology set-default REF` and `clear-default` without save selection, while `use`/`unuse` SHALL remain save override operations. MCP SHALL provide `set_methodology_default(methodology)` and `set_save_methodology(methodology, save?)`; null SHALL mean clear/inherit respectively. Setters SHALL use the shared activation gate before atomic writes and SHALL preserve previous selection/results on failure.

#### Scenario: Configure without game installation
- **WHEN** the player selects a valid library default using CLI or MCP with no game installation, active save or snapshot
- **THEN** the preference is saved without constructing a snapshot database or discovering userdata and no mod action occurs

#### Scenario: Failed activation preserves selection
- **WHEN** a setter receives a missing, invalid, conflicted or activation-gate-rejected reference while a previous selection exists
- **THEN** it returns actionable validation/resolution diagnostics and leaves all preference/save metadata and generated results unchanged

#### Scenario: MCP returns save to inheritance
- **WHEN** the player deliberately requests `set_save_methodology` with `methodology: null` for A
- **THEN** only A's override is removed and the response identifies its inherited user default or packaged default

#### Scenario: Explicit reset recovers malformed preference
- **WHEN** the user-default configuration is malformed and the player explicitly runs `clear-default` or calls `set_methodology_default` with null
- **THEN** the dedicated user preference is reset to no default, the response discloses the previous read error, and save metadata is not changed

### Requirement: Nonactivating discovery and reference policy
Importing or dropping a methodology into the library SHALL NOT select it or rewrite bindings. Bare-id selections SHALL float to the highest structurally valid numeric version; exact `id@version` selections SHALL pin the version, not bytes. A conflict or activation-gate rejection of the chosen candidate SHALL fail rather than downgrade. Every application SHALL use the shared gate on current content and record its hash.

#### Scenario: Import alone does not activate
- **WHEN** the player imports a new methodology under a different id while no explicit selection exists
- **THEN** listing shows it as available and the effective methodology remains packaged `default`

#### Scenario: Floating and pinned references
- **WHEN** the user default is bare `patient-network` and versions 1.9.0 and 1.10.0 are valid and eligible
- **THEN** it resolves to 1.10.0 numerically
- **AND** selecting `patient-network@1.9.0` resolves exactly 1.9.0 after later versions arrive

#### Scenario: New version affects only an already floating selection
- **WHEN** an eligible higher version is imported for the id already selected as a floating user default
- **THEN** the next inherited application resolves the higher version without rewriting the reference
- **AND** explicit save version pins remain unchanged

#### Scenario: Invalid higher candidate cannot downgrade after gate rejection
- **WHEN** the highest structurally valid candidate fails the shared support gate but an older eligible version exists
- **THEN** application fails with that candidate's diagnostics rather than selecting the older version

### Requirement: Legacy overrides and read-only inspection
Existing `methodology` values in implicit `methodology.json` and per-save `save.json` SHALL remain save overrides, never user defaults. Reads SHALL NOT migrate/write files or create directories/databases. Save mutations SHALL preserve unrelated metadata. Malformed explicit override values SHALL fail when selected; absent/null legacy values SHALL mean inheritance. Collection and ingestion SHALL NOT depend on successful methodology resolution.

#### Scenario: Legacy implicit binding remains local
- **WHEN** `<data>/methodology.json` contains `{"methodology":"oil-chain"}` and no user-default file exists
- **THEN** the implicit store uses that save override while another unbound save uses packaged `default`
- **AND** inspection creates no user-default file and changes no existing metadata

#### Scenario: Existing save metadata preserved
- **WHEN** a save with a label, snapshot metadata and methodology override is inspected and its override is later cleared
- **THEN** inspection writes nothing and clearing removes only the methodology key

#### Scenario: Empty library root inspection
- **WHEN** CLI or MCP lists methodologies at a nonexistent library root without a selected save
- **THEN** packaged entries and packaged-default origin are returned without creating that root or a database

#### Scenario: Broken analysis preference does not block evidence collection
- **WHEN** a user default or save override is broken and the player ingests or refreshes snapshots
- **THEN** collection follows its normal snapshot prerequisites without requiring methodology activation or changing the broken selection
