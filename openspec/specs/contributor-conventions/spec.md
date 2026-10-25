# contributor-conventions Specification

## Purpose
Define consistent contributor instructions for humans and agents, enforcing English repository content while preserving read-only gameplay boundaries, verification requirements and OpenSpec planning conventions.

## Requirements

### Requirement: Contributor instructions at repository root
The repository SHALL provide root `AGENTS.md` containing actionable contributor conventions, not a reference to itself. It SHALL cover the language rule, the read-only gameplay boundary, verification expectations and OpenSpec planning, consistently with `CONTRIBUTING.md` and `openspec/config.yaml`.

#### Scenario: Agent opens the repository
- **WHEN** an AI agent loads `AGENTS.md`
- **THEN** it finds the conventions themselves rather than a pointer back to the same file

### Requirement: English-only repository content
All content written for the repository SHALL be in English without exception: code, identifiers, file and folder names, comments, docstrings, string literals in source, tests, scripts, docs, commit messages and OpenSpec artifacts. The rule SHALL apply anywhere in the working tree, including gitignored locations such as `data/` and `scripts/`.

#### Scenario: New author-local script
- **WHEN** an agent creates a script under a gitignored directory
- **THEN** the file name, identifiers, comments and strings are English

#### Scenario: Domain term in source
- **WHEN** code must refer to a game concept
- **THEN** it uses the English term, not a localized literal such as a Portuguese vehicle or cargo name

### Requirement: Conversation language is separate
`AGENTS.md` SHALL state that conversation with the player MAY use the player's language, and that this does not extend to anything written to files or commits.

#### Scenario: Portuguese-speaking player
- **WHEN** the player writes in Portuguese
- **THEN** the agent may reply in Portuguese but writes all files and commit messages in English

### Requirement: Rule reaches Claude-based agents
`CLAUDE.md` SHALL resolve to the same content as `AGENTS.md`, so the rule is loaded by agents that read either file.

#### Scenario: Claude-based agent
- **WHEN** an agent reads `CLAUDE.md`
- **THEN** it receives the full `AGENTS.md` content including the Language section

### Requirement: Contributing guide mirrors the rule
`CONTRIBUTING.md` SHALL state the same English-only rule and refer contributors to `AGENTS.md`.

#### Scenario: Human contributor
- **WHEN** a contributor reads the principles in `CONTRIBUTING.md`
- **THEN** the English-only rule, including file names and gitignored paths, is stated there

### Requirement: Player-facing output language is not decided here
The conventions SHALL NOT require or forbid localized rendering of reports for players. Source code SHALL NOT contain localized literals; any localization of output is deferred to a separate change.

#### Scenario: Report for a Portuguese-speaking player
- **WHEN** localized output is wanted
- **THEN** it is handled by a future change and not by embedding Portuguese strings in source

### Requirement: Verifiable absence of Portuguese in tracked files
A documented command SHALL search tracked files, excluding `data/`, for common Portuguese accented characters and words and SHALL return no matches when the repository complies, apart from an explicit, reviewed allowlist of legitimate occurrences. The same check SHALL run automatically before each commit when hooks are installed and in continuous integration for every pull request, and `CONTRIBUTING.md` SHALL tell contributors how to install the hooks.

#### Scenario: Compliant repository
- **WHEN** the command is run at the repository root
- **THEN** it exits with no matches

#### Scenario: Violation in a pull request
- **WHEN** a pull request adds Portuguese text outside the allowlist
- **THEN** the automated check fails and names the file and line

#### Scenario: New contributor
- **WHEN** a contributor reads `CONTRIBUTING.md`
- **THEN** it explains how to install the hooks and run every check locally
