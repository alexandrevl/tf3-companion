## Why

After the five preceding changes the code is a coherent, English, cross-platform product, but nothing around it
is publishable: the README is a Portuguese prototype note, there is no LICENSE, CI, fixtures free of personal data,
mod artwork, or install path other than a macOS shell script. A stranger cannot go from the repository to a first
finding in 10 minutes, and the mod cannot be uploaded to mod.io. This change closes ROADMAP phase P3 ("Public").

## What Changes

No runtime behaviour changes; this is packaging, documentation, quality gates and release assets
(`skip_specs: true`: there is no spec-level behaviour to contract).

- **README** rewritten: what/why, an "unofficial, not affiliated with Urban Games or Paradox Interactive" disclaimer,
  a 10-minute quickstart for Windows and macOS, the compatibility table, screenshots (placeholders until the player
  takes real ones, then replaced).
- **Docs set**: `docs/install-mod.md`, `agents.md` (MCP config for Claude Code, Claude Desktop, Cursor, Codex, omp on
  Windows + macOS), `cli.md`, `reports.md`, `snapshot-schema.md`, `troubleshooting.md`, `privacy.md`, `publishing-mod.md`
  (mod.io via the in-game Mod Hub: logo, gallery, `_metadata/modinfo.json`, revision bump, release checklist).
- **Repo hygiene**: `LICENSE` (MIT, Alexandre Lima), `CHANGELOG.md` (Keep a Changelog), `CONTRIBUTING.md`,
  GitHub issue templates (bug, feature) requiring `tf3c doctor` output and `[tf3c]` log lines, PR template.
- **CI** (GitHub Actions): pytest on windows/macos/ubuntu-latest; Lua syntax check + stubbed-API harness + luacheck for
  the mod; on tag, build wheel + sdist + `tf3_companion_bridge-<revision>.zip` and attach to a draft GitHub release.
- **Mod test harness** `mod/tests/`: stubbed game API driving the bridge script (none exists today).
- **Anonymised fixtures** in `tests/fixtures/` (small and large synthetic-from-real snapshots; no player/company/town
  names from a personal save), plus a guard test that scans the repo for forbidden strings.
- **Mod assets**: logo PNG, `image_00.tga` thumbnail, gallery screenshot slots (player-taken), `assets/` source files.
- **Packaging**: wheel contains knowledge topics and the mod files as package data; `uvx tf3-companion` / `pipx`
  smoke-tested from the built wheel; version single-sourced (one place feeds package, `tf3c --version`, MCP server
  version, mod `modinfo` text, release zip name).
- **Compatibility table** (game build × mod revision × schema version × companion version), maintained in README and
  CHANGELOG.
- **Manual release checklist** for the steps that cannot be done now: create the GitHub repo, push, tag, publish
  to PyPI, upload to mod.io. Only local commits are made by this change; no remote exists.

## Capabilities

### New Capabilities
None (documentation, CI and assets only).

### Modified Capabilities
None. Behaviour is not changed; `tf3c --version` and MCP `serverInfo.version` read the single-sourced version
and `mod install` bundling reads the mod from package data, both already in the specs of earlier changes
(this change only verifies them).

## Impact

- New: `README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/*.md`, `.github/`, `assets/`, `mod/tests/`,
  `tests/fixtures/`, `.luacheckrc`.
- Touched: `pyproject.toml` (dynamic version, metadata, classifiers, URLs, package data/force-include for the mod),
  `mod/tf3_companion_bridge/` (artwork, modinfo text, revision), `.gitignore`.
- Depends on all earlier changes having landed (names, `tf3c doctor`, `tf3c mod install`, reports, MCP prompts).
- External, later and manual: GitHub repository, PyPI project name `tf3-companion` (availability to re-check at
  publish time), mod.io listing.
- Legal: knowledge/docs paraphrase game scripts and never paste game code; trademarks are named only descriptively.
