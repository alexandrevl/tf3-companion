## Why

Portuguese keeps appearing in work produced for this project: author-local scripts named `gerar.py` and `raio_x.py`, and string literals such as "Ônibus" and "Passageiros intermunicipal". The only English rule today lives in `openspec/config.yaml` `context:`, which agents see only while writing OpenSpec artifacts. The root `AGENTS.md` (294 bytes) says only "Follow AGENTS.md", so it points to itself and states no conventions. `CLAUDE.md` is a symlink to `AGENTS.md`, so it has the same defect. `CONTRIBUTING.md` principle 4 requires English, but agents are not directed to read it.

## What Changes

- Rewrite root `AGENTS.md` into real contributor instructions. It gets a `Language` section: English only, without exception, for code, identifiers, file and folder names, comments, docstrings, string literals in source, tests, scripts anywhere in the repo (including gitignored `data/` and `scripts/`), docs, commit messages and OpenSpec artifacts. Conversation with the player may use the player's language.
- Keep the other conventions `AGENTS.md` already promises (read-only gameplay boundary, verification, OpenSpec planning) as short sections consistent with `openspec/config.yaml` and `CONTRIBUTING.md`.
- Keep `CLAUDE.md` as the existing symlink to `AGENTS.md`, so Claude-based agents load the same rule with no second copy.
- Mirror the rule in `CONTRIBUTING.md` principle 4 (strengthen it; point to `AGENTS.md`).
- Add a verification command that finds Portuguese text in tracked files.

## Capabilities

### New Capabilities
- `contributor-conventions`: the repository's contributor-facing rules, starting with the language rule, and how agents are directed to them.

### Modified Capabilities
<!-- none: no existing spec covers contributor conventions -->

## Impact

- Files: `AGENTS.md`, `CONTRIBUTING.md`. `CLAUDE.md` unchanged (symlink).
- No runtime behaviour, mod, CLI or MCP change.
- Overlap: `cross-platform-and-saves`, `analysis-insights`, `basic-reports` and `agent-experience` are not edited; their future code and artifacts are bound by the new rule.

## Out of scope

- Renaming, translating or deleting `data/analise/` (author-local Portuguese playtest scripts; the author will retire it later). The rule applies to it, but this change does not touch it.
- Player-facing output language (for example reports rendered for a Portuguese-speaking player). Source code never contains localized literals; any localization of output is a future change.
- Translating existing Portuguese in tracked files beyond what the verification command surfaces; any hits it finds are fixed as part of this change's final task.
- Linters or CI hooks enforcing the rule.
