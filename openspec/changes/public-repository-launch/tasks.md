# Tasks

## 1. Board and baseline

- [x] 1.1 Move the `TODO.md` card for this change to **In progress** with a link to `openspec/changes/public-repository-launch/`; verify the board shows exactly one active workstream.
- [x] 1.2 Warm the uv cache with network access (`uv sync --locked`) and record the full baseline with `uv run pytest -q`; verify the 13 `test_installed_analysis.py` errors become passes and note the exact totals as the new baseline in `TODO.md`. If no network is available, leave this task open and record the missing prerequisite.

## 2. MCP tool lifecycle (P1)

- [x] 2.1 Reproduce the thread-affinity failure first: add a test that builds an isolated synthetic store and calls each non-evaluate read tool repeatedly from different worker threads; verify it fails on the current code with a thread-affinity error and never touches player data.
- [x] 2.2 Replace the module-level cached `Companion` in `src/tf3companion/mcp_server.py` with a short-lived writable `Companion` per call under one process-wide lock for every tool that goes through an ingesting `Companion` method, keep `evaluate` and the other stored-only tools without writes (design D4); remove the cache outright. Verify the test from 2.1 passes for twenty sequential and concurrent calls.
- [x] 2.3 Add behavioural tests that stored-only tools never create files, never ingest pending snapshots and succeed on a read-only store, that every connection is closed after success and after failure, that overlapping `record_decision` calls store each decision once, that overlapping ingesting tools ingest a pending snapshot once, and that an empty store yields an actionable tool error; verify with `uv run pytest tests -k mcp`.
- [x] 2.4 Add the package `version` to MCP and CLI `status`, document "restart the server after upgrading" in `docs/agents.md` and `docs/troubleshooting.md`, and add a test asserting `status` reports the single-sourced version; verify with `uv run tf3c status` against an isolated `TF3C_DATA_DIR` and the new test.
- [x] 2.5 Measure the per-call cost on the synthetic store; verify typical read-tool latency stays interactive and, if constructing `Companion` per call does avoidable discovery work, split a cheap read-only constructor instead of caching.

## 3. Line detail capacity (P1)

- [x] 3.1 Add synthetic fixtures reproducing P-010/P-011 (thirty-seven capacity entries, one positive, one-based indices) and failing tests for the CLI `tf3c line` and MCP `line_detail` outputs; verify the tests fail on the current code for wrong names and zero entries.
- [x] 3.2 Move the cargo-offset convention and the positive-capacity filter into one shared place used by `service.py` and `analysis_views/towns.py`; remove the duplicate constant. Verify the new tests and the existing towns-view tests pass.
- [x] 3.3 Render unresolvable issue cargo as an explicit unknown marker and add its test; verify no wrong name appears for an index absent from the cargo table.
- [x] 3.4 Update `knowledge/snapshot_schema.md` only where it differs from delivered behaviour, mark P-010 and P-011 resolved in the board with the test names as evidence, and verify with `uv run pytest -q`.

## 4. Lint and format tooling

- [x] 4.1 Add `ruff` and `pre-commit` to the dev dependency group, add the conservative rule set and format settings to `pyproject.toml`, refresh `uv.lock`; verify `uv sync --locked` succeeds and `uv run ruff --version` runs.
- [x] 4.2 Fix lint findings without behaviour change, using local, justified suppressions only where a fix would alter behaviour; verify `uv run ruff check .` exits 0 and the full suite result matches the 1.2 baseline.
- [x] 4.3 Apply `ruff format` as one isolated mechanical commit with no logic edits and record it in a `.git-blame-ignore-revs` entry once the commit exists; verify `uv run ruff format --check .` exits 0 and the full suite and `uv run tf3c --help`, `uv run tf3c knowledge` still behave identically.
- [x] 4.4 Mark the installed-wheel acceptance tests with a `slow` marker registered in `pyproject.toml`; verify `uv run pytest -m "not slow"` skips only those tests and a plain `uv run pytest` still runs them.

## 5. Repository guards

- [x] 5.1 Write `scripts/check_repo.py` (standard library only) with the private-data guard, language guard, required-public-files check and link-identity check reading `git ls-files`, with commented allowlists; verify `uv run python scripts/check_repo.py` exits 0 on the clean tree and prints file, line and rule on a seeded violation.
- [x] 5.2 Write `tests/test_repo_guards.py` against temporary git repositories seeding each violation class (personal path, Steam id, tracked `.db`, tracked `tf3c_snap_*.lua`, foreign e-mail, Portuguese string, missing required file) and each allowed placeholder; verify each seeded violation fails and each placeholder passes with `uv run pytest tests/test_repo_guards.py`.
- [x] 5.3 Ask the maintainer for approval to install `luac` on this machine (for example `brew install lua`), install it, and record the exact command and `luac -v` output; verify `luac -p` passes on both files under `mod/tf3_companion_bridge/content/tf3_companion/`. If approval is not given, leave this task, 5.4 and 6.1 open and record the missing prerequisite.
- [x] 5.4 Add the Lua gate to `scripts/check_repo.py` running `luac -p` (names `luac`, `luac5.4`) over every tracked `.lua` file, failing with a per-platform install message when no binary exists and with no fallback parser, and add tests using a deliberately broken temporary Lua file and a simulated missing binary; verify the broken file fails naming the file, the missing binary fails rather than skips, and both mod files pass.
- [x] 5.5 Replace the grep command in the archived English-only requirement's documentation with the guard command in `CONTRIBUTING.md` and `AGENTS.md`; verify the documented command runs as written from the repository root.

## 6. Commit-time hooks

- [x] 6.1 Write `.pre-commit-config.yaml` with hygiene hooks (trailing whitespace, end of file, merge conflict markers, large files, YAML/JSON/TOML syntax), ruff check and format, the repo guards, the `luac -p` Lua gate and `pytest -m "not slow"` using `language: system` entries through `uv run`; verify `uv run pre-commit run --all-files` exits 0.
- [x] 6.2 Prove the gate by staging a throwaway violation in a temporary clone (a merge marker, then a personal path), installing the hook there with `uv run pre-commit install`, and attempting a commit; verify each commit is rejected naming the file, and that the clean commit is accepted.
- [x] 6.3 Document hook installation, the `luac` prerequisite with per-platform install commands, and the fast-versus-full check split in `CONTRIBUTING.md` (setup section and release checklist), explain that CI repeats every check, and keep `AGENTS.md`'s "syntax only" boundary; verify each documented command runs as written.

## 7. Public governance files and identity

- [x] 7.1 Confirm the repository name `alexandrevl/tf3-companion`, the security channel and the conduct contact with the maintainer, then record them as the single identity list in `docs/first-push.md`; verify the list names every file that carries a URL.
- [x] 7.2 Add `NOTICE` crediting MPFever (MIT, commit `ae5fc96`) and the derived topics with the paraphrase statement, and link it from README; verify by reading `NOTICE` and by the guard's required-files check. Confirm `knowledge/engine.md` file-and-line citations are references, not copied source.
- [x] 7.3 Add `SECURITY.md`, `CODE_OF_CONDUCT.md` and `.github/CODEOWNERS`; verify the files exist, contain the stated channel and boundary, and `CODEOWNERS` covers `.github/workflows/`, `mod/` and release files.
- [x] 7.4 Apply the repository identity to `.github/ISSUE_TEMPLATE/config.yml`, `pyproject.toml` `[project.urls]` and classifiers, the README, docs and the bridge `modinfo.json` `url`; verify the guard's link-identity check passes and the built wheel metadata (`uv build` then reading `METADATA`) shows the Homepage, Repository and Issues URLs.
- [x] 7.5 Update the README: unofficial statement, third-party and security sections, quickstart checked line by line, no badges or published-package links yet; verify every command in the README runs against an isolated `TF3C_DATA_DIR`.

## 8. GitHub Actions

- [x] 8.1 Rewrite `.github/workflows/ci.yml` with `lint`, `guards`, `openspec` jobs and the OS-matrix `test` job (locked tests, installed-wheel acceptance, wheel and sdist build, setup-guide smoke, per-OS `luac` installation followed by the `luac -p` gate), `permissions: contents: read`, concurrency cancellation and SHA-pinned actions; verify with `actionlint` (or `uvx actionlint-py`), a YAML parse, and that the installation step provides `luac` on each runner (confirmed on the first hosted run; until then the step is reviewed against each runner's package manager and the claim is not made).
- [x] 8.2 Add `codeql.yml` (Python), `dependency-review.yml` and `.github/dependabot.yml` for `github-actions` and `uv`; verify each file passes `actionlint` and the schema check.
- [x] 8.3 Add `release.yml` (tag-triggered, version-equals-tag check, wheel, sdist, bridge-mod zip, draft release, no publish step); verify with `actionlint` and by running its build and version-check script steps locally against a matching and a mismatching tag value.
- [x] 8.4 Resolve action SHAs and record the pinned versions in `docs/first-push.md`; verify each pinned SHA corresponds to the commented version. If network access is unavailable, leave this task open and record the missing prerequisite.
- [x] 8.5 Static Windows review: search tests and source for path-separator, newline and shell assumptions that the Windows runner will exercise (`os.sep`, hard-coded `/`, `chmod`, `symlink`, `rm -rf`) and fix or mark each with a justified skip; verify with `uv run pytest -q` and a written list of reviewed call sites in the task note.
  - Reviewed 2026-10-25: source uses `os.replace`, `O_EXCL` lock files and `is_junction` already; the only call without an explicit encoding was `tests/test_evaluation.py` (HTML report read), now UTF-8; `.gitattributes` forces LF checkouts (the Windows runner defaults to CRLF); `tests/test_setup.py` symlink tests rely on the hosted runner's administrator token; `tests/test_evaluation.py` and `tests/test_mcp_runtime.py` use `chmod`, whose Windows effect is only the read-only attribute and which restore their state in `finally`; `os.sep` appears only in `methodology/library.py` path detection; the one `/tmp` is a string inside a Lua-sandbox test; no `rm -rf`, `fork`, `fcntl` or `signal` use. Not proven until the first Windows run.

## 9. Documentation, release hygiene and board

- [ ] 9.1 Write `docs/first-push.md`: the ordered private-first runbook (confirm identity, create the repository private, push with `git push -u origin main`, watch the three-platform CI run, enable branch protection, private vulnerability reporting, secret scanning and Dependabot, switch visibility to public, optional tag), each step with its evidence; verify every command in it runs or is marked as user-run.
- [ ] 9.2 Add a `CHANGELOG.md` section for the first public version with the fixes, tooling and governance files, and keep the compatibility table's "not verified" statuses; verify the version in the section equals `src/tf3companion/__init__.py`.
- [ ] 9.3 Update `AGENTS.md`, `CONTRIBUTING.md`, `docs/ROADMAP.md` and `ROADMAP.md` for hooks, guards and the launch status, consistently with `openspec/config.yaml`; verify the guard's language check passes and links resolve.
- [ ] 9.4 Re-baseline `release-readiness` against delivered work: mark covered tasks superseded with a pointer to this change, leave unexercised release gates unchecked, and update the `TODO.md` card; verify `openspec validate release-readiness --strict` passes.
- [ ] 9.5 Update `TODO.md`: move the fixed MCP and `line_detail` cards to **Done** with the test names as evidence, add the first-push runbook as a user-owned **Blocked** card, and refresh the dated baseline; verify the board has no checked box outside **Done**.

## 10. Final verification and handoff

- [ ] 10.1 Run the full local gate: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python scripts/check_repo.py`, `uv run pre-commit run --all-files`, `uv build`, `openspec validate --all --strict`; verify every command exits 0 and record the totals.
- [ ] 10.2 Exercise the installed product from the built wheel in a clean temporary environment: `tf3c --version`, `tf3c doctor`, `tf3c evaluate --json` with synthetic evidence, and the MCP server answering `status`, `list_lines` and `line_detail` over stdio; verify the outputs and that no real player data is read.
- [ ] 10.3 Run a final privacy sweep over tracked files and over the full git history for personal paths, Steam ids, snapshot files and databases; verify no matches beyond the allowlist.
- [ ] 10.4 Review changed paths for language compliance, including gitignored scripts, and for AGENTS.md product-boundary compliance; verify with `uv run python scripts/check_repo.py` and a written review note.
- [ ] 10.5 Commit the verified work in coherent units when authorized, archive this change with `openspec archive public-repository-launch` after sync, and hand off with the user-run steps from `docs/first-push.md`; verify `git status` is clean and `git log` shows the coherent commits. Do not push.
