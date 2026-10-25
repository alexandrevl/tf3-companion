# Design

## Context

See `proposal.md` for motivation and scope. Observed state on 2026-10-25:

- Clean worktree, ten local commits, no remote, no git hooks installed, no `ruff`, `pre-commit` or `gh` on the machine. `luajit` exists (`/opt/homebrew/bin/luajit`); `luac` does not. `lupa` is already a locked dev dependency.
- `uv run pytest`: 930 passed, 13 errors. All errors are `tests/test_installed_analysis.py` failing its documented offline prerequisite (uv cache lacks `openpyxl`/`hatchling`), not product failures.
- `mcp_server.py` caches one module-level `Companion()` (lines 19-26) used by every non-evaluate tool. `store.py:101` opens a writable `sqlite3.connect(path)` without `check_same_thread=False`. `evaluate` already uses per-call read-only connections (`store.py:99`), and `analyse` already builds a transient `Companion` for save overrides.
- `service.py:195` maps `line.capacity` through `snap.cargo(c["cargo"])` with no offset and no positive-capacity filter. `analysis_views/towns.py:34` already defines `LINE_CAPACITY_CARGO_OFFSET = 1`. `knowledge/snapshot_schema.md` documents that `line.capacity[].cargo` is cargo id plus one.
- `ci.yml` has one matrix job (pytest, `uv build`, setup-guide smoke). It has no `permissions`, no concurrency, no lint, no Lua check, no OpenSpec validation and uses floating major tags.
- The knowledge base adapts MPFever (MIT, commit `ae5fc96`); attribution is in topic legends and `CHANGELOG.md` but not in a root `NOTICE`.
- `release-readiness` (41 tasks, 0 checked) predates most delivered work; `TODO.md` already asks for it to be re-baselined.

## Goals / Non-Goals

**Goals:**

- Every check that guards the public repository is defined once and runs identically in the hook, in `pytest` and in CI.
- Close the two launch-blocking P1 defects with regression tests that fail before and pass after.
- Give strangers the files they expect (licence, notice, security, conduct, owners, runbook) with no claim the evidence cannot support.
- Leave the user with an exact, ordered, low-risk push procedure.

**Non-Goals:**

- No publication, tagging, account or repository creation by this change.
- No behaviour change to the bridge mod; no new Lua features.
- No attempt to make hosted CI "proven" locally: the first hosted run is an evidence gate owned by the user.
- No broad refactor behind the lint pass; findings are fixed mechanically or with a justified, local suppression.

## Decisions

### D1. `pre-commit` framework, not Husky

Husky is Node tooling and would add a runtime and `package.json` to a Python project. `pre-commit` is the Python-ecosystem equivalent, ships through `uv` as a dev dependency, installs a standard git hook and runs the same configuration in CI. Hooks use `language: system` entries calling `uv run ...` so they use the locked environment and need no hook-managed virtualenvs for first-party checks.

Alternatives: a hand-written `.git/hooks/pre-commit` (not versioned, not shared); `lefthook` (extra binary). Rejected.

### D2. One guard module shared by hook, tests and CI

`scripts/check_repo.py` is standard-library only and exposes functions plus a `main()` returning a non-zero exit code. It implements the private-data guard, language guard, required-public-files check and tracked-file inventory, reading `git ls-files` so ignored local files are never judged by the public gates (but `AGENTS.md`'s all-locations rule still applies to authors). `tests/test_repo_guards.py` imports the same functions and exercises them against temporary git repositories with seeded violations. CI and the hook call `uv run python scripts/check_repo.py`. Allowlists live in this module as small, commented tuples; each entry names why it is legitimate (for example the `/Users/username/` placeholder or `Petróleo Bruto` in `docs/methodologies.md`).

Alternatives: separate shell one-liners per surface (drift guaranteed); `detect-secrets` (heavy, generic, does not know Steam ids or the language rule).

### D3. Lua syntax gate is `luac -p`, mandatory

`AGENTS.md` fixes the standing rule: "Lua is checked with `luac -p` only; that proves syntax, not game behaviour." The gate therefore runs `luac -p` on every tracked Lua file, in the commit hook and in CI, with no substitute parser. The checker resolves the binary by the names `luac` and `luac5.4`, and **fails** (never skips, never falls back) when none is found, printing the install command for the platform. Nothing in this design makes `lupa` or `luajit` an accepted syntax checker; `lupa` stays a test-only dependency it already was.

Installing the binary:

- CI installs it per operating system before the gate: `apt-get install lua5.4` on Linux, `brew install lua` on macOS, `choco install lua` on Windows (or a pinned setup action if the package does not ship `luac`; resolved and recorded in the implementation task).
- This machine has no `luac` (`TODO.md` records it; `luajit` is present but is not the rule). Installing it changes the player's computer, so the task asks the maintainer for approval first and records the exact command and version it ran.
- `CONTRIBUTING.md` lists `luac` as a contributor prerequisite for the hook.

The documentation keeps the boundary: syntax proof only. Live-game behaviour acceptance (activation, refresh, snapshot content) stays in the separate in-game gates on the board and is never closed by this check. The Lua version the game embeds is not verified in this repository; the task records which `luac` version was used and leaves the dialect question as an evidence note, not a claim.

Alternatives: `lupa` as the primary parser (contradicts the standing rule, a different engine than `luac`); `luajit -bl` (LuaJIT is Lua 5.1 syntax, not the rule); `luacheck` (a linter, optional later, not a replacement).

### D4. MCP tools open stored evidence per call

Implementation finding (2026-10-25): most non-evaluate tools are not pure reads. Their `Companion` methods start with `current()`, which runs checked ingestion of pending snapshots before answering (`service.py` `_checked_ingest`). Making them read-only would change delivered behaviour (agents would stop seeing newly exported snapshots) and is outside the two bug cards. The classification is therefore by ingestion, not by name:

- Stored-only tools (`evaluate`, `list_methodologies`, `methodology_detail`, `validate_methodology`, `knowledge`, `doctor`) never write; `evaluate` keeps its per-call read-only store.
- Every tool that goes through an ingesting `Companion` method opens a short-lived writable `Companion` inside the call, closes it in `finally`, and runs under one process-wide lock so ingestion and writes never overlap in the process (cross-process safety stays with the store's transactions and the refresh file lock).

Nothing holds a connection across calls, so thread affinity cannot be violated and a stale cached connection cannot outlive an upgraded store. The module-level cache is removed (clean cutover; no compatibility shim). Consequence: a long `refresh` holds the lock for up to its timeout, so other ingesting tools wait; this is documented.

Alternatives: `check_same_thread=False` plus a lock (shared writable connection remains; one slow tool blocks reads, stale WAL/schema risk); a connection pool (unneeded for a local stdio server). Rejected.

`status` gains a `version` field from the single package version source and `docs/agents.md` states "restart the server after upgrading", closing the freshness card without promising hot reload.

To be confirmed while implementing: whether constructing `Companion` per call performs avoidable discovery work (Steam path scans). If it does, split a cheap read-only constructor rather than caching the object.

### D5. Capacity decoding uses one named convention

`line_detail` resolves capacity through the same offset constant already used by the towns view. The constant moves to a shared module (for example `snapshot.py`) imported by both consumers, and the positive-capacity filter lives in the same place, so the CLI and MCP outputs cannot diverge. The line-issue cargo field is decoded by the convention documented for `line.getLineIssues` and unresolved values render as an explicit unknown marker. The regression fixtures are synthetic and encode both the offset and the thirty-seven-entry shape from P-010/P-011.

Alternatives: a per-call-site `+1` (the cause of the bug); rewriting snapshots at ingest (alters evidence, rejected).

### D6. Ruff for lint and format; hook runs the quick subset only

`ruff` is configured in `pyproject.toml` with a conservative rule set (pycodestyle errors, pyflakes, import order, bugbear subset) and `ruff format`. The formatting pass is one mechanical commit verified by the full suite before and after, so reviewers can skip it with blame-ignore. The hook runs ruff on staged files, the guards, the Lua gate and `pytest -m "not slow"`; the installed-wheel acceptance test is marked `slow` and runs in CI. Slow tests are excluded only from the hook, never from CI or from a plain `uv run pytest`.

Alternatives: black plus flake8 plus isort (three tools); enforcing format without a dedicated commit (noisy diffs).

### D7. CI structure

`ci.yml` becomes jobs `lint`, `guards`, `openspec`, and the existing OS-matrix `test` job extended with the installed-wheel acceptance and the Lua gate. Third-party actions are pinned to commit SHAs with a version comment; Dependabot proposes updates. Top-level `permissions: contents: read`, per-job escalation only where needed, `concurrency` with `cancel-in-progress` for non-default refs. `codeql.yml` analyses Python on push, pull request and weekly schedule. `dependency-review.yml` runs on pull requests. `release.yml` triggers on `v*` tags, verifies the tag equals the package version, builds wheel, sdist and a zip of `mod/tf3_companion_bridge`, and creates a **draft** release with `contents: write` limited to that job. There is no PyPI or mod hub step.

Alternatives: floating tags (supply-chain risk, flagged by the review); trusted PyPI publishing now (publication is a separate manual decision).

### D8. Repository identity as a single decision

The assumed repository is `alexandrevl/tf3-companion`, matching the package name and the `git clone <repo-url>; cd tf3-companion` flow in `CONTRIBUTING.md`. The issue-template config today points at `alexandrevl/tf3`. The name is applied from one list in the tasks (config, `pyproject.toml` `[project.urls]`, README, docs, `modinfo.json` `url`) and verified by a link-consistency check inside the guard. If the maintainer prefers another name, only that list changes.

Security reporting uses GitHub private vulnerability reporting; the conduct contact and the security fallback use the author e-mail already published in `pyproject.toml`, so no new personal data is introduced.

### D9. Safe first push: private first, then public

The runbook recommends creating the repository as private, pushing, waiting for the three-platform CI run and fixing what the first hosted run exposes, and only then switching visibility to public. History is unchanged by that sequence. The user can choose to go public immediately; the runbook states the trade-off. Windows has never been exercised by CI or by a real install, so a first-run failure there is plausible.

### D10. `release-readiness` reconciliation

This change owns repository, CI, community and governance work. `release-readiness` keeps only what this change does not cover (asset and listing verification already live in `mod-listing-assets`). Its tasks are re-baselined against delivered code in this change's reconciliation task: covered items are marked superseded with a pointer here, and unexercised gates stay unchecked.

## Risks / Trade-offs

- [First hosted run fails, especially on Windows] → Private-first push (D9); review path and newline handling statically; keep the failing platform visible with `fail-fast: false`.
- [Ruff format churn hides a behavioural change] → Format in an isolated commit; run the full suite and a CLI smoke before and after; no logic edits in that commit.
- [Per-call store open slows MCP tools] → Measure with the synthetic store; SQLite open is milliseconds. If measurable, introduce the cheap read-only constructor (D4), not a cache.
- [Per-call read-only open breaks a tool that implicitly ingests] → Test each tool for "reads never write"; tools that ingest by design are classified as write tools.
- [Guard false positives annoy contributors] → Allowlist entries carry a reason; the guard prints file, line and the rule that fired.
- [Action SHA pins go stale] → Dependabot for GitHub Actions; the review checklist lists pinned versions.
- [Offline machine cannot resolve action SHAs or refresh the uv cache] → Resolving pins and the installed-wheel acceptance need network access; if unavailable the affected task stays open with the missing prerequisite recorded, never marked done.
- [`luac` version differs from the game's embedded Lua] → The gate remains a syntax proof; the version used is recorded and the dialect mismatch is listed as an open evidence item, not hidden.
- [Contributors without `luac` cannot commit] → The hook message names the install command per platform; CI is the backstop and installs the binary itself.
- [Public metadata exposes the author's e-mail and name] → Already in `pyproject.toml` and `modinfo.json` and in all ten commits; the runbook asks the maintainer to confirm before the first push because it cannot be undone afterward.
- [Scope creep into the Next lane] → The proposal lists exactly two bug cards; every other card stays on the board.

## Migration Plan

1. Land code fixes with tests, then lint tooling, guards, hooks, community files, workflows, docs, in that order (each group commits separately when authorized).
2. Run every local check; record the evidence and the limits (no hosted CI, no real game).
3. Hand the user the runbook. The user creates the repository, pushes, watches CI, and sets protections.
4. Rollback before the push is `git reset` of local commits; after the push, a defect is fixed forward on a branch. Removing a public repository is the user's decision.
