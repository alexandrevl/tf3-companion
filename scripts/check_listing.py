"""Validate the bridge mod's public listing: text and images.

Exit 0 when valid, 1 with one line per problem otherwise. Reads files only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

COVER_SIZE = (1920, 1080)
LOGO_SIZE = (512, 512)
GALLERY_SIZE = (1920, 1080)
GALLERY_SLOTS = {
    "01": "mod list with the bridge enabled",
    "02": "company findings answered by an assistant",
    "03": "a report or exported spreadsheet",
    "04": "a loss-making line beside its finding",
}
SUMMARY_MAX = 120
MOD_DIR = Path("mod") / "tf3_companion_bridge"


def _image_problems(path: Path, size: tuple[int, int], label: str, mode: str | None = None) -> list[str]:
    if not path.is_file():
        return [f"{label}: missing {path} (expected PNG {size[0]}x{size[1]})"]
    try:
        with Image.open(path) as image:
            fmt, actual, actual_mode = image.format, image.size, image.mode
    except (UnidentifiedImageError, OSError):
        return [f"{label}: {path} is not a readable image (expected PNG {size[0]}x{size[1]})"]
    problems = []
    if fmt != "PNG":
        problems.append(f"{label}: {path} is {fmt}, expected PNG")
    if actual != size:
        problems.append(f"{label}: {path} is {actual[0]}x{actual[1]}, expected {size[0]}x{size[1]}")
    if mode and actual_mode != mode:
        problems.append(f"{label}: {path} mode is {actual_mode}, expected {mode}")
    return problems


def _text_problems(modinfo_path: Path) -> list[str]:
    if not modinfo_path.is_file():
        return [f"modinfo: missing {modinfo_path}"]
    try:
        info = json.loads(modinfo_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"modinfo: cannot read {modinfo_path}: {exc}"]
    summary, description = info.get("summary"), info.get("description")
    problems = []
    if not isinstance(summary, str) or not summary.strip():
        problems.append("modinfo: summary is missing")
    elif "\n" in summary or len(summary) > SUMMARY_MAX:
        problems.append(f"modinfo: summary must be one line of at most {SUMMARY_MAX} characters (got {len(summary)})")
    if not isinstance(description, str):
        return problems + ["modinfo: description is missing"]
    text = description.lower()
    if not ("unofficial" in text and "urban games" in text and "paradox interactive" in text
            and ("not affiliated" in text or "not endorsed" in text)):
        problems.append("modinfo: description lacks the unofficial / not affiliated with Urban Games or Paradox Interactive disclaimer")
    if "read-only" not in text:
        problems.append("modinfo: description does not state that the mod is read-only")
    if "companion app" not in text:
        problems.append("modinfo: description does not say the TF3 Companion app is required")
    return problems


def check(root: Path) -> list[str]:
    root = Path(root)
    problems = _text_problems(root / MOD_DIR / "_metadata" / "modinfo.json")
    problems += _image_problems(root / MOD_DIR / "_metadata" / "0.png", COVER_SIZE, "cover", "RGBA")
    problems += _image_problems(root / "assets" / "logo.png", LOGO_SIZE, "logo")
    gallery = root / "assets" / "gallery"
    for slot, subject in GALLERY_SLOTS.items():
        matches = sorted(gallery.glob(f"{slot}-*.png")) if gallery.is_dir() else []
        if not matches:
            problems.append(f"gallery slot {slot} ({subject}): missing assets/gallery/{slot}-<name>.png "
                            f"(expected PNG {GALLERY_SIZE[0]}x{GALLERY_SIZE[1]})")
            continue
        for path in matches:
            problems += _image_problems(path, GALLERY_SIZE, f"gallery slot {slot}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    problems = check(root)
    for line in problems:
        print(line)
    if not problems:
        print("listing ok")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
