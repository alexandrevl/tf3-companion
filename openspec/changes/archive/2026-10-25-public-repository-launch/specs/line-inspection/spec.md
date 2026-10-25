# Spec Delta

## Purpose

Defines what line detail reports about a line's cargo capacity and issues, so cargo names and quantities are correct wherever line detail is shown.

## ADDED Requirements

### Requirement: Capacity entries name the cargo they carry
Each capacity entry of a line SHALL name the cargo it describes, resolving the stored one-based cargo index to the correct cargo, using the same convention as every other consumer of line capacity.

#### Scenario: Freight line
- **WHEN** a line's stored capacity entry with index `19` has positive capacity and cargo id `18` is Crude Oil in the snapshot
- **THEN** line detail shows Crude Oil for that entry

#### Scenario: Passenger line
- **WHEN** a passenger line's capacity entry has index `1` and cargo id `0` is Passengers
- **THEN** line detail shows Passengers

### Requirement: Only carried cargo is listed
Line detail SHALL list only capacity entries with a capacity above zero. A line with no positive capacity SHALL report an empty list, not a list of zero entries.

#### Scenario: Thirty-seven cargo types, one carried
- **WHEN** the stored capacity contains thirty-seven entries and only one is above zero
- **THEN** line detail lists exactly that entry

### Requirement: Consistent across interfaces
The CLI and the MCP `line_detail` tool SHALL show the same capacity entries and cargo names for the same snapshot.

#### Scenario: CLI and MCP agree
- **WHEN** the same line is requested through `tf3c line` and the MCP tool
- **THEN** both list identical cargo names and capacities

### Requirement: Issues resolve cargo the same way
Where a line issue refers to a cargo, line detail SHALL resolve that cargo using the convention of the stored issue data, and SHALL show an explicit unknown marker rather than a wrong name when the cargo cannot be resolved.

#### Scenario: Unresolvable cargo
- **WHEN** an issue refers to a cargo index absent from the snapshot's cargo table
- **THEN** the issue shows an unknown cargo marker and no other cargo name
