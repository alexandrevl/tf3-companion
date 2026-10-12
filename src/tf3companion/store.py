"""SQLite persistence: snapshot history, time series and the decision journal."""

from __future__ import annotations

import json
from collections import Counter
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        try:
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.executescript(SCHEMA)
        except BaseException:
            self.conn.close()
            raise

    def close(self) -> None:
        self.conn.close()

    # ---- snapshots ---------------------------------------------------------------
    def add_snapshot(self, snap: Snapshot, source_mtime: float = 0.0) -> None:
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

    # ---- decision journal --------------------------------------------------------
    def add_decision(
        self, title: str, rationale: str, entities: list[Any] | None = None, snapshot: Snapshot | None = None
    ) -> dict[str, Any]:
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
