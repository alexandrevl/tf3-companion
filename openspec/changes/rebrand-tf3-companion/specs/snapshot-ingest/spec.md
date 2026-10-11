# Spec Delta

## Purpose

Turns snapshot files written by the mod into a local history that analyses, reports and agents can query.

## ADDED Requirements

### Requirement: Import new snapshot files
The companion SHALL import every `tf3c_snap_*.lua` file it has not imported yet (same name and modification time) from the game's `towns_industries` folder before answering any data query.

#### Scenario: New file present
- **WHEN** a new snapshot file appears and the player runs any data command
- **THEN** the file is imported first and the answer reflects it

#### Scenario: Already imported
- **WHEN** the same file with the same modification time is seen again
- **THEN** it is skipped and counted as skipped

### Requirement: Tolerate partial files
A file that cannot be parsed (for example while the game is still writing it) SHALL be reported as failed and retried on the next import, without aborting the import of other files.

#### Scenario: Half-written file
- **WHEN** one file is truncated
- **THEN** the other files are imported and the truncated one is listed under `failed` with the parse error

### Requirement: Snapshot schema compatibility
The companion SHALL reject snapshots whose `meta.schemaVersion` is newer than it supports, with a message telling the player to update the companion.

#### Scenario: Newer schema
- **WHEN** a snapshot declares a schema version above the supported one
- **THEN** the file is listed under `failed` with an "update TF3 Companion" message

### Requirement: Snapshot file retention
After a successful import the companion SHALL keep at most the 10 newest imported snapshot files in the game folder and delete older imported ones; files that failed to import MUST NOT be deleted.

#### Scenario: Eleventh file
- **WHEN** 11 snapshot files have been imported
- **THEN** the oldest one is deleted from `towns_industries` and its data remains in history

### Requirement: Local data directory
The companion SHALL store its database and outputs in the platform user-data directory for `tf3-companion`, or in `TF3C_DATA_DIR` when set, and MUST NOT write player data inside the installed package or source tree.

#### Scenario: Override
- **WHEN** `TF3C_DATA_DIR` points to a folder
- **THEN** the database and exports are created there
