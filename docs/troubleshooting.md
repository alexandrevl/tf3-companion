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
