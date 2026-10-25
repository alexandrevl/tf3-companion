"""Command-line entry point: tf3c <command>."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from .discovery import ConfigError
from .paths import load_paths
from .service import Companion, NoSnapshotError, open_default


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _print_findings(items: list[dict[str, Any]]) -> None:
    if not items:
        print("Nothing to report in this snapshot.")
        return
    icons = {"high": "!!", "medium": "! ", "low": "· "}
    first = items[0]
    if first.get("methodology"):
        print(f"Methodology: {first['methodology']} ({first.get('methodology_hash')})")
    for finding in items:
        print(f"{icons[finding['severity']]} [{finding['category']}] {finding['title']}")
        print(f"     {finding['detail']}")
        print(f"     → {finding['suggestion']}")


def main(argv: list[str] | None = None) -> int:
    from . import __version__

    parser = argparse.ArgumentParser(prog="tf3c", description="TF3 Companion: read-only Transport Fever 3 data analyst")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="diagnose setup without requiring the game to be installed")
    p = sub.add_parser("mod", help="install or remove the bundled bridge")
    p.add_argument("action", choices=("install", "uninstall"))
    sub.add_parser("status", help="data paths, mod and latest snapshot")
    sub.add_parser("ingest", help="import new snapshots into SQLite")
    p = sub.add_parser("refresh", help="request a fresh snapshot from the open game")
    p.add_argument("--timeout", type=float, default=30.0)
    sub.add_parser("overview", help="company overview")
    p = sub.add_parser("lines", help="company lines")
    p.add_argument(
        "--sort",
        default="profitYear",
        choices=("profitYear", "transportedYear", "rate", "load", "vehicles", "ageYears"),
    )
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("line", help="line details by id or name")
    p.add_argument("ref")
    p = sub.add_parser("findings", help="problems and recommendations")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--methodology",
        metavar="ID|FILE",
        help="one-off id[@version] or path; otherwise save override > user default > packaged default",
    )
    p = sub.add_parser("opportunities", help="unshipped cargo opportunities")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("notes", help="read or append dated player notes")
    p.add_argument("--append", metavar="TEXT")
    p = sub.add_parser("knowledge", help="read packaged knowledge without game discovery")
    p.add_argument("topic", nargs="?")
    p = sub.add_parser("log", help="mod lines from the game log")
    p.add_argument("--lines", type=int, default=40)
    p = sub.add_parser("export", help="export XLSX data")
    p.add_argument("--open", action="store_true", help="open using the default application")
    p = sub.add_parser("report", help="generate evidence-backed Markdown or offline HTML")
    from .reports import VALID_KINDS

    p.add_argument("kind", choices=VALID_KINDS)
    p.add_argument("--year", type=int)
    p.add_argument("--html", action="store_true")
    p.add_argument("--open", action="store_true")
    p.add_argument(
        "--methodology",
        metavar="ID|FILE",
        help="one-off id[@version] or path; otherwise save override > user default > packaged default",
    )
    sub.add_parser("mcp", help="start the MCP server over stdio")
    from .methodology.cli import add_parsers

    add_parsers(sub)
    args = parser.parse_args(argv)

    companion = None
    try:
        if args.command == "mcp":
            from .mcp_server import main as run_mcp

            run_mcp()
            return 0
        if args.command == "doctor":
            from .setup_tools import doctor

            result = doctor()
            _print(result)
            return 0 if result["ok"] else 1
        if args.command == "mod":
            from .setup_tools import install_mod, uninstall_mod

            _print((install_mod if args.action == "install" else uninstall_mod)(load_paths()))
            return 0
        if args.command == "knowledge":
            result = Companion.knowledge(args.topic)
            print(result["content"]) if args.topic else _print(result)
            return 0
        if args.command == "methodology":
            from .methodology.cli import run_methodology

            return run_methodology(args)
        if args.command == "evaluate":
            from .methodology.cli import parse_params, print_evaluation

            companion = Companion.open_stored(save=args.save)
            result = companion.evaluate(
                args.methodology, allow_path=True, param_overrides=parse_params(args.param), views=args.view or ()
            )
            _print(result) if args.json else print_evaluation(result)
            return 0
        companion = Companion(save=args.save) if args.command == "analyse" else Companion()
        match args.command:
            case "status":
                _print(companion.status())
            case "ingest":
                result = companion.ingest()
                _print(result)
                return 1 if result["failed"] else 0
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
                items = companion.findings(methodology=args.methodology, allow_path=True)
                _print(items) if args.json else _print_findings(items)
            case "opportunities":
                _print(companion.opportunities(args.limit))
            case "notes":
                print(companion.save_notes(args.append))
            case "log":
                print("\n".join(companion.log_tail(args.lines)))
            case "export":
                _print(companion.export_spreadsheet(open_app=args.open))
            case "report":
                result = companion.report(
                    args.kind, args.year, args.html, methodology=args.methodology, allow_path=True
                )
                if args.open:
                    try:
                        open_default(Path(result.get("html_file", result["file"])))
                    except (OSError, subprocess.CalledProcessError) as exc:
                        print(
                            f"warning: Report saved, but the default application could not open it: {exc}",
                            file=sys.stderr,
                        )
                _print({key: value for key, value in result.items() if key != "markdown"})
            case "analyse":
                from .methodology.cli import parse_params, print_analysis

                summary = companion.analyse(args.methodology, allow_path=True, param_overrides=parse_params(args.param))
                _print(summary) if args.json else print_analysis(summary)
    except (
        NoSnapshotError,
        ConfigError,
        LookupError,
        ValueError,
        OSError,
        sqlite3.Error,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if companion is not None:
            companion.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
