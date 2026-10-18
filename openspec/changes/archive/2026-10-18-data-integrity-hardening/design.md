# Design: Data Integrity Hardening

## Architecture Decisions

### 1. File Stability and Safe Pruning
When reading snapshots from `folders`:
- Read files and capture their filesystem metadata (`st_dev`, `st_ino`, `st_size`, `st_mtime_ns`, `st_ctime_ns`).
- If metadata changes between pre-read and post-read, fail the file and leave it untouched for the next round.
- Maintain an `imported_files` table in SQLite (`source_path`, `content_hash`, `game_time`).
- Pruning selects only successfully imported files outside the `keep_files` window. Before unlinking, it verifies that the file metadata and SHA-256 hash match the imported state exactly. Any discrepancy aborts deletion and records a failure.
- Files that failed parsing or validation are NEVER added to the pruning list.

### 2. Colliding Filenames
- If two folders contain files with the same basename (e.g. `tf3c_snap_000000000001000.lua`), keys in `IngestResult` use resolved absolute paths for duplicates, preventing dict key collision in `failed`.

### 3. Fail-Closed Save Identity
- The store is explicitly single-save.
- If a snapshot carries `meta.saveId`, it is checked against existing snapshots in the database.
- If the store already contains snapshots and the incoming snapshot has a differing `saveId` (or mixes an identified save with legacy un-identified snapshots), `add_snapshot` raises a `ValueError` rather than overwriting or merging histories.
- Automatic routing based on town hashes is strictly avoided.

### 4. Lua Data Security and Correctness
- `luadata` rejects duplicate keys in table literals (which can silently overwrite earlier fields and mask bugs).
- Rejects non-data table keys (tables, NaN).
- Traps parser recursion / indexing exceptions and converts them to `LuaDataError`.

### 5. Reporting History Query APIs
- `snapshots(year: int | None = None) -> list[Snapshot]`: Chronological list.
- `snapshots_for_year(year: int) -> list[Snapshot]`: Chronological list for a specific calendar or game year.
- `available_years() -> list[int]`: Sorted distinct list of years present.
- `latest_before(game_time: int) -> Snapshot | None`: Strict predecessor (`< game_time`).
- `snapshot_at_or_before(game_time: int) -> Snapshot | None`: Non-strict predecessor (`<= game_time`).
- `recent_snapshots(limit: int = 24) -> list[Snapshot]`: Chronological slice of the newest `limit` snapshots.
- `latest_with_catalog(game_time: int | None = None) -> Snapshot | None`: Filters by non-empty catalog, optionally bounded by `<= game_time`.
- All query bounds strictly validate that values are non-boolean, non-negative integers up to `2**63 - 1`.
