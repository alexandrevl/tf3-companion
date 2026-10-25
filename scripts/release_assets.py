"""Release helpers used by the tag-triggered workflow, runnable and testable locally.

    uv run python scripts/release_assets.py check-tag v0.1.0
    uv run python scripts/release_assets.py bridge-zip --out dist

`check-tag` fails unless the tag is `v<version>` and the version matches `pyproject.toml` and the
source-checkout fallback in `src/tf3companion/__init__.py`. `bridge-zip` packs the bridge mod folder
into `tf3_companion_bridge-<revision>.zip` with the mod folder as the archive root.
Nothing here publishes anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_DIR = Path("mod") / "tf3_companion_bridge"
FALLBACK_VERSION = re.compile(r'__version__\s*=\s*"([^"]+)"')
TAG = re.compile(r"^v(\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.-]+)?)$")


def package_version(root: Path = ROOT) -> str:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def fallback_version(root: Path = ROOT) -> str:
    text = (root / "src" / "tf3companion" / "__init__.py").read_text(encoding="utf-8")
    match = FALLBACK_VERSION.search(text)
    if not match:
        raise ValueError('src/tf3companion/__init__.py has no `__version__ = "..."` fallback')
    return match.group(1)


def check_tag(tag: str, root: Path = ROOT) -> str:
    """The version for a matching tag; raises ValueError naming the mismatch otherwise."""
    match = TAG.match(tag)
    if not match:
        raise ValueError(f"tag {tag!r} is not of the form v<major>.<minor>.<patch>")
    version = match.group(1)
    declared = package_version(root)
    fallback = fallback_version(root)
    if version != declared:
        raise ValueError(f"tag {tag} does not match the package version {declared} in pyproject.toml")
    if fallback != declared:
        raise ValueError(f"source fallback version {fallback} does not match the package version {declared}")
    return version


def mod_revision(root: Path = ROOT) -> int:
    revision = json.loads((root / MOD_DIR / "mod.json").read_text(encoding="utf-8")).get("revision")
    if type(revision) is not int:
        raise ValueError("mod.json has no integer revision")
    return revision


def bridge_zip(out: Path, root: Path = ROOT) -> Path:
    """Pack the bridge mod, folder name first, into `out`; returns the archive path."""
    source = root / MOD_DIR
    if not (source / "mod.json").is_file():
        raise ValueError(f"{source} is not a mod folder (no mod.json)")
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"tf3_companion_bridge-{mod_revision(root)}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, Path(source.name) / path.relative_to(source))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-tag", help="fail unless the tag matches the package version")
    check.add_argument("tag")
    pack = sub.add_parser("bridge-zip", help="write the bridge mod archive")
    pack.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args(argv)
    try:
        if args.command == "check-tag":
            print(check_tag(args.tag))
        else:
            print(bridge_zip(args.out))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
