# Troubleshooting

Diagnose and resolve common problems with installation, mod activation, snapshot collection, and MCP agent communication.

## Quick diagnostic: `tf3c doctor`

Run `tf3c doctor` before changing settings:

```sh
uv run tf3c doctor
```

`doctor` is read-only. It inspects Python version, package data, storage directories, and standard Steam candidate paths. If errors are found, the command exits with code `1` and explains the missing path or configuration.

---

## Mod installation and game activation

### Symptom: `Transport Fever 3 userdata not found` or multiple accounts detected

- **Cause:** Automatic Steam path discovery could not find the `local` directory under your Steam library, or found more than one account folder under `userdata/`.
- **Fix:** Locate your Steam account's numeric folder manually and set `TF3C_USERDATA_DIR`:
  - macOS:
    ```sh
    export TF3C_USERDATA_DIR="$HOME/Library/Application Support/Steam/userdata/YOUR_ACCOUNT_ID/3493540/local"
    ```
  - Windows PowerShell:
    ```powershell
    $env:TF3C_USERDATA_DIR = 'C:\Program Files (x86)\Steam\userdata\YOUR_ACCOUNT_ID\3493540\local'
    ```
  - Note: Ensure the path ends with `local`, not the Steam game installation directory (`steamapps/common`).

### Symptom: Mod installed, but game does not see it

- **Check:** Run `uv run tf3c status`. Check whether `staging_area` points to the expected path.
- **Check directory structure:** Inside `<userdata>/staging_area/tf3_companion_bridge/`, you should see `mod.json` directly. If you see a nested directory `tf3_companion_bridge/tf3_companion_bridge/`, move the contents up one level.
- **Save mod list:** In the game's main menu or save loading screen, open the save's mod list and ensure **TF3 Companion Bridge** is checked (enabled). Reload the save and save it again.

### Symptom: Red in-game error banner

- **Cause:** A Lua runtime error occurred inside the mod.
- **Check:** Run `uv run tf3c log` to read lines marked with `[tf3c]` from `stdout.txt`.
- **Report:** Check that the mod files were copied without corruption. If reproducible, submit a bug report including the `[tf3c]` lines from your log.

---

## Snapshot collection and refreshes

### Symptom: `uv run tf3c refresh` times out after 30 seconds

- **Check 1: Is the game running and unpaused?** The bridge exports on game update cycles. If the game is minimized or in the main menu, it will not process the request.
- **Check 2: Is the mod enabled in the currently loaded save?** An enabled mod in save A does not activate in save B. Check the save's mod list.
- **Check 3: Inspect the request file:** Look inside `<userdata>/towns_industries/` for `tf3c_request.lua`. If the file is missing or not consumed, the bridge is not active in the running session.
- **Check 4: Game log:** Run `uv run tf3c log --lines 50`. Look for `[tf3c] request read` or Lua collector errors.

### Symptom: Old or unchanging snapshot dates

- **Cause:** The game may be paused, or snapshot files are not being generated.
- **Fix:** Unpause the simulation for a few in-game seconds, then run `uv run tf3c refresh`. If snapshots were generated earlier while the companion was closed, run `uv run tf3c ingest` to import pending snapshots.

### Symptom: Snapshot ingestion rejected due to save mismatch

- **Cause:** A snapshot was received with a `saveId` that differs from the existing database records, or an identified snapshot was fed into an unpartitioned legacy database.
- **Fix:** TF3 Companion's single-store fail-closed guard prevents corrupting company histories across different saves. Direct the new save to its own data directory using `TF3C_DATA_DIR`:
  ```sh
  export TF3C_DATA_DIR="$HOME/Library/Application Support/tf3-companion-alt"
  uv run tf3c refresh
  ```

---

## Game files, logs and crashes

Locations below are relative to `<userdata>`, the `.../Steam/userdata/<account id>/3493540/local` folder (`3493540` is the Transport Fever 3 Steam app id) that `tf3c status` reports or that `TF3C_USERDATA_DIR` overrides. The ones marked "checked" are the paths TF3 Companion itself uses (`discovery.py`, `paths.py`); the rest come from MPFever's published research (MIT) and are not verified by this project.

| What | Location | Notes |
|---|---|---|
| Snapshots and refresh request (checked) | `towns_industries/` | `tf3c_snap_<gameTime>.lua`, `tf3c_request.lua` |
| Mod staging (checked) | `staging_area/tf3_companion_bridge/` | `mod.json` directly inside |
| Game log (checked) | `crash_dump/stdout.txt` | What `tf3c log` reads |
| Crash dumps | `crash_dump/` (newest files) | Written by the game when it crashes |
| Saves, crash saves, autosaves | `save/` | A save is `<name>.sav` plus extra files that start with `<name>.sav.`; autosaves start with `autosave_`, crash saves with `crash_` and carry the world name and date |
| Mods and settings | `mods/`, `settings.lua`, `profile.lua` | The game rewrites `settings.lua` when it exits, so edit it only while the game is closed |

### Symptom: `uv run tf3c log` prints `Log not found: <path>`

- **Cause:** `<userdata>/crash_dump/stdout.txt` does not exist: the game has never started under this userdata folder, or `TF3C_USERDATA_DIR` points to a different account folder.
- **Fix:** Start the game once, then run `uv run tf3c status` to confirm the userdata path and look for `crash_dump/stdout.txt` inside it.

### Symptom: `uv run tf3c log` shows no lines, or lines from an earlier session are gone

- **Cause 1:** The game rewrites `stdout.txt` at every start, so the log of a previous run is lost once the game is launched again. The file may also not be complete until the game has closed (MPFever research, not verified here).
- **Cause 2:** `tf3c log` prints only the lines that contain `[tf3c]`, newest last, up to `--lines` (default 40). Other game output is not shown; open `crash_dump/stdout.txt` directly for it.
- **Fix:** Copy `stdout.txt` somewhere safe before relaunching the game when you need the evidence of a crash or a failed collection, then read the copy.

### Symptom: The game crashed or was closed after an error

- **Cause:** Crashes leave a dump in `crash_dump/` and a crash save (`crash_<world>_<date>.sav`) in `save/`. A crashed game process can stay open after writing its crash save. A crash save keeps the state that caused the crash (MPFever research, not verified here).
- **Fix:** Close the leftover process, copy `crash_dump/stdout.txt` and the newest dump, then continue from an earlier save or autosave instead of the crash save. When reporting, include the `[tf3c]` lines and say whether the bridge mod was enabled.

### Symptom: Many dump files appear in `crash_dump/` and the game freezes briefly

- **Cause:** MPFever measured that each failed property read inside a script makes the game write a dump and stall (about 0.1 s even inside `pcall`). A collector that probes unknown members in a loop can therefore flood the folder.
- **Fix:** Check `uv run tf3c log --lines 100` for repeated `[tf3c]` collector errors and report them; do not keep re-requesting snapshots while they repeat.

---

## MCP agent connection issues

### Symptom: GUI client (Claude Desktop / Cursor) says server failed to start

- **Cause 1: Relative path in GUI config.** GUI applications start in arbitrary working directories. Always specify absolute paths:
  - Command: use the full path to `uv` (e.g. `/Users/username/.cargo/bin/uv` or `C:\Users\username\.cargo\bin\uv.exe`).
  - Project argument: `--project /absolute/path/to/tf3-companion`.
- **Cause 2: Missing environment variables.** GUI applications on macOS do not inherit your shell's `.zshrc` / `.bashrc` environment variables. Include `TF3C_USERDATA_DIR` in the client configuration's `env` block if you rely on an override.
- **Verification:** Test the exact command from a bare shell first:
  ```sh
  /path/to/uv run --project /absolute/path/to/tf3-companion tf3c status
  ```

### Symptom: Agent cannot read `notes` or reports

- **`tf3c://notes`:** Requires at least one imported snapshot to anchor the current game date.
- **`tf3c://report/latest`:** Requires at least one report to have been generated. Generate one using the CLI (`uv run tf3c report company`) or ask the agent to call the `report` tool first.
- **Static knowledge:** Topics under `tf3c://knowledge` are bundled inside the Python package and remain available even without a game installation or active snapshot.

### Symptom: A tool is missing or behaves like an older release after upgrading

- **Cause:** The MCP server keeps the code and tool definitions it started with; it does not hot reload.
- **Fix:** Restart the server from the client, then call `status` and compare its `version` with `uv run tf3c --version`.
