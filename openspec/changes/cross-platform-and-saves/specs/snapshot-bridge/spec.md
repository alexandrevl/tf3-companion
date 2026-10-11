# Spec Delta

## ADDED Requirements

### Requirement: Configurable snapshot interval
The mod SHALL read `snapshotsPerYear` (1, 4 or 12) from the refresh request file and use it for interval snapshots until another value is read; without a value it SHALL use 12.

#### Scenario: Quarterly snapshots
- **WHEN** the request file contains `snapshotsPerYear = 4`
- **THEN** interval snapshots are written every quarter of a game year

#### Scenario: Invalid value
- **WHEN** the request file contains `snapshotsPerYear = 7`
- **THEN** the mod keeps the previous interval and logs a `[tf3c]` warning

### Requirement: Snapshot schema 2
Snapshots SHALL declare `meta.schemaVersion = 2`, include the mod revision and game build, and include `meta.companyName` when the game exposes the player's company name.

#### Scenario: Company name available
- **WHEN** the player's company is named "Lima Transport"
- **THEN** the snapshot's `meta.companyName` is "Lima Transport"

### Requirement: Lineage-scoped snapshot files
Schema-2 snapshots SHALL include `meta.saveId` and be written as `towns_industries/tf3c_snap_<saveId>_<gameTime>.lua`; the id SHALL persist across reload and save-as, without mutating gameplay entities.

#### Scenario: Identical game times
- **WHEN** two independent games export snapshots at the same game time
- **THEN** both files remain available for ingestion without overwriting each other
