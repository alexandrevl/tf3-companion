# Spec Delta

## ADDED Requirements

### Requirement: Report tool
The MCP server SHALL expose a tool `report` with parameters `kind` (`company`, `lines`, `fleet`, `cargo`, `decisions`, `annual`) and optional `year` (annual only) that ingests new snapshots, generates the report for the active save and returns the Markdown text. It SHALL also write the Markdown file to the save's `reports/` directory and state its path in the result so the agent can tell the player where it is.

#### Scenario: Markdown returned
- **WHEN** an agent calls `report` with kind `fleet`
- **THEN** the result contains the Markdown of the fleet report, including its tables and Mermaid blocks

#### Scenario: File written
- **WHEN** an agent calls `report` with kind `annual` and year 1984
- **THEN** `reports/annual-1984.md` exists and its path appears in the result

#### Scenario: Invalid arguments
- **WHEN** an agent calls `report` with kind `weekly`, or with `year` on a non-annual kind, or with a year without data
- **THEN** the tool returns an error message that names the valid kinds or the available years, and writes no file

#### Scenario: Tool description
- **WHEN** an agent lists the tools
- **THEN** the `report` description explains each kind in one line, that `year` is for `annual`, and that output is Markdown with Mermaid charts

### Requirement: Spreadsheet tool opening parameter
The `export_spreadsheet` tool SHALL take an optional boolean `open` that defaults to false and, when true, opens the workbook with the OS default application on Windows and macOS. The previous `open_in_numbers` parameter SHALL no longer exist. The result SHALL always include the file path.

#### Scenario: Default does not open
- **WHEN** an agent calls `export_spreadsheet` without arguments
- **THEN** the workbook is written, its path is returned and no application is launched

#### Scenario: Open requested
- **WHEN** an agent calls `export_spreadsheet` with `open` true
- **THEN** the workbook is opened with the OS default application and the result reports `opened: true`

#### Scenario: Old parameter rejected
- **WHEN** an agent calls `export_spreadsheet` with `open_in_numbers`
- **THEN** the call is rejected by the tool schema
