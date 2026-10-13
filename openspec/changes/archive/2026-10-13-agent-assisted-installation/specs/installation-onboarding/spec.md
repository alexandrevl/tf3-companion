# Spec Delta

## Purpose

Help players and their AI clients bootstrap TF3 Companion safely and distinguish configured components from verified game-to-report operation on Windows and macOS.

## ADDED Requirements

### Requirement: Installation guidance before MCP connection
The project SHALL provide an English agent-assisted installation entrypoint that works before the companion or MCP connection exists, with Windows and macOS instructions and a copyable bootstrap request.

#### Scenario: First-time player
- **WHEN** a player opens the README without a configured companion
- **THEN** they can find installation guidance without invoking MCP tools or possessing game snapshots
- **AND** the bootstrap request tells their agent to establish its terminal and filesystem capabilities before acting

### Requirement: Offline MCP onboarding surfaces
The MCP server SHALL expose a `setup-check` prompt and `tf3c://setup` Markdown resource without requiring game installation, Steam userdata or snapshots. Existing analysis prompts SHALL remain available.

#### Scenario: Missing game and player data
- **WHEN** a client connects with no usable game or player-data paths
- **THEN** it can retrieve the setup prompt and resource
- **AND** onboarding directs diagnosis through `doctor` without pretending analysis data exists

#### Scenario: Installed distribution
- **WHEN** the server runs from an installed distribution outside the repository
- **THEN** the same setup guidance remains available through MCP

### Requirement: Capability-aware assistance
Installation guidance SHALL distinguish a local agent capable of approved terminal operations from text-only chat. It SHALL describe local stdio-compatible clients without claiming that ChatGPT web can directly connect to a local stdio server.

#### Scenario: Text-only assistant
- **WHEN** an assistant cannot access the player's machine
- **THEN** it provides commands for the player to run and requests their output
- **AND** it does not claim commands or filesystem checks were executed

### Requirement: Explicit mutation boundaries
Onboarding SHALL require explicit player authorization for dependency installation, mod installation or replacement, and client configuration changes. It SHALL preserve unrelated client configuration and leave game activation and gameplay changes to the player.

#### Scenario: Mod not installed
- **WHEN** diagnosis identifies a missing bridge
- **THEN** guidance explains the intended installation location and asks permission before a capable agent installs it
- **AND** it identifies enabling the mod and loading the game as manual player steps

#### Scenario: Existing client configuration
- **WHEN** guidance explains adding the MCP server to a client's configuration
- **THEN** it instructs merging the new server entry rather than replacing unrelated settings

### Requirement: Evidence-based completion
Onboarding SHALL report package availability, bridge revision, MCP connectivity, fresh snapshot collection and report generation as separate verification stages. It SHALL NOT treat `doctor.ok`, an existing snapshot, or an installed mod alone as proof of end-to-end readiness.

#### Scenario: Diagnostics pass with warnings
- **WHEN** `doctor.ok` is true but bridge or snapshot checks are warnings
- **THEN** onboarding reports the incomplete stages and their next actions instead of declaring installation complete

#### Scenario: Game activation pending
- **WHEN** local setup is verified but the player has not enabled the bridge and loaded the game
- **THEN** onboarding reports readiness for the manual game step with in-game verification pending

#### Scenario: Verified operation
- **WHEN** a requested refresh receives a new snapshot and a report is successfully generated
- **THEN** onboarding cites the observed snapshot date and report result
- **AND** it surfaces collection errors and limitations rather than claiming complete coverage

### Requirement: First-use analyst routing
Packaged analyst instructions SHALL route missing setup or missing snapshot conditions to onboarding before attempting data-dependent analysis.

#### Scenario: Analysis requested before setup
- **WHEN** a player asks for company analysis but setup or observations are missing
- **THEN** the assistant explains the missing prerequisite and follows installation guidance instead of inventing findings
