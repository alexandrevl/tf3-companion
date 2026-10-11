# Tasks

## 1. Game discovery

- [ ] 1.1 Implement `discovery.py` (D1) with injectable platform/env/home/registry; verify pytest cases for Windows registry path, Windows default path, macOS, Linux native and Flatpak, two accounts, override, and the not-found message listing searched paths
- [ ] 1.2 Wire `paths.py` to discovery and remove the macOS-only detection; verify `uv run tf3c status` still finds the author's userdata

## 2. Mod bundling and installation

- [ ] 2.1 Ship the mod in the wheel via hatch `force-include` to `tf3companion/_mod/` with a dev-checkout fallback (D3); verify `uv build` and that the wheel lists `tf3companion/_mod/tf3_companion_bridge/mod.json`
- [ ] 2.2 Implement `tf3c mod install|uninstall` with reload hint, delete `scripts/install-mod.sh`; verify with a pytest on a temp userdata and by running `uv run tf3c mod install` on the author's machine

## 3. Save identity and storage

- [ ] 3.1 Prove bridge-only script-state identity survives reload and save-as and differs between independent games on the same scenario; save the observations before choosing automatic isolation. If persistence fails, implement explicit profiles that refuse ambiguous imports. Verify with the player-controlled in-game probe in D4.
- [ ] 3.2 Implement `SaveRegistry` and route ingestion by verified lineage ids; verify tests with two interleaved saves sharing identical town ids and game times, pinning, labels, and rejection of unassigned legacy snapshots.
- [ ] 3.3 Compress stored snapshot data (D7); verify a test that stores the largest fixture and asserts the size bound, and measure the author's real snapshot
- [ ] 3.4 Detect backwards game-time jumps over one year within a save and surface them in `status`; verify pytest
- [ ] 3.5 Scope `Companion` queries, notes, decisions and exports to the active or requested save; verify existing tests pass with a save fixture

## 4. CLI and MCP surface

- [ ] 4.1 Add `tf3c doctor`, `saves` (list/use/unpin/label), `config snapshots-per-year` and global `--save`; verify pytest on argument parsing and exit codes, and run `uv run tf3c doctor` on the author's machine
- [ ] 4.2 Add MCP tools `doctor`, `list_saves`, `use_save` and save fields in `status`; verify by calling them through an MCP client session in a test

## 5. Mod: interval and schema 2

- [ ] 5.1 Read interval configuration at startup before baselining request ids, initialise bridge-owned lineage metadata through the documented state interface, write `meta.saveId` and lineage-scoped filenames, add `meta.companyName`, and bump schema/revision to 2. Verify Lua syntax and harness behavior, including refresh posted before the first poll.
- [ ] 5.2 Accept schema 1 and 2 in the Python loader and document new fields in the `snapshot_schema` knowledge topic; verify pytest

## 6. Migration and verification

- [ ] 6.1 Bind the author's existing history and notes to the verified lineage id and compress existing rows without losing data; verify pre/post snapshot and decision counts, dates and entity metrics.
- [ ] 6.2 In-game check: reinstall with `uv run tf3c mod install`, reload "Hollanda II", run `uv run tf3c config snapshots-per-year 12` and `uv run tf3c refresh`; verify the snapshot has `schemaVersion = 2`, `companyName` if available, lands in the same save, and `uv run tf3c doctor` exits 0
- [ ] 6.3 Run `uv run pytest` green and commit
