"""Repository guards shared by the commit hook, the test suite and CI.

One definition of every public-repository rule, standard library only. It judges tracked files
(`git ls-files`), so ignored local data is never inspected; the all-locations English rule in
AGENTS.md still applies to authors.

Run from anywhere: `uv run python scripts/check_repo.py [--root PATH] [--rule NAME ...]`.
Exit status 0 means no violation; each violation prints `path:line: [rule] message`.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------------------------
# Repository identity: the single list every URL and metadata field must agree with.
OWNER = "alexandrevl"
REPOSITORY = "tf3-companion"

# The declared project author. Any other address in a tracked file is a violation.
ALLOWED_EMAILS = frozenset({"alexandrevl@gmail.com"})

# Files every public repository must carry. Add a file here in the change that creates it.
REQUIRED_PUBLIC_FILES: tuple[str, ...] = (
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "TODO.md",
)

# ---------------------------------------------------------------------------------------------
# Private data
PRIVATE_PATH_PATTERNS = (
    # A real home directory. Documented placeholders (`username`, `name`, `you`, `user`, `<...>`) are allowed.
    re.compile(r"(?:/Users|/home)/(?!(?:username|name|you|user|USER|NAME)(?:/|\b)|<)[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\Users\\(?!(?:username|name|you|user|USER|NAME)\\|<)[A-Za-z0-9._-]+\\"),
)
STEAM_ID_PATTERN = re.compile(r"7656119\d{9}|userdata[/\\]\d{5,}")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
# `name@1.0.0.something.json` looks like an address but is a file name in tests and docs.
NOT_A_DOMAIN_SUFFIXES = (".json", ".tga", ".png", ".lua", ".md", ".py", ".txt")
FORBIDDEN_TRACKED_NAMES = (
    re.compile(r"(?:^|/)tf3c_snap_[^/]*\.lua$"),
    re.compile(r"\.(?:db|sqlite|sqlite3)$"),
    re.compile(r"^data/"),
    re.compile(r"(?:^|/)tf3c_request\.lua$"),
)
# Files that are inventories of third-party metadata, or that define and seed the rules themselves with
# deliberate violations, and are therefore not content-scanned for private data.
CONTENT_SCAN_SKIP = frozenset({"uv.lock", "scripts/check_repo.py", "tests/test_repo_guards.py"})

# ---------------------------------------------------------------------------------------------
# Language
PORTUGUESE_ACCENTS = re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]")
PORTUGUESE_WORDS = re.compile(r"\b(?:não|você|vocês|para o|ônibus|passageiros|gerar|raio)\b", re.IGNORECASE)
# English (or international) words that happen to carry an accent.
ACCENTED_ENGLISH = ("clichés", "cliché", "café", "résumé", "naïve", "façade", "Español", "Deutsch")
# Files that legitimately quote Portuguese or other non-English text, each with its reason.
LANGUAGE_ALLOWLIST: dict[str, str] = {
    "CHANGELOG.md": "names the retired author-local scripts it removed",
    "docs/methodologies.md": "shows a localized cargo name as the example of why keys are preferred",
    "openspec/changes/agent-experience/design.md": "describes the stop-word check that detects Portuguese remnants",
    "openspec/changes/public-repository-launch/design.md": "quotes the localized cargo name that the language allowlist permits",
    "openspec/changes/archive/2026-10-18-analysis-methodologies/tasks.md": "archived record naming a local-only comparison",
    "openspec/changes/archive/2026-10-18-enforce-english-only/design.md": "archived record of the language-check command",
    "openspec/changes/archive/2026-10-18-enforce-english-only/proposal.md": "archived record naming the Portuguese scripts removed",
    "openspec/changes/archive/2026-10-18-enforce-english-only/tasks.md": "archived record of the language-check command",
    "openspec/changes/archive/2026-10-18-engine-runtime-knowledge/research/native-engine.md": "lists the game's language names in their own language",
    "openspec/changes/archive/2026-10-18-retire-local-analysis-generator/design.md": "archived record naming the retired scripts",
    "openspec/changes/archive/2026-10-18-retire-local-analysis-generator/proposal.md": "archived record naming the retired scripts",
    "openspec/changes/archive/2026-10-18-retire-local-analysis-generator/tasks.md": "archived record naming the retired scripts",
    "scripts/check_repo.py": "defines the language rule itself",
    "tests/test_repo_guards.py": "seeds Portuguese violations to prove the guard fails",
}

# ---------------------------------------------------------------------------------------------
# Links
GITHUB_REPO_URL = re.compile(rf"github\.com/{re.escape(OWNER)}/([A-Za-z0-9._-]+)")
MARKDOWN_LINK = re.compile(r"\]\((?!https?:|mailto:|#|<)([^)\s#]+)(?:#[^)\s]*)?\)")
LINK_CHECK_SKIP_PREFIXES = ("openspec/changes/archive/",)


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: [{self.rule}] {self.message}"


def tracked_files(root: Path) -> list[str]:
    """Tracked paths relative to `root`, as git reports them."""
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True)
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def read_text(root: Path, rel: str) -> str | None:
    """File text, or None for binary, unreadable or deleted-but-listed files."""
    try:
        return (root / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def lines_of(text: str) -> Iterator[tuple[int, str]]:
    yield from enumerate(text.splitlines(), 1)


# ---------------------------------------------------------------------------------------------
# Rules. Each takes (root, files) and returns violations.
Rule = Callable[[Path, list[str]], Iterable[Violation]]


def rule_private_data(root: Path, files: list[str]) -> Iterator[Violation]:
    for rel in files:
        for pattern in FORBIDDEN_TRACKED_NAMES:
            if pattern.search(rel):
                yield Violation("private-data", rel, 0, "player data, database or snapshot file must not be tracked")
                break
        if rel in CONTENT_SCAN_SKIP:
            continue
        text = read_text(root, rel)
        if text is None:
            continue
        for number, line in lines_of(text):
            for pattern in PRIVATE_PATH_PATTERNS:
                match = pattern.search(line)
                if match:
                    yield Violation("private-data", rel, number, f"personal absolute path `{match.group(0)}`")
            match = STEAM_ID_PATTERN.search(line)
            if match:
                yield Violation("private-data", rel, number, f"Steam account identifier `{match.group(0)}`")
            for address in EMAIL_PATTERN.findall(line):
                if address in ALLOWED_EMAILS or address.lower().endswith(NOT_A_DOMAIN_SUFFIXES):
                    continue
                yield Violation("private-data", rel, number, f"e-mail address `{address}` is not the declared author")


def rule_language(root: Path, files: list[str]) -> Iterator[Violation]:
    for rel in files:
        if rel in LANGUAGE_ALLOWLIST or rel == "uv.lock":
            continue
        text = read_text(root, rel)
        if text is None:
            continue
        for number, line in lines_of(text):
            scrubbed = line
            for word in ACCENTED_ENGLISH:
                scrubbed = scrubbed.replace(word, "")
            match = PORTUGUESE_ACCENTS.search(scrubbed) or PORTUGUESE_WORDS.search(scrubbed)
            if match:
                yield Violation(
                    "language", rel, number, f"Portuguese text `{match.group(0)}`; write everything in English"
                )


def rule_required_files(root: Path, files: list[str]) -> Iterator[Violation]:
    present = set(files)
    for rel in REQUIRED_PUBLIC_FILES:
        if rel not in present:
            yield Violation("required-files", rel, 0, "required public file is missing or not tracked")


def rule_identity(root: Path, files: list[str]) -> Iterator[Violation]:
    """Repository URLs name this repository, and relative Markdown links resolve to tracked files."""
    tracked = set(files)
    for rel in files:
        text = read_text(root, rel)
        if text is None or rel in CONTENT_SCAN_SKIP:
            continue
        for number, line in lines_of(text):
            for name in GITHUB_REPO_URL.findall(line):
                if name.removesuffix(".git") != REPOSITORY:
                    yield Violation(
                        "identity",
                        rel,
                        number,
                        f"link names `{OWNER}/{name}`; this repository is `{OWNER}/{REPOSITORY}`",
                    )
        if rel.endswith(".md") and not rel.startswith(LINK_CHECK_SKIP_PREFIXES):
            base = Path(rel).parent
            for number, line in lines_of(text):
                for target in MARKDOWN_LINK.findall(line):
                    resolved = (base / target).as_posix()
                    parts: list[str] = []
                    for piece in resolved.split("/"):
                        if piece == "..":
                            if parts:
                                parts.pop()
                        elif piece not in ("", "."):
                            parts.append(piece)
                    normalized = "/".join(parts)
                    if normalized not in tracked and not any(t.startswith(normalized + "/") for t in tracked):
                        yield Violation(
                            "identity", rel, number, f"relative link `{target}` does not resolve to a tracked file"
                        )


LUAC_NAMES = ("luac", "luac5.4")
LUAC_INSTALL_HINT = (
    "`luac` was not found. Install it (Linux: `apt-get install lua5.4`; macOS: `brew install lua@5.4` and add "
    "`$(brew --prefix lua@5.4)/bin` to PATH; Windows: `choco install lua`) or point the LUAC environment variable "
    "at the binary. There is no fallback parser: `luac -p` is the repository's Lua check (AGENTS.md)."
)


def find_luac() -> str | None:
    """The `luac` binary named by LUAC, else the first of LUAC_NAMES on PATH."""
    explicit = os.environ.get("LUAC")
    if explicit:
        return explicit if shutil.which(explicit) or Path(explicit).is_file() else None
    for name in LUAC_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def rule_lua_syntax(root: Path, files: list[str]) -> Iterator[Violation]:
    """Every tracked Lua file passes `luac -p`. Syntax only: this never shows the mod works in the game."""
    lua_files = [rel for rel in files if rel.endswith(".lua")]
    if not lua_files:
        return
    luac = find_luac()
    if luac is None:
        yield Violation("lua-syntax", lua_files[0], 0, LUAC_INSTALL_HINT)
        return
    for rel in lua_files:
        done = subprocess.run([luac, "-p", str(root / rel)], capture_output=True, text=True)
        if done.returncode:
            message = (done.stderr or done.stdout).strip().splitlines()
            yield Violation("lua-syntax", rel, 0, message[0] if message else "luac -p failed")


RULES: dict[str, Rule] = {
    "private-data": rule_private_data,
    "language": rule_language,
    "required-files": rule_required_files,
    "identity": rule_identity,
    "lua-syntax": rule_lua_syntax,
}


def check(root: Path, rules: Iterable[str] | None = None) -> list[Violation]:
    """Run the named rules (all by default) over the tracked files of `root`."""
    selected = list(rules) if rules else list(RULES)
    unknown = [name for name in selected if name not in RULES]
    if unknown:
        raise ValueError(f"unknown rule(s): {', '.join(unknown)}; choose from {', '.join(RULES)}")
    files = tracked_files(root)
    violations: list[Violation] = []
    for name in selected:
        violations.extend(RULES[name](root, files))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the repository against the public-release guards.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="repository root")
    parser.add_argument("--rule", action="append", choices=sorted(RULES), help="run only this rule (repeatable)")
    args = parser.parse_args(argv)
    violations = check(args.root, args.rule)
    for violation in violations:
        print(violation)
    if violations:
        print(f"{len(violations)} violation(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
