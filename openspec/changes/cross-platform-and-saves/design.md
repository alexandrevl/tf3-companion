# Design

## Context

After `rebrand-tf3-companion`: `paths.py` resolves the game userdata from `TF3C_USERDATA_DIR` or the macOS
Steam folder only; one `companion.db` and one `notes.md` in the data dir; mod installed by
`scripts/install-mod.sh`. Facts about TF3 folders come from the author's macOS install (build 40420):
`<Steam>/userdata/<account>/3493540/local/{staging_area,towns_industries,crash_dump/stdout.txt,save}`.
The same layout on Windows/Linux is an [INFERENCE] from Transport Fever 2 and Steam conventions; nobody on
the team runs Windows, so discovery is unit-tested on fake trees and validated later by Windows players.

Snapshot meta today: `buildVersion`, `gameTime`, `yearDuration`, `date`, `reason`, `requestId`,
`schemaVersion`, `modRevision`; `company.player` is the player entity id; `towns[]` carry stable `id`s
(e.g. 33 towns, ids 55329…55334 in the author's save). The full snapshot is ≈570 KB as JSON.

## Goals / Non-Goals

**Goals:** zero-config start on Windows and macOS; separate games never mix; one command installs the mod.

**Non-Goals:** detecting the save file name (not exposed to game scripts as far as the API shows);
reading Windows registry beyond the Steam path; GUI installers.

## Decisions

### D1 — Discovery order
1. `TF3C_USERDATA_DIR`.
2. Steam roots per OS:
   - Windows: `HKCU\Software\Valve\Steam\SteamPath` (via `winreg`), then `%ProgramFiles(x86)%\Steam`, `%ProgramFiles%\Steam`.
   - macOS: `~/Library/Application Support/Steam`.
   - Linux: `~/.steam/steam`, `~/.local/share/Steam`, `~/.var/app/com.valvesoftware.Steam/.local/share/Steam`.
3. Candidates `root/userdata/*/3493540/local`; choose by newest mtime of the candidate's `towns_industries` or the folder itself.
Implemented in `discovery.py` as pure functions taking `platform`, `env`, `home` and a registry reader so tests can fake each OS on any CI runner.

### D2 — Doctor
`discovery.diagnose() -> list[Check(name, status: ok|warning|error, detail, fix)]`, shared by CLI (`tf3c doctor`,
table output, exit 1 on any error) and MCP (`doctor`). Mod revision read from the installed `mod.json` (`revision`)
versus the bundled one. Log check scans the last 2,000 lines of `crash_dump/stdout.txt` for `[tf3c]`.

### D3 — Bundled mod
The mod stays at the repo root (`mod/tf3_companion_bridge/`), the single source for the release zip.
The wheel maps it with hatch `force-include` to `tf3companion/_mod/tf3_companion_bridge`.
Runtime uses the bundled resource when installed and the repo-root folder in an editable checkout.
`tf3c mod install` replaces only its own staging folder; unrelated mods are never touched.
`scripts/install-mod.sh` is deleted.

### D4 — Save lineage id and label
Town entity ids are not a unique save identity: two games on the same scenario can share them.
Do not use a town fingerprint as the primary key. The bridge owns a persistent lineage id,
initialised in its script state via the documented `GameScriptState:get/set` interface on the
simulation `update` callback and read from the read-only state in `guiUpdate`.
This stores bridge metadata only; it issues no game commands and changes no gameplay entities.
The game API defines these state interfaces, but persistence across reloads is not yet verified.
Before implementation can claim save isolation, an in-game probe MUST prove: reload keeps the id,
two independently started games on the same scenario get different ids, and save-as retains the id.
If that probe fails, use explicit player-assigned profiles instead; never silently merge games.
Snapshots carry `meta.saveId`; filenames become `tf3c_snap_<saveId>_<gameTime>.lua` to prevent
different games at the same game time from overwriting files before ingestion.
Label precedence: player label (`save.json`) → `meta.companyName` → three largest town names.

### D5 — Storage layout and routing
```
<data>/
  active_save            # pinned save id, absent = follow newest
  saves/<id>/save.json   # label, firstSeen/lastSeen game dates, lastSnapshotMtime
  saves/<id>/companion.db
  saves/<id>/notes.md  reports/  exports/
```
`SaveRegistry` scans `saves/`. Ingest reads each new file once, requires its `meta.saveId`, opens that save's
`Store` and adds it. Schema-1 snapshots lacking an id require an explicit import target; they MUST NOT
be automatically assigned using town ids. Active save follows the newest successfully ingested file
unless pinned. `Companion(save=...)` scopes every query; MCP `use_save` persists the pin.

### D6 — Author migration (manual, not shipped)
Create one lineage id for the author's existing game, move its `companion.db` and `notes.md`
into `saves/<id>/`, and bind the bridge to that lineage during the verified cutover.

### D7 — Compression
`snapshots.data` becomes a zlib-compressed JSON BLOB (level 6). The schema field `data_format` is not needed
since there is no released data; the author's DB is converted during D6 with a one-off script.
Measured target: 570 KB JSON → ≤150 KB (map data compresses ~5–10×; verify with the real snapshot).

### D8 — Interval via request file
Request file `towns_industries/tf3c_request.lua` = `{ id = <int>, snapshotsPerYear = <1|4|12> }`.
`tf3c config snapshots-per-year N` stores N in `<data>/config.json` and writes a request with a new id; every
`refresh` carries the configured interval and a request id. On startup the bridge reads any existing
request as its baseline before exporting the start snapshot; subsequent ids trigger request snapshots.
A request posted after startup MUST be served even if it arrives before the first 60-frame poll.
Alternative considered: `mod.json` params — rejected because mod params are chosen when a game is created
(`startGame2(..., modParams)`) and cannot be changed for an existing save.

### D9 — Company name
The mod tries `api.engine.getComponent(player, NAME)` (same helper as other entity names); stores `meta.companyName`
when it is a non-empty string. Schema version 2. Python accepts 1 and 2.

## Risks / Trade-offs

- [Windows layout differs from the inference] → `doctor` shows every searched path; `TF3C_USERDATA_DIR` works; first Windows tester validates; docs ask for doctor output in issues.
- [Script-state persistence is not verified] → the in-game identity probe is a blocking acceptance gate, not a claimed capability.
- [Company name component unavailable] → field omitted, label falls back to towns.
- [Request file read on every 60th frame] → unchanged cost from today.
