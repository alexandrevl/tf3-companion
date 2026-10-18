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
The CLI SHALL provide `tf3c methodology list`, `show <id>`, `validate <file>`, `import <file>`, `export <id>` and `use`/`unuse`. `validate` SHALL report errors, unsupported rules and the snapshot data each rule needs, without importing. `import` SHALL validate first, copy the file into the user folder under a name derived from `id` and `version`, and refuse to overwrite an existing `id@version` with different content unless explicitly forced. `export` SHALL write the stored file unchanged to a path chosen by the player.

#### Scenario: Import a shared file
- **WHEN** the player runs import on a valid downloaded file
- **THEN** it is copied into the user folder and `list` shows it

#### Scenario: Import refuses an invalid file
- **WHEN** import is run on a file with an unknown structural key
- **THEN** nothing is copied and the error names the key

#### Scenario: Import would overwrite
- **WHEN** a different file with the same `id@version` is already in the folder
- **THEN** import fails unless forced, and says both content hashes

#### Scenario: Export round trip
- **WHEN** a methodology is exported and imported on another machine
- **THEN** the content hash on both machines is identical

### Requirement: Per-save binding
A save SHALL be able to have a default methodology, set by `tf3c methodology use <id[@version]>` and cleared by `unuse`. The binding SHALL be stored with that save's metadata so that two saves can use different methodologies. A binding to `id` without version SHALL resolve to the highest valid version in the library; a binding with a version SHALL resolve exactly. If no save layout is available, the single companion store SHALL behave as one implicit save, and the system SHALL NOT claim save isolation in that case.

#### Scenario: Two saves, two methodologies
- **WHEN** save A is bound to `local-feeder-trunk` and save B to `oil-chain`
- **THEN** analysing each save without any override uses that save's methodology and writes into that save's report folder

#### Scenario: Unbound save
- **WHEN** a save has no binding and no override is given
- **THEN** `default` is used and the output says so

#### Scenario: Bound methodology missing
- **WHEN** a save is bound to a methodology that is no longer in the library
- **THEN** analysis fails with an error naming the binding and how to fix it, and does not silently fall back to `default`

### Requirement: Resolution precedence and explicit override
The methodology applied to a request SHALL be chosen in this order: an explicit request value (CLI `--methodology`, MCP `methodology` parameter), then the save's binding, then `default`. An explicit request SHALL NOT change the binding. The CLI override MAY be an `id[@version]` or a path to a file; MCP tools SHALL accept only `id[@version]` and SHALL NOT read arbitrary file paths. The effective methodology and where it came from (request, binding or default) SHALL be stated in the output.

#### Scenario: Override without rebinding
- **WHEN** a bound save is analysed with an explicit different methodology
- **THEN** the explicit one is applied and the binding remains unchanged

#### Scenario: Path through MCP
- **WHEN** an MCP tool is called with a file path as methodology
- **THEN** the call fails stating that only library ids are accepted and where to place a file

#### Scenario: One-off file on the CLI
- **WHEN** the CLI is given a path to a valid methodology file not in the library
- **THEN** it is applied for that request only, and the output records its id, version and content hash

### Requirement: One-step analysis
The CLI SHALL provide `tf3c analyse [--methodology …] [--save …]` and the MCP server SHALL provide an `analyse` tool with the same parameters. The operation SHALL resolve the methodology, evaluate roles, rules, aggregates, recommendations and ladders on the latest snapshot and the stored history, generate the methodology's standard reports, write them to the output folder and return a summary: methodology identity and source, counts per role and marker, the highest-severity findings, recommendations, the skipped/unsupported/not-evaluable lists, and the output folder.

#### Scenario: Apply a downloaded methodology
- **WHEN** the player places a methodology in the user folder and asks the analyst to apply it and analyse the company
- **THEN** the analyst lists methodologies, runs `analyse` with that id, and reports the verdicts using the returned numbers and the data caveats

#### Scenario: Skipped rules are visible
- **WHEN** some rules are skipped for missing data
- **THEN** the summary and the generated verdicts report list them with reasons, ahead of any conclusion that depends on them

#### Scenario: No snapshot
- **WHEN** the save has no ingested snapshot
- **THEN** `analyse` fails with the same actionable error as other analysis tools and writes nothing

### Requirement: Methodology inspection tools
The MCP server SHALL provide `list_methodologies` (id, version, name, source, validation status, which save binds it) and `methodology_detail` (description, roles, rules with rationale, parameters, required snapshot data, unsupported rules). Returned free text SHALL be marked as untrusted methodology content. Existing `findings` and `report` tools and the CLI `findings` and `report` commands SHALL accept the same methodology selection and SHALL record the methodology in their results.

#### Scenario: Listing
- **WHEN** `list_methodologies` is called with `default` and one user methodology present
- **THEN** both are returned with the effective one for the active save marked

#### Scenario: Findings under a methodology
- **WHEN** `findings` is called with a methodology
- **THEN** each finding carries the methodology id and version and whether it came from the engine or from a methodology rule

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
