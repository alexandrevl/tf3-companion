# Contributing to TF3 Companion

Thank you for contributing to TF3 Companion. This project is an unofficial, local-first, read-only data analyst for Transport Fever 3.

## Principles

1. **Read-only:** Never execute gameplay commands, purchase vehicles, or alter simulation state.
2. **Local-first:** No telemetry, cloud databases, or background network requests. All analyses remain on the user's machine.
3. **Evidence over assumption:** Every finding, recommendation, and report must be tied to verified observations and explicitly cite game mechanics.
4. **Clean language separation:** Write everything in English: code, identifiers, file and folder names, comments, docstrings, string literals, tests, scripts, docs, commit messages and OpenSpec artifacts. This includes gitignored locations such as `data/` and `scripts/`. Agents may converse with players in their preferred language via MCP instructions, but that never reaches files or commits. See [AGENTS.md](AGENTS.md).
5. **Privacy in testing:** Never commit real player snapshots, personal computer paths, save names, or Steam IDs to the repository.

---

## Local development setup

Install [uv](https://docs.astral.sh/uv/) and ensure Python 3.12+ is installed.

```sh
# Clone and prepare locked environment
git clone https://github.com/alexandrevl/tf3-companion.git
cd tf3-companion
uv sync --locked

# Run test suite (includes the installed-wheel acceptance test)
uv run pytest

# Verify CLI commands
uv run tf3c --help
uv run tf3c doctor
uv run tf3c knowledge
```

Use `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` during testing to isolate tests from your actual game data.

`tests/test_installed_analysis.py` (marked `slow`) builds the wheel into a temporary directory, installs it offline into a clean temporary environment and runs the installed service, `tf3c evaluate`, the MCP `evaluate` tool, all seven analysis views, report composition/publication and `tf3c analyse` from outside the checkout with synthetic evidence. It needs `uv` and uv's local cache to already hold the build backend and dependency wheels (run `uv sync --locked` once with network access, then install the built wheel once into a scratch environment so the registry metadata is cached); when they are missing it fails naming that prerequisite and never reaches a package index.

### Install the Lua checker

The Lua check is `luac -p`: syntax only, never evidence that the mod works in the game. It **fails instead of skipping** when `luac` is missing, so install it before running the checks:

| Platform | Command |
| --- | --- |
| Linux | `sudo apt-get install lua5.4` |
| macOS | `brew install lua@5.4`, then `export PATH="$(brew --prefix lua@5.4)/bin:$PATH"` (the formula is keg-only) |
| Windows | `choco install lua` |

If the binary has an unusual name or location, set the `LUAC` environment variable to it.

### Checks and the commit hook

Every check has one definition and runs in three places: the commit hook, `uv run pytest` and CI.

```sh
uv run pre-commit install             # once per clone: runs the fast checks before every commit
uv run pre-commit run --all-files     # the same checks over the whole tree, without committing
uv run python scripts/check_repo.py   # private data, Portuguese text, required files, links, `luac -p` on Lua
uv run ruff check . && uv run ruff format --check .
uv run pytest                         # everything, including the slow installed-wheel tests
```

| Where | What runs |
| --- | --- |
| Commit hook (fast) | whitespace, end-of-file, merge-marker, large-file, YAML/JSON/TOML checks; `ruff check`; `ruff format`; `scripts/check_repo.py` (includes `luac -p`); `pytest -m "not slow"` |
| CI (full, Linux, macOS and Windows) | all of the above plus the slow installed-wheel tests, the wheel and sdist build, strict OpenSpec validation, CodeQL and dependency review |

Skipping the hook (`git commit --no-verify`) does not skip a check: the same checks fail the pull request. `.git-blame-ignore-revs` lists the mechanical formatting commit; run `git config blame.ignoreRevsFile .git-blame-ignore-revs` to make local `git blame` skip it (GitHub applies it automatically).

---

## Project structure

```text
src/tf3companion/
  paths.py         # OS paths, Steam discovery, configuration
  luadata.py       # Robust parser for game Lua snapshot tables
  snapshot.py      # Typed snapshot domain models
  store.py         # SQLite schema, ingestion receipts, decision store
  analysis.py      # Rule engine: findings, opportunities, insights
  evaluation.py    # Structured, read-only evaluation result over stored evidence
  analysis_views/  # Seven optional structured analyses of stored history
  methodology/     # Declarative policies, library, validation, packaged examples
  export.py        # XLSX workbook generation
  reports.py       # Report composition; Markdown and self-contained offline HTML rendering
  report_*.py      # Thin per-family report builders over structured analyses
  service.py       # Core application service (Companion): evaluate, analyse, report
  cli.py           # Command line interface (tf3c)
  mcp_server.py    # MCP stdio server: tools, prompts, resources
  knowledge/       # Shipped markdown knowledge base topics
mod/
  tf3_companion_bridge/  # Read-only Lua bridge mod
docs/              # Markdown guides and reference
openspec/          # Specification changes and architectural tasks
tests/             # Unit and integration test suites, including the installed-wheel acceptance test
```

The responsibility split (evidence, analysis, presentation, interfaces) is described in [docs/architecture.md](docs/architecture.md): a new calculation lives in the analysis layer and returns structured data, reports present it, and the CLI and MCP server add no logic. Acceptance tests are behavioural and independent of the retired author-local analysis scripts; never reintroduce a private generator or a dependency on a checkout's `data/` folder.

Branding (colours, typography, logo, voice, generated art) follows [docs/brand/identity.md](docs/brand/identity.md); colours and typefaces come only from `assets/brand/tokens.json`.

---

## Making changes: OpenSpec workflow

We manage changes through structured specifications under `openspec/changes/<change-name>/`:

1. Identify or propose a change folder containing `proposal.md`, `design.md`, `specs/`, and `tasks.md`.
2. Keep edits focused on the designated change scope.
3. Update task acceptance criteria only after genuine verification.
4. Add behavioral regression tests. Do not assert on volatile text wording, doc phrasing, or mocked tool lists.

### Work tracking and delivery

`TODO.md` is the project board, not a second implementation checklist. Its lanes are **In progress**, **Next**, **Blocked**, **Backlog** and **Done**. Order in **Next** is execution priority; do not silently replace that order with an easier task.

1. **Start:** read the board and relevant OpenSpec artifacts. Select one workstream, put its card in **In progress**, and state its scope. One session owns the worktree; delegated agents get disjoint file ownership and return to that integration owner.
2. **Plan:** behavioral changes use an OpenSpec proposal/design/specs/tasks. A board card links to that change; do not copy all task checkboxes into the board. Small documentation and housekeeping fixes can stay as cards.
3. **Implement:** follow the selected scope. Add newly discovered work as separate cards. Update implementation task checks only after their actual acceptance has passed.
4. **Verify:** exercise the changed behavior and run `uv run pytest` for Python work. For OpenSpec, validate the change strictly. Lua syntax and synthetic tests never close real-game/platform gates. Keep exact verification evidence and its limitations.
5. **Finish:** update existing docs/changelog, sync/archive fully verified changes, move the board card to **Done**, and commit the completed coherent work when authorized. Unfinished manual gates stay in **Blocked** with the required evidence, even when the source portion is committed.
6. **Handoff:** leave the next action and any interruption in the board. Do not leave advertised half-built interfaces, mark work done because an agent stopped, or start another feature to avoid finishing the current one.

Use the current source and fresh commands to reconcile the board. Historical task counts and old test totals are records, not proof of the current state. Do not call an item fixed based only on a checked box or a plausible implementation. Publishing, pushing, installing the bridge and interacting with live player data remain separate explicit decisions.


---

## Mod test harness and Lua boundaries

The bridge mod under `mod/tf3_companion_bridge/` is read-only.

- Any Lua test harness or stub proves file formatting and syntactical structure (`luac -p`), not game API runtime behavior or script persistence.
- Do not add gameplay command calls (`api.cmd`) or write outside the designated `towns_industries` userdata sink.
- Live mod installation, game activation, and snapshot extraction require real in-game player verification on target platforms.

---

## Release checklist (manual gates)

Releasing a new version involves human verification gates:

- [ ] Version bumped in `pyproject.toml` and in the matching source-checkout fallback in `src/tf3companion/__init__.py`; `CHANGELOG.md` has a section for it.
- [ ] Compatibility matrix updated in `README.md` and `docs/ROADMAP.md`.
- [ ] No personal player data, paths, or unapproved screenshot placeholders in repository (`uv run python scripts/check_repo.py`).
- [ ] CI suite passing on Windows, macOS, and Linux runners (lint, guards, OpenSpec validation, `uv sync --locked`, `uv run pytest` including the slow installed-wheel tests).
- [ ] Clean package build verified: `uv build`.
- [ ] Mod bundle verified in clean staging directory.
- [ ] In-game activation and refresh verified on live game builds.
- [ ] Tag git commit: `git tag vX.Y.Z`.
- [ ] Publish step executed manually by maintainer.
