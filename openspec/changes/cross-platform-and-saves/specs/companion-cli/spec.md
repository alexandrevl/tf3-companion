# Spec Delta

## ADDED Requirements

### Requirement: Setup and save commands
`tf3c` SHALL provide `doctor`, `mod install`, `mod uninstall`, `saves`, `saves use <id|label>`, `saves unpin`, `saves label <id> <text>` and `config snapshots-per-year <1|4|12>`.

#### Scenario: Pin by label
- **WHEN** the player runs `tf3c saves use "Holland main"`
- **THEN** that save becomes active and pinned

#### Scenario: Unknown save
- **WHEN** the player runs `tf3c saves use nope`
- **THEN** the command exits 1 and lists known saves

### Requirement: Global save option
Data commands SHALL accept `--save <id|label>` to answer about a save without pinning it.

#### Scenario: One-off query
- **WHEN** the player runs `tf3c findings --save "Holland main"` while another save is active
- **THEN** findings are computed for "Holland main" and the active save does not change
