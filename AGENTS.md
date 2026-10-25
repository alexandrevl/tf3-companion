# Contributor Instructions

Conventions for every agent and human working in this repository. Details live in [CONTRIBUTING.md](CONTRIBUTING.md) and `openspec/config.yaml`; this file does not duplicate them. `CLAUDE.md` is a symlink to this file.

## Language

Everything written to disk or to history MUST be in English, without exception:

- code, identifiers, file and folder names, comments, docstrings and string literals in source;
- tests, scripts, docs and OpenSpec artifacts;
- commit messages.

The rule also applies to gitignored locations such as `data/` and `scripts/`; do not create author-local files with non-English names, comments or strings. Refer to game concepts (vehicles, cargo, industries) by their English domain terms, never by localized literals.

Conversation with the player MAY use the player's language. That never extends to files or commits: a Portuguese-speaking player gets Portuguese replies, and English files and commit messages.

Localizing player-facing output is out of scope here: it is neither required nor forbidden, and a future change must design it (for example a message catalog). Until then, source contains no localized literals.

Review changed paths and content for language compliance before delivery, including gitignored scripts. The guard command under Verification enforces the rule on tracked files; it is a review aid, not proof: accented characters can be valid proper names, and English-only ASCII can still contain non-English words.

## Product boundary

- Read-only: never execute gameplay commands (`api.cmd`) or alter the simulation.
- Local-first: no telemetry, no background network requests; player data stays on the player's disk.
- Never commit real player snapshots, personal paths, save names or Steam IDs.
- Never copy Urban Games source code verbatim; paraphrase and cite file paths.

## Verification

- Run `uv run pytest` for the Python package.
- Run `uv run python scripts/check_repo.py` for the repository guards (private data, Portuguese text, required public files, link identity). It reads tracked files and also runs `luac -p` on every tracked Lua file; the commit hook and CI run the same command.
- Lua is checked with `luac -p` only; that proves syntax, not game behaviour. Install `luac` first (see CONTRIBUTING.md); the check fails rather than skipping when it is missing.
- Mod behaviour can only be verified in the game by the player; plan an in-game step for any mod change.
- Add behavioural regression tests; do not assert on volatile wording.

## OpenSpec planning

- Changes live under `openspec/changes/<name>/` with `proposal.md`, `design.md`, `specs/` and `tasks.md`.
- Proposals state what is out of scope.
- The final task of every change names the exact command or in-game check that verifies it.
- Check task boxes only after genuine verification.

## Work tracking and session ownership

- Read `TODO.md` before starting work. It is the single ordered project board; OpenSpec task files own implementation acceptance details.
- Keep one active workstream per worktree. One session owns integration and commits; parallel agents must have disjoint file ownership and must not run competing verification or archive operations.
- Before changing code, move the selected card to **In progress** and link its OpenSpec change. Newly discovered work goes on the board, not into an unrelated implementation.
- Completion requires exercised acceptance, updated documentation and a truthful board entry. Move verified work to **Done** with its evidence; incomplete live-game or platform gates stay blocked.
- Commit completed, verified work in coherent units when authorized. Do not let multiple completed changes accumulate uncommitted. Commit is not permission to push, publish or install.
- At handoff, record unfinished work, the next action and blockers in `TODO.md`. Ending a session never makes its open tasks complete.
- Follow the detailed lifecycle in [CONTRIBUTING.md](CONTRIBUTING.md#work-tracking-and-delivery).

Player-facing analyst instructions are packaged in `src/tf3companion/agent_instructions.md`; they are not the contributor role.
