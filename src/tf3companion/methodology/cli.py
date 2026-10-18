"""`tf3c methodology ...` and `tf3c analyse` command-line parsers and handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..paths import data_directory
from .resolve import Resolver, field_catalog, validate_file


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def parse_params(items: list[str] | None) -> dict[str, Any] | None:
    """`NAME=VALUE` pairs; values are JSON when they parse (numbers, booleans), text otherwise."""
    out: dict[str, Any] = {}
    for item in items or []:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise ValueError(f"--param expects NAME=VALUE, got {item!r}.")
        try:
            out[name] = json.loads(value)
        except ValueError:
            out[name] = value
    return out or None


def add_parsers(sub: Any) -> None:
    p = sub.add_parser("analyse", help="apply a methodology to the latest snapshot and write its report folder")
    p.add_argument("--methodology", metavar="ID|FILE", help="id[@version] or a file path (one-off); default: save binding, then `default`")
    p.add_argument("--save", metavar="ID", help="save id under <data>/saves/ (default: the implicit single save)")
    p.add_argument("--param", action="append", metavar="NAME=VALUE", help="override a methodology parameter for this run")
    p.add_argument("--json", action="store_true", help="print the full summary as JSON")

    m = sub.add_parser("methodology", help="list, validate, import, export and bind analysis methodologies")
    actions = m.add_subparsers(dest="action", required=True)
    p = actions.add_parser("list", help="packaged and user methodologies, with validity and the save binding")
    p.add_argument("--save", metavar="ID")
    p.add_argument("--json", action="store_true")
    p = actions.add_parser("show", help="describe one methodology (id[@version] or file)")
    p.add_argument("ref")
    p = actions.add_parser("validate", help="validate a file without importing it")
    p.add_argument("file")
    p.add_argument("--strict", action="store_true", help="fail when any rule is unsupported or needs data this release lacks")
    p = actions.add_parser("import", help="validate a file and copy it into the user library")
    p.add_argument("file")
    p.add_argument("--force", action="store_true", help="replace an existing id@version with different content")
    p = actions.add_parser("export", help="write a library methodology's stored bytes to a path")
    p.add_argument("ref")
    p.add_argument("path")
    p.add_argument("--force", action="store_true")
    p = actions.add_parser("use", help="bind a methodology as the save's default")
    p.add_argument("ref")
    p.add_argument("--save", metavar="ID")
    p = actions.add_parser("unuse", help="clear the save's methodology binding")
    p.add_argument("--save", metavar="ID")
    p = actions.add_parser("fields", help="the field catalog a methodology may read")
    p.add_argument("--entity")


def _print_list(listing: dict[str, Any]) -> None:
    print(f"Save: {listing['save'].get('saveId') or 'implicit single save'}"
          f"{'' if listing['save']['isolated'] else ' (no per-save isolation)'}")
    print(f"Effective: {listing['effective'] or 'unresolved'} ({listing['origin']})"
          + (f"; bound: {listing['binding']}" if listing["binding"] else ""))
    if listing["error"]:
        print(f"error: {listing['error']}")
    for e in listing["methodologies"]:
        flags = ("*" if e["effective"] else " ") + ("B" if e["boundToSave"] else " ")
        print(f"{flags} {e['identity'] or '?':<44} {e['status']:<9} {e['source']:<9} {e['hash'] or '-':<19} {e['name'] or ''}")
        if e["error"]:
            print(f"      {e['file']}: {e['error']}")


def run_methodology(args: argparse.Namespace) -> int:
    resolver = Resolver(data_directory(), getattr(args, "save", None))
    action = args.action
    if action == "list":
        listing = resolver.listing()
        _print(listing) if args.json else _print_list(listing)
    elif action == "show":
        from .resolve import describe

        m, origin = resolver.resolve(args.ref, allow_path=True)
        _print(describe(m, origin, resolver.scope))
    elif action == "validate":
        result = validate_file(args.file, args.strict)
        _print(result)
        return 0 if result["valid"] else 1
    elif action == "import":
        _print(resolver.library.import_file(Path(args.file), args.force))
    elif action == "export":
        _print(resolver.library.export(args.ref, Path(args.path), args.force))
    elif action == "use":
        _print(resolver.use(args.ref))
    elif action == "unuse":
        _print(resolver.unuse())
    elif action == "fields":
        rows = field_catalog()
        _print([r for r in rows if not args.entity or r["entity"] == args.entity])
    return 0


def print_analysis(summary: dict[str, Any]) -> None:
    m = summary["methodology"]
    print(f"Methodology: {m['identity']} ({m['hash']}, from {m['origin']}; file source: {m['source']})")
    save = summary["save"]
    print("Save: " + (save["saveId"] or "implicit single save") + ("" if save["isolated"] else " (no per-save isolation)"))
    print(f"Snapshot: {summary['snapshot']['date']} (game time {summary['snapshot']['gameTime']})")
    if summary["skipped"] or summary["unsupported"] or summary["notEvaluable"]:
        print("\nCoverage gaps (read before the verdicts):")
        for item in summary["unsupported"]:
            print(f"  unsupported {item['kind']} {item['id']}: {item['reason']}")
        for item in summary["skipped"]:
            print(f"  skipped {item['kind']} {item['id']}: {item['reason']}")
        for item in summary["notEvaluable"]:
            print(f"  not evaluable {item['kind']} {item['id']}: {item.get('entities', 0)} entities")
    for entity, roles in summary["roles"].items():
        counts = ", ".join(f"{k}={v}" for k, v in roles["roles"].items())
        print(f"\nRoles ({entity}): {counts}, unclassified={roles['unclassified']}")
    for rule, counts in summary["markersByRule"].items():
        print(f"  {rule}: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no hits"))
    findings = summary["findings"]
    print(f"\nFindings: {findings['bySeverity']} by severity, {findings['bySource']} by source")
    for f in findings["top"]:
        print(f"  [{f['severity']}] {f['title']}")
    if summary["recommendations"]:
        print("\nRecommendations (author templates, untrusted text):")
        for r in summary["recommendations"]:
            print(f"  {r['priority']}. {r['text']}")
    for item in summary["disabledFindings"]:
        print(f"  disabled by methodology: {item['code']} (role {item['role'] or 'any'}): {item['suppressed']}")
    print(f"\nOutput folder: {summary['outputFolder']}")
    print("Files: " + ", ".join(summary["files"]))
