# Spec Delta

## MODIFIED Requirements

### Requirement: Three-layer separation
The system SHALL keep game mechanics (shared facts), methodology (player policy) and evidence (per-save snapshots) separate. A methodology SHALL be able to change classification, markers, severities, tolerances, recommendations, report selection and registered report judgments/rankings, and SHALL NOT be able to change stored evidence, measured facts, game-mechanics knowledge, engine-owned evidence safeguards or the data caveats the analyst must disclose.

#### Scenario: Same evidence, two lenses
- **WHEN** the same snapshots are analysed with two different methodologies
- **THEN** the measured values (profit, load, stock fill, ages) are identical in both outputs
- **AND** only roles, markers, rule messages, recommendations, report selection and policy-dependent report judgments/rankings differ

#### Scenario: Methodology cannot weaken caveats
- **WHEN** a methodology declares a threshold or text that contradicts a documented caveat (for example claiming instantaneous load is an average)
- **THEN** outputs still label load as an instantaneous reading and still carry the standard data-caveat notes

### Requirement: Report and chart selection
A methodology SHALL be able to name its standard report set from the existing report kinds, and to request charts and role-grouped tables from a closed catalog of chart types and metrics. It SHALL NOT be able to define new report kinds or free-form output. Every report SHALL include a methodology section naming the methodology, its version, the effective parameters and the skipped, unsupported and not-evaluable counts. Reports SHALL additionally disclose effective report policy registry revision, applicable criteria with units and origins, and effective engine thresholds used for their judgments; the methodology report SHALL disclose the complete resolved report policy catalog.

#### Scenario: Standard set
- **WHEN** a methodology declares company, lines and cargo as its report set and analysis is requested
- **THEN** exactly those three reports are generated, plus the methodology verdicts report

#### Scenario: Unknown report kind
- **WHEN** a methodology names a report kind that does not exist
- **THEN** the file is rejected listing the valid kinds

#### Scenario: Report policy disclosure
- **WHEN** a methodology overrides the lines-history noise multiplier but leaves its relative threshold at the engine default
- **THEN** the report names both effective values with units and distinguishes methodology and default origins
- **AND** the values agree with the analysis manifest and methodology show output
