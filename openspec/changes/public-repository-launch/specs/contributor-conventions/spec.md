# Spec Delta

## MODIFIED Requirements

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
