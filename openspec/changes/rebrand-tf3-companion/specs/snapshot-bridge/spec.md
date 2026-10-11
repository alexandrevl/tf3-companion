# Spec Delta

## Purpose

The in-game TF3 Companion Bridge mod exports read-only snapshots of the player's company so the companion can analyse them outside the game.

## ADDED Requirements

### Requirement: Read-only operation
The mod SHALL only read game state. It MUST NOT issue game commands, change the simulation or require confirmation when added to or removed from a save.

#### Scenario: Adding the mod to an existing save
- **WHEN** the player adds "TF3 Companion Bridge" to a save's mod list
- **THEN** the game shows no add/remove warning and the save's simulation is unchanged

### Requirement: Mod identity
The mod SHALL be identified as `tf3_companion_bridge` with the display name "TF3 Companion Bridge", English-only maintained descriptions, and author Alexandre Lima.

#### Scenario: Mod list
- **WHEN** the player opens the mod list of a save
- **THEN** "TF3 Companion Bridge" is listed with an English summary stating it exports a read-only snapshot

### Requirement: Snapshot triggers
The mod SHALL write a snapshot on the first frame after a save loads, whenever 1/12 of a game year has passed since the previous snapshot, and when the companion posts a refresh request with an id it has not served yet.

#### Scenario: Monthly snapshot
- **WHEN** one twelfth of a game year passes after the last snapshot
- **THEN** a new snapshot is written with `meta.reason = "interval"`

#### Scenario: Refresh request
- **WHEN** the request file contains an id different from the last one served
- **THEN** a snapshot is written within a few seconds with `meta.reason = "request"` and `meta.requestId` equal to that id

### Requirement: Snapshot location
The mod SHALL write each snapshot to `<game userdata>/towns_industries/tf3c_snap_<gameTime>.lua`, with the game time zero-padded to 15 digits, and SHALL read refresh requests from `<game userdata>/towns_industries/tf3c_request.lua`.

#### Scenario: File written
- **WHEN** a snapshot is written at game time 78842800
- **THEN** the file `towns_industries/tf3c_snap_000000078842800.lua` exists and loads as a Lua `data()` table

#### Scenario: No request file
- **WHEN** no request file exists
- **THEN** the mod raises no visible in-game error

### Requirement: Fault isolation
Each collected section (company, lines, vehicles, stations, industries, towns, problems, stocks, depots, catalog) SHALL be collected independently; a failure in one section MUST be recorded in `errors` and MUST NOT prevent the snapshot from being written.

#### Scenario: One collector fails
- **WHEN** reading depots raises an error
- **THEN** the snapshot is still written and `errors` contains an entry starting with `depots:`

### Requirement: Log lines
The mod SHALL prefix every log line with `[tf3c]` and log each written snapshot with its reason, game time, line count, vehicle count and error count.

#### Scenario: Snapshot logged
- **WHEN** a snapshot is written
- **THEN** the game log contains a `[tf3c] snapshot written (...)` line
