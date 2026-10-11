# Spec Delta

## Purpose

Gives agents and players sourced knowledge about how Transport Fever 3 works, plus durable notes about the player's own game.

## ADDED Requirements

### Requirement: Shipped topics
The companion SHALL ship English knowledge topics `mechanics`, `strategy`, `cargo_economy` and `snapshot_schema` with the installed package, and list them when no topic is requested.

#### Scenario: Topic list
- **WHEN** the knowledge tool is called without a topic
- **THEN** it returns the four topic names

#### Scenario: Unknown topic
- **WHEN** an unknown topic is requested
- **THEN** the error lists the available topics

### Requirement: Sourced claims
Every game-mechanic claim in a shipped topic SHALL cite its source (official wiki page or a game file path) or be marked `[INFERENCE]` or `[UNVERIFIED]`, and topics MUST NOT contain verbatim game source code.

#### Scenario: Claim without source
- **WHEN** a topic states a mechanic that is not documented
- **THEN** the statement carries `[INFERENCE]` or `[UNVERIFIED]`

### Requirement: Player notes
The companion SHALL keep free-form Markdown notes about the player's game in the data directory, returning them on read and appending a dated entry on write.

#### Scenario: Append a note
- **WHEN** a note "Trunk lines end at the Tilburg steel mill" is appended
- **THEN** reading the notes returns it under a heading with the latest snapshot's game date
