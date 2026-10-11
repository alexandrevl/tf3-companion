"""Command-line entry point: tf3c <command>."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from .paths import ConfigError
from .service import Companion, NoSnapshotError


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_findings(items: list[dict[str, Any]]) -> None:
    if not items:
        print("Nothing to report in this snapshot.")
        return
    icons = {"high": "!!", "medium": "! ", "low": "· "}
    for finding in items:
        print(f"{icons[finding['severity']]} [{finding['category']}] {finding['title']}")
        print(f"     {finding['detail']}")
        print(f"     → {finding['suggestion']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tf3c", description="TF3 Companion: read-only Transport Fever 3 data analyst")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="data paths, mod and latest snapshot")
    sub.add_parser("ingest", help="import new snapshots into SQLite")
    p = sub.add_parser("refresh", help="request a fresh snapshot from the open game")
    p.add_argument("--timeout", type=float, default=30.0)
    sub.add_parser("overview", help="company overview")
    p = sub.add_parser("lines", help="company lines")
    p.add_argument("--sort", default="profitYear")
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("line", help="line details by id or name")
    p.add_argument("ref")
    p = sub.add_parser("findings", help="problems and recommendations")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("opportunities", help="unshipped cargo opportunities")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("notes", help="read or append dated player notes")
    p.add_argument("--append", metavar="TEXT")
    p = sub.add_parser("log", help="mod lines from the game log")
    p.add_argument("--lines", type=int, default=40)
    p = sub.add_parser("export", help="export an XLSX under the data directory")
    p.add_argument("--open", action="store_true", help="open using the default application")
    sub.add_parser("mcp", help="start the MCP server over stdio")
    args = parser.parse_args(argv)

    if args.command == "mcp":
        from .mcp_server import main as run_mcp
        run_mcp()
        return 0

    companion = None
    try:
        companion = Companion()
        match args.command:
            case "status":
                _print(companion.status())
            case "ingest":
                _print(companion.ingest())
            case "refresh":
                result = companion.refresh(timeout_s=args.timeout)
                _print(result)
                if not result["ok"]:
                    print(f"error: {result['message']}", file=sys.stderr)
                    return 1
            case "overview":
                _print(companion.overview())
            case "lines":
                _print(companion.lines(args.sort, args.limit))
            case "line":
                _print(companion.line_detail(args.ref))
            case "findings":
                items = companion.findings()
                _print(items) if args.json else _print_findings(items)
            case "opportunities":
                _print(companion.opportunities(args.limit))
            case "notes":
                print(companion.save_notes(args.append))
            case "log":
                print("\n".join(companion.log_tail(args.lines)))
            case "export":
                _print(companion.export_spreadsheet(open_app=args.open))
    except (NoSnapshotError, ConfigError, LookupError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if companion is not None:
            companion.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
