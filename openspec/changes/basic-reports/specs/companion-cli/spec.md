# Spec Delta

## ADDED Requirements

### Requirement: Report command
The CLI SHALL provide `tf3c report <kind>` with kinds `company`, `lines`, `fleet`, `cargo`, `decisions` and `annual`, and the options `--year <Y>` (annual only), `--html`, `--open` and `--save <id>`. The command SHALL ingest new snapshots first, write the Markdown report to the selected save's `reports/` directory, and print the written path(s). With `--html` it SHALL also write the HTML variant. On success it SHALL exit 0.

#### Scenario: Markdown report
- **WHEN** the user runs `tf3c report company`
- **THEN** `reports/company.md` is written for the active save, its path is printed and the exit code is 0

#### Scenario: HTML as well
- **WHEN** the user runs `tf3c report lines --html`
- **THEN** both `reports/lines.md` and `reports/lines.html` are written and both paths are printed

#### Scenario: Annual with year
- **WHEN** the user runs `tf3c report annual --year 1984`
- **THEN** `reports/annual-1984.md` is written

#### Scenario: Explicit save
- **WHEN** the user runs `tf3c report fleet --save <id>` for a non-active save
- **THEN** the report is written under that save's directory and the active save is unchanged

### Requirement: Report command errors
`tf3c report` SHALL exit non-zero with a one-line English message on stderr, and write no file, for an unknown kind, `--year` combined with a kind other than `annual`, a year without snapshots (the message lists the available years), an unknown save, or an empty store.

#### Scenario: Year on wrong kind
- **WHEN** the user runs `tf3c report company --year 1984`
- **THEN** the command exits non-zero explaining that `--year` applies only to `annual`

#### Scenario: Year without data
- **WHEN** the user runs `tf3c report annual --year 1950`
- **THEN** the command exits non-zero and the message lists the years with data

#### Scenario: Empty store
- **WHEN** the user runs `tf3c report company` before any snapshot was ingested
- **THEN** the command exits non-zero with a message that no snapshot exists

### Requirement: Opening files with the OS default application
`--open` on `tf3c report` and `tf3c export` SHALL open the generated file with the operating system's default application on Windows and macOS (and via the desktop opener on Linux). For `report`, `--open` opens the HTML file when `--html` is given and the Markdown file otherwise. The CLI MUST NOT depend on a specific application such as Numbers. Without `--open`, no application is launched. If opening fails, the command SHALL print a warning, still print the file path, and exit 0.

#### Scenario: Open HTML
- **WHEN** the user runs `tf3c report annual --html --open`
- **THEN** the HTML file is opened with the default handler of the OS

#### Scenario: Export opens without Numbers
- **WHEN** the user runs `tf3c export --open` on a machine without Numbers
- **THEN** the `.xlsx` is opened with the default handler and no error mentions Numbers

#### Scenario: No handler available
- **WHEN** the OS reports no handler for the file
- **THEN** a warning is printed, the path is printed and the exit code is 0
