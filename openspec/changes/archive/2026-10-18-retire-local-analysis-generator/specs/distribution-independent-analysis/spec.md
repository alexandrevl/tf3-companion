# Spec Delta

## Purpose

Support generic, local-first analysis from installed distributions independently of checkout-local scripts, personal policies and author data, while preserving player-owned evidence.

## ADDED Requirements

### Requirement: Installed analysis is independent of checkout assets

Supported evaluation and report workflows SHALL operate from an installed distribution without a source checkout or its `data/` directory. Shipped package resources MAY be used. Explicitly configured runtime evidence stores and validated imported methodology files SHALL remain supported; a configurable directory named `data` SHALL NOT be rejected because of its name. No personal save path, line-name convention, localized cargo literal or town-code mapping SHALL be required for these workflows.

#### Scenario: Installed package with generic evidence

- **WHEN** the installed package runs outside the checkout against a temporary synthetic store whose lines have arbitrary names, with a validated methodology based on factual fields rather than name captures
- **THEN** stored-evidence evaluation returns factual and policy results with provenance and coverage
- **AND** report composition and explicitly requested publication succeed using those same results
- **AND** no checkout asset, network request, mod installation or live-game action is needed

#### Scenario: Imported methodology remains configurable

- **WHEN** a player selects a validated methodology imported into their configured runtime library
- **THEN** evaluation uses that selected policy and runtime evidence without requiring a packaged personal example or a checkout

### Requirement: One supported analysis implementation

The local generator entrypoint and its six helper/report sources SHALL be retired, not relocated, wrapped or retained as an oracle. Supported evaluation and reports SHALL use the shared product evaluation and report-analysis contracts. Acceptance SHALL use independent synthetic expected values, not execution or parsing of retired sources, blanket page parity or personal naming/page conventions.

#### Scenario: Generic capability retained

- **WHEN** equivalent stored evidence is evaluated and reported after retirement
- **THEN** preserved generic facts and diagnostics follow the documented product contracts
- **AND** no legacy generator is invoked or required for comparison

#### Scenario: Unsafe legacy conclusions are not compatibility promises

- **WHEN** evidence lacks verified station-industry links, capacity/queue measurements or verified replacement financial units
- **THEN** the system does not recreate the local generator's inferred cargo-chain ownership, congestion conclusion or replacement payback to satisfy parity
- **AND** supported raw facts, uncertainty and guarded product comparisons remain available

### Requirement: Retirement preserves player-owned records

Retirement SHALL NOT delete or migrate player snapshots, databases, configuration, preferences, notes, methodology files or historical generated reports. Historical playtest records and archived specifications SHALL remain records of their time. Current operational documentation SHALL direct users to supported package workflows, not require retired code to exist. Source-reference migration in local analysis notes SHALL preserve recorded evidence and policy history.

#### Scenario: Existing player data on upgrade

- **WHEN** a store already contains evidence, user policy/preferences and generated historical reports
- **THEN** retirement leaves those records intact and does not regenerate or relabel historical outputs

#### Scenario: Current instructions versus historical records

- **WHEN** contributors or players follow current analysis documentation
- **THEN** it describes supported evaluation, analysis and report commands and self-contained policy examples
- **AND** a historical mention of the retired generator does not make that generator an executable dependency
