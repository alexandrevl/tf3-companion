# Spec Delta

## Purpose

Exposes the companion's data, analyses, journal and knowledge to any MCP-capable AI agent over stdio.

## ADDED Requirements

### Requirement: MCP server
The companion SHALL run an MCP server named `tf3-companion` over stdio via `tf3c mcp`.

#### Scenario: Agent connects
- **WHEN** an MCP client starts `tf3c mcp`
- **THEN** it lists the companion's tools

### Requirement: Tool set
The server SHALL expose the tools `status`, `refresh`, `company_overview`, `list_lines`, `line_detail`, `list_vehicles`, `list_industries`, `list_towns`, `findings`, `opportunities`, `company_history`, `list_stocks`, `list_depots`, `vehicle_catalog`, `export_spreadsheet`, `record_decision`, `update_decision`, `list_decisions`, `knowledge`, `save_notes` and `log_tail`, each with an English description.

#### Scenario: Notes tool
- **WHEN** the agent calls `save_notes` with text to append
- **THEN** the note is stored and the full notes are returned

### Requirement: Actionable errors
A tool that cannot answer SHALL return an English error explaining the cause and the next step instead of a stack trace.

#### Scenario: No snapshot yet
- **WHEN** a data tool is called before any snapshot was imported
- **THEN** the error tells the player to open the game with the mod enabled and call `refresh`

#### Scenario: Unknown line
- **WHEN** `line_detail` is called with a name that matches no line
- **THEN** the error lists up to 10 lines whose names contain the text

### Requirement: Refresh round trip
`refresh` SHALL post a new request id, wait up to the given timeout for a snapshot carrying that id, import it and report its date; on timeout it MUST say the game did not answer and point to `log_tail`.

#### Scenario: Game closed
- **WHEN** `refresh` is called with the game closed
- **THEN** after the timeout it returns `ok: false` with the hint to check the mod and the log
