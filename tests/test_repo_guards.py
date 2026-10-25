"""Repository guards: each violation class fails, each documented placeholder passes."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("check_repo", REPO / "scripts" / "check_repo.py")
guards = importlib.util.module_from_spec(SPEC)
sys.modules["check_repo"] = guards
SPEC.loader.exec_module(guards)


def make_repo(tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    """A temporary git repository whose tracked files are `files`."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


def violations(tmp_path: Path, files: dict[str, str | bytes], *rules: str) -> list:
    return guards.check(make_repo(tmp_path, files), rules or None)


def rules_of(found) -> set[str]:
    return {v.rule for v in found}


def test_the_checked_in_repository_complies():
    assert guards.check(REPO) == []


@pytest.mark.parametrize("line", [
    "export PATH=/Users/realperson/bin",
    "cd /home/realperson/projects",
    r"set C:\Users\realperson\Documents",
])
def test_personal_absolute_paths_fail(tmp_path, line):
    found = violations(tmp_path, {"docs/a.md": f"intro\n{line}\n"}, "private-data")
    assert [(v.path, v.line) for v in found] == [("docs/a.md", 2)]


@pytest.mark.parametrize("line", [
    "use /Users/username/.cargo/bin/uv",
    r"use C:\Users\username\.cargo\bin\uv.exe",
    "see /home/name/project",
    "$HOME/Library/Application Support/Steam/userdata/ACCOUNT_ID/3493540/local",
])
def test_documented_placeholder_paths_pass(tmp_path, line):
    assert violations(tmp_path, {"docs/a.md": line + "\n"}, "private-data") == []


@pytest.mark.parametrize("line", ["id 76561198012345678", "Steam/userdata/123456789/3493540/local"])
def test_steam_account_identifiers_fail(tmp_path, line):
    assert rules_of(violations(tmp_path, {"docs/a.md": line + "\n"}, "private-data")) == {"private-data"}


@pytest.mark.parametrize("name", ["data/tf3.db", "notes/store.sqlite3", "tf3c_snap_000000000010000.lua",
                                  "mod/tf3c_request.lua"])
def test_tracked_player_data_files_fail(tmp_path, name):
    found = violations(tmp_path, {name: "x"}, "private-data")
    assert [v.path for v in found] == [name]


def test_only_the_declared_author_address_is_allowed(tmp_path):
    ok = violations(tmp_path / "ok", {"a.md": "mail alexandrevl@gmail.com\nid sample@1.0.0.tf3c-methodology.json\n"},
                    "private-data")
    bad = violations(tmp_path / "bad", {"a.md": "mail someone.else@example.org\n"}, "private-data")
    assert ok == [] and rules_of(bad) == {"private-data"}


def test_portuguese_text_fails_with_file_and_line(tmp_path):
    found = violations(tmp_path, {"src/a.py": 'x = 1\nmessage = "Linha sem passageiros não atendida"\n'}, "language")
    assert [(v.path, v.line) for v in found] == [("src/a.py", 2)]


def test_accented_english_words_are_not_portuguese(tmp_path):
    assert violations(tmp_path, {"docs/a.md": "Avoid AI clichés and the café metaphor.\n"}, "language") == []


def test_allowlisted_file_may_quote_localized_names(tmp_path):
    assert violations(tmp_path, {"docs/methodologies.md": "for example `Petróleo Bruto`\n"}, "language") == []


def test_the_same_text_outside_the_allowlist_fails(tmp_path):
    found = violations(tmp_path, {"docs/other.md": "for example `Petróleo Bruto`\n"}, "language")
    assert rules_of(found) == {"language"}


def test_missing_required_files_fail_and_present_ones_pass(tmp_path):
    missing = violations(tmp_path / "missing", {"README.md": "x"}, "required-files")
    assert {v.path for v in missing} == set(guards.REQUIRED_PUBLIC_FILES) - {"README.md"}
    everything = {name: "x" for name in guards.REQUIRED_PUBLIC_FILES}
    assert violations(tmp_path / "all", everything, "required-files") == []


def test_links_to_another_repository_name_fail(tmp_path):
    other = f"https://github.com/{guards.OWNER}/something-else/blob/main/docs/a.md"
    own = f"https://github.com/{guards.OWNER}/{guards.REPOSITORY}/blob/main/docs/a.md"
    assert rules_of(violations(tmp_path / "bad", {"a.md": f"[x]({other})\n"}, "identity")) == {"identity"}
    assert violations(tmp_path / "good", {"a.md": f"[x]({own})\n"}, "identity") == []


def test_relative_markdown_links_must_resolve(tmp_path):
    files = {"docs/a.md": "[ok](b.md) [up](../README.md#top) [gone](missing.md)\n", "docs/b.md": "x", "README.md": "x"}
    found = violations(tmp_path, files, "identity")
    assert [(v.path, v.line) for v in found] == [("docs/a.md", 1)]
    assert "missing.md" in found[0].message


def test_untracked_files_are_not_judged(tmp_path):
    repo = make_repo(tmp_path, {"a.md": "clean\n"})
    (repo / "local.md").write_text("/Users/realperson/x\n", encoding="utf-8")
    assert guards.check(repo, ["private-data"]) == []


def test_cli_exits_nonzero_and_prints_the_violation(tmp_path, capsys):
    repo = make_repo(tmp_path, {"a.md": "/Users/realperson/x\n"})
    assert guards.main(["--root", str(repo), "--rule", "private-data"]) == 1
    assert "a.md:1: [private-data]" in capsys.readouterr().out
    clean = make_repo(tmp_path / "clean", {"a.md": "fine\n"})
    assert guards.main(["--root", str(clean), "--rule", "private-data"]) == 0


def test_unknown_rule_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown rule"):
        guards.check(make_repo(tmp_path, {"a.md": "x"}), ["nope"])


def need_luac() -> str:
    luac = guards.find_luac()
    if luac is None:
        pytest.fail(guards.LUAC_INSTALL_HINT)
    return luac


def test_broken_lua_fails_naming_the_file(tmp_path):
    need_luac()
    files = {"mod/ok.lua": "local x = 1\nreturn x\n", "mod/broken.lua": "local = = 3\n"}
    found = violations(tmp_path, files, "lua-syntax")
    assert [v.path for v in found] == ["mod/broken.lua"]
    assert "broken.lua" in found[0].message


def test_valid_lua_passes(tmp_path):
    need_luac()
    assert violations(tmp_path, {"mod/ok.lua": "local function f(a) return a + 1 end\nreturn f\n"}, "lua-syntax") == []


def hide_luac(monkeypatch):
    monkeypatch.delenv("LUAC", raising=False)
    monkeypatch.setattr(guards.shutil, "which", lambda *args, **kwargs: None)


def test_a_missing_luac_fails_instead_of_passing_silently(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {"mod/ok.lua": "return 1\n"})
    hide_luac(monkeypatch)
    found = guards.check(repo, ["lua-syntax"])
    assert [v.rule for v in found] == ["lua-syntax"]
    assert "luac" in found[0].message and "install" in found[0].message.lower()


def test_a_repository_without_lua_files_needs_no_luac(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {"a.md": "x\n"})
    hide_luac(monkeypatch)
    assert guards.check(repo, ["lua-syntax"]) == []
