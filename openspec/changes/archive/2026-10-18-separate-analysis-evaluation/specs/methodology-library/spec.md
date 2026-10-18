# Spec Delta

## MODIFIED Requirements

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
