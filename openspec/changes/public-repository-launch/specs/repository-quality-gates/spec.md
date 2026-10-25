# Spec Delta

## Purpose

Defines the automated checks every commit and pull request must pass before it can enter the public repository, so quality, privacy and language rules are enforced by tooling rather than by memory.

## ADDED Requirements

### Requirement: Commit-time hooks
The repository SHALL provide a `pre-commit` configuration that, once installed, runs fast checks before each commit and rejects the commit when one fails. The hooks SHALL cover whitespace and merge-marker hygiene, oversized files, lint and format, Lua syntax, the repository guards and a quick test subset.

#### Scenario: Clean commit
- **WHEN** a contributor with hooks installed commits a change that passes every check
- **THEN** the commit succeeds without manual steps

#### Scenario: Leftover merge marker
- **WHEN** a staged file contains a merge conflict marker
- **THEN** the commit is rejected and the offending file is named

#### Scenario: Hooks not installed
- **WHEN** a contributor skips the hooks
- **THEN** the same checks still fail the pull request in CI

### Requirement: One definition of every check
Each check SHALL have a single definition used by the commit hook, the test suite and CI. A rule changed in one place SHALL take effect in all three.

#### Scenario: Guard rule tightened
- **WHEN** a forbidden pattern is added to the guard definition
- **THEN** the hook, `uv run pytest` and CI all reject a file containing it

### Requirement: Private-data guard
A guard SHALL fail when a tracked file contains a personal absolute path, a Steam account identifier, a tracked database or snapshot file, or an e-mail address other than the declared project author. Documented placeholder paths and the declared author SHALL be allowed explicitly.

#### Scenario: Personal path committed
- **WHEN** a tracked file contains a path under a real user's home directory
- **THEN** the guard fails and prints the file and line

#### Scenario: Placeholder path
- **WHEN** documentation uses `/Users/username/...` or `ACCOUNT_ID` as a placeholder
- **THEN** the guard accepts it

#### Scenario: Snapshot file staged
- **WHEN** a `tf3c_snap_*.lua` file or a `.db` file is tracked
- **THEN** the guard fails

### Requirement: Language guard
A guard SHALL fail when tracked files contain Portuguese text outside an explicit allowlist of legitimate occurrences, including documented examples of localized game names.

#### Scenario: Portuguese string in source
- **WHEN** a Python source file contains a Portuguese sentence or accented Portuguese word
- **THEN** the guard fails and prints the file and line

#### Scenario: Allowlisted example
- **WHEN** the methodology guide shows a localized cargo name as an example of why keys are preferred
- **THEN** the guard accepts it

### Requirement: Lua syntax gate
Every tracked Lua file SHALL be checked with `luac -p` in the commit hook and in CI, and no other parser SHALL stand in for it. The gate SHALL fail, not skip, when `luac` is unavailable and SHALL name how to install it. The gate SHALL be documented as a syntax proof only, never as evidence of game behaviour, and live-game acceptance SHALL remain a separate gate.

#### Scenario: Broken Lua
- **WHEN** a mod Lua file has a syntax error
- **THEN** the hook and the CI job fail naming the file

#### Scenario: luac missing
- **WHEN** the gate runs on a machine without `luac`
- **THEN** it fails with the install instruction instead of passing silently

#### Scenario: Passing gate
- **WHEN** every Lua file passes `luac -p`
- **THEN** no documentation or release note claims the mod works in the game on that basis

### Requirement: Lint and format
The repository SHALL define one lint and format configuration for Python source and tests. CI SHALL fail when either check reports a finding, and the checks SHALL not change program behaviour.

#### Scenario: Unformatted file
- **WHEN** a pull request adds an unformatted Python file
- **THEN** the lint job fails

### Requirement: Continuous integration matrix
CI SHALL run on Linux, macOS and Windows for every push to the default branch and every pull request. It SHALL run the locked test suite, the installed-wheel acceptance test, a wheel and sdist build, the Lua syntax gate and strict OpenSpec validation. Workflows SHALL declare least-privilege permissions, SHALL pin third-party actions to reviewed versions and SHALL cancel superseded runs of the same ref.

#### Scenario: Pull request from a fork
- **WHEN** a fork opens a pull request
- **THEN** CI runs with read-only repository permissions and no secrets

#### Scenario: Platform-specific failure
- **WHEN** a test passes on Linux and fails on Windows
- **THEN** the run reports the failing platform and the other platforms still complete

#### Scenario: Superseded push
- **WHEN** a new commit is pushed to a branch with a run in progress
- **THEN** the older run is cancelled

### Requirement: Supply-chain automation
The repository SHALL enable automated dependency update proposals for GitHub Actions and Python dependencies, a dependency review on pull requests and static security analysis of the Python source.

#### Scenario: Vulnerable dependency added
- **WHEN** a pull request adds a dependency with a known advisory
- **THEN** the dependency review reports it on the pull request

### Requirement: Draft release assembly without publication
A tag-triggered workflow SHALL build the wheel, the sdist and the bridge-mod archive from the tagged commit and attach them to a draft release. It SHALL NOT publish to a package index or the in-game mod hub, and SHALL fail when the tag does not match the single-sourced package version.

#### Scenario: Matching tag
- **WHEN** tag `v0.1.0` is pushed and the package version is `0.1.0`
- **THEN** a draft release is created with three attached artifacts

#### Scenario: Mismatched tag
- **WHEN** the tag version differs from the package version
- **THEN** the workflow fails before any artifact is attached

### Requirement: Hosted evidence is not claimed early
Documentation SHALL NOT show a CI badge, a passing-build statement or a published-package link before the corresponding hosted run or publication exists.

#### Scenario: Before first hosted run
- **WHEN** no hosted CI run has completed
- **THEN** the README and changelog do not claim a passing build
