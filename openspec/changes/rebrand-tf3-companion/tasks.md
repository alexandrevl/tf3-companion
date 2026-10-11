# Tasks

## 1. Package rename and paths

- [x] 1.1 Rename the package, paths module, service and CLI; update package metadata and MCP configuration. Verified by `uv sync` and `uv run tf3c --help`.
- [x] 1.2 Implement platform user-data paths and environment overrides. Verified by the passing environment/database behavior test.
- [x] 1.3 Use the renamed snapshot and request paths. Verified by ingestion and refresh behavior tests.

## 2. English everywhere

- [x] 2.1 Translate maintained comments, descriptions, errors and CLI help; accent/old-brand search across source, mod, tests and guides returned no matches.
- [x] 2.2 Add stable finding codes and English categories/messages; behavior tests pass.
- [x] 2.3 Reject unsupported newer snapshot schemas without blocking other ingestion; regression passes.
- [ ] 2.4 Verify actual OS-default opening on macOS and Windows. The helper is implemented and XLSX generation succeeds; GUI opening remains unverified.

## 3. Knowledge and notes

- [x] 3.1 Package the four translated knowledge topics; heading counts remain 14/11/6/4 and a real MCP client retrieved the topic list and mechanics content.
- [x] 3.2 Add dated notes through CLI/MCP; append/history behavior tests pass.

## 4. Mod rename and single sink

- [x] 4.1 Rename bridge directories and registrations; use English-only metadata with Alexandre Lima credit. Old-brand search returned no maintained-source matches.
- [x] 4.2 Remove unsupported sinks and use `[tf3c]` and the new paths. Both Lua files parsed successfully with an isolated Lupa runtime.
- [x] 4.3 Update the installer and log filter. Installer exercised successfully against temporary userdata, without modifying the live installation.

## 5. Repository docs

- [x] 5.1 Write English contributor and user guides and MCP analyst instructions; real stdio initialization and tool calls succeeded with 21 registered tools.
- [x] 5.2 Explicit staged-file inspection excludes databases, snapshots and private notes; original data remains as an ignored local backup.

## 6. Migration and verification

- [x] 6.1 Copy the database safely and preserve original files; import remaining prototype snapshots without deleting them. CLI status reports 20 snapshots through 1983-07-17. Private notes and original knowledge backups live outside the repository.
- [ ] 6.2 Player-controlled live cutover: enable only the renamed bridge, reload/save and verify fresh snapshot plus `[tf3c]` log. The installed prototype remains untouched.
- [ ] 6.3 Commit locally after validation. Observed: 35 passing tests, real CLI status/overview/XLSX, MCP status/knowledge/findings, isolated mod install, and Lua syntax. No remote or publication.
