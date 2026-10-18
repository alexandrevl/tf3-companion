# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
