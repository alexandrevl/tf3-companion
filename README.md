# TF3 Companion

An unofficial, local-first, read-only data analyst for **Transport Fever 3**. A small game mod exports company snapshots; the companion stores history in SQLite, explains problems and opportunities, exports spreadsheets, and serves the same data to any MCP-capable agent. You decide and act in the game. No telemetry or network service is required.

Not affiliated with Urban Games or Paradox. Author: Alexandre Lima. License: MIT.

## Install from source

Install [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer, then in this repository:

```sh
uv sync
uv run tf3c --help
```

The companion's data paths and default-app export opener support Windows and macOS; Linux is best effort. Game-folder auto-detection is currently macOS Steam only. On Windows or an alternate Steam installation, set `TF3C_USERDATA_DIR` to the game's userdata `local` folder. For Steam, the app id is `3493540`.

Install the bundled mod on macOS (or a POSIX shell with the userdata override):

```sh
scripts/install-mod.sh
```

On Windows without a POSIX shell, copy `mod/tf3_companion_bridge/` to `<userdata>/staging_area/tf3_companion_bridge/`. In the game's mod list for **each save**, enable **TF3 Companion Bridge**, reload the save and save it. Renaming the prototype mod requires enabling the new mod per save; an installed folder alone does not activate it. The bridge only reads the simulation.

## Use

```sh
uv run tf3c status
uv run tf3c refresh
uv run tf3c overview
uv run tf3c lines
uv run tf3c line "Your line name"
uv run tf3c findings
uv run tf3c findings --json
uv run tf3c opportunities
uv run tf3c notes --append "A durable goal for this game"
uv run tf3c notes
uv run tf3c export --open
uv run tf3c log
```

`ingest` imports files already written by the mod. Data queries automatically import new files. `refresh --timeout 30` asks the running, loaded game for a snapshot; if it times out, check mod activation and `tf3c log`. Snapshots are written to `<userdata>/towns_industries/tf3c_snap_<gameTime>.lua`; refresh requests use `tf3c_request.lua`. Log entries begin with `[tf3c]`. Successfully imported snapshots retain the ten newest raw files; history remains in the database.

Annual profit covers a rolling game-year window and is partial for new lines. The interpretation of `transportedYear` remains unverified; do not use it for annual accounting until investigated. Vehicle load is a snapshot reading, not an average or proof of unmet demand; compare snapshots before changing fleet size. Collection errors can make sections incomplete.

## Data and environment

The current version keeps one store (not yet isolated per save):

| Platform | Default companion data directory |
| --- | --- |
| macOS | `~/Library/Application Support/tf3-companion` |
| Windows | `%LOCALAPPDATA%\tf3-companion` |
| Linux | `~/.local/share/tf3-companion` |

It contains `companion.db`, `notes.md` and `exports/`. Notes are appended under the latest snapshot's game date. Packaged knowledge is separate from player notes.

- `TF3C_DATA_DIR`: override the companion data directory.
- `TF3C_USERDATA_DIR`: override the game's userdata directory; required when auto-detection is unavailable.

Player data must not be committed. No automatic prototype migration is shipped; keep existing data and installed mods until you explicitly migrate and reload your save.

## MCP

Run `uv run tf3c mcp` for the stdio server named `tf3-companion`. `.mcp.json` configures this command for repository-aware clients. Tools cover status/refresh, company and entity queries, findings/opportunities, history, knowledge, dated notes (`save_notes`), decisions, logs and spreadsheet export. Server instructions describe the read-only analyst role; agents answer in the user's language.

Contributor workflow: [AGENTS.md](AGENTS.md). Planned work: [docs/ROADMAP.md](docs/ROADMAP.md).
