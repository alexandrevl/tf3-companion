# Spec Delta

## Purpose

Deterministic, explainable analyses that turn a snapshot (and the one before it) into findings and opportunities backed by numbers.

## ADDED Requirements

### Requirement: Finding shape
Every finding SHALL contain a stable `code`, a `severity` (high, medium, low), a `category` (finance, lines, vehicles, industries, data), an English `title`, `detail` and `suggestion`, the related `entity` (kind, id, full name) or null, and the `evidence` numbers that triggered it.

#### Scenario: Codes are stable
- **WHEN** the same condition is detected in two different snapshots
- **THEN** both findings carry the same `code`

### Requirement: Ordering
Findings SHALL be ordered by severity (high first), then category, then title.

#### Scenario: Mixed severities
- **WHEN** a snapshot yields high and low findings
- **THEN** all high findings precede the low ones

### Requirement: Line findings
The companion SHALL report lines without vehicles (`line_no_vehicles`), lines with negative annual profit (`line_losing_money`, high when the line is at least one year old, low otherwise), lines at or above 90% load (`line_overloaded`), lines at or below 30% load with two or more vehicles (`line_underused`), game-reported line issues (`line_config_issue`) and a profit drop of at least 30% and 100,000 since the previous snapshot (`line_profit_dropping`).

#### Scenario: Young losing line
- **WHEN** a line younger than one year has negative annual profit
- **THEN** a low-severity `line_losing_money` finding states the number is partial

#### Scenario: Instant load caveat
- **WHEN** `line_underused` is reported
- **THEN** its detail states that load is an instant reading, not an average

### Requirement: Vehicle findings
The companion SHALL report vehicles without a path (`vehicle_no_path`), loss-making vehicles at least one year old on a profitable line (`vehicle_losing_on_profitable_line`) and one aggregate finding for vehicles idle in a depot without a line for 30 or more days with their summed value (`vehicles_idle_in_depot`).

#### Scenario: Idle vehicles
- **WHEN** three vehicles sit in depots without a line for 40 days
- **THEN** one `vehicles_idle_in_depot` finding lists them and their total value

### Requirement: Industry and data findings
The companion SHALL report industries scheduled to close (`industry_closing`) and snapshots with collection errors (`snapshot_collection_errors`, listing up to 20 errors).

#### Scenario: Collection errors
- **WHEN** a snapshot contains errors
- **THEN** a `snapshot_collection_errors` finding warns that numbers may be incomplete

### Requirement: Cargo opportunities
The companion SHALL list outputs that ship less than half of what they produce, with the nearest consumers of that cargo and their distance in kilometres.

#### Scenario: Unshipped iron ore
- **WHEN** a mine produces 120 ore per year and ships none
- **THEN** it appears with the nearest steel mills and their distances
