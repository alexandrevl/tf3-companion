"""`tf3c methodology ...` and `tf3c analyse` command-line parsers and handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..paths import data_directory
from .resolve import Resolver, field_catalog, validate_file

SHOWN_FINDINGS = 15


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
    p.add_argument("--methodology", metavar="ID|FILE", help="one-off id[@version] or path; otherwise save override > user default > packaged default")
    p.add_argument("--save", metavar="ID", help="save id under <data>/saves/ (default: the implicit single save)")
    p.add_argument("--param", action="append", metavar="NAME=VALUE", help="override a methodology parameter for this run")
    p.add_argument("--json", action="store_true", help="print the full summary as JSON")

    p = sub.add_parser("evaluate", help="complete analytical result over stored evidence; writes nothing and never ingests")
    p.add_argument("--methodology", metavar="ID|FILE", help="one-off id[@version] or path; otherwise save override > user default > packaged default")
    p.add_argument("--save", metavar="ID", help="save id under <data>/saves/ (default: the implicit single save)")
    p.add_argument("--param", action="append", metavar="NAME=VALUE", help="override a methodology parameter for this run")
    p.add_argument("--view", action="append", metavar="NAME", help="also compute one analysis view over stored history (repeatable): "
                   "bottlenecks, expansion, lines-history, history, industries, vehicle-roi, towns")
    p.add_argument("--json", action="store_true", help="print the complete version-1 result as JSON")

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
    p.add_argument("--param", action="append", metavar="NAME=VALUE", help="validate effective parameter overrides")
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
    p = actions.add_parser("unuse", help="clear the save override and inherit the user or packaged default")
    p.add_argument("--save", metavar="ID")
    p = actions.add_parser("set-default", help="select a library-root user default, independent of saves")
    p.add_argument("ref")
    actions.add_parser("clear-default", help="reset the library-root user default, including malformed preferences")
    p = actions.add_parser("fields", help="the field catalog a methodology may read")
    p.add_argument("--entity")


def _print_list(listing: dict[str, Any]) -> None:
    print(f"Save: {listing['save'].get('saveId') or 'implicit single save'}"
          f"{'' if listing['save']['isolated'] else ' (no per-save isolation)'}")
    print(f"Effective: {listing['effective'] or 'unresolved'} ({listing['origin']})")
    print(f"Library root: {listing['libraryRoot']}")
    print(f"User default: {listing['userDefault']['reference']}; save override: {listing['saveOverride']['reference']}")
    if listing["error"]:
        print(f"error: {listing['error']}")
    for e in listing["methodologies"]:
        flags = ("*" if e["effective"] else " ") + ("S" if e["selectedAsSaveOverride"] else "U" if e["selectedAsUserDefault"] else " ")
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
        from .library import looks_like_path
        from .resolve import describe
        origin = "file" if looks_like_path(args.ref) else "request"
        m = resolver.library.load_path(args.ref) if origin == "file" else resolver.library.resolve(args.ref)
        _print(describe(m, origin, resolver.scope))
    elif action == "validate":
        result = validate_file(args.file, args.strict, parse_params(args.param))
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
    elif action == "set-default":
        _print(resolver.set_default(args.ref))
    elif action == "clear-default":
        _print(resolver.clear_default())
    elif action == "fields":
        rows = field_catalog()
        _print([r for r in rows if not args.entity or r["entity"] == args.entity])
    return 0


def _print_identity_and_gaps(result: dict[str, Any], skipped: list, unsupported: list, not_evaluable: list) -> None:
    m = result["methodology"]
    print(f"Methodology: {m['identity']} ({m['hash']}, from {m['origin']}; file source: {m['source']})")
    save = result["save"]
    print("Save: " + (save["saveId"] or "implicit single save") + ("" if save["isolated"] else " (no per-save isolation)"))
    print(f"Snapshot: {result['snapshot']['date']} (game time {result['snapshot']['gameTime']})")
    if skipped or unsupported or not_evaluable:
        print("\nCoverage gaps (read before the verdicts):")
        for item in unsupported:
            print(f"  unsupported {item['kind']} {item['id']}: {item['reason']}")
        for item in skipped:
            print(f"  skipped {item['kind']} {item['id']}: {item['reason']}")
        for item in not_evaluable:
            print(f"  not evaluable {item['kind']} {item['id']}: {item.get('entities', 0)} entities")


def print_evaluation(result: dict[str, Any]) -> None:
    """Human summary of a stored-evidence evaluation; it states nothing about reports or files."""
    coverage = result["coverage"]
    _print_identity_and_gaps(result, coverage["skipped"], coverage["unsupported"], coverage["notEvaluable"])
    for entity, roles in result["roles"].items():
        counts = ", ".join(f"{k}={v}" for k, v in roles["roles"].items())
        print(f"\nRoles ({entity}): {counts}, unclassified={roles['unclassified']}")
    for rule in result["ruleResults"]:
        if rule["status"] == "ok":
            print(f"  {rule['id']}: " + (", ".join(f"{k}={v}" for k, v in sorted(rule["markerCounts"].items())) or "no hits"))
    findings = result["findings"]
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
    print(f"\nFindings: {len(findings)} ({by_severity} by severity)")
    for f in findings[:SHOWN_FINDINGS]:
        print(f"  [{f['severity']}] {f['title']}")
    if len(findings) > SHOWN_FINDINGS:
        print(f"  ... {len(findings) - SHOWN_FINDINGS} more; `--json` returns the complete result.")
    if result["recommendations"]:
        print("\nRecommendations (author templates, untrusted text):")
        for r in result["recommendations"]:
            print(f"  {r['priority']}. {r['text']}")
    for item in result["disabledFindings"]:
        print(f"  disabled by methodology: {item['code']} (role {item['role'] or 'any'}): {item['suppressed']}")
    for name, view in result["analysisViews"].items():
        cov = view["coverage"]
        print(f"\nView {name}: {cov['used']} of {cov['eligible']} eligible samples used up to tick {cov['endpoint']['tick']}"
              + (f"; warnings: {'; '.join(cov['warnings'])}" if cov["warnings"] else "") + "; `--json` returns the full view.")


def print_analysis(summary: dict[str, Any]) -> None:
    _print_identity_and_gaps(summary, summary["skipped"], summary["unsupported"], summary["notEvaluable"])
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
