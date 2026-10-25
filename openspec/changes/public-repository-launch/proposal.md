# Proposal

## Why

The repository has no remote and has never run its CI. Before the first public push, strangers will read it, clone it, connect its MCP server to their agents and send issues. A 2026-10-25 review of the tree found no leaked personal data, a clean worktree, 930 passing tests (13 installed-wheel errors that only need a warm uv cache) and valid OpenSpec specs. The review also found launch blockers: two known P1 defects that public users hit first, missing legal and community files, issue-template links that point at the wrong repository, a CI that never checks Lua or lint and has no automated privacy or language guard, and no commit-time gate. Publishing before these are fixed would make the first impression a broken MCP tool and a pending licence question.

## What Changes

- **Fix the two launch-blocking P1 defects** from `TODO.md`:
  - MCP non-evaluate tools share one cached, writable `Companion` and SQLite connection across threads. Repeated tool calls must work, as `evaluate` already does with per-call read-only connections.
  - `line_detail` returns zero-capacity entries and resolves the line's one-based cargo index as a cargo id (P-010/P-011).
- **Public legal and community files**: a `NOTICE` crediting MPFever (MIT, commit `ae5fc96`) for the adopted knowledge, a `SECURITY.md`, a `CODE_OF_CONDUCT.md`, a `.github/CODEOWNERS`, and a README "Third-party" and "Reporting security issues" section.
- **Repository identity**: choose and apply the final GitHub repository name consistently in issue-template links, `pyproject.toml` `[project.urls]`, README and docs.
- **Commit-time gate**: a `pre-commit` configuration (the Python-ecosystem equivalent of Husky, which is Node tooling) with fast local hooks: whitespace and merge-marker hygiene, large-file guard, Lua syntax check, English-only check, forbidden-content check, ruff lint and format check, and a quick pytest subset. Document `uv run pre-commit install`.
- **Quality tooling**: add `ruff` configuration and fix its findings without changing behaviour, so CI and the hook run the same checks.
- **Repository guard tests** that run in `uv run pytest` and in CI: no personal paths, Steam account ids, e-mail addresses beyond the declared author, local database or snapshot files in tracked files; no Portuguese text; every tracked Lua file passes a syntax check; required public files exist.
- **GitHub Actions**:
  - Harden `ci.yml`: pinned action versions, least-privilege `permissions`, concurrency cancellation, lint job, Lua syntax job, OpenSpec validation job, wheel build and installed-wheel acceptance on all three operating systems.
  - Add `codeql.yml` (Python), `dependency-review.yml`, `dependabot.yml` (GitHub Actions and uv) and a tag-triggered `release.yml` that builds the wheel, sdist and bridge-mod zip and attaches them to a **draft** release without publishing to PyPI or mod.io.
- **Release hygiene**: single-sourced version check, `CHANGELOG.md` section for the first public version, README compatibility table and CI badge only after a hosted run exists, `CONTRIBUTING.md` and `AGENTS.md` updates for hooks and checks, and a fresh `TODO.md` baseline.
- **First-push runbook**: an exact, ordered, user-run checklist (create the repository, push, watch CI, protect `main`, enable security features). This change prepares and verifies everything locally. The push itself stays a separate explicit user action.

Out of scope:

- Pushing, creating the GitHub repository, tagging, publishing to PyPI, uploading to Mod Hub, or any account action; each remains a manual gate.
- Real-game, Windows and Linux acceptance (`Blocked` lane): live activation, save-identity probing, refresh false negative P-001, depot guard P-002, cover verification and gallery images.
- Collector expansion, ID-reuse audit, hydration coverage, overview labelling, brand application and every other `Next`/`Backlog` card not listed above.
- Rewriting git history. The ten existing commits and their declared author stay as they are; the author confirms identity before the push.
- Reproducing or vendoring any Urban Games or MPFever source.

## Capabilities

### New Capabilities

- `repository-quality-gates`: the automated checks that every commit and every pull request must pass (hooks, lint, guard tests, CI jobs, supply-chain automation, draft release assembly).
- `public-project-governance`: the legal, security, community and identity files a public repository must carry and keep consistent.
- `mcp-server-runtime`: how MCP tools obtain stored evidence so repeated and concurrent tool calls are safe.
- `line-inspection`: what `line_detail` reports about a line's cargo capacity and issues.

### Modified Capabilities

- `contributor-conventions`: the verifiable-absence requirement becomes an automated, enforced check (hook and CI), and contributors are told how to install the hooks.

## Impact

- Code: `src/tf3companion/mcp_server.py`, `src/tf3companion/service.py` (line detail), `src/tf3companion/store.py` only if the read-only connection API needs a small extension; lint-driven mechanical edits across `src/` and `tests/`.
- New files: `.pre-commit-config.yaml`, `NOTICE`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/workflows/{codeql,dependency-review,release}.yml`, `scripts/check_repo.py` (hook entry shared with guard tests), `docs/first-push.md`, new tests.
- Changed: `pyproject.toml` (ruff, pre-commit, URLs, classifiers), `.github/workflows/ci.yml`, issue-template config, `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CHANGELOG.md`, `TODO.md`, `docs/ROADMAP.md`.
- Dependencies: dev-only additions (`ruff`, `pre-commit`). Runtime dependencies are unchanged.
- Overlap: supersedes the repository, CI and community parts of `release-readiness`; its remaining tasks are re-baselined rather than duplicated (see design).
- Bridge mod: no Lua behaviour change, so no in-game step is required by this change. Only a syntax gate is added.
