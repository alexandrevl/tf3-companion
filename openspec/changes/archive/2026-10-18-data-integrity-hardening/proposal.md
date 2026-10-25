# Data Integrity Hardening

## Why
Analysis of ingestion, parsing, and storage revealed several real-world data corruption and safety failure modes:
1. Snapshot file deletion during pruning could race against game rewrites or unverified/failed files, permanently losing simulation history.
2. If multiple folder roots or colliding filenames appeared, error maps collapsed and pruning could delete untracked files.
3. Lua loading lacked guards against duplicate keys, invalid UTF-8 escapes, recursion limits, or non-data expressions.
4. Snapshot model accepted negative/invalid integers and unbounded types that later corrupted SQLite queries or triggered database crashes.
5. Ingestion implicitly allowed mixed save timelines or foreign saves to overwrite existing snapshots with identical game times.
6. Downstream reports lacked chronological querying and time-bounded vehicle catalog lookup primitives, risking ad-hoc raw queries.

## What Changes
- **luadata**: Enforces strict data evaluation, validates table keys (rejecting duplicates, nested tables, NaN), and wraps parser exceptions in `LuaDataError`.
- **snapshot**: Validates `schemaVersion` (supported positive integers <= 1), 64-bit integer ranges for time and IDs, unique entity IDs, valid calendar dates, and safe filenames.
- **store**:
  - Tracks file content digests via an additive `imported_files` table, preserving full backward compatibility with legacy `companion.db` files.
  - Verifies read file stability and refuses to prune files whose signatures or contents mutated after import.
  - Retains all malformed, partial, or conflicting files; never deletes failed ingestion targets.
  - Rejects foreign `saveId` values from being written to a store holding another save's history, fail-closed without claiming automatic save isolation.
  - Rejects differing contents at a shared game time across source paths. A verified rewrite of the same source path can replace its prior sample.
  - Adds strictly validated reporting history APIs: `snapshots_for_year`, `available_years`, `snapshots`, `latest_before`, `snapshot_at_or_before`, `recent_snapshots`, and optional `game_time` bound on `latest_with_catalog`.
  - Rejects negative or non-integer query bounds to avoid SQL driver or semantics errors.

## Capabilities

### New Capabilities
- `import-integrity`: Verified receipts, strict data boundaries, identified-lineage conflicts, and chronological/time-bounded history queries.

## Impact
- Files: `src/tf3companion/luadata.py`, `src/tf3companion/snapshot.py`, `src/tf3companion/store.py`, `tests/test_luadata.py`, `tests/test_store.py`.
- Migration: Seamless. Schema adds `imported_files` if absent. Old databases continue working with no manual data conversion required.
- Isolation: Explicitly does NOT guess save identity from towns or other heuristics. A distinct `saveId` fails closed rather than silently mixing.
