# Spec Delta

## Purpose

Keeps the history, notes, decisions and reports of each Transport Fever 3 game separate and lets the player choose which game the companion talks about.

## ADDED Requirements

### Requirement: Save lineage identity
The companion SHALL identify games by a bridge-owned persistent lineage id, not by town names or entity ids. Reloading and save-as SHALL retain the id; independently started games, including on the same scenario, SHALL receive different ids.

#### Scenario: Same game, new save file
- **WHEN** the player continues "Example Region - 13" as "Example Region - 14"
- **THEN** snapshots from both files share one save id

#### Scenario: Two games on the same scenario
- **WHEN** the player independently starts two games on the same scenario map
- **THEN** their snapshots have different lineage ids and never share history

### Requirement: Per-save storage
Each save SHALL have its own folder `<data>/saves/<saveId>/` containing its history database, notes, reports and exports.

#### Scenario: Two games
- **WHEN** the player alternates between two games
- **THEN** findings, history and decisions of one never include data from the other

### Requirement: Save label
Each save SHALL have a human label: the company name from the snapshot when present, otherwise the names of its three largest towns, and the player MAY replace it.

#### Scenario: Custom label
- **WHEN** the player runs `tf3c saves label <id> "Holland main"`
- **THEN** listings show "Holland main"

### Requirement: Active save
The active save SHALL be the save of the most recently written snapshot unless the player pinned one; queries, notes, decisions and reports use the active save.

#### Scenario: Pinned save
- **WHEN** the player pins save A and then plays save B
- **THEN** queries still answer about A, and `status` shows that B has newer snapshots

### Requirement: List saves
The companion SHALL list saves with id, label, first and last game date, snapshot count, whether it is active and whether it is pinned.

#### Scenario: Listing
- **WHEN** the player runs `tf3c saves`
- **THEN** each known save appears once with those fields

### Requirement: Timeline rewind is visible
The companion SHALL report a backwards game-time jump exceeding one game year within a lineage in `status` and `doctor`; it MUST NOT represent a replayed timeline as uninterrupted progress.

#### Scenario: Earlier save loaded
- **WHEN** the player loads an earlier save of the same lineage
- **THEN** status reports the rewind and year-over-year comparisons disclose the timeline discontinuity
