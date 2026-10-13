# TF3 Companion setup guide

This guide installs and verifies TF3 Companion on Windows and macOS. It is written for a player working with an AI assistant, and is readable before the MCP server exists. The same text is served over MCP as `tf3c://setup`.

TF3 Companion is read-only for gameplay: the bridge mod exports snapshots, the companion stores and analyses them, and the player makes every change in the game.

## Rules for the assistant

1. **Establish your capabilities first.** State whether you can run terminal commands and read files on the player's computer, and with which approval model.
   - **Local agent** (terminal/filesystem access the player has approved): you may run read-only checks such as `tf3c doctor`. Report the actual output.
   - **Text-only chat** (no access to the computer): give the player one command at a time, ask them to paste the output, and never claim you ran or saw anything you did not receive.
2. **Ask before every change.** Obtain explicit approval before installing uv or dependencies, cloning or updating the checkout, installing, replacing or removing the bridge mod, or editing an AI client's configuration. Approval for one change is not approval for the next.
3. **Merge, never replace, client configuration.** Add only the `tf3-companion` server entry; keep other servers and settings. Back up the file before editing.
4. **Leave the game to the player.** Enabling the mod for a save, loading and saving the game, unpausing and every gameplay action are manual player steps. Do not claim they happened until evidence shows it.
5. **Report stages, not a single "done".** Use the stage table below and say exactly which stages are verified, pending or failing.

## Stage 1: Companion package

The package is not published on PyPI. Do not use `pip install tf3-companion` or `uvx tf3-companion`. Install from a source checkout:

1. Install [uv](https://docs.astral.sh/uv/) if `uv --version` fails (requires approval). uv provisions Python 3.12+.
2. Download or clone the repository from its actual GitHub location (requires approval), then open a terminal in the checkout.
3. Run `uv sync --locked`, then `uv run tf3c --version`.

Windows PowerShell:

```powershell
Set-Location C:\Projects\tf3-companion
uv sync --locked
uv run tf3c --version
uv run tf3c doctor
```

macOS:

```sh
cd /path/to/tf3-companion
uv sync --locked
uv run tf3c --version
uv run tf3c doctor
```

Evidence: `tf3c --version` prints a version, and `doctor` returns JSON.

## Stage 2: Game paths (`tf3c doctor`)

`doctor` is read-only and works without the game. Read each entry in `checks`, not only `ok`:

- `ok: false` means at least one `error` check. Typical cause: `userdata` not found or ambiguous between Steam accounts.
- `ok: true` only means there are no errors. Warnings such as `installed_mod`, `snapshots` or `game_log` mean setup is **not** complete.

If `userdata` fails, set `TF3C_USERDATA_DIR` to the game's existing `local` folder (not the Steam library or the game executable) in the same terminal and in the MCP client environment:

| Platform | Typical folder |
| --- | --- |
| Windows | `C:\Program Files (x86)\Steam\userdata\ACCOUNT_ID\3493540\local` |
| macOS | `~/Library/Application Support/Steam/userdata/ACCOUNT_ID/3493540/local` |

```powershell
$env:TF3C_USERDATA_DIR = 'C:\Program Files (x86)\Steam\userdata\ACCOUNT_ID\3493540\local'
```

```sh
export TF3C_USERDATA_DIR="$HOME/Library/Application Support/Steam/userdata/ACCOUNT_ID/3493540/local"
```

With several Steam accounts, ask the player which one plays the save; never guess. One companion data directory is shared across saves; use a separate `TF3C_DATA_DIR` per save to keep their history apart.

## Stage 3: Bridge mod revision

Explain that `uv run tf3c mod install` writes only `<userdata>/staging_area/tf3_companion_bridge`, replacing an older copy of this bridge and nothing else. Ask for approval, then run it. Close or unload the game before replacing an existing copy.

Evidence: rerun `doctor`; the `installed_mod` check is `ok` and `mod.revision` equals `mod.bundled_revision`. An installed folder is not proof the mod is active.

## Stage 4: Player activation (manual)

The player must:

1. Open the game and enable **TF3 Companion Bridge** in the mod list of the intended save.
2. Load that save, save it, and keep the simulation running (not paused, not in the main menu).

If the player has not done this yet, stop here and report: "Local setup verified; in-game activation and the first snapshot are pending."

## Stage 5: MCP client connection

Configure a local stdio MCP client only after approval. The server command is:

```sh
uv run --project /absolute/path/to/tf3-companion tf3c mcp
```

Use absolute paths to `uv` and the checkout; GUI clients do not inherit the terminal's PATH or environment. Add `TF3C_USERDATA_DIR` (and optionally `TF3C_DATA_DIR`) to the entry's `env` when discovery needed an override. JSON clients (Claude Desktop and similar `mcpServers` maps):

```json
{
  "mcpServers": {
    "tf3-companion": {
      "command": "/absolute/path/to/uv",
      "args": ["run", "--project", "/absolute/path/to/tf3-companion", "tf3c", "mcp"]
    }
  }
}
```

Merge this entry into the existing `mcpServers` object. On Windows, escape backslashes in JSON (`C:\\Projects\\tf3-companion`). Codex and other clients use their own formats; see `docs/agents.md` in the repository.

ChatGPT in a web browser cannot start a local stdio server on the player's computer. A text-only assistant can still guide setup and read pasted CLI output.

Evidence: after the client restarts or reconnects, a `doctor` or `status` tool call returns a result through the client. A saved configuration file alone is not proof.

## Stage 6: Fresh snapshot

Only after the player confirms the save is loaded with the bridge enabled, run `uv run tf3c refresh --timeout 30` (or call the `refresh` tool).

Evidence: `ok: true` with a `date` and snapshot `file`. Older snapshots in the folder do not prove that the current save or the bridge are working.

## Stage 7: First report

Run `uv run tf3c report company` (or call the `report` tool with `kind: company`).

Evidence: the command returns a report path, or the tool returns Markdown with the observation date. Cite the snapshot date and any collection errors from `status`; a report is limited to observed data.

## Completion statement

| Stage | Verified by |
| --- | --- |
| 1 Package | `tf3c --version` output |
| 2 Paths | `doctor` `userdata` check `ok` |
| 3 Bridge revision | `doctor` `installed_mod` `ok`, revisions equal |
| 4 Activation | Player confirmation plus stage 6 evidence |
| 5 MCP | A tool result received through the client |
| 6 Snapshot | `refresh` `ok: true` with date and file |
| 7 Report | Report generated from that snapshot |

Declare setup complete only when every stage has its evidence. Otherwise list each stage as verified, pending (with the next action and who performs it) or failing (with the observed error). Mention that one companion store is shared across saves.

## Recovery

| Observation | Next action |
| --- | --- |
| `userdata` error or several candidates | Ask which account; set `TF3C_USERDATA_DIR` to its `local` folder |
| `installed_mod` warning, revision missing or different | With approval, `tf3c mod install`; then player reloads the save |
| `snapshots` warning, no files | Player enables the bridge, loads the save; then `refresh` |
| `refresh` times out | Confirm the game is open, unpaused and the mod enabled in this save; read `tf3c log` for `[tf3c]` lines |
| Snapshot date does not change | Player unpauses the simulation; `refresh` again; `tf3c ingest` imports pending files |
| `status` shows collection errors | Report them; conclusions using affected data are limited |
| Red error in game or missing `[tf3c]` log lines | Read `tf3c log`; reinstall the bridge with approval; report the log lines |
| Save mismatch on ingestion | Use a separate `TF3C_DATA_DIR` for the other save |
| MCP server fails to start | Run the exact configured command in a terminal; use absolute paths and the `env` block |
