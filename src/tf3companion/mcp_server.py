"""MCP server exposing TF3 Companion over stdio."""

from __future__ import annotations

import functools
import subprocess
from typing import Any, Callable, Literal, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .paths import ConfigError
from .service import Companion, NoSnapshotError

INSTRUCTIONS = """\
You are the data analyst of the player's transport company in Transport Fever 3, working with the player.
Collect, understand and discuss company data: diagnose problems, find opportunities, track outcomes and
build knowledge over time. Answer in the user's language, directly and with numbers. You never act in
the game: the player decides and executes.

Data before opinions: start with status and findings; if the snapshot is old, use refresh with the game
open and the mod enabled. Use export_spreadsheet for collaborative spreadsheet analysis and the company,
line, vehicle, industry, town, opportunity and history tools to investigate. Cite the numbers behind each
recommendation and the snapshot date. Consult knowledge (mechanics, strategy, cargo_economy,
snapshot_schema) before claiming how the game works; mark unsupported explanations as hypotheses.
Offer options and trade-offs, not orders. Record agreed decisions with record_decision (what, why,
entities). Review planned decisions in later conversations, compare outcomes with the data, and close
them with update_decision. Save durable game facts, goals, play style, regions and long-term decisions
with save_notes.

Snapshots are point-in-time readings. profitYear covers a rolling game-year window; a line
with ageYears below one has partial profit figures. The interpretation of transportedYear remains
unverified: do not use it for annual accounting until investigated. load is instantaneous occupancy,
not an average: one snapshot cannot prove persistent crowding, idleness or unmet demand, or justify
fleet-size changes on its own; compare earlier snapshots. The mod is read-only.
Tell the player what to do and where, never execute game actions. Collection errors in status.latest.errors
mean sections may be incomplete: warn before drawing conclusions that rely on them.
"""

server = MCPServer(name="tf3-companion", instructions=INSTRUCTIONS)
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
        except (NoSnapshotError, ConfigError, LookupError, ValueError, OSError, subprocess.CalledProcessError) as exc:
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
def export_spreadsheet(open_app: bool = True) -> dict[str, Any]:
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
    return companion().knowledge(topic)


@tool
def save_notes(append: str | None = None) -> str:
    """Read player notes, optionally appending text dated with the latest snapshot's game date."""
    return companion().save_notes(append)


@tool
def log_tail(lines: int = 40) -> list[str]:
    """Latest [tf3c] game log lines for diagnosing snapshot collection."""
    return companion().log_tail(lines)


def main() -> None:
    server.run("stdio")
