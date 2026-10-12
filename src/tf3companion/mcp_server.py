"""MCP server exposing TF3 Companion over stdio."""

from __future__ import annotations

import functools
import sqlite3
import subprocess
from typing import Any, Callable, Literal, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .paths import ConfigError
from .service import Companion, NoSnapshotError
from .agent_experience import load_instructions, register_experience


server = MCPServer(name="tf3-companion", instructions=load_instructions())
_companion: Companion | None = None


def companion() -> Companion:
    global _companion
    if _companion is None:
        _companion = Companion()
    return _companion


F = TypeVar("F", bound=Callable[..., Any])


def tool(fn: F) -> F:
    """Register a tool and report expected failures as actionable tool errors."""
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (NoSnapshotError, ConfigError, LookupError, ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as exc:
            raise ToolError(str(exc)) from exc
    server.tool()(wrapper)
    return fn


@tool
def status() -> dict[str, Any]:
    """Show data paths, mod installation and the latest snapshot, including collection errors."""
    return companion().status()


@tool
def refresh(timeout_seconds: float = 30.0) -> dict[str, Any]:
    """Request a fresh snapshot from the open game with the mod enabled and wait for it."""
    return companion().refresh(timeout_s=timeout_seconds)


@tool
def company_overview() -> dict[str, Any]:
    """Company finances and totals, with changes since the previous snapshot."""
    return companion().overview()


@tool
def list_lines(sort_by: Literal["profitYear", "transportedYear", "rate", "load", "vehicles", "ageYears"] = "profitYear", limit: int = 50) -> list[dict[str, Any]]:
    """Company lines: worst profit or lowest load first; other measures largest first."""
    return companion().lines(sort_by, limit)


@tool
def line_detail(line: str) -> dict[str, Any]:
    """A line by id or name: stops, cargo occupancy, issues, vehicles and history."""
    return companion().line_detail(line)


@tool
def list_vehicles(filter: Literal["all", "losing", "problems", "depot"] = "all", line: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Vehicles, optionally on a line: losing annual money, lacking a route/stopped, or in a depot."""
    return companion().vehicles(filter, line, limit=limit)


@tool
def list_industries(filter: Literal["all", "unserved", "closing"] = "all", cargo: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Industry annual production/consumption by cargo; unserved means shipping less than half of output."""
    return companion().industries(filter, cargo, limit)


@tool
def list_towns(limit: int = 50) -> list[dict[str, Any]]:
    """Towns largest first: population (residential/commercial/industrial capacity sum) and line usage."""
    return companion().towns(limit)


@tool
def findings(category: Literal["finance", "lines", "vehicles", "industries", "data"] | None = None, severity: Literal["high", "medium", "low"] | None = None) -> list[dict[str, Any]]:
    """Problems and alerts with evidence and suggestions, most severe first."""
    return companion().findings(category, severity)


@tool
def opportunities(limit: int = 20) -> list[dict[str, Any]]:
    """Unshipped production and the nearest consumers of that cargo, with distances in kilometres."""
    return companion().opportunities(limit)


@tool
def company_history(limit: int = 24) -> list[dict[str, Any]]:
    """Historical balance, loan, line and vehicle counts, one point per snapshot."""
    return companion().company_history(limit)


@tool
def list_stocks(kind: Literal["station", "industry", "warehouse"] | None = None, name: str | None = None, only_full: bool = False) -> list[dict[str, Any]]:
    """Stock count/capacity at stations, industries and warehouses; only_full selects 90%+ filled stocks. Full destination stocks can prevent unloading and destroy cargo."""
    return companion().stocks(kind, name, only_full)


@tool
def list_depots() -> list[dict[str, Any]]:
    """Depots: name, transport mode, position and number of vehicles currently inside."""
    return companion().depots()


@tool
def vehicle_catalog(carrier: Literal["ROAD", "RAIL", "TRAM", "WATER", "AIR"] | None = None, cargo: str | None = None, available_only: bool = True) -> dict[str, Any]:
    """Vehicle models available in the game year or arriving within ten years: cargo capacity, speed, price, operating cost and lifespan. Use to assess line suitability."""
    return companion().catalog(carrier, cargo, available_only)


@tool
def export_spreadsheet(open_app: bool = False) -> dict[str, Any]:
    """Export an XLSX with summary, lines, vehicles, industries, towns, opportunities, findings, history charts and decisions under the data directory; optionally open the default application."""
    return companion().export_spreadsheet(open_app=open_app)


@tool
def record_decision(title: str, rationale: str, entities: list[str] | None = None) -> dict[str, Any]:
    """Record a decision agreed with the player, its rationale and entities, dated with the latest game snapshot."""
    return companion().record_decision(title, rationale, entities)


@tool
def update_decision(decision_id: int, status: Literal["planned", "done", "dropped"], outcome: str | None = None) -> dict[str, Any]:
    """Update a decision's status and observed outcome."""
    return companion().update_decision(decision_id, status, outcome)


@tool
def list_decisions(status: Literal["planned", "done", "dropped"] | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Decision journal, newest first, optionally filtered by status."""
    return companion().decisions(status, limit)


@tool
def knowledge(topic: str | None = None) -> dict[str, Any]:
    """Read packaged game knowledge; without a topic, list available topics."""
    return Companion.knowledge(topic)


@tool
def save_notes(append: str | None = None) -> str:
    """Read player notes, optionally appending text dated with the latest snapshot's game date."""
    return companion().save_notes(append)


@tool
def log_tail(lines: int = 40) -> list[str]:
    """Latest [tf3c] game log lines for diagnosing snapshot collection."""
    return companion().log_tail(lines)


@tool
def doctor() -> dict[str, Any]:
    """Diagnose setup and report fixes even when the game is not installed."""
    from .setup_tools import doctor as diagnose
    return diagnose()


@tool
def report(kind: Literal["company", "lines", "fleet", "cargo", "decisions", "annual"], year: int | None = None) -> str:
    """Generate a Markdown report from stored observations. Annual coverage may be partial; rolling annual profits are not calendar-year totals."""
    return companion().report(kind, year)["markdown"]


register_experience(server, companion)


def main() -> None:
    server.run("stdio")
