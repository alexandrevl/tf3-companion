# Spec Delta

## Purpose

Gives players and developers direct access to the companion from a terminal, without any AI agent.

## ADDED Requirements

### Requirement: Command surface
The `tf3c` command SHALL provide `status`, `ingest`, `refresh`, `overview`, `lines`, `line`, `findings`, `opportunities`, `notes`, `log`, `export` and `mcp`, with English help text.

#### Scenario: Help
- **WHEN** the player runs `tf3c --help`
- **THEN** every command is listed with an English description

### Requirement: Readable findings
`tf3c findings` SHALL print findings grouped by severity with title, detail and suggestion, and `--json` SHALL print the structured findings.

#### Scenario: Nothing to report
- **WHEN** a snapshot yields no findings
- **THEN** the command prints "Nothing to report in this snapshot."

### Requirement: Exit codes
Commands SHALL exit 0 on success and 1 on a user-facing error (no snapshot, unknown entity, invalid argument, refresh timeout), printing the message to standard error.

#### Scenario: Refresh timeout
- **WHEN** `tf3c refresh` times out
- **THEN** the command exits with status 1

### Requirement: Open exports with the default application
`tf3c export --open` SHALL open the generated spreadsheet with the operating system's default application on Windows and macOS.

#### Scenario: Windows
- **WHEN** the player runs `tf3c export --open` on Windows
- **THEN** the XLSX opens in the default spreadsheet application
