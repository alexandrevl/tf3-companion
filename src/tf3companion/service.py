"""Application service shared by the CLI and the MCP server."""

from __future__ import annotations

import math
from collections import deque
from contextlib import contextmanager
import tempfile
import os
import sys
from importlib.resources import files
import subprocess
import time
from pathlib import Path
from typing import Any

from . import analysis, luadata
from .paths import Paths, load_paths
from .export import export_workbook
from .snapshot import Snapshot, snapshot_files
from .store import Store

LOG_PREFIX = "[tf3c]"


class NoSnapshotError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "No snapshot imported yet. Open the game with the mod enabled and call `refresh` (or `tf3c ingest`)."
        )


class Companion:
    def __init__(self, paths: Paths | None = None) -> None:
        self.paths = paths or load_paths()
        self.store = Store(self.paths.database)

    def close(self) -> None:
        self.store.close()

    # ---- data flow ---------------------------------------------------------------
    def ingest(self) -> dict[str, Any]:
        result = self.store.ingest_folders([self.paths.snapshot_folder])
        return {
            "ingested": result.ingested,
            "skipped": len(result.skipped),
            "failed": result.failed,
            "pruned": len(result.pruned),
        }

    def refresh(self, timeout_s: float = 30.0, poll_s: float = 1.0) -> dict[str, Any]:
        """Atomically request one snapshot, without overlapping other refresh writers."""
        if not math.isfinite(timeout_s) or not 0 < timeout_s <= 3600:
            raise ValueError("timeout must be finite and between 0 and 3600 seconds.")
        if not math.isfinite(poll_s) or poll_s <= 0:
            raise ValueError("poll interval must be finite and positive.")
        self.paths.snapshot_folder.mkdir(parents=True, exist_ok=True)
        with _refresh_lock(self.paths.request_file):
            request_id = time.time_ns() // 1_000_000
            _atomic_text(self.paths.request_file, luadata.dumps({"id": request_id}))
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                for path in reversed(snapshot_files([self.paths.snapshot_folder])):
                    try:
                        snap = Snapshot.from_file(path)
                    except (OSError, ValueError):
                        continue  # The game may still be writing this file.
                    if snap.meta.get("requestId") == request_id:
                        ingest = self.ingest()
                        if ingest["failed"]:
                            return {"ok": False, "requestId": request_id,
                                    "message": "The game answered but snapshot ingestion failed.",
                                    "ingest": ingest}
                        return {"ok": True, "date": snap.date_label, "file": path.name, "ingest": ingest}
                time.sleep(min(poll_s, max(0, deadline - time.monotonic())))
            return {
                "ok": False, "requestId": request_id,
                "message": "The game did not answer. Load a save with TF3 Companion Bridge enabled; inspect `tf3c log`.",
                "ingest": self.ingest(),
            }

    def _checked_ingest(self) -> None:
        ingest = self.ingest()
        if ingest["failed"]:
            raise ValueError(f"Some snapshots could not be imported: {ingest['failed']}. Inspect `tf3c status`; do not treat older data as current.")

    def current(self) -> Snapshot:
        self._checked_ingest()
        snap = self.store.latest()
        if snap is None:
            raise NoSnapshotError()
        return snap

    def _with_prev(self) -> tuple[Snapshot, Snapshot | None]:
        snap = self.current()
        return snap, self.store.previous_of(snap)

    # ---- queries -----------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        ingest = self.ingest()
        snap = self.store.latest()
        receipt = None if snap is None else self.store.conn.execute(
            "SELECT source_mtime FROM snapshots WHERE game_time = ?", (snap.game_time,)
        ).fetchone()
        modified = receipt["source_mtime"] if receipt and receipt["source_mtime"] > 0 else None
        return {
            "userdata": str(self.paths.userdata),
            "snapshotFolders": {str(self.paths.snapshot_folder): self.paths.snapshot_folder.is_dir()},
            "modInstalled": (self.paths.staging_area / "tf3_companion_bridge" / "mod.json").is_file(),
            "retainedFutureSnapshots": 0 if snap is None else self.store.conn.execute(
                "SELECT COUNT(*) FROM snapshots WHERE game_time > ?", (snap.game_time,)
            ).fetchone()[0],
            "database": str(self.paths.database),
            "snapshots": self.store.snapshot_count(),
            "lastIngest": ingest,
            "latest": None if snap is None else {
                "date": snap.date_label,
                "gameTime": snap.game_time,
                "ageSeconds": max(0, time.time() - modified) if modified is not None else None,
                "reason": snap.meta.get("reason"),
                "file": snap.source,
                "lines": len(snap.lines),
                "vehicles": len(snap.vehicles),
                "industries": len(snap.industries),
                "towns": len(snap.towns),
                "errors": snap.errors[:20],
            },
        }

    def overview(self) -> dict[str, Any]:
        snap, prev = self._with_prev()
        return analysis.company_overview(snap, prev)

    def lines(self, sort_by: str = "profitYear", limit: int = 50) -> list[dict[str, Any]]:
        _positive_limit(limit)
        snap = self.current()
        rows = [analysis.line_row(snap, line) for line in snap.lines]
        return _sorted(rows, sort_by)[:limit]

    def line_detail(self, ref: int | str) -> dict[str, Any]:
        snap = self.current()
        line = snap.find_line(ref)
        if line is None:
            candidates = [l.get("name") for l in snap.lines if str(ref).casefold() in (l.get("name") or "").casefold()]
            raise LookupError(f"Line '{ref}' not found. Candidates: {candidates[:10]}")
        stops = [
            {**stop, "linesAtStation": len(_station(snap, stop.get("stationGroup")).get("lines") or [])}
            for stop in line.get("stops") or []
        ]
        return {
            **analysis.line_row(snap, line),
            "stops": stops,
            "capacity": [{**c, "cargo": snap.cargo(c.get("cargo"))} for c in line.get("capacity") or []],
            "issues": [{**i, "cargo": snap.cargo(i.get("cargo"))} for i in line.get("issues") or []],
            "vehicleList": [analysis.vehicle_row(snap, v) for v in snap.line_vehicles(line)],
            "history": self.store.line_history(line["id"]),
        }

    def vehicles(self, filter: str = "all", line: int | str | None = None, sort_by: str = "profitYear", limit: int = 100) -> list[dict[str, Any]]:
        _positive_limit(limit)
        snap = self.current()
        items = snap.vehicles
        if line is not None:
            target = snap.find_line(line)
            if target is None:
                raise LookupError(f"Line '{line}' not found.")
            items = snap.line_vehicles(target)
        rows = [analysis.vehicle_row(snap, v) for v in items]
        if filter == "losing":
            rows = [r for r in rows if (r["profitYear"] or 0) < 0]
        elif filter == "problems":
            rows = [r for r in rows if r["noPath"] or r["userStopped"]]
        elif filter == "depot":
            rows = [r for r in rows if r["state"] in ("IN_DEPOT", "GOING_TO_DEPOT")]
        elif filter != "all":
            raise ValueError("filter: all | losing | problems | depot")
        return _sorted(rows, sort_by)[:limit]

    def industries(self, filter: str = "all", cargo: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        _positive_limit(limit)
        snap = self.current()
        rows = [analysis.industry_row(snap, i) for i in snap.industries]
        if cargo:
            needle = cargo.casefold()
            rows = [
                r for r in rows
                if any(needle in (f.get("cargo") or "").casefold() for f in r["inputs"] + r["outputs"])
            ]
        if filter == "closing":
            rows = [r for r in rows if r["closing"]]
        elif filter == "unserved":
            rows = [
                r for r in rows
                if any(0 < (f.get("producedYear") or 0) and (f.get("shippedYear") or 0) < 0.5 * f["producedYear"] for f in r["outputs"])
            ]
        elif filter != "all":
            raise ValueError("filter: all | unserved | closing")
        return rows[:limit]

    def towns(self, limit: int = 50) -> list[dict[str, Any]]:
        _positive_limit(limit)
        snap = self.current()
        rows = [analysis.town_row(t) for t in snap.towns]
        return _sorted(rows, "population")[:limit]

    def findings(self, category: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        if category is not None and category not in ("finance", "lines", "vehicles", "industries", "data"):
            raise ValueError("category must be finance, lines, vehicles, industries or data.")
        if severity is not None and severity not in ("high", "medium", "low"):
            raise ValueError("severity must be high, medium or low.")
        snap, prev = self._with_prev()
        items = analysis.findings(snap, prev)
        if category:
            items = [f for f in items if f.category == category]
        if severity:
            items = [f for f in items if f.severity == severity]
        return [f.to_dict() for f in items]

    def opportunities(self, limit: int = 20) -> list[dict[str, Any]]:
        _positive_limit(limit)
        return analysis.opportunities(self.current(), limit=limit)

    def company_history(self, limit: int = 24) -> list[dict[str, Any]]:
        _positive_limit(limit)
        self._checked_ingest()
        return self.store.company_history(limit)

    def stocks(self, kind: str | None = None, name: str | None = None, only_full: bool = False) -> list[dict[str, Any]]:
        """Stock levels at stations, industries and warehouses (fill = count / capacity)."""
        snap = self.current()
        rows = []
        for s in snap.stocks:
            cap = s.get("capacity") or 0
            count = s.get("count")
            rows.append({
                "kind": s.get("kind"), "owner": s.get("ownerName"), "ownerId": s.get("owner"),
                "stockId": s.get("stockId"), "cargos": [snap.cargo(c) for c in s.get("cargos") or []],
                "count": count, "capacity": cap,
                "fill": round(count / cap, 3) if count is not None and cap else None,
            })
        if kind:
            rows = [r for r in rows if r["kind"] == kind]
        if name:
            rows = [r for r in rows if name.casefold() in (r["owner"] or "").casefold()]
        if only_full:
            rows = [r for r in rows if (r["fill"] or 0) >= 0.9]
        return sorted(rows, key=lambda r: (r["fill"] is None, -(r["fill"] or 0)))

    def depots(self) -> list[dict[str, Any]]:
        snap = self.current()
        counts: dict[int, int] = {}
        for v in snap.vehicles:
            if v.get("state") in ("IN_DEPOT", "GOING_TO_DEPOT"):
                counts[v.get("depot")] = counts.get(v.get("depot"), 0) + 1
        return [{**d, "vehiclesInDepot": counts.get(d["id"], 0)} for d in snap.depots]

    def catalog(self, carrier: str | None = None, cargo: str | None = None, available_only: bool = True) -> dict[str, Any]:
        """Vehicle models available in the game year (plus those arriving within 10 years)."""
        current = self.current()
        snap = self.store.latest_with_catalog(current.game_time)
        if snap is None:
            raise LookupError("No catalog yet: call `refresh` (catalogs arrive in initial and requested snapshots).")
        rows = []
        for m in snap.catalog:
            year = current.meta.get("date", {}).get("year", current.meta.get("year"))
            start, end = m.get("yearFrom"), m.get("yearTo")
            available = year is not None and (start is None or start <= 0 or start <= year) and (end is None or end <= 0 or year < end)
            if available_only and not available:
                continue
            if carrier and m.get("carrier") != carrier.upper():
                continue
            caps = {snap.cargo(c["cargo"]): c["capacity"] for c in m.get("capacity") or []}
            if cargo and not any(cargo.casefold() in (k or "").casefold() for k in caps):
                continue
            rows.append({**{k: v for k, v in m.items() if k not in ("capacity", "id", "groupFileName")},
                         "available": available, "capacity": caps})
        return {"date": current.date_label, "catalogDate": snap.date_label,
                "year": current.meta.get("date", {}).get("year", current.meta.get("year")), "models": rows}

    def export_spreadsheet(self, open_app: bool = False) -> dict[str, Any]:
        """Write an XLSX under the data directory and optionally open the default application."""
        snap, prev = self._with_prev()
        path = export_workbook(self.store, snap, prev, self.paths.data / "exports")
        result = {"file": str(path), "date": snap.date_label, "opened": False}
        if open_app:
            try:
                open_default(path)
                result["opened"] = True
            except (OSError, subprocess.CalledProcessError) as exc:
                result["openError"] = f"Export saved, but the default application could not open it: {exc}"
        return result

    def report(self, kind: str, year: int | None = None, html: bool = False) -> dict[str, Any]:
        """Render a snapshot-backed report and replace output files atomically."""
        from .reports import render_report

        snap = self.current()
        markdown = render_report(self.store, kind, year=year)
        stem = f"annual-{year if year is not None else snap.meta.get('year', snap.meta.get('date', {}).get('year'))}" if kind == "annual" else kind
        output = self.paths.data / "reports"
        path = output / f"{stem}.md"
        html_text = render_report(self.store, kind, year=year, html=True) if html else None
        _atomic_text(path, markdown)
        _atomic_text(output / "latest.md", markdown)
        result = {"markdown": markdown, "file": str(path), "date": snap.date_label}
        if html_text is not None:
            html_path = output / f"{stem}.html"
            _atomic_text(html_path, html_text)
            result["html_file"] = str(html_path)
        return result

    def latest_report(self) -> str:
        path = self.paths.data / "reports" / "latest.md"
        if not path.is_file():
            raise LookupError("No report generated yet. Call `report` or run `tf3c report company`.")
        return path.read_text(encoding="utf-8")

    # ---- decisions ---------------------------------------------------------------
    def record_decision(self, title: str, rationale: str, entities: list[Any] | None = None) -> dict[str, Any]:
        self._checked_ingest()
        return self.store.add_decision(title, rationale, entities, self.store.latest())

    def update_decision(self, decision_id: int, status: str, outcome: str | None = None) -> dict[str, Any]:
        return self.store.update_decision(decision_id, status, outcome)

    def decisions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        _positive_limit(limit)
        return self.store.list_decisions(status, limit)

    # ---- knowledge & diagnostics ---------------------------------------------------
    @staticmethod
    def knowledge(topic: str | None = None) -> dict[str, Any]:
        """Read packaged knowledge without requiring a game installation."""
        topics = {entry.name[:-3]: entry for entry in files("tf3companion").joinpath("knowledge").iterdir()
                  if entry.name.endswith(".md")}
        if topic is None:
            return {"topics": sorted(topics)}
        if topic not in topics:
            raise LookupError(f"Topic '{topic}' does not exist. Available: {sorted(topics)}")
        return {"topic": topic, "content": topics[topic].read_text(encoding="utf-8")}

    def save_notes(self, append: str | None = None) -> str:
        """Read player notes, optionally appending an entry dated with the latest snapshot."""
        if append is not None:
            self._checked_ingest()
            snap = self.store.latest()
            date = snap.date_label if snap is not None else "no snapshot"
            self.paths.data.mkdir(parents=True, exist_ok=True)
            with self.paths.notes.open("a", encoding="utf-8") as handle:
                handle.write(f"\n## {date}\n\n{append}\n")
        return self.paths.notes.read_text(encoding="utf-8") if self.paths.notes.exists() else ""

    def log_tail(self, lines: int = 40, bridge_only: bool = True) -> list[str]:
        _positive_limit(lines, "lines")
        path = self.paths.game_log
        if not path.is_file():
            return [f"Log not found: {path}"]
        with path.open(encoding="utf-8", errors="replace") as handle:
            selected = (line.rstrip("\r\n") for line in handle
                        if not bridge_only or LOG_PREFIX in line)
            return list(deque(selected, maxlen=lines))


def _positive_limit(value: int, name: str = "limit") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
        raise ValueError(f"{name} must be an integer between 1 and 10000.")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def _refresh_lock(request: Path):
    lock = request.with_suffix(".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            f"A refresh is already running ({lock}). If its process crashed, remove this lock only after confirming no refresh is running."
        ) from exc
    os.close(descriptor)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _station(snap: Snapshot, group_id: int | None) -> dict[str, Any]:
    return next((s for s in snap.stations if s.get("id") == group_id), {})


def _sorted(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    if not rows or key not in rows[0]:
        return rows
    reverse = key not in ("profitYear", "load")  # worst first for money/load, biggest first otherwise
    present = [r for r in rows if r.get(key) is not None]
    missing = [r for r in rows if r.get(key) is None]
    return sorted(present, key=lambda r: r[key], reverse=reverse) + missing


def open_default(path: Path) -> None:
    """Open a file using the operating system's default application."""
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=True)


__all__ = ["Companion", "NoSnapshotError"]
