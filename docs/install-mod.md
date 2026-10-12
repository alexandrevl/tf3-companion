# Install, update and remove the bridge

The bridge reads the simulation and writes snapshot userdata; it does not buy vehicles, edit lines or issue gameplay commands. Installing files changes your local mod folder and is a separate action from activating a mod in a save. Only perform it when you intend to change that installation.

## Find the correct userdata directory

From the source checkout:

```sh
uv run tf3c doctor
```

Doctor is read-only and can diagnose a missing game installation. Automatic discovery considers Steam locations on macOS, Windows and Linux; multiple accounts require an explicit choice rather than guessing. Discovery candidates do not establish live Windows/Proton compatibility.

Steam userdata is distinct from the game executable and Steam library. Typical candidates are:

| Platform | Candidate directory |
| --- | --- |
| macOS | `~/Library/Application Support/Steam/userdata/ACCOUNT_ID/3493540/local` |
| Windows | `C:\Program Files (x86)\Steam\userdata\ACCOUNT_ID\3493540\local` |
| Linux | `~/.local/share/Steam/userdata/ACCOUNT_ID/3493540/local` |
| Flatpak Steam | `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/userdata/ACCOUNT_ID/3493540/local` |

Actual Steam roots can differ. Use the existing `local` folder for your account. Set an override in the same terminal as the commands (and in your MCP client environment if needed):

```powershell
$env:TF3C_USERDATA_DIR = 'D:\Steam\userdata\ACCOUNT_ID\3493540\local'
```

```sh
export TF3C_USERDATA_DIR="/absolute/path/to/Steam/userdata/ACCOUNT_ID/3493540/local"
```

## Install

```sh
uv run tf3c mod install
```

The command installs the bundled bridge in `<userdata>/staging_area/tf3_companion_bridge`. It is scoped to that mod, not other mods, snapshots, notes or the database. Unsafe symlink/junction paths are refused. Review errors instead of bypassing these boundaries.

Manual alternative: copy the repository's `mod/tf3_companion_bridge` directory into `<userdata>/staging_area/`, preserving its name and contents. The resulting directory must contain `mod.json` directly; avoid a second nested `tf3_companion_bridge` folder. This source guide does not assume a Workshop or Mod Hub listing exists.

## Activate for a save

1. Enable **TF3 Companion Bridge** in the game's mod list for the intended save.
2. Reload the save and save it.
3. Keep the simulation loaded and run `uv run tf3c refresh --timeout 30`.
4. Inspect `uv run tf3c status` and `uv run tf3c log` for snapshot output and collection errors.

The mod's cosmetic designation communicates that it is not intended to alter gameplay. It is not a substitute for testing activation/removal on the actual game build. A successful check includes a fresh snapshot, no red game error and no unexplained collector failures; a quiet terminal alone is insufficient.

## Update

Close or unload the game before replacing bridge files. Update the checkout and locked environment, then reinstall:

```sh
uv sync --locked
uv run tf3c mod install
```

Reload the save and verify a fresh snapshot. Keep backups of existing player data; do not silently migrate prototype mods or histories. If the mod id changes, enabling the old mod does not enable the new one.

## Remove

Disable the bridge for the save and reload it before removing its installed directory:

```sh
uv run tf3c mod uninstall
```

This removes only the installed bridge folder. Companion history, notes, reports and raw snapshot userdata are retained; see [privacy and deletion](privacy.md). Removing files does not itself edit a save's active-mod selection.

## Verification boundary

The existing plan records prototype output on macOS game build 40420. This review did not install the mod or load a player's game. Updated macOS and real Windows install/activation/refresh rehearsals remain release gates; Linux/Proton is best effort.
