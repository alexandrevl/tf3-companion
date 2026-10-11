## ADDED Requirements

### Requirement: Entity references on decisions
Decisions SHALL link to game entities through references of kind line, vehicle, industry or station, each with id and name. References given as free text SHALL be resolved against the current snapshot by id or exact full name when recorded; unresolved text SHALL be kept as a note and not used for follow-up. A decision whose status becomes `done` SHALL store the game time of that transition.

#### Scenario: Reference resolved
- **WHEN** a decision is recorded with the entity "Line 12 - Oak Hill to Port"
- **THEN** it is stored as a line reference with that line's id and name

#### Scenario: Done time stored
- **WHEN** a planned decision is updated to done
- **THEN** the latest snapshot's game time is stored as the done time

### Requirement: Decision follow-up
The system SHALL provide a follow-up for a decision that compares, for each linked entity, metrics in a baseline snapshot with the latest snapshot. The baseline SHALL be the stored snapshot at or immediately before the decision's done time (or creation time for decisions not marked done). Metrics: for lines — profit per year, vehicles, mean load over the 3 snapshots around each point; for vehicles — profit per year; for industries — shipped per year and output stock fill; for stations — stock fill. Each result SHALL carry a maturity state based on game time elapsed since the baseline relative to the year duration: `too_early` (< 25% of a year), `provisional` (25% to < 100%, because the profit figure is a rolling 12-month window still containing pre-change months) and `mature` (≥ 100%). Entities that no longer exist SHALL be reported `entity_missing`. Decisions without a resolvable entity or without a baseline snapshot SHALL be reported `not_trackable` with the reason. Follow-up SHALL be available through the service, an MCP tool and a `tf3c` command, and SHALL NOT change the decision.

#### Scenario: Mature follow-up
- **WHEN** a decision marked done 14 game months ago linked a line whose profit per year was 100k at baseline and is 400k now
- **THEN** the follow-up shows both values, a change of +300k and maturity `mature`

#### Scenario: Profit window still moving
- **WHEN** only 4 game months have passed
- **THEN** the result is `provisional` and states that profit still includes months before the change

#### Scenario: Deleted line
- **WHEN** a linked line is absent from the latest snapshot
- **THEN** that entity is `entity_missing` and other entities are still compared

#### Scenario: No baseline
- **WHEN** no stored snapshot exists at or before the decision time
- **THEN** the decision is `not_trackable` with reason `no_baseline_snapshot`

### Requirement: Follow-up prompt finding
The system SHALL produce a `decision_followup_ready` finding (low, category data) for each decision with status done whose follow-up is `mature` for at least one entity and whose outcome has not been recorded, so the player or agent is reminded to review and record the outcome.

#### Scenario: Reminder
- **WHEN** a done decision with no outcome becomes mature
- **THEN** one `decision_followup_ready` finding references its id and title

#### Scenario: Outcome recorded
- **WHEN** the decision already has an outcome text
- **THEN** no reminder finding is produced
