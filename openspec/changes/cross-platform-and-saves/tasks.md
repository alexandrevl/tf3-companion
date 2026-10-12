# Tasks

## 1. Game discovery

- [x] 1.1 Implement `discovery.py` (D1) with injectable platform/env/home/registry and regression cases for Windows registry/default paths, macOS, Linux native/Flatpak, ambiguous accounts, overrides and searched-path failures.
- [x] 1.2 Wire `paths.py` to discovery, preserve existing single-store and request/snapshot paths, and remove macOS-only selection.
- [x] 1.3 Run the discovery regression suite after integration.
- [ ] 1.4 Validate Windows/Linux game layout with native players and rehearse authorized macOS game activation/status.

## 2. Mod bundling and installation

- [x] 2.1 Configure wheel-only hatch `force-include` to `tf3companion/_mod/` and a source-checkout resource fallback.
- [x] 2.2 Implement safe `install_mod(paths)` and `uninstall_mod(paths)` APIs with reload instructions; remove `scripts/install-mod.sh`; add isolated-folder, preservation, symlink and failed-copy regression cases.
- [x] 2.3 Implement read-only structured `doctor()` independent of `Companion` and game installation; report game discovery, revisions, snapshots, logs, knowledge and single-store limitations.
- [x] 2.4 Verify integrated CLI commands and preservation regressions; build, inspect and exercise bundled assets from a wheel outside the checkout.
- [ ] 2.5 Rehearse the native installer and bridge activation with player-controlled real saves on Windows and macOS.

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
- [ ] 6.2 In-game check: reinstall with `uv run tf3c mod install`, reload the intended test save, run `uv run tf3c config snapshots-per-year 12` and `uv run tf3c refresh`; verify schema 2, verified lineage and company name, same-save routing, and `tf3c doctor` exit status.
- [ ] 6.3 Run `uv run pytest` green and commit
