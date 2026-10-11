## ADDED Requirements

### Requirement: Finding contract for new analyses
Every finding produced by the analyses in this capability SHALL carry a stable snake_case `code`, a `severity` (high|medium|low), a `category` (finance|lines|vehicles|industries|data), English `title`/`detail`/`suggestion`, an `entity` (`{kind,id,name}` or null) and an `evidence` object holding the numbers that triggered it. Entity names SHALL be the full game names (lines, vehicles, industries, depots with their town), never ids alone. The `findings` service call and tool SHALL accept an optional `code` filter.

#### Scenario: Evidence accompanies every finding
- **WHEN** any new finding is produced
- **THEN** its `evidence` contains the measured values and the thresholds applied, and its `code` is one of the codes listed in this capability

#### Scenario: Filter by code
- **WHEN** findings are requested with `code` set to `industry_output_full`
- **THEN** only findings with that code are returned

### Requirement: Cargo config mismatch
The system SHALL report, for each vehicle on a line, a `vehicle_cargo_mismatch` finding (high) when the vehicle's configured load cargo is neither loadable nor unloadable at any stop of its line, that is, no stop's served industries (as producer or consumer) or towns (as supplier or acceptor) handle that cargo. Vehicles of one line with the same mismatch SHALL be aggregated into a single finding per (line, cargo) listing the vehicle ids and their configured cargo versus the cargos the line's stops handle. Passenger and mail cargo served by a stop in a town SHALL count as handled. If the snapshot lacks station links the analysis SHALL be skipped and a single low `analysis_data_missing` data finding SHALL name the analysis and the missing fields.

#### Scenario: Trucks set to the wrong cargo
- **WHEN** a line's stops serve a sawmill that outputs Logs and its trucks are configured for Planks only
- **THEN** one `vehicle_cargo_mismatch` finding names the line, lists the trucks, the configured cargo (Planks) and the handled cargos (Logs)

#### Scenario: Correctly configured line
- **WHEN** every vehicle's configured cargo is handled by at least one stop of its line
- **THEN** no mismatch finding is produced for that line

#### Scenario: Station links absent
- **WHEN** the latest snapshot has no station-to-industry/town links
- **THEN** no mismatch findings are produced and one `analysis_data_missing` finding explains that the mod must be updated

### Requirement: Full stocks
The system SHALL report stocks that are full, where full means count/capacity ≥ 0.90: `industry_output_full` for an industry output stock of an industry whose lines ship it (shipped per year > 0), `warehouse_full` for a warehouse stock, and `station_stock_full` for a stock waiting at a station the company uses. Industry output stocks full on industries with no shipping SHALL NOT be listed individually; they SHALL be summarised in one low `industries_output_full_unserved` finding carrying the total count and the top entries by fill. Severity SHALL be medium for warehouse and station stocks and for served industries; low for the unserved summary.

#### Scenario: Warehouse at capacity
- **WHEN** a warehouse holds 500 of 500 Logs
- **THEN** a `warehouse_full` finding names the warehouse and shows count, capacity and fill 1.0

#### Scenario: Many unserved industries
- **WHEN** 50 industries have a full output stock and none of their cargo is shipped
- **THEN** a single `industries_output_full_unserved` finding reports the count 50 and its top entries, and no per-industry finding is created for them

### Requirement: Load trend over recent snapshots
The system SHALL compute per-line occupancy over the last N stored snapshots (default N=6, at most one snapshot per game month considered) and expose mean load, latest load, number of samples and a slope in occupancy points per snapshot. It SHALL produce `line_load_persistently_high` (mean ≥ 0.90) and `line_load_persistently_low` (mean ≤ 0.30 and at least 2 vehicles) findings only when at least 3 samples exist for the line. Samples in which the line had no capacity SHALL be ignored. When a line has fewer than 3 samples the instant-load findings (`line_overloaded`, `line_underused`) SHALL still be produced; when it has 3 or more they SHALL be replaced by the trend findings.

#### Scenario: Persistently overloaded line
- **WHEN** a line's load was 0.95, 0.92, 0.97 and 0.90 in the last four snapshots
- **THEN** a `line_load_persistently_high` finding is produced with the mean, the samples and the slope in evidence, and no instant overloaded finding is produced for it

#### Scenario: Spike in one snapshot
- **WHEN** a line's load was 0.40, 0.45, 0.95
- **THEN** no persistently-high finding is produced

#### Scenario: Short history
- **WHEN** only two snapshots exist
- **THEN** the instant-load findings are produced and the trend view reports `insufficient_history` for the line

### Requirement: Fleet fit against the year's catalog
The system SHALL rate each vehicle's model with a fit score = capacity for the line's main cargo × top speed ÷ running cost per year, and compare it with every catalog model that is available this game year, has the same carrier and can carry that cargo. It SHALL expose a per-line view (`fleet_fit`) listing the current models, their scores and the best alternatives, and SHALL produce: `vehicle_better_model_available` (low) when the best alternative scores at least 25% higher; `vehicle_near_end_of_life` (medium) when age ≥ 80% of the model lifespan; `vehicle_model_out_of_production` (low) when the model is not available this year in the catalog. Findings SHALL be aggregated per line and model. If the snapshot history has no catalog the analysis SHALL be skipped with an `analysis_data_missing` finding, and if the model cannot be matched to a catalog entry the vehicle SHALL be reported as `unmatched` in the view without a finding.

#### Scenario: Better model available
- **WHEN** a line runs a model scoring 100 and the catalog has an available same-carrier model scoring 140 for the same cargo
- **THEN** a `vehicle_better_model_available` finding shows both scores, the improvement of 40% and the replacement model name

#### Scenario: End of life
- **WHEN** a vehicle is 85% through its model lifespan
- **THEN** a `vehicle_near_end_of_life` finding shows age, lifespan and fraction

#### Scenario: No catalog
- **WHEN** no stored snapshot carries a catalog
- **THEN** fleet fit findings are not produced and an `analysis_data_missing` finding is reported

### Requirement: Idle capital
The system SHALL report vehicles in a depot with no line for at least 30 days (`daysInDepot`) as one `fleet_idle_in_depot` finding per depot (medium), naming the depot with its town, the vehicles and the summed `value`. A top-level total of tied-up value SHALL appear in the evidence of every such finding as `totalIdleValue`.

#### Scenario: Ships idle in depots
- **WHEN** ten ships worth 9.8M sit in two harbour depots for over 30 days
- **THEN** two `fleet_idle_in_depot` findings are produced, one per depot, each with its vehicle list, its value and the total 9.8M

#### Scenario: Recently bought vehicle
- **WHEN** a vehicle has been in a depot for 5 days
- **THEN** it is not reported

### Requirement: Empty and orphan lines
The system SHALL report `line_no_vehicles` (medium) for lines with stops but no vehicles, `line_no_stops` (medium) for lines with vehicles but fewer than two stops, and `line_orphan` (medium) for lines with neither, instead of the two separate findings.

#### Scenario: Line without vehicles and stops
- **WHEN** a line has zero vehicles and zero stops
- **THEN** exactly one `line_orphan` finding is produced for it

#### Scenario: Line with one stop
- **WHEN** a line with vehicles has a single stop
- **THEN** a `line_no_stops` finding states the stop count

### Requirement: Line scope economics
The system SHALL derive each line's length as the sum of straight-line distances (metres) between consecutive stop positions, classify it as local (< 5 km), regional (5–25 km) or intercity (> 25 km), and expose profit per vehicle per band (lines, vehicles, total profit, mean and median profit per vehicle) over mature lines (≥ 1 year) with vehicles. It SHALL NOT use line names to classify. It SHALL produce a `scope_band_weak` finding (low) for a band whose median profit per vehicle is below 25% of the best band's, provided both bands hold at least 3 lines. Lines without stop positions SHALL be listed as `unclassified`.

#### Scenario: Regional beats local
- **WHEN** local lines earn a median of 22k per vehicle and regional lines 647k
- **THEN** the view lists both bands and a `scope_band_weak` finding for local carries both medians and line counts

#### Scenario: Names are irrelevant
- **WHEN** lines have arbitrary names
- **THEN** their band depends only on stop positions

#### Scenario: Missing positions
- **WHEN** stop positions are absent in the snapshot
- **THEN** all lines are `unclassified` and one `analysis_data_missing` finding is reported

### Requirement: Analysis availability reporting
Whenever an analysis cannot run because the snapshot or history lacks data, the system SHALL emit exactly one `analysis_data_missing` finding (category data, low) per analysis, with evidence naming the analysis and the missing fields, instead of silently returning nothing.

#### Scenario: Older snapshot
- **WHEN** the latest snapshot predates the station-link fields
- **THEN** cargo mismatch and scope economics each report one `analysis_data_missing` finding

### Requirement: Documented `transportedYear` semantics
The `transportedYear` field SHALL NOT be used by any finding or view until its meaning has been established in-game and documented in the shipped knowledge. The documentation SHALL state the measured unit and window and the discrepancy that made earlier values look too low.

#### Scenario: Knowledge topic updated
- **WHEN** the investigation is complete
- **THEN** the `mechanics` and `snapshot_schema` topics describe what `transportedYear` measures and how it was verified, with `[INFERENCE]` marks for anything unverified
