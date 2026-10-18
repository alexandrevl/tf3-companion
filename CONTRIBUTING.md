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
git clone <repo-url>
cd tf3-companion
uv sync --locked

# Run test suite
uv run pytest

# Verify CLI commands
uv run tf3c --help
uv run tf3c doctor
uv run tf3c knowledge
```

Use `TF3C_DATA_DIR` and `TF3C_USERDATA_DIR` during testing to isolate tests from your actual game data.

---

## Project structure

```text
src/tf3companion/
  paths.py         # OS paths, Steam discovery, configuration
  luadata.py       # Robust parser for game Lua snapshot tables
  snapshot.py      # Typed snapshot domain models
  store.py         # SQLite schema, ingestion receipts, decision store
  analysis.py      # Rule engine: findings, opportunities, insights
  export.py        # XLSX workbook generation
  reports.py       # Markdown and self-contained offline HTML reports
  service.py       # Core application service (Companion)
  cli.py           # Command line interface (tf3c)
  mcp_server.py    # MCP stdio server: tools, prompts, resources
  knowledge/       # Shipped markdown knowledge base topics
mod/
  tf3_companion_bridge/  # Read-only Lua bridge mod
docs/              # Markdown guides and reference
openspec/          # Specification changes and architectural tasks
tests/             # Unit and integration test suites
```

Branding (colours, typography, logo, voice, generated art) follows [docs/brand/identity.md](docs/brand/identity.md); colours and typefaces come only from `assets/brand/tokens.json`.

---

## Making changes: OpenSpec workflow

We manage changes through structured specifications under `openspec/changes/<change-name>/`:

1. Identify or propose a change folder containing `proposal.md`, `design.md`, `specs/`, and `tasks.md`.
2. Keep edits focused on the designated change scope.
3. Update task acceptance criteria only after genuine verification.
4. Add behavioral regression tests. Do not assert on volatile text wording, doc phrasing, or mocked tool lists.

---

## Mod test harness and Lua boundaries

The bridge mod under `mod/tf3_companion_bridge/` is read-only.

- Any Lua test harness or stub proves file formatting and syntactical structure (`luac -p`), not game API runtime behavior or script persistence.
- Do not add gameplay command calls (`api.cmd`) or write outside the designated `towns_industries` userdata sink.
- Live mod installation, game activation, and snapshot extraction require real in-game player verification on target platforms.

---

## Release checklist (manual gates)

Releasing a new version involves human verification gates:

- [ ] Single version updated in `src/tf3companion/__init__.py`.
- [ ] Compatibility matrix updated in `README.md` and `docs/ROADMAP.md`.
- [ ] No personal player data, paths, or unapproved screenshot placeholders in repository.
- [ ] CI suite passing on Windows, macOS, and Linux runners (`uv sync --locked`, `uv run pytest`).
- [ ] Clean package build verified: `uv build`.
- [ ] Mod bundle verified in clean staging directory.
- [ ] In-game activation and refresh verified on live game builds.
- [ ] Tag git commit: `git tag vX.Y.Z`.
- [ ] Publish step executed manually by maintainer.
