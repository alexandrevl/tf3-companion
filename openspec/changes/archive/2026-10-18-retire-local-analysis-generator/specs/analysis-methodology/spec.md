# Spec Delta

## ADDED Requirements

### Requirement: Generic declarative policies and optional examples
The schema SHALL support optional factual and name-pattern classification, roles, graded tolerances, missing-data outcomes, aggregate ratios, notices and maintenance-state markers without making any author's naming convention or playstyle an engine assumption. Packaged examples SHALL be self-contained English methodology files, selectable rather than implicitly mandatory, with documented fixture outcomes independent of retired local generator sources. The existing `local-feeder-intercity-trunk` example identity SHALL remain selectable. The neutral default and explicit/user/save selection semantics SHALL remain unchanged.

The retained feeder/intercity example SHALL document its own policy boundaries: intercity loss and town feeder-cost ratio alerts use strict greater-than comparisons, instantaneous high-load notices use greater-or-equal, and maintenance alerts use strictly-below comparisons. Its existing aircraft-per-terminal policy SHALL remain watch from 3.0 and problem from 3.5, with both markers explicitly described as policy screening, not measured capacity, arrivals or congestion. Retirement SHALL preserve the packaged example bytes, identity, version, parameters and outcomes, including `air_per_terminal_problem`. The historical local generator's watch-only policy SHALL NOT be migrated into the engine or treated as a parity blocker. Existing user-imported methodologies and historical output SHALL NOT be rewritten. Missing terminal data SHALL remain unavailable, never zero. Screening alone SHALL NOT justify adding infrastructure or cutting a fleet.

#### Scenario: No personal conventions required
- **WHEN** a valid methodology declares no name patterns and classifies entities through supported factual fields
- **THEN** it evaluates arbitrary line and town names without requiring personal mode, town or scope codes

#### Scenario: Example policy boundary fixtures
- **WHEN** the retained example evaluates synthetic entities at intercity loss 100,000, town cost ratio 0.25, instantaneous load 0.90 and maintenance-state boundaries
- **THEN** the markers follow the example's self-contained documented comparison directions
- **AND** expected results do not depend on executing or inspecting the removed generator

#### Scenario: Existing aircraft screening policy remains selectable
- **WHEN** the retained example evaluates screening ratios of 3.0 and 3.5 aircraft per used terminal
- **THEN** the existing example produces watch at 3.0 and problem at 3.5 with manual-check guidance, neither marker claiming measured congestion
- **AND** an absent denominator produces unavailable coverage rather than a fabricated zero ratio

#### Scenario: Historical policy remains historical
- **WHEN** a player retains an imported methodology or previously generated report
- **THEN** retirement does not edit its policy or reinterpret its stored provenance

## REMOVED Requirements

### Requirement: Author's methodology expressible without loss
**Reason**: It makes one author's local generator an implicit source-parity contract for the product; the generator is being retired and its policy must not be an engine assumption.
**Migration**: Replaced by "Generic declarative policies and optional examples". The packaged `local-feeder-intercity-trunk` example is preserved unchanged and remains selectable.
