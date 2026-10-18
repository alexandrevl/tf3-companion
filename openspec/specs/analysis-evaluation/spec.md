# analysis-evaluation Specification

## Purpose
Defines reusable evaluation of stored company evidence under an explicit methodology, independent of document generation, file publication and game-data acquisition.

## Requirements

### Requirement: Stored-only evaluation
The system SHALL offer evaluation of stored evidence without ingesting exports, requesting game snapshots, discovering Steam, rendering reports, writing preferences or outputs, or persisting verdicts. An absent store or snapshot SHALL fail without creating storage. Existing supported stores SHALL be opened without schema migration.

#### Scenario: New export is not silently ingested
- **WHEN** stored snapshot A exists and a newer export B is present in the game folder
- **THEN** evaluation uses A and identifies its game date and tick
- **AND** the database, exports, preferences, reports and request files remain unchanged

#### Scenario: Offline stored analysis
- **WHEN** stored evidence and a compatible methodology are available but the game and Steam are absent
- **THEN** evaluation succeeds without game discovery or network access

#### Scenario: Missing evidence
- **WHEN** evaluation targets an absent database or a supported empty database
- **THEN** it returns an actionable missing-evidence error and creates no database, directory or report

#### Scenario: Unsupported stored schema
- **WHEN** the existing database requires an unsupported schema or a migration before it can be read
- **THEN** evaluation reports that prerequisite without migrating or repairing it

### Requirement: Complete structured analytical result
Evaluation SHALL return a versioned result containing snapshot/save identity, methodology provenance, effective criteria, time basis, roles, rule outcomes and aggregate measures, findings, recommendations, disabled findings and coverage reasons. Factual evidence SHALL retain units and caveats. Analytical lists SHALL NOT be truncated by document summary or chart limits.

#### Scenario: Findings exceed the summary limit
- **WHEN** evaluation produces more findings or recommendations than the report summary displays
- **THEN** every result remains available in the evaluation response with its entity and evidence references
- **AND** summary presentation limits do not remove analytical results

#### Scenario: Unknown evidence remains visible
- **WHEN** a compatible rule cannot judge an entity because evidence is missing
- **THEN** the result records not-evaluable coverage with the reason and affected entity count
- **AND** missing values remain unknown rather than zero or a success marker

### Requirement: Single operation evidence and policy selection
An evaluation SHALL use one selected snapshot, a consistent stored evidence view and the exact validated effective methodology bytes and parameters. History SHALL be bounded to the selected endpoint, with each analysis retaining its supported sampling rules. No output SHALL claim verified save isolation when evidence scope is unverified.

#### Scenario: Evidence arrives during evaluation
- **WHEN** another process stores a newer snapshot while an evaluation is running
- **THEN** the running operation retains its original snapshot and consistent history
- **AND** a subsequent operation can select the newly stored evidence

#### Scenario: Methodology file changes after preparation
- **WHEN** the selected file is changed after its content was validated for an operation
- **THEN** that operation uses the captured validated content and matching hash
- **AND** a subsequent operation validates the new bytes independently

#### Scenario: Future observations exist in a mixed store
- **WHEN** the selected endpoint precedes other stored observations
- **THEN** those later observations cannot affect the evaluation's facts or conclusions
- **AND** existing evidence-scope warnings remain disclosed

### Requirement: Peer command-line and MCP interfaces
The CLI SHALL provide `tf3c evaluate` with methodology, save and parameter selection plus machine-readable JSON output. MCP SHALL provide `evaluate` over the same stored-only operation. CLI one-off methodology paths SHALL remain local explicit inputs; MCP SHALL accept library references only. Equivalent requests SHALL return equivalent analytical results and validation failures.

#### Scenario: Equivalent adapter requests
- **WHEN** CLI and MCP evaluate the same unchanged store, methodology and effective parameters
- **THEN** snapshot identity, factual values, findings, rule outcomes, recommendations and provenance agree
- **AND** neither interface creates report artifacts

#### Scenario: MCP supplied path
- **WHEN** MCP evaluation receives a filesystem path as its methodology reference
- **THEN** it rejects the reference without reading that arbitrary file

#### Scenario: Invalid effective policy
- **WHEN** evaluation is requested with an invalid methodology or parameter override
- **THEN** the shared validation diagnostics are returned before any partial result is applied
- **AND** existing reports, preferences and stored evidence remain unchanged

### Requirement: Independent interpretation and presentation
Structured evaluation SHALL be usable without Markdown, HTML, charts or publication. Changing presentation SHALL NOT change the underlying evaluation. Methodology text and game names SHALL remain untrusted data in machine responses and rendered outputs. The baseline policy SHALL be identified explicitly rather than described as absence of judgment.

#### Scenario: Reuse without a report
- **WHEN** a consumer requests company findings and rule outcomes only
- **THEN** it receives structured evidence and conclusions without requiring report generation or parsing

#### Scenario: Two policies over the same evidence
- **WHEN** two compatible methodologies apply different loss tolerances to the same stored line
- **THEN** its measured rolling profit remains identical while its policy outcome can differ
- **AND** both results identify the applied criteria and their origins
