## Context

See proposal.md. Facts grounded in the current tree and game install (build 40420, macOS):

- `pyproject.toml` has a hardcoded `version = "0.1.0"`, hatchling backend, wheel packages `src/<pkg>` only.
  After change 1 the package is `tf3companion` with `knowledge/` as package data.
- The mod lives in `mod/<id>/` with `mod.json` (`revision`, `cosmetic: true`, `severityAdd/Remove: None`),
  `_content.json` (file list), `_metadata/modinfo.json` (name, summary, description, `localization`, authors, tags) and
  `content/<dir>/*.lua`. There is no `image_00.tga`, no logo, no Lua test.
- Game files (read-only inspection): `api/tealdef/api/modhub.d.tl` and `api/type/modhub.d.tl` define the Mod Hub
  publishing API: `ModPublishHelper` with `validate`, `publish`, `addLogoImage`, `addGalleryImages`,
  `moveGalleryImage`, `setModDetails`, `setRemoteModId`, `openFolder`; media types `Logo`, `GalleryThumb180p`,
  `GalleryThumb720p`, `GalleryOriginal`. The game binary contains the strings `image_00.tga`, `modinfo.json`,
  `_metadata/mod.io_fileid.txt`, `mods/{}/gallery/{}/`, "Gallery file doesn't exist". Stock mods in `mods/release/*`
  ship `_metadata/0.png` (1920x1080 RGBA PNG) and `_metadata/modinfo.json`, no `image_00.tga`.
  So which file is the in-game mod-list thumbnail is **not settled by static inspection**; task 6.1 settles it empirically.
- Findings carry a single `entity` field (`{kind,id,name}` or null), category in `finance|lines|vehicles|industries|data`;
  `snapshot-schema.md` documents schema 3 (after `analysis-insights`) and that, not an `entities[]` list.
- No git history and no remote: the repo has zero commits.

## Goals / Non-Goals

**Goals:**
- A new user reaches a first finding in <= 10 minutes from README on Windows or macOS, without knowing the repo.
- Every claim in docs is checkable: commands copy-paste runnable, config snippets validated against each agent's format.
- CI proves what it can on three OSes; what only the game can prove is an explicit in-game checklist.
- One source of truth for the version; releases reproducible from a tag.

**Non-Goals:**
- Publishing anything (GitHub, PyPI, mod.io) or creating the remote; documented as a manual checklist.
- New product features, new MCP tools, behaviour changes.
- Automating mod.io upload (the game's Mod Hub is the only upload path we rely on).
- Linux in-game support is best effort. Windows and macOS are required release gates; lack of a Windows machine is unverified status, not a completed acceptance criterion.

## Decisions

**D1. Docs are plain Markdown in `docs/`, README is a funnel.** README holds pitch, disclaimer, quickstart, compat table,
screenshots, links; depth lives in `docs/`. Alternative (mkdocs site): rejected, extra toolchain for no reader benefit.

**D2. Verify docs with execution.** Parse configuration examples, check links and exercise the
documented install, CLI and MCP workflows using throwaway scripts and clean environments.
Keep permanent tests for behavior, isolation, errors and boundaries, not wording or copied lists.
Use real screenshots only; unavailable images stay in the capture checklist rather than broken
links or placeholder claims in user documentation.

**D3. Version single-sourced via hatch.** `[tool.hatch.version] path = "src/tf3companion/__init__.py"`
(`__version__`), `dynamic = ["version"]`. `tf3c --version`, MCP `serverInfo` and the release workflow read it
(workflow checks tag `vX.Y.Z` == `__version__` and fails otherwise). The mod `revision` is an independent integer in
`mod.json`, recorded against the companion version in the compatibility table; the zip is named
`tf3_companion_bridge-r<revision>.zip`. Alternative (setuptools-scm from tags): rejected, no git history yet and
the file approach is trivially testable.

**D4. Mod ships inside the wheel** (implemented by changes 1/2; this change only verifies it) via `force-include` to `tf3companion/_mod/` so `tf3c mod install` works from `uvx`/pipx with no checkout; the repo-root
`mod/` stays the editable source. A test asserts the built wheel lists the mod files, `_content.json` entries, and every
knowledge topic. Alternative (download from GitHub at install time): violates "no network".

**D5. CI layout.** `.github/workflows/ci.yml`: matrix job `python` on `windows-latest, macos-latest, ubuntu-latest`
using `astral-sh/setup-uv`, `uv sync --locked`, `uv run pytest`; job `lua` on ubuntu: `apt install lua5.4 luarocks`,
`luarocks install luacheck`, `luac5.4 -p` on every mod Lua file, `luacheck mod/`, then `lua5.4 mod/tests/run.lua`.
`.github/workflows/release.yml` on tag `v*`: verify version, `uv build`, build mod zip via `scripts/build_mod_zip.py`
(zip root = the mod folder, matching how `staging_area` expects it), smoke-install the wheel in a clean venv
(`tf3c --version`, `tf3c mod install --help`), attach to a **draft** release. No PyPI step
in CI at first; publishing is manual (checklist), optionally trusted-publishing later.
Actions pinned to major versions. Alternative (single job everywhere): too slow, mixes failures.

**D6. Lua harness with stubbed API.** `mod/tests/run.lua` defines stub globals the game provides (`game`, `api`, `app`,
`print`, entity/line/vehicle queries as small tables), loads the bridge script, calls its lifecycle entry points,
and exercises interval settings, missing request files, refresh arriving before the first poll,
lineage-scoped snapshot filenames, collector error isolation and absence of gameplay commands.
The harness is a regression tool for meaningful state transitions; it cannot prove real API
signatures or script-state persistence. Those remain explicit player-controlled in-game checks.
Python parses emitted snapshots as an interoperability smoke exercise.
No literal-source or copied-wiring assertions are needed.

**D7. Fixtures are generated, not copied.** `scripts/make_fixtures.py` reads a real snapshot and writes an anonymised copy:
company, line, vehicle, station, industry and town names replaced by deterministic synthetic names (`Line 007`,
`Town 012`), coordinates shifted, ids remapped consistently and synthetic lineage ids assigned.
Two fixtures exercise meaningful analysis boundaries on small and large companies.
Manually inspect for personal names and paths before committing; no original snapshots enter git.
Keep the existing minimal behavior fixtures where they make edge cases easier to understand.
No permanent tests pin documentation wording or incidental fixture defaults.
Package privacy is checked by inspecting a built wheel and exercising offline use.

**D8. Mod assets.** `assets/` holds sources: `logo.svg` (hand-written, original art, no game assets or Paradox/Urban Games
marks), `logo.png`, exported thumbnails and `gallery/` screenshots. The mod folder gets `image_00.tga` (uncompressed 32-bit
TGA, size to be fixed by task 6.1 from observation) and, because stock mods use it for hub media, `_metadata/` keeps
`0.png`-style image only if 6.1 shows the game picks it up. Gallery images (1920x1080 PNG, 3-4) are taken by the player in game
and live in `assets/gallery/`; they are not in the mod zip. A script `scripts/make_assets.py` (Pillow, dev-only
dependency group) renders TGA/PNG from the SVG-equivalent so assets are reproducible. Alternative (hand-exported binaries
only): unreproducible.

**D9. Compatibility table is data, not prose.** A table in README is the source, and
`test_docs.py` asserts that the latest row matches `__version__`, `mod.json` revision and the snapshot
`schemaVersion` constant. CHANGELOG entries reference it. Rows start at the first release with game build 40420 as
"validated on macOS"; Windows/Linux rows read "reported by users / untested" until evidence exists.

**D10. Docs are in English; MCP configs per agent are copied from each agent's current documentation.** The task fetches
the current format (Claude Code `claude mcp add` / `.mcp.json`, Claude Desktop `claude_desktop_config.json`
with the Windows `%APPDATA%\Claude` and macOS `~/Library/Application Support/Claude` paths, Cursor `mcp.json`, Codex
`config.toml`, omp `mcp.json`), pins command to `uvx tf3-companion mcp` with a pipx variant, and notes that GUI apps
on macOS do not inherit shell PATH (use absolute `uvx` path). Snippets are JSON/TOML-validated by D2.

**D11. Privacy document distinguishes layers:** collection and analysis are local and require no
network; package installation and connected AI clients may use networks. Doctor inspects OS and
Steam paths, so do not claim no system/account information is ever read. Snapshot outputs contain
company and game-entity data, not credentials. Explain per-save deletion and raw-file retention.

**D12. Local commits only.** The change ends with an organised commit series on `master` (docs, CI, mod, fixtures)
and a `docs/publishing-mod.md` + `RELEASING.md`-style checklist section (inside `CONTRIBUTING.md`) for the remote steps.

## Risks / Trade-offs

- [Thumbnail file convention unverified] -> task 6.1 tests `image_00.tga` and `_metadata` image in the game's mod list before
  fixing the docs; docs state only what was observed.
- [Windows paths/agent configs untested by the author] -> CI runs pytest on windows-latest (path logic is unit-tested);
  docs mark Windows steps "verified by CI only" until a Windows user confirms; issue template asks for OS.
- [Stub harness diverges from real API] -> stubs only cover names present in `api/tealdef`; the in-game checklist in
  `docs/publishing-mod.md` remains the gate before each revision upload.
- [Anonymisation leaks via ids or coordinates] -> remapping + denylist guard + manual diff review of fixtures once.
- [Agent config formats change] -> docs show "last verified" date per agent; troubleshooting points at the `tf3c doctor` output.
- [Trademark confusion] -> disclaimer in README, mod description, and PyPI metadata; logo contains no game artwork.
- [Wheel size/mod duplication] -> mod is a few KB; acceptable.
- [PyPI name `tf3-companion` may be taken by publish time] -> checklist item to re-check; fallback documented only if it happens.

## Migration Plan

1. Land docs/CI/fixtures/assets as local commits (no remote). 2. Player takes screenshots and the in-game checks;
placeholders replaced. 3. Manual, later: create GitHub repo, add remote, push, set branch protection, tag `v0.1.0`,
review draft release, publish to PyPI, upload mod via Mod Hub, fill `_metadata/mod.io_fileid.txt` back into the repo.
Rollback: nothing is published by this change; reverting commits is sufficient.
