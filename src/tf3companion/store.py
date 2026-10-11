"""SQLite persistence: snapshot history, time series and the decision journal."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .snapshot import Snapshot, snapshot_files

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
"""

DECISION_STATUSES = ("planned", "done", "dropped")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- snapshots ---------------------------------------------------------------
    def add_snapshot(self, snap: Snapshot, source_mtime: float = 0.0) -> None:
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
        """Import new or rewritten snapshot files; then delete all but the newest `keep_files` imported files."""
        result = IngestResult(ingested=[], skipped=[], failed={}, pruned=[])
        files = snapshot_files(folders)
        for path in files:
            mtime = path.stat().st_mtime
            if self._is_imported(path.name, mtime):
                result.skipped.append(path.name)
                continue
            try:
                snap = Snapshot.from_file(path)
            except Exception as exc:  # malformed or partially written file
                result.failed[path.name] = str(exc)
                continue
            self.add_snapshot(snap, mtime)
            result.ingested.append(path.name)
        imported = [p for p in files if p.name not in result.failed]
        for path in imported[: max(len(imported) - keep_files, 0)]:
            path.unlink()
            result.pruned.append(path.name)
        return result

    def _is_imported(self, source_file: str, mtime: float) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM snapshots WHERE source_file = ? AND source_mtime = ?", (source_file, mtime)
        ).fetchone()
        return row is not None

    def latest(self, offset: int = 0) -> Snapshot | None:
        """Most recent snapshot by ingestion order (offset=1 → the one before)."""
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots ORDER BY ingested_at DESC, game_time DESC LIMIT 1 OFFSET ?",
            (offset,),
        ).fetchone()
        if row is None:
            return None
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"])

    def latest_with_catalog(self) -> Snapshot | None:
        """Most recent snapshot that carries a vehicle catalog (written on start/request snapshots only)."""
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots WHERE data LIKE '%\"catalog\": [{%' "
            "ORDER BY game_time DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"])

    def previous_of(self, snap: Snapshot) -> Snapshot | None:
        """The snapshot with the greatest game time before `snap` (same timeline assumption)."""
        row = self.conn.execute(
            "SELECT data, source_file FROM snapshots WHERE game_time < ? ORDER BY game_time DESC LIMIT 1",
            (snap.game_time,),
        ).fetchone()
        if row is None:
            return None
        return Snapshot(raw=json.loads(row["data"]), source=row["source_file"])

    def snapshot_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

    def company_history(self, limit: int = 24) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT game_time, date_label, balance, loan, lines, vehicles FROM snapshots
               ORDER BY game_time DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def line_history(self, line_id: int, limit: int = 24) -> list[dict[str, Any]]:
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
        if status is not None and status not in DECISION_STATUSES:
            raise ValueError(f"status must be one of {DECISION_STATUSES}")
        query = "SELECT id FROM decisions" + (" WHERE status = ?" if status else "") + " ORDER BY id DESC LIMIT ?"
        params: tuple = (status, limit) if status else (limit,)
        return [self.get_decision(r["id"]) for r in self.conn.execute(query, params).fetchall()]
