# Spec Delta

## ADDED Requirements

### Requirement: Route snapshots to saves
During import each snapshot SHALL be stored in the history of the save its towns identify, creating the save folder on first sight.

#### Scenario: First snapshot of a new game
- **WHEN** a snapshot with an unknown save id is imported
- **THEN** a new save folder is created and the snapshot is stored there

### Requirement: Compact storage
Stored snapshot data SHALL be compressed so that a monthly snapshot of a large company (≈100 lines, ≈340 vehicles) adds no more than 150 KB to the save database.

#### Scenario: Large company
- **WHEN** a 570 KB (JSON) snapshot is imported
- **THEN** the database grows by at most 150 KB

### Requirement: Schema 1 and 2 accepted
The companion SHALL import snapshots of schema versions 1 and 2.

#### Scenario: Older mod
- **WHEN** a player still runs a mod writing schema 1
- **THEN** its snapshots are imported and `doctor` suggests updating the mod
