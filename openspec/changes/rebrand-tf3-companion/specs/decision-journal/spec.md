# Spec Delta

## Purpose

Keeps a journal of what the player decided and why, stamped with the game date, so outcomes can be checked against later data.

## ADDED Requirements

### Requirement: Record a decision
The companion SHALL store a decision with title, rationale, related entity references, status `planned`, the real-world creation time and the game time and date of the latest snapshot.

#### Scenario: Decision recorded
- **WHEN** a decision is recorded while the latest snapshot is dated 1983-07-17
- **THEN** it is returned with an id, status `planned` and game date 1983-07-17

### Requirement: Update a decision
The companion SHALL let a decision move to `planned`, `done` or `dropped` and attach an observed outcome; any other status MUST be rejected.

#### Scenario: Invalid status
- **WHEN** a decision is updated with status `maybe`
- **THEN** the update is rejected with the list of valid statuses

### Requirement: List decisions
The companion SHALL list decisions newest first, optionally filtered by status.

#### Scenario: Planned only
- **WHEN** decisions are listed with status `planned`
- **THEN** only planned decisions are returned, newest first
