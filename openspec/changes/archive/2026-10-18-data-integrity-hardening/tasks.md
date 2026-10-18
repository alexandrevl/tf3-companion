# Tasks: Data Integrity Hardening

## Implementation and Verification

- [x] Hardened Lua data subset parser (`src/tf3companion/luadata.py`) against duplicate table keys, NaN keys, and malformed escape sequences.
- [x] Enforced strict metadata and section schema validation in `Snapshot` (`src/tf3companion/snapshot.py`), including non-negative 64-bit integer IDs and calendar bounds.
- [x] Created backward-compatible `imported_files` table in SQLite (`src/tf3companion/store.py`) to store content digests and enforce safe pruning.
- [x] Implemented race-resistant ingestion reading: files undergoing modification during read or pruning are skipped/preserved.
- [x] Enforced fail-closed save identity validation in `Store.add_snapshot` to prevent corrupting legacy or foreign save histories.
- [x] Added safe chronological history query APIs to `Store` for reporting (`snapshots`, `snapshots_for_year`, `available_years`, `latest_before`, `snapshot_at_or_before`, `recent_snapshots`, `latest_with_catalog`).
- [x] Implemented non-negative integer parameter validation across all Store querying APIs.
- [x] Added unit and regression tests in `tests/test_luadata.py` and `tests/test_store.py`.
