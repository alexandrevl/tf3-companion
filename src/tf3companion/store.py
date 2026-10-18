"""SQLite persistence: snapshot history, time series and the decision journal."""

from __future__ import annotations

import json
import re
from collections import Counter
import hashlib
import sqlite3
from collections.abc import Collection
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .snapshot import Snapshot, snapshot_files
from . import luadata

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    game_time    INTEGER PRIMARY KEY,
    date_label   TEXT NOT NULL,
    reason       TEXT,
    request_id   INTEGER,
    source_file  TEXT NOT NULL,
    source_mtime REAL NOT NULL,
    ingested_at  TEXT NOT NULL,
    balance      INTEGER,
    loan         INTEGER,
    lines        INTEGER,
    vehicles     INTEGER,
    errors       INTEGER,
    data         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS line_history (
    game_time        INTEGER NOT NULL REFERENCES snapshots(game_time) ON DELETE CASCADE,
    line_id          INTEGER NOT NULL,
    name             TEXT,
    profit_year      INTEGER,
    transported_year INTEGER,
    rate             INTEGER,
    vehicles         INTEGER,
    PRIMARY KEY (game_time, line_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    game_time   INTEGER,
    game_date   TEXT,
    title       TEXT NOT NULL,
    rationale   TEXT NOT NULL,
    entities    TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'done', 'dropped')),
    outcome     TEXT
);
CREATE TABLE IF NOT EXISTS imported_files (
    source_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    game_time INTEGER NOT NULL
);
"""

FETCH_BATCH = 256
DECISION_STATUSES = ("planned", "done", "dropped")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _nonnegative_integer(value: int, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(f"{name} must be a nonnegative 64-bit integer")


@dataclass
class IngestResult:
    ingested: list[str]
    skipped: list[str]
    failed: dict[str, str]
    pruned: list[str]


class Store:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        """Open (and create or complete) the store, or with `read_only` open an existing supported one as is.

        A read-only store uses a SQLite read-only connection: no directory, database, schema or
        migration is ever created, and every writing method fails before any side effect.
        """
        self.path = path
        self.read_only = read_only
        self._view_depth = 0
        if read_only:
            if not Path(path).is_file():
                raise LookupError(f"No companion database at {path}. Import evidence first: run `tf3c ingest` "
                                  "(or `tf3c refresh` with the game open); stored-only commands never create it.")
            self.conn = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
        else:
            self.conn = sqlite3.connect(path)
        try:
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            if read_only:
                self._require_supported_schema()
            else:
                self.conn.executescript(SCHEMA)
        except BaseException:
            self.conn.close()
            raise

    def _require_supported_schema(self) -> None:
        expected = sqlite3.connect(":memory:")
        try:
            expected.executescript(SCHEMA)
            wanted = {t: {r[1] for r in expected.execute(f"PRAGMA table_info({t})")}
                      for (t,) in expected.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            expected.close()
        try:
            actual = {t: {r[1] for r in self.conn.execute(f"PRAGMA table_info({t})")} for t in wanted}
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{self.path} is not a readable companion database ({exc}).") from exc
        problems = [f"{t} ({'missing' if not actual[t] else 'missing columns ' + ', '.join(sorted(cols - actual[t]))})"
                    for t, cols in sorted(wanted.items()) if not cols <= actual[t]]
        if problems:
            raise ValueError(f"Unsupported companion database schema at {self.path}: {'; '.join(problems)}. "
                             "Stored-only commands never migrate or repair it; open it once with a writable "
                             "command such as `tf3c ingest`, or use a separate data directory.")

    def _require_writable(self) -> None:
        if self.read_only:
            raise ValueError("This store was opened read-only for stored-only evaluation; it cannot be modified.")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def read_view(self) -> Iterator[None]:
        """One consistent read transaction: selection and every evidence read see the same committed state.

        Nested views join the outer one. Without WAL a concurrent writer waits for the view to close
        (SQLite's busy timeout); in WAL mode it commits and the view keeps its earlier state. Callers
        end the view before writing report files.
        """
        if self._view_depth:
            self._view_depth += 1
            try:
                yield
            finally:
                self._view_depth -= 1
            return
        self.conn.execute("BEGIN")
        try:
            self.conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()  # takes the read snapshot
            self._view_depth = 1
            yield
        finally:
            self._view_depth = 0
            self.conn.rollback()

    # ---- snapshots ---------------------------------------------------------------
    def time_context(self, snapshot: Snapshot):
        """Read compact calendar anchors without changing stored evidence.

        Legacy merges/overwrites without a surviving identity or rewind trace cannot
        be detected; monotone history is never proof of save/branch isolation.
        """
        from .game_time import GameCalendarClock
        rows = self.conn.execute(
            "SELECT game_time, ingested_at, json_extract(data, '$.meta.date') AS date, "
            "json_extract(data, '$.meta.saveId') AS save_id FROM snapshots "
            "WHERE game_time <= ? ORDER BY ingested_at, game_time",
            (snapshot.game_time,),
        ).fetchall()
        samples = [{"gameTime": r["game_time"],
                    "date": json.loads(r["date"]) if r["date"] else None,
                    "saveId": r["save_id"]} for r in rows]
        if not any(s["gameTime"] == snapshot.game_time for s in samples):
            samples.append({"gameTime": snapshot.game_time, "date": snapshot.date,
                            "saveId": snapshot.meta.get("saveId")})
        chronology = self.conn.execute(
            "SELECT game_time, (SELECT MAX(game_time) FROM snapshots) AS max_tick "
            "FROM snapshots ORDER BY ingested_at DESC, game_time DESC LIMIT 1"
        ).fetchone()
        rewind = bool(chronology and chronology["game_time"] < chronology["max_tick"])
        return GameCalendarClock.from_samples(samples, context={
            "selectedTick": snapshot.game_time, "saveId": snapshot.meta.get("saveId"),
            "isolation": "legacy-unverified", "ambiguous": rewind,
        })

    def calendar_baseline(self, snapshot: Snapshot) -> Snapshot | None:
        """Latest dated observation at least 365.25 calendar days before evaluation."""
        from .game_time import calendar_ordinal, DAYS_PER_YEAR
        clock = self.time_context(snapshot)
        ordinal = calendar_ordinal(snapshot.date)
        if clock.ambiguous or ordinal is None:
            return None
        eligible = [tick for tick, day in clock.anchors if day <= ordinal - DAYS_PER_YEAR]
        return self.snapshot_at_or_before(int(max(eligible))) if eligible else None

    def add_snapshot(self, snap: Snapshot, source_mtime: float = 0.0) -> None:
        self._require_writable()
        existing = self.conn.execute("SELECT data FROM snapshots LIMIT 1").fetchone()
        if existing is not None:
            save_id = json.loads(existing["data"]).get("meta", {}).get("saveId")
            if save_id != snap.meta.get("saveId"):
                raise ValueError("single-store save identity mismatch; use a separate data directory "
                                 "for each save, and explicitly migrate legacy history")
        company = snap.company
        with self.conn:
            self.conn.execute("DELETE FROM snapshots WHERE game_time = ?", (snap.game_time,))
            self.conn.execute(
                """INSERT INTO snapshots (game_time, date_label, reason, request_id, source_file, source_mtime,
                                          ingested_at, balance, loan, lines, vehicles, errors, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snap.game_time,
                    snap.date_label,
                    snap.meta.get("reason"),
                    snap.meta.get("requestId"),
                    snap.source,
                    source_mtime,
                    _now(),
                    company.get("balance"),
                    company.get("loan"),
                    len(snap.lines),
                    len(snap.vehicles),
                    len(snap.errors),
                    json.dumps(snap.raw, ensure_ascii=False),
                ),
            )
            self.conn.executemany(
                """INSERT INTO line_history (game_time, line_id, name, profit_year, transported_year, rate, vehicles)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        snap.game_time,
                        line["id"],
                        line.get("name"),
                        line.get("profitYear"),
                        line.get("transportedYear"),
                        line.get("rate"),
                        len(line.get("vehicles") or []),
                    )
                    for line in snap.lines
                ],
            )

    def ingest_folders(self, folders: list[Path], keep_files: int = 10) -> IngestResult:
        """Import stable files; prune only unchanged files with committed content receipts."""
        self._require_writable()
        _nonnegative_integer(keep_files, "keep_files")
        result = IngestResult(ingested=[], skipped=[], failed={}, pruned=[])
        files = snapshot_files(folders)
        name_counts = Counter(p.name for p in files)
        duplicate_names = {name for name, count in name_counts.items() if count > 1}
        imported: list[tuple[Path, str, tuple]] = []
        for path in files:
            label = str(path) if path.name in duplicate_names else path.name
            try:
                before = path.stat()
                content = path.read_bytes()
                after = path.stat()
                signature = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                if signature != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns):
                    raise ValueError("snapshot changed while being read; retry ingestion")
                digest = hashlib.sha256(content).hexdigest()
                receipt = self.conn.execute(
                    "SELECT content_hash, game_time FROM imported_files WHERE source_path = ?", (str(path),)
                ).fetchone()
                snap = Snapshot(raw=luadata.loads(content.decode("utf-8")), source=path.name)
                if snap.game_time != int(path.stem.removeprefix("tf3c_snap_")):
                    raise ValueError("snapshot filename does not match meta.gameTime")
                stored = self.conn.execute("SELECT data FROM snapshots WHERE game_time = ?", (snap.game_time,)).fetchone()
                same_data = stored is not None and json.loads(stored["data"]) == snap.raw
                if receipt is not None and receipt["content_hash"] == digest and same_data:
                    result.skipped.append(label)
                else:
                    other = self.conn.execute(
                        "SELECT source_path FROM imported_files WHERE game_time = ? AND source_path != ?",
                        (snap.game_time, str(path)),
                    ).fetchone()
                    if other is not None and not same_data:
                        raise ValueError("conflicting snapshots share a game time; use separate data directories")
                    with self.conn:
                        if not same_data:
                            self.add_snapshot(snap, after.st_mtime)
                        self.conn.execute(
                            "INSERT OR REPLACE INTO imported_files VALUES (?, ?, ?)",
                            (str(path), digest, snap.game_time),
                        )
                    result.ingested.append(label)
                imported.append((path, digest, signature))
            except Exception as exc:  # preserve malformed, partial and conflicting inputs
                result.failed[label] = str(exc)
        for path, digest, signature in imported[:max(len(imported) - keep_files, 0)]:
            label = str(path) if path.name in duplicate_names else path.name
            if path.name in duplicate_names and any(str(p) in result.failed for p in files if p.name == path.name):
                continue
            try:
                stat = path.stat()
                current = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                if current != signature or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError("snapshot changed before pruning; file retained")
                path.unlink()
                result.pruned.append(label)
            except OSError as exc:
                result.failed[label] = str(exc)
            except ValueError as exc:
                result.failed[label] = str(exc)
        return result

    def latest(self, offset: int = 0) -> Snapshot | None:
        """Most recent snapshot by ingestion order (offset=1 → the one before)."""
        _nonnegative_integer(offset, "offset")
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots ORDER BY ingested_at DESC, game_time DESC LIMIT 1 OFFSET ?",
            (offset,),
        ).fetchone()
        if row is None:
            return None
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"])

    def latest_with_catalog(self, game_time: int | None = None) -> Snapshot | None:
        """Newest catalog at or before an optional game time."""
        if game_time is not None:
            _nonnegative_integer(game_time, "game_time")
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots WHERE json_array_length(data, '$.catalog') > 0 "
            + ("AND game_time <= ? " if game_time is not None else "")
            + "ORDER BY game_time DESC LIMIT 1",
            (game_time,) if game_time is not None else (),
        ).fetchone()
        if row is None:
            return None
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"])

    def previous_of(self, snap: Snapshot) -> Snapshot | None:
        return self.latest_before(snap.game_time)

    def latest_before(self, game_time: int) -> Snapshot | None:
        _nonnegative_integer(game_time, "game_time")
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots WHERE game_time < ? ORDER BY game_time DESC LIMIT 1",
            (game_time,),
        ).fetchone()
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"]) if row else None

    def snapshot_at_or_before(self, game_time: int) -> Snapshot | None:
        _nonnegative_integer(game_time, "game_time")
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots WHERE game_time <= ? ORDER BY game_time DESC LIMIT 1",
            (game_time,),
        ).fetchone()
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"]) if row else None

    def snapshots(self, year: int | None = None) -> list[Snapshot]:
        if year is not None:
            _nonnegative_integer(year, "year")
        rows = self.conn.execute("SELECT data, source_file FROM snapshots ORDER BY game_time").fetchall()
        snapshots = [Snapshot(raw=json.loads(r["data"]), source=r["source_file"]) for r in rows]
        return [s for s in snapshots if year is None or (s.date or {}).get("year", s.meta.get("year")) == year]

    def snapshots_for_year(self, year: int) -> list[Snapshot]:
        _nonnegative_integer(year, "year")
        return self.snapshots(year)

    def available_years(self) -> list[int]:
        return sorted({year for s in self.snapshots()
                       if type(year := (s.date or {}).get("year", s.meta.get("year"))) is int})

    def recent_snapshots(self, limit: int = 24, game_time: int | None = None) -> list[Snapshot]:
        _nonnegative_integer(limit, "limit")
        if game_time is not None:
            _nonnegative_integer(game_time, "game_time")
        rows = self.conn.execute(
            "SELECT data, source_file FROM snapshots "
            + ("WHERE game_time <= ? " if game_time is not None else "")
            + "ORDER BY game_time DESC LIMIT ?",
            (game_time, limit) if game_time is not None else (limit,),
        ).fetchall()
        return [Snapshot(raw=json.loads(r["data"]), source=r["source_file"]) for r in reversed(rows)]

    def snapshot_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

    def company_history(self, limit: int = 24) -> list[dict[str, Any]]:
        _nonnegative_integer(limit, "limit")
        rows = self.conn.execute(
            """SELECT game_time, date_label, balance, loan, lines, vehicles FROM snapshots
               ORDER BY game_time DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def line_history(self, line_id: int, limit: int = 24) -> list[dict[str, Any]]:
        _nonnegative_integer(limit, "limit")
        rows = self.conn.execute(
            """SELECT h.game_time, s.date_label, h.name, h.profit_year, h.transported_year, h.rate, h.vehicles
               FROM line_history h JOIN snapshots s USING (game_time)
               WHERE h.line_id = ? ORDER BY h.game_time DESC LIMIT ?""",
            (line_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ---- compact endpoint-bounded projections -------------------------------------
    def _stream(self, sql: str, params: tuple) -> Iterator[sqlite3.Row]:
        """Rows in fetch batches of FETCH_BATCH; the cursor never materialises the whole result."""
        cursor = self.conn.execute(sql, params)
        while rows := cursor.fetchmany(FETCH_BATCH):
            yield from rows

    def count_samples(self, endpoint: int) -> int:
        """Stored samples at or before the endpoint tick."""
        _nonnegative_integer(endpoint, "endpoint")
        return self.conn.execute("SELECT COUNT(*) FROM snapshots WHERE game_time <= ?", (endpoint,)).fetchone()[0]

    def iter_sample_index(self, endpoint: int) -> Iterator[tuple[int, str, dict[str, Any] | None]]:
        """(game_time, date_label, meta.date) of every sample at or before the endpoint, oldest first."""
        _nonnegative_integer(endpoint, "endpoint")
        for row in self._stream("SELECT game_time, date_label, json_extract(data, '$.meta.date') AS date FROM snapshots "
                                "WHERE game_time <= ? ORDER BY game_time", (endpoint,)):
            yield row["game_time"], row["date_label"], json.loads(row["date"]) if row["date"] else None

    def iter_company_points(self, endpoint: int) -> Iterator[dict[str, Any]]:
        """Company counters of every sample at or before the endpoint, oldest first."""
        _nonnegative_integer(endpoint, "endpoint")
        for row in self._stream("SELECT game_time, date_label, balance, loan, lines, vehicles, errors FROM snapshots "
                                "WHERE game_time <= ? ORDER BY game_time", (endpoint,)):
            yield dict(row)

    def iter_line_points(self, endpoint: int, line_id: int | None = None) -> Iterator[dict[str, Any]]:
        """Stored per-line series rows at or before the endpoint, ordered by line then time."""
        _nonnegative_integer(endpoint, "endpoint")
        where, params = ("h.game_time <= ?", (endpoint,)) if line_id is None else ("h.game_time <= ? AND h.line_id = ?", (endpoint, line_id))
        for row in self._stream(
                "SELECT h.line_id, h.game_time, s.date_label, h.name, h.profit_year, h.transported_year, h.rate, h.vehicles "
                f"FROM line_history h JOIN snapshots s USING (game_time) WHERE {where} ORDER BY h.line_id, h.game_time", params):
            yield dict(row)

    def iter_projection(self, endpoint: int, keys: tuple[str, ...],
                        ticks: Collection[int] | None = None) -> Iterator[tuple[int, str, dict[str, Any]]]:
        """(game_time, date_label, {top-level key: value}) at or before the endpoint, one source row parsed at a time.

        SQLite extracts only the requested top-level keys, so no whole raw snapshot is hydrated.
        Missing keys are absent from the mapping. With `ticks`, only those samples are visited.
        """
        _nonnegative_integer(endpoint, "endpoint")
        for key in keys:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key):
                raise ValueError(f"unsupported projection key {key!r}")
        columns = "".join(f", json_extract(data, '$.{key}') AS k{i}" for i, key in enumerate(keys))
        for row in self._stream(f"SELECT game_time, date_label{columns} FROM snapshots WHERE game_time <= ? ORDER BY game_time",
                                (endpoint,)):
            if ticks is not None and row["game_time"] not in ticks:
                continue
            yield row["game_time"], row["date_label"], {key: json.loads(row[f"k{i}"]) for i, key in enumerate(keys)
                                                       if row[f"k{i}"] is not None}

    def hydrate(self, game_time: int) -> Snapshot | None:
        """Full snapshot at exactly this tick, or None."""
        _nonnegative_integer(game_time, "game_time")
        row = self.conn.execute("SELECT data, source_file FROM snapshots WHERE game_time = ?", (game_time,)).fetchone()
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"]) if row else None

    # ---- decision journal --------------------------------------------------------
    def add_decision(
        self, title: str, rationale: str, entities: list[Any] | None = None, snapshot: Snapshot | None = None
    ) -> dict[str, Any]:
        self._require_writable()
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO decisions (created_at, game_time, game_date, title, rationale, entities)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    _now(),
                    snapshot.game_time if snapshot else None,
                    snapshot.date_label if snapshot else None,
                    title,
                    rationale,
                    json.dumps(entities or [], ensure_ascii=False),
                ),
            )
        return self.get_decision(cur.lastrowid)

    def get_decision(self, decision_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            raise KeyError(f"decision {decision_id} not found")
        out = dict(row)
        out["entities"] = json.loads(out["entities"])
        return out

    def update_decision(self, decision_id: int, status: str, outcome: str | None = None) -> dict[str, Any]:
        if status not in DECISION_STATUSES:
            raise ValueError(f"status must be one of {DECISION_STATUSES}")
        self.get_decision(decision_id)
        self._require_writable()
        with self.conn:
            self.conn.execute(
                "UPDATE decisions SET status = ?, outcome = COALESCE(?, outcome) WHERE id = ?",
                (status, outcome, decision_id),
            )
        return self.get_decision(decision_id)

    def list_decisions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        _nonnegative_integer(limit, "limit")
        if status is not None and status not in DECISION_STATUSES:
            raise ValueError(f"status must be one of {DECISION_STATUSES}")
        query = "SELECT id FROM decisions" + (" WHERE status = ?" if status else "") + " ORDER BY id DESC LIMIT ?"
        params: tuple = (status, limit) if status else (limit,)
        return [self.get_decision(r["id"]) for r in self.conn.execute(query, params).fetchall()]

    # ---- history family projection (SQL-side compaction) --------------------------
    def iter_history_points(self, endpoint: int) -> Iterator[dict[str, Any]]:
        """Per-sample company counters and entity membership at or before the endpoint, oldest first.

        SQLite extracts only the compact fields (integer counters, station count, id/name/carrier/value/
        purchase of lines and vehicles, errors) so no whole raw snapshot is parsed; rows arrive in batches.
        """
        _nonnegative_integer(endpoint, "endpoint")

        def integer(path: str, root: str = "data") -> str:
            return f"CASE WHEN json_type({root}, '{path}') = 'integer' THEN json_extract({root}, '{path}') END"

        sql = (
            "SELECT game_time, date_label, json_extract(data, '$.meta.date') AS date, "
            "json_extract(data, '$.meta.reason') AS reason, "
            f"{integer('$.meta.yearDuration')} AS year_duration, "
            f"{integer('$.company.balance')} AS balance, {integer('$.company.loan')} AS loan, "
            f"{integer('$.company.earnings')} AS earnings, {integer('$.company.value.totalScore')} AS score, "
            f"{integer('$.company.value.trackTotalLength')} AS track, "
            f"{integer('$.company.passengersTransported')} AS passengers, "
            f"{integer('$.company.cargoTransported')} AS cargo, "
            "(SELECT COUNT(*) FROM json_each(data, '$.stations')) AS stations, "
            "(SELECT json_group_array(json_object('id', json_extract(e.value, '$.id'), "
            "'name', json_extract(e.value, '$.name'), "
            f"'profit', {integer('$.profitYear', 'e.value')})) FROM json_each(data, '$.lines') AS e) AS lines, "
            "(SELECT json_group_array(json_object('id', json_extract(e.value, '$.id'), "
            "'name', json_extract(e.value, '$.name'), 'carrier', json_extract(e.value, '$.carrier'), "
            f"'value', {integer('$.value', 'e.value')}, 'purchase', {integer('$.purchaseTime', 'e.value')})) "
            "FROM json_each(data, '$.vehicles') AS e) AS vehicles, "
            "json_extract(data, '$.errors') AS errors "
            "FROM snapshots WHERE game_time <= ? ORDER BY game_time")
        for row in self._stream(sql, (endpoint,)):
            out = dict(row)
            for key in ("date", "lines", "vehicles", "errors"):
                out[key] = json.loads(out[key]) if isinstance(out[key], str) else None
            yield out
